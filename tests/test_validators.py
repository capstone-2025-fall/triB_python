"""
Unit tests for validation utilities (services/validators.py).

Tests cover all validation functions with normal cases, edge cases, and error conditions.
"""

import pytest
from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag
from services.validators import (
    extract_all_place_names,
    validate_must_visit,
    validate_days_count,
    time_to_minutes,
    minutes_to_time,
    update_travel_times_from_routes,
    adjust_schedule_with_new_travel_times
)


# Test Fixtures

@pytest.fixture
def sample_visit():
    """Create a sample Visit2 object for testing."""
    return Visit2(
        order=1,
        display_name="Test Place",
        name_address="123 Test St, Test City",
        place_tag=PlaceTag.TOURIST_SPOT,
        latitude=37.5665,
        longitude=126.9780,
        arrival="09:00",
        departure="11:00",
        travel_time=30
    )


@pytest.fixture
def sample_itinerary():
    """Create a sample itinerary with 2 days and multiple visits."""
    day1 = DayItinerary2(
        day=1,
        visits=[
            Visit2(
                order=1,
                display_name="Morning Museum",
                name_address="123 Museum St",
                place_tag=PlaceTag.TOURIST_SPOT,
                latitude=37.5,
                longitude=127.0,
                arrival="09:00",
                departure="11:00",
                travel_time=60  # Non-last visit: travel_time > 0
            ),
            Visit2(
                order=2,
                display_name="Lunch Restaurant",
                name_address="456 Food St",
                place_tag=PlaceTag.RESTAURANT,
                latitude=37.6,
                longitude=127.1,
                arrival="12:00",
                departure="13:30",
                travel_time=0  # Last visit: travel_time = 0
            )
        ]
    )

    day2 = DayItinerary2(
        day=2,
        visits=[
            Visit2(
                order=1,
                display_name="Park Visit",
                name_address="789 Park Ave",
                place_tag=PlaceTag.TOURIST_SPOT,
                latitude=37.7,
                longitude=127.2,
                arrival="10:00",
                departure="12:00",
                travel_time=0  # Only visit: travel_time = 0
            )
        ]
    )

    return ItineraryResponse2(
        itinerary=[day1, day2],
        budget=500000
    )


# Tests for extract_all_place_names()

def test_extract_all_place_names_normal(sample_itinerary):
    """Test extracting place names from a normal itinerary."""
    result = extract_all_place_names(sample_itinerary)

    assert len(result) == 3
    assert "Morning Museum" in result
    assert "Lunch Restaurant" in result
    assert "Park Visit" in result


def test_extract_all_place_names_empty():
    """Test extracting from an empty itinerary."""
    empty_itinerary = ItineraryResponse2(itinerary=[], budget=0)
    result = extract_all_place_names(empty_itinerary)

    assert result == []


def test_extract_all_place_names_preserves_order(sample_itinerary):
    """Test that place names are extracted in order."""
    result = extract_all_place_names(sample_itinerary)

    assert result[0] == "Morning Museum"
    assert result[1] == "Lunch Restaurant"
    assert result[2] == "Park Visit"


# Tests for validate_must_visit()

def test_validate_must_visit_all_found(sample_itinerary):
    """Test when all must_visit places are found."""
    must_visit = ["Morning Museum", "Park Visit"]
    result = validate_must_visit(sample_itinerary, must_visit)

    assert result["is_valid"] is True
    assert len(result["missing"]) == 0
    assert len(result["found"]) == 2
    assert result["total_required"] == 2
    assert result["total_found"] == 2


def test_validate_must_visit_partial_match(sample_itinerary):
    """Test case-insensitive and partial matching."""
    must_visit = ["morning museum", "PARK"]  # Case variations and partial
    result = validate_must_visit(sample_itinerary, must_visit)

    assert result["is_valid"] is True
    assert "morning museum" in result["found"]
    assert "PARK" in result["found"]


