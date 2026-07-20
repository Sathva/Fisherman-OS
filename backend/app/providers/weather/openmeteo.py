import math
import asyncio
from datetime import date, datetime
import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.enums import WeatherSource
from app.providers.weather.base import (
    WeatherProvider,
    WeatherReading,
    WeatherUnavailable,
    CoastalReport,
    degrees_to_compass,
)
from app.services.safety import estimate_wave_height_from_wind

# INCOIS divides the coastline into sectors; the TextData page takes a
# secid (SEC001..SEC014) and shows that sector's PFZ table with the sector
# name in <p id="sectorname">. Confirmed mapping so far:
_KNOWN_SECIDS: dict[str, str] = {
    "WEST BENGAL": "SEC011",
}
_SECID_CANDIDATES = [f"SEC{i:03d}" for i in range(1, 15)]
# Filled at runtime by probing the sector pages once (per process).
_secid_cache: dict[str, str] = {}


def extract_sector_name(html: str) -> str | None:
    """Pull the sector/state name out of an INCOIS TextData page."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.find(id="sectorname")
        if node is not None:
            name = node.get_text(strip=True).upper()
            return name or None
    except Exception:
        pass
    return None


def dms_to_decimal(dms_str: str) -> float | None:
    """Convert a string like '21 0 37 N' to decimal degrees."""
    try:
        parts = dms_str.strip().split()
        if len(parts) < 4:
            return None
        
        degrees = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        direction = parts[3].upper()
        
        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if direction in ['S', 'W']:
            decimal *= -1
        return round(decimal, 4)
    except Exception:
        return None


class OpenMeteoProvider(WeatherProvider):
    source = WeatherSource.OPENMETEO
    INCOIS_DATA_URL_TEMPLATE = "https://incois.gov.in/MarineFisheries/TextData?secid={secid}"
    INCOIS_HOME_URL = "https://incois.gov.in/MarineFisheries/TextDataHome?mfid=1&request_locale=en"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def _resolve_secid(
        self, client: httpx.AsyncClient, headers: dict, state_key: str
    ) -> str | None:
        """secid for a state: env override > known map > runtime discovery."""
        override = (get_settings().incois_secid or "").strip()
        if override:
            if override.isdigit():
                override = f"SEC{int(override):03d}"
            return override.upper()
        secid = _KNOWN_SECIDS.get(state_key) or _secid_cache.get(state_key)
        if secid:
            return secid

        async def probe(candidate: str) -> tuple[str, str | None]:
            try:
                resp = await client.get(
                    self.INCOIS_DATA_URL_TEMPLATE.format(secid=candidate),
                    headers=headers,
                )
                resp.raise_for_status()
                return candidate, extract_sector_name(resp.text)
            except Exception:
                return candidate, None

        results = await asyncio.gather(*(probe(c) for c in _SECID_CANDIDATES))
        for candidate, sector_name in results:
            if sector_name and sector_name not in _secid_cache:
                _secid_cache[sector_name] = candidate
        return _secid_cache.get(state_key)

    async def fetch(
        self, latitude: float, longitude: float, day: date,
        village_name: str = "", state: str = "",
    ) -> WeatherReading:
        MAX_NEAREST = 5  # Show up to 5 nearest INCOIS coastal points

        client = self._client or httpx.AsyncClient(timeout=15, verify=False)
        
        # Standard browser headers to avoid getting blocked by INCOIS
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-GPC": "1",
        }
        
        state_key = (state or "GOA").strip().upper()
        state_label = state_key.title()

        try:
            # 1. Fetch JSESSIONID cookie
            await client.get(self.INCOIS_HOME_URL, headers=headers)

            # 2. Resolve the sector id for the village's state, then fetch its page
            secid = await self._resolve_secid(client, headers, state_key)
            pfz_note: str | None = None
            page_text = ""
            if secid is None:
                pfz_note = (
                    f"Fishing zone data isn't available for {state_label} right now, "
                    "so this is the weather near your village only."
                )
            else:
                response = await client.get(
                    self.INCOIS_DATA_URL_TEMPLATE.format(secid=secid), headers=headers
                )
                response.raise_for_status()
                page_text = response.text

            # List of (dist, name, lat, lon, direction, bearing, distance_km, depth) tuples
            all_points: list[tuple[float, str, float, float, str, str, str, str]] = []

            try:
                # 3. Parse coordinates, coast name, and PFZ data using BeautifulSoup
                soup = BeautifulSoup(page_text, "html.parser")
                forecast_div = soup.find('div', id='forecastdata')
                
                if forecast_div:
                    table = forecast_div.find('table')
                    if table:
                        rows = table.find_all("tr")
                        if rows and len(rows) >= 2:
                            header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                            if "Latitude (dms)" in header_cells and "Longitude (dms)" in header_cells:
                                lat_idx = header_cells.index("Latitude (dms)")
                                lon_idx = header_cells.index("Longitude (dms)")
                                # PFZ columns
                                coast_idx = header_cells.index("From the coast of") if "From the coast of" in header_cells else None
                                dir_idx = header_cells.index("Direction") if "Direction" in header_cells else None
                                bear_idx = header_cells.index("Bearing (deg)") if "Bearing (deg)" in header_cells else None
                                dist_idx = header_cells.index("Distance (km)From-To") if "Distance (km)From-To" in header_cells else None
                                depth_idx = header_cells.index("Depth (mtr)From-To") if "Depth (mtr)From-To" in header_cells else None

                                for row in rows[1:]:
                                    cells = row.find_all(["th", "td"])
                                    if len(cells) > max(lat_idx, lon_idx):
                                        lat_dms = cells[lat_idx].get_text(strip=True)
                                        lon_dms = cells[lon_idx].get_text(strip=True)
                                        p_lat = dms_to_decimal(lat_dms)
                                        p_lon = dms_to_decimal(lon_dms)
                                        if p_lat is not None and p_lon is not None:
                                            def _cell(idx, _cells=cells):
                                                return _cells[idx].get_text(strip=True) if idx is not None and len(_cells) > idx else ""
                                            # Approx distance in degrees (good enough for sorting)
                                            dist = math.sqrt((p_lat - latitude) ** 2 + (p_lon - longitude) ** 2)
                                            name = _cell(coast_idx) or f"{p_lat:.3f}°N, {p_lon:.3f}°E"
                                            all_points.append((
                                                dist, name, p_lat, p_lon,
                                                _cell(dir_idx), _cell(bear_idx),
                                                _cell(dist_idx), _cell(depth_idx),
                                            ))
            except Exception:
                pass  # Ignore parsing errors and fall back to village point

            # Sort by distance and pick the N nearest INCOIS points
            all_points.sort(key=lambda x: x[0])
            nearby_points = [pt[1:] for pt in all_points[:MAX_NEAREST]]  # drop the distance

            # Fallback: use the village's own coordinates if INCOIS had no data
            if not nearby_points:
                if pfz_note is None:
                    if "ban" in page_text.lower():
                        pfz_note = (
                            f"INCOIS has suspended fishing zone data for {state_label} "
                            "(seasonal fishing ban), so this is the weather near your "
                            "village only."
                        )
                    else:
                        pfz_note = (
                            f"Fishing zone data isn't available for {state_label} today, "
                            "so this is the weather near your village only."
                        )
                fallback_name = village_name or f"{latitude:.3f}°N, {longitude:.3f}°E"
                nearby_points.append((fallback_name, latitude, longitude, "", "", "", ""))

            # 4. Fetch Open-Meteo for all points in range
            tasks = [self._fetch_point_weather(client, name, p_lat, p_lon, day) for name, p_lat, p_lon, *_ in nearby_points]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            valid_readings = [
                (pt, r) for pt, r in zip(nearby_points, results) if isinstance(r, WeatherReading)
            ]
            if not valid_readings:
                raise WeatherUnavailable(f"Open-Meteo failed for all {len(tasks)} nearby points.")
            
            # 5. Aggregate worst-case scenarios
            all_readings = [r for _, r in valid_readings]
            max_wind_speed = max(r.wind_speed_kmh for r in all_readings)
            max_wave_height = max(r.wave_height_m for r in all_readings)
            max_rain_prob = max(r.rain_probability for r in all_readings)
            base_reading = all_readings[0]

            # 6. Build per-coast breakdown with PFZ data
            coastal_reports = [
                CoastalReport(
                    name=pt[0],
                    latitude=pt[1],
                    longitude=pt[2],
                    wind_speed_kmh=r.wind_speed_kmh,
                    wave_height_m=r.wave_height_m,
                    rain_probability=r.rain_probability,
                    wind_direction=r.wind_direction,
                    pfz_direction=pt[3],
                    pfz_bearing_deg=pt[4],
                    pfz_distance_km=pt[5],
                    pfz_depth_m=pt[6],
                )
                for pt, r in valid_readings
            ]

            return WeatherReading(
                forecast_date=day,
                wind_speed_kmh=max_wind_speed,
                wind_direction=base_reading.wind_direction,
                wave_height_m=max_wave_height,
                rain_probability=max_rain_prob,
                rain_timing=base_reading.rain_timing,
                sea_temp_c=base_reading.sea_temp_c,
                source=self.source,
                hourly=base_reading.hourly,
                coastal_reports=coastal_reports,
                pfz_note=pfz_note,
            )

        except Exception as e:
            if not isinstance(e, WeatherUnavailable):
                raise WeatherUnavailable(f"INCOIS regional open-meteo failed: {str(e)}") from e
            raise
        finally:
            if self._client is None:
                await client.aclose()


    async def _fetch_point_weather(self, client: httpx.AsyncClient, name: str, lat: float, lon: float, day: date) -> WeatherReading:
        url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,wind_speed_10m,wind_direction_10m,precipitation_probability&timezone=Asia/Kolkata"
        url_marine = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height&timezone=Asia/Kolkata"
        
        weather_res = await client.get(url_weather)
        marine_res = await client.get(url_marine)
        
        weather_res.raise_for_status()
        marine_res.raise_for_status()
        
        weather_data = weather_res.json()
        marine_data = marine_res.json()
        
        hourly_w = weather_data.get("hourly", {})
        hourly_m = marine_data.get("hourly", {})
        
        times = hourly_w.get("time", [])
        
        # Filter for the requested day
        day_indices = [
            i for i, t in enumerate(times) 
            if datetime.fromisoformat(t).date() == day
        ]
        
        if not day_indices:
            raise WeatherUnavailable(f"No forecast slots for date {day}")
            
        wind_speeds = [hourly_w["wind_speed_10m"][i] for i in day_indices if hourly_w["wind_speed_10m"][i] is not None]
        wave_heights = [hourly_m["wave_height"][i] for i in day_indices if hourly_m["wave_height"][i] is not None]
        rain_probs = [hourly_w["precipitation_probability"][i] for i in day_indices if hourly_w["precipitation_probability"][i] is not None]
        wind_dirs = [hourly_w["wind_direction_10m"][i] for i in day_indices if hourly_w["wind_direction_10m"][i] is not None]
        temps = [hourly_w["temperature_2m"][i] for i in day_indices if hourly_w["temperature_2m"][i] is not None]

        # Max for the day
        max_wind = max(wind_speeds) if wind_speeds else 0.0
        max_wave = max(wave_heights) if wave_heights else estimate_wave_height_from_wind(max_wind)
        max_rain = max(rain_probs) if rain_probs else 0
        avg_dir = degrees_to_compass(wind_dirs[0]) if wind_dirs else "SW"
        avg_temp = temps[0] if temps else None
        
        # Next 6 hours from the start of the day or from current time
        # For simplicity, just grab the first 6 hours of the day
        hourly_strip = []
        for i in day_indices[:6]:
            w_spd = hourly_w["wind_speed_10m"][i] or 0.0
            wv_h = hourly_m["wave_height"][i] or estimate_wave_height_from_wind(w_spd)
            r_prb = hourly_w["precipitation_probability"][i] or 0
            hourly_strip.append((w_spd, wv_h, r_prb))
            
        return WeatherReading(
            forecast_date=day,
            wind_speed_kmh=round(max_wind, 1),
            wind_direction=avg_dir,
            wave_height_m=round(max_wave, 1),
            rain_probability=max_rain,
            rain_timing=None,
            sea_temp_c=round(avg_temp, 1) if avg_temp else None,
            source=self.source,
            hourly=hourly_strip,
        )
