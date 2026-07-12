"""Deterministic synthetic forecasts for development, tests and demos.

Seeded from (village coordinates, date) so the same village gets the same
"weather" all day — repeated calls and the 3:30 AM push agree with the
on-demand "1" detailed forecast.
"""

import hashlib
import random
from datetime import date

from app.enums import WeatherSource
from app.providers.weather.base import WeatherProvider, WeatherReading


class SyntheticWeatherProvider(WeatherProvider):
    source = WeatherSource.SYNTHETIC

    async def fetch(self, latitude: float, longitude: float, day: date) -> WeatherReading:
        seed = hashlib.sha256(f"{latitude:.3f}:{longitude:.3f}:{day.isoformat()}".encode()).hexdigest()
        rng = random.Random(seed)

        # Goa pre-monsoon/post-monsoon typical ranges, with occasional rough days.
        roughness = rng.random()
        if roughness > 0.9:      # ~10% rough days
            wind = rng.uniform(40, 60)
            wave = rng.uniform(2.5, 4.0)
            rain = rng.randint(60, 95)
        elif roughness > 0.7:    # ~20% caution days
            wind = rng.uniform(28, 40)
            wave = rng.uniform(1.5, 2.4)
            rain = rng.randint(30, 70)
        else:                    # calm days
            wind = rng.uniform(6, 22)
            wave = rng.uniform(0.4, 1.3)
            rain = rng.randint(0, 40)

        hourly = []
        h_wind, h_wave, h_rain = wind, wave, float(rain)
        for _ in range(6):
            h_wind = max(2.0, h_wind + rng.uniform(-3, 5))
            h_wave = max(0.2, h_wave + rng.uniform(-0.15, 0.3))
            h_rain = min(100.0, max(0.0, h_rain + rng.uniform(-8, 12)))
            hourly.append((h_wind, h_wave, int(h_rain)))

        rain_timing = None
        if rain >= 40:
            rain_timing = rng.choice(["after 12PM", "after 2PM", "in the evening", "by late morning"])

        return WeatherReading(
            forecast_date=day,
            wind_speed_kmh=round(wind, 1),
            wind_direction=rng.choice(["SW", "W", "WSW", "NW", "S"]),
            wave_height_m=round(wave, 1),
            rain_probability=rain,
            rain_timing=rain_timing,
            sea_temp_c=round(rng.uniform(27.0, 30.0), 1),
            source=self.source,
            hourly=hourly,
        )