def test_validate_must_visit_some_missing(sample_itinerary):
    """Test when some must_visit places are missing."""
    must_visit = ["Morning Museum", "Missing Place", "Park Visit"]
    result = validate_must_visit(sample_itinerary, must_visit)

    assert result["is_valid"] is False
    assert "Missing Place" in result["missing"]
    assert len(result["found"]) == 2
    assert result["total_required"] == 3
    assert result["total_found"] == 2


def test_validate_must_visit_all_missing(sample_itinerary):
    """Test when all must_visit places are missing."""
    must_visit = ["Place A", "Place B", "Place C"]
    result = validate_must_visit(sample_itinerary, must_visit)

    assert result["is_valid"] is False
    assert len(result["missing"]) == 3
    assert len(result["found"]) == 0


def test_validate_must_visit_empty_list(sample_itinerary):
    """Test with empty must_visit list (always valid)."""
    result = validate_must_visit(sample_itinerary, [])

    assert result["is_valid"] is True
    assert result["missing"] == []
    assert result["total_required"] == 0


def test_validate_must_visit_none_list(sample_itinerary):
    """Test with None must_visit list."""
    result = validate_must_visit(sample_itinerary, None)

    assert result["is_valid"] is True


# Tests for validate_days_count()

def test_validate_days_count_exact_match(sample_itinerary):
    """Test when day count matches exactly."""
    result = validate_days_count(sample_itinerary, 2)

    assert result["is_valid"] is True
    assert result["actual"] == 2
    assert result["expected"] == 2
    assert result["difference"] == 0


def test_validate_days_count_too_few(sample_itinerary):
    """Test when itinerary has fewer days than expected."""
    result = validate_days_count(sample_itinerary, 5)

    assert result["is_valid"] is False
    assert result["actual"] == 2
    assert result["expected"] == 5
    assert result["difference"] == -3


def test_validate_days_count_too_many(sample_itinerary):
    """Test when itinerary has more days than expected."""
    result = validate_days_count(sample_itinerary, 1)

    assert result["is_valid"] is False
    assert result["actual"] == 2
    assert result["expected"] == 1
    assert result["difference"] == 1


def test_validate_days_count_empty_itinerary():
    """Test with empty itinerary."""
    empty_itinerary = ItineraryResponse2(itinerary=[], budget=0)
    result = validate_days_count(empty_itinerary, 0)

    assert result["is_valid"] is True
    assert result["actual"] == 0


# =============================================================================
# validate_travel_time_with_grounding() Tests
# =============================================================================

