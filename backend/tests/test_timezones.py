from zoneinfo import ZoneInfo

from dailycommit.services.clock import FRIENDLY_ZONES, is_valid_timezone, zone_label


def test_friendly_zones_are_real_iana_zones_eastern_first():
    assert FRIENDLY_ZONES[0] == ("America/New_York", "Eastern (ET)")
    assert [label for _, label in FRIENDLY_ZONES] == [
        "Eastern (ET)",
        "Central (CT)",
        "Mountain (MT)",
        "Arizona",
        "Pacific (PT)",
        "Alaska",
        "Hawaii",
    ]
    for zone, _ in FRIENDLY_ZONES:
        assert is_valid_timezone(zone)
        ZoneInfo(zone)  # stored as-is, so daylight saving follows the zone


def test_labels_for_listed_and_other_zones():
    assert zone_label("America/Los_Angeles") == "Pacific (PT)"
    assert zone_label("Pacific/Honolulu") == "Hawaii"
    # Groups can still hold any IANA zone (e.g. created via the API): shown by city.
    assert zone_label("Europe/London") == "London"
    assert zone_label("America/Argentina/Buenos_Aires") == "Buenos Aires"
    assert zone_label("UTC") == "UTC"
