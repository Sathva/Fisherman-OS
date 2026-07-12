"""Sea-safety classification thresholds."""

from app.enums import SafetyLevel
from app.services.safety import classify_sea_state, describe_waves, estimate_wave_height_from_wind


def test_calm_day_is_safe():
    result = classify_sea_state(wind_speed_kmh=12, wave_height_m=0.8, rain_probability=20)
    assert result.level == SafetyLevel.SAFE
    assert result.reasons == []


def test_moderate_waves_trigger_caution():
    result = classify_sea_state(wind_speed_kmh=15, wave_height_m=1.6, rain_probability=10)
    assert result.level == SafetyLevel.CAUTION
    assert any("waves" in r for r in result.reasons)


def test_strong_wind_triggers_caution():
    result = classify_sea_state(wind_speed_kmh=32, wave_height_m=1.0, rain_probability=10)
    assert result.level == SafetyLevel.CAUTION


def test_high_rain_triggers_caution():
    result = classify_sea_state(wind_speed_kmh=10, wave_height_m=0.5, rain_probability=65)
    assert result.level == SafetyLevel.CAUTION


def test_high_waves_trigger_danger():
    result = classify_sea_state(wind_speed_kmh=20, wave_height_m=2.8, rain_probability=0)
    assert result.level == SafetyLevel.DANGER


def test_gale_wind_triggers_danger():
    result = classify_sea_state(wind_speed_kmh=50, wave_height_m=1.0, rain_probability=0)
    assert result.level == SafetyLevel.DANGER


def test_boundary_values():
    # Exactly at the yellow thresholds -> caution, exactly at red -> danger.
    assert classify_sea_state(30.0, 0.5, 0).level == SafetyLevel.CAUTION
    assert classify_sea_state(45.0, 0.5, 0).level == SafetyLevel.DANGER
    assert classify_sea_state(10.0, 1.5, 0).level == SafetyLevel.CAUTION
    assert classify_sea_state(10.0, 2.5, 0).level == SafetyLevel.DANGER


def test_danger_collects_all_reasons():
    result = classify_sea_state(wind_speed_kmh=55, wave_height_m=3.5, rain_probability=90)
    assert result.level == SafetyLevel.DANGER
    assert len(result.reasons) == 3


def test_describe_waves():
    assert describe_waves(0.5) == "calm"
    assert describe_waves(1.2) == "moderate"
    assert describe_waves(2.0) == "rough"
    assert describe_waves(3.0) == "very rough"


def test_wave_estimate_monotonic():
    winds = [5, 15, 25, 35, 45, 60]
    estimates = [estimate_wave_height_from_wind(w) for w in winds]
    assert estimates == sorted(estimates)