def test_fetch_actual_travel_times_valid():
    """
    Test fetch_actual_travel_times with valid route.

    Note: This test uses real Google Routes API calls.
    It may fail if API key is invalid or API is unavailable.
    """
    from services.validators import fetch_actual_travel_times
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    # Create itinerary with realistic Seoul locations
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=15  # Approximately 15 min to Bukchon
                    ),
                    Visit2(
                        order=2,
                        display_name="Bukchon Hanok Village",
                        name_address="Bukchon Hanok Village, 37 Gyedong-gil, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5825,
                        longitude=126.9830,
                        arrival="11:15",
                        departure="13:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = fetch_actual_travel_times(itinerary)

    # Should return dict with (day, order) -> time mapping
    assert isinstance(result, dict)
    # Should have 1 route (day 1, order 1 -> order 2)
    assert (1, 1) in result
    # Travel time should be positive
    assert result[(1, 1)] > 0


def test_fetch_actual_travel_times_single_visit():
    """
    Test fetch_actual_travel_times with single visit (no routes to fetch).
    """
    from services.validators import fetch_actual_travel_times
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = fetch_actual_travel_times(itinerary)

    # Should return empty dict (no routes to fetch)
    assert isinstance(result, dict)
    assert len(result) == 0


def test_fetch_actual_travel_times_multiple_days():
    """
    Test fetch_actual_travel_times with multiple days.
    """
    from services.validators import fetch_actual_travel_times
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=2,
                        display_name="Bukchon Hanok Village",
                        name_address="Bukchon Hanok Village, 37 Gyedong-gil, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5825,
                        longitude=126.9830,
                        arrival="11:15",
                        departure="13:00",
                        travel_time=0
                    )
                ]
            ),
            DayItinerary2(
                day=2,
                visits=[
                    Visit2(
                        order=1,
                        display_name="N Seoul Tower",
                        name_address="N Seoul Tower, 105 Namsangongwon-gil, Yongsan-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5512,
                        longitude=126.9882,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=20
                    ),
                    Visit2(
                        order=2,
                        display_name="Myeongdong",
                        name_address="Myeongdong, Jung-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5636,
                        longitude=126.9826,
                        arrival="11:20",
                        departure="13:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = fetch_actual_travel_times(itinerary)

    # Should have 2 routes (one per day)
    assert isinstance(result, dict)
    assert len(result) == 2
    assert (1, 1) in result  # Day 1, order 1 -> 2
    assert (2, 1) in result  # Day 2, order 1 -> 2
    assert result[(1, 1)] > 0
    assert result[(2, 1)] > 0


def test_fetch_actual_travel_times_empty_itinerary():
    """
    Test fetch_actual_travel_times with empty itinerary.
    """
    from services.validators import fetch_actual_travel_times
    from models.schemas2 import ItineraryResponse2

    itinerary = ItineraryResponse2(
        itinerary=[],
        budget=100000
    )

    result = fetch_actual_travel_times(itinerary)

    # Should return empty dict
    assert isinstance(result, dict)
    assert len(result) == 0


# Custom tolerance test removed - no longer applicable
# fetch_actual_travel_times does not perform validation with tolerance


# =============================================================================
# validate_operating_hours_with_grounding() Tests
# =============================================================================

def test_validate_operating_hours_with_grounding_valid():
    """
    Test validate_operating_hours_with_grounding with valid operating hours.

    Note: This test uses real Google Places API calls.
    """
    from services.validators import validate_operating_hours_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    # Create itinerary with realistic Seoul locations during reasonable hours
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_with_grounding(itinerary)

    assert "is_valid" in result
    assert "violations" in result
    assert "total_validated" in result
    assert "statistics" in result
    assert result["total_validated"] == 1


def test_validate_operating_hours_with_grounding_empty():
    """
    Test validate_operating_hours_with_grounding with empty itinerary.
    """
    from services.validators import validate_operating_hours_with_grounding
    from models.schemas2 import ItineraryResponse2

    itinerary = ItineraryResponse2(
        itinerary=[],
        budget=100000
    )

    result = validate_operating_hours_with_grounding(itinerary)

    assert result["is_valid"] is True
    assert result["total_validated"] == 0
    assert len(result["violations"]) == 0
    assert result["statistics"]["closed_visits"] == 0
    assert result["statistics"]["outside_hours_visits"] == 0


def test_validate_operating_hours_with_grounding_multiple_visits():
    """
    Test validate_operating_hours_with_grounding with multiple visits.
    """
    from services.validators import validate_operating_hours_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=2,
                        display_name="Bukchon Hanok Village",
                        name_address="Bukchon Hanok Village, 37 Gyedong-gil, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5825,
                        longitude=126.9830,
                        arrival="12:15",
                        departure="14:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_with_grounding(itinerary)

    assert result["total_validated"] == 2
    assert "statistics" in result


def test_validate_operating_hours_with_grounding_statistics():
    """
    Test that statistics are properly calculated.
    """
    from services.validators import validate_operating_hours_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_with_grounding(itinerary)

    assert "closed_visits" in result["statistics"]
    assert "outside_hours_visits" in result["statistics"]
    assert "no_hours_data" in result["statistics"]
    assert isinstance(result["statistics"]["closed_visits"], int)
    assert isinstance(result["statistics"]["outside_hours_visits"], int)
    assert isinstance(result["statistics"]["no_hours_data"], int)


def test_validate_operating_hours_with_grounding_multiple_days():
    """
    Test validate_operating_hours_with_grounding with multiple days.
    """
    from services.validators import validate_operating_hours_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            ),
            DayItinerary2(
                day=2,
                visits=[
                    Visit2(
                        order=1,
                        display_name="N Seoul Tower",
                        name_address="N Seoul Tower, 105 Namsangongwon-gil, Yongsan-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5512,
                        longitude=126.9882,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_with_grounding(itinerary)

    assert result["total_validated"] == 2


# =============================================================================
# validate_rules_with_gemini() Tests
# =============================================================================

def test_validate_rules_with_gemini_no_rules():
    """
    Test validate_rules_with_gemini with no rules.
    """
    from services.validators import validate_rules_with_gemini
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_rules_with_gemini(itinerary, [])

    assert result["is_valid"] is True
    assert result["total_rules"] == 0
    assert len(result["violations"]) == 0
    assert len(result["rule_results"]) == 0


def test_validate_rules_with_gemini_structure():
    """
    Test that validate_rules_with_gemini returns proper structure.

    Note: This test uses real Gemini API calls.
    """
    from services.validators import validate_rules_with_gemini
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    rules = ["첫날은 경복궁을 방문해야 함"]

    result = validate_rules_with_gemini(itinerary, rules)

    assert "is_valid" in result
    assert "violations" in result
    assert "total_violations" in result
    assert "total_rules" in result
    assert "rule_results" in result
    assert result["total_rules"] == 1
    assert len(result["rule_results"]) == 1


def test_validate_rules_with_gemini_multiple_rules():
    """
    Test validate_rules_with_gemini with multiple rules.
    """
    from services.validators import validate_rules_with_gemini
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=2,
                        display_name="Bukchon Hanok Village",
                        name_address="Bukchon Hanok Village, 37 Gyedong-gil, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5825,
                        longitude=126.9830,
                        arrival="12:15",
                        departure="14:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    rules = [
        "첫날은 경복궁을 방문해야 함",
        "북촌한옥마을을 포함해야 함"
    ]

    result = validate_rules_with_gemini(itinerary, rules)

    assert result["total_rules"] == 2
    assert len(result["rule_results"]) == 2


# =============================================================================
# validate_all_with_grounding() Tests
# =============================================================================

def test_validate_all_with_grounding_empty():
    """
    Test validate_all_with_grounding with empty requirements.
    """
    from services.validators import validate_all_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_all_with_grounding(itinerary, [], 1, [])

    assert "all_valid" in result
    assert "must_visit" in result
    assert "days" in result
    assert "rules" in result
    assert "operating_hours" in result
    # "travel_time" removed - no longer validated


def test_validate_all_with_grounding_structure():
    """
    Test that validate_all_with_grounding returns proper structure.
    """
    from services.validators import validate_all_with_grounding
    from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag

    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Gyeongbokgung Palace",
                        name_address="Gyeongbokgung Palace, 161 Sajik-ro, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5796,
                        longitude=126.9770,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=2,
                        display_name="Bukchon Hanok Village",
                        name_address="Bukchon Hanok Village, 37 Gyedong-gil, Jongno-gu, Seoul",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5825,
                        longitude=126.9830,
                        arrival="12:15",
                        departure="14:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    must_visit = ["Gyeongbokgung Palace"]
    rules = ["첫날은 경복궁을 방문"]

    result = validate_all_with_grounding(itinerary, must_visit, 1, rules)

    assert isinstance(result["all_valid"], bool)
    assert result["must_visit"]["is_valid"] is True
    assert result["days"]["is_valid"] is True


# ==================== Time Utility Functions Tests ====================


def test_time_to_minutes_normal():
    """Test time_to_minutes with normal time strings."""
    assert time_to_minutes("00:00") == 0
    assert time_to_minutes("01:00") == 60
    assert time_to_minutes("09:30") == 570
    assert time_to_minutes("12:00") == 720
    assert time_to_minutes("23:59") == 1439


def test_time_to_minutes_edge_cases():
    """Test time_to_minutes with edge cases."""
    assert time_to_minutes("00:01") == 1
    assert time_to_minutes("00:59") == 59
    assert time_to_minutes("23:00") == 1380


def test_minutes_to_time_normal():
    """Test minutes_to_time with normal minute values."""
    assert minutes_to_time(0) == "00:00"
    assert minutes_to_time(60) == "01:00"
    assert minutes_to_time(570) == "09:30"
    assert minutes_to_time(720) == "12:00"
    assert minutes_to_time(1439) == "23:59"


def test_minutes_to_time_overflow():
    """Test minutes_to_time with values >= 24 hours (should wrap)."""
    assert minutes_to_time(1440) == "00:00"  # 24:00 -> 00:00
    assert minutes_to_time(1500) == "01:00"  # 25:00 -> 01:00
    assert minutes_to_time(2880) == "00:00"  # 48:00 -> 00:00


def test_minutes_to_time_edge_cases():
    """Test minutes_to_time with edge cases."""
    assert minutes_to_time(1) == "00:01"
    assert minutes_to_time(59) == "00:59"
    assert minutes_to_time(1380) == "23:00"


# ==================== Update Travel Times Tests ====================


def test_update_travel_times_from_routes_normal():
    """Test update_travel_times_from_routes with normal routes_data."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=10  # Original value
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",
                        departure="11:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=50000
    )

    routes_data = {(1, 1): 25}  # Update travel_time from 10 to 25

    updated = update_travel_times_from_routes(itinerary, routes_data)

    # Check travel_time was updated
    assert updated.itinerary[0].visits[0].travel_time == 25
    # Check other fields unchanged
    assert updated.itinerary[0].visits[0].arrival == "09:00"
    assert updated.itinerary[0].visits[0].departure == "10:00"
    # Check original not modified
    assert itinerary.itinerary[0].visits[0].travel_time == 10


def test_update_travel_times_from_routes_partial():
    """Test update_travel_times_from_routes with partial routes_data."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=10
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",
                        departure="11:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=3,
                        display_name="Place C",
                        name_address="Place C Address",
                        place_tag=PlaceTag.CAFE,
                        latitude=37.5720,
                        longitude=126.9850,
                        arrival="11:15",
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=50000
    )

    # Only update first visit's travel_time
    routes_data = {(1, 1): 25}

    updated = update_travel_times_from_routes(itinerary, routes_data)

    # Check first was updated
    assert updated.itinerary[0].visits[0].travel_time == 25
    # Check second was NOT updated (kept original)
    assert updated.itinerary[0].visits[1].travel_time == 15
    # Check last is still 0
    assert updated.itinerary[0].visits[2].travel_time == 0


def test_update_travel_times_from_routes_empty():
    """Test update_travel_times_from_routes with empty routes_data."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=10
                    )
                ]
            )
        ],
        budget=50000
    )

    routes_data = {}  # Empty

    updated = update_travel_times_from_routes(itinerary, routes_data)

    # Check nothing changed
    assert updated.itinerary[0].visits[0].travel_time == 10


# ==================== Adjust Schedule Tests ====================


def test_adjust_schedule_with_new_travel_times_normal():
    """Test adjust_schedule with sufficient stay duration."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=25  # Updated from 10 to 25
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",
                        departure="11:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=50000
    )

    adjusted = adjust_schedule_with_new_travel_times(itinerary, min_stay_minutes=30)

    # First visit: arrival should stay the same
    assert adjusted.itinerary[0].visits[0].arrival == "09:00"
    # First visit: departure should be adjusted to match travel_time
    # Expected arrival at next = 10:10
    # Required departure = 10:10 - 25 = 09:45
    # Stay duration = 09:45 - 09:00 = 45 minutes >= 30 ✓
    assert adjusted.itinerary[0].visits[0].departure == "09:45"
    # Second visit: arrival should stay the same
    assert adjusted.itinerary[0].visits[1].arrival == "10:10"


def test_adjust_schedule_with_new_travel_times_insufficient_stay():
    """Test adjust_schedule when stay duration is too short (must push arrival forward)."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=50  # Very long travel time
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",  # Too soon!
                        departure="11:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=50000
    )

    adjusted = adjust_schedule_with_new_travel_times(itinerary, min_stay_minutes=30)

    # First visit: arrival unchanged
    assert adjusted.itinerary[0].visits[0].arrival == "09:00"
    # First visit: departure = arrival + min_stay = 09:00 + 30 = 09:30
    assert adjusted.itinerary[0].visits[0].departure == "09:30"
    # Second visit: arrival must be pushed forward
    # New arrival = 09:30 + 50 = 10:20
    assert adjusted.itinerary[0].visits[1].arrival == "10:20"


def test_adjust_schedule_with_new_travel_times_cascade():
    """Test adjust_schedule with cascading adjustments."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=60  # Long travel
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",  # Too soon
                        departure="11:00",
                        travel_time=20
                    ),
                    Visit2(
                        order=3,
                        display_name="Place C",
                        name_address="Place C Address",
                        place_tag=PlaceTag.CAFE,
                        latitude=37.5720,
                        longitude=126.9850,
                        arrival="11:20",  # Will be cascaded
                        departure="12:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=50000
    )

    adjusted = adjust_schedule_with_new_travel_times(itinerary, min_stay_minutes=30)

    # First visit: departure = 09:00 + 30 = 09:30
    assert adjusted.itinerary[0].visits[0].arrival == "09:00"
    assert adjusted.itinerary[0].visits[0].departure == "09:30"

    # Second visit: arrival = 09:30 + 60 = 10:30
    assert adjusted.itinerary[0].visits[1].arrival == "10:30"
    # Second visit: departure = 10:30 + 30 = 11:00
    assert adjusted.itinerary[0].visits[1].departure == "11:00"

    # Third visit: arrival = 11:00 + 20 = 11:20 (cascaded)
    assert adjusted.itinerary[0].visits[2].arrival == "11:20"


def test_adjust_schedule_with_new_travel_times_multiple_days():
    """Test adjust_schedule with multiple days."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Place A Address",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5665,
                        longitude=126.9780,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=25
                    ),
                    Visit2(
                        order=2,
                        display_name="Place B",
                        name_address="Place B Address",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.5700,
                        longitude=126.9800,
                        arrival="10:10",
                        departure="11:00",
                        travel_time=0
                    )
                ]
            ),
            DayItinerary2(
                day=2,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place C",
                        name_address="Place C Address",
                        place_tag=PlaceTag.CAFE,
                        latitude=37.5720,
                        longitude=126.9850,
                        arrival="09:00",
                        departure="10:00",
                        travel_time=15
                    ),
                    Visit2(
                        order=2,
                        display_name="Place D",
                        name_address="Place D Address",
                        place_tag=PlaceTag.OTHER,
                        latitude=37.5740,
                        longitude=126.9900,
                        arrival="10:10",
                        departure="11:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    adjusted = adjust_schedule_with_new_travel_times(itinerary, min_stay_minutes=30)

    # Day 1: first visit departure adjusted
    assert adjusted.itinerary[0].visits[0].arrival == "09:00"
    assert adjusted.itinerary[0].visits[0].departure == "09:45"  # 10:10 - 25

    # Day 2: first visit departure adjusted
    assert adjusted.itinerary[1].visits[0].arrival == "09:00"
    assert adjusted.itinerary[1].visits[0].departure == "09:55"  # 10:10 - 15
