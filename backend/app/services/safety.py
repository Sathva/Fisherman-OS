"""Sea-safety classification.

Thresholds follow INCOIS Ocean State Forecast / IMD small-craft advisory
practice for small motorized craft (the 9 m outboard canoes typical of Goa):

  * IMD issues fishermen warnings when winds exceed ~45 km/h (25 kt) or
    seas become rough (significant wave height >= ~3 m).
  * INCOIS "high wave alerts" for the Goa coast typically start at 2.5-3 m.

We classify one notch conservatively — a wrong "go" costs lives, a wrong
"don't go" costs one day's catch.
"""

from dataclasses import dataclass

from app.enums import SafetyLevel

# RED — do not go
WAVE_RED_M = 2.5
WIND_RED_KMH = 45.0
RAIN_RED_PCT = 85

# YELLOW — caution
WAVE_YELLOW_M = 1.5
WIND_YELLOW_KMH = 30.0
RAIN_YELLOW_PCT = 60


@dataclass(frozen=True)
class SafetyAssessment:
    level: SafetyLevel
    reasons: list[str]


def classify_sea_state(
    wind_speed_kmh: float,
    wave_height_m: float,
    rain_probability: int,
) -> SafetyAssessment:
    """Classify a forecast into 🟢 SAFE / 🟡 CAUTION / 🔴 DANGER."""
    reasons: list[str] = []

    if wave_height_m >= WAVE_RED_M:
        reasons.append(f"waves {wave_height_m:.1f}m")
    if wind_speed_kmh >= WIND_RED_KMH:
        reasons.append(f"wind {wind_speed_kmh:.0f} km/h")
    if rain_probability >= RAIN_RED_PCT:
        reasons.append(f"rain {rain_probability}%")
    if reasons:
        return SafetyAssessment(SafetyLevel.DANGER, reasons)

    if wave_height_m >= WAVE_YELLOW_M:
        reasons.append(f"waves {wave_height_m:.1f}m")
    if wind_speed_kmh >= WIND_YELLOW_KMH:
        reasons.append(f"wind {wind_speed_kmh:.0f} km/h")
    if rain_probability >= RAIN_YELLOW_PCT:
        reasons.append(f"rain {rain_probability}%")
    if reasons:
        return SafetyAssessment(SafetyLevel.CAUTION, reasons)

    return SafetyAssessment(SafetyLevel.SAFE, [])


def describe_waves(wave_height_m: float) -> str:
    if wave_height_m < 1.0:
        return "calm"
    if wave_height_m < 1.5:
        return "moderate"
    if wave_height_m < 2.5:
        return "rough"
    return "very rough"


def estimate_wave_height_from_wind(wind_speed_kmh: float) -> float:
    """Rough open-coast estimate used only when the source (e.g. OpenWeatherMap)
    has no marine data. Piecewise fit loosely based on the Beaufort sea-state
    scale for fully developed nearshore seas."""
    if wind_speed_kmh < 12:
        return 0.4
    if wind_speed_kmh < 20:
        return 0.8
    if wind_speed_kmh < 29:
        return 1.2
    if wind_speed_kmh < 39:
        return 1.8
    if wind_speed_kmh < 50:
        return 2.8
    return 4.0
