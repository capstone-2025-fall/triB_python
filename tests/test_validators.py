"""
Unit tests for validation utilities (services/validators.py).

Tests cover all validation functions with normal cases, edge cases, and error conditions.
"""

import pytest
from models.schemas2 import ItineraryResponse2, DayItinerary2, Visit2, PlaceTag
from services.validators import (
    extract_all_place_names,
    is_unusual_time,
    validate_must_visit,
    validate_days_count,
    validate_operating_hours_basic,
    validate_travel_time,
    validate_all
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


# Tests for is_unusual_time()

def test_is_unusual_time_normal_hours():
    """Test normal operating hours (not unusual)."""
    assert is_unusual_time("09:00") is False
    assert is_unusual_time("12:00") is False
    assert is_unusual_time("18:30") is False
    assert is_unusual_time("23:59") is False


def test_is_unusual_time_unusual_hours():
    """Test unusual hours (2 AM - 5 AM)."""
    assert is_unusual_time("02:00") is True
    assert is_unusual_time("03:30") is True
    assert is_unusual_time("04:45") is True
    assert is_unusual_time("05:00") is True


def test_is_unusual_time_boundary_cases():
    """Test boundary cases around unusual hours."""
    assert is_unusual_time("01:59") is False  # Just before 2 AM
    assert is_unusual_time("02:00") is True   # Exactly 2 AM
    assert is_unusual_time("05:00") is True   # Exactly 5 AM
    assert is_unusual_time("05:01") is False  # Just after 5 AM


def test_is_unusual_time_invalid_format():
    """Test invalid time format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid time format"):
        is_unusual_time("25:00")

    with pytest.raises(ValueError, match="Invalid time format"):
        is_unusual_time("invalid")

    with pytest.raises(ValueError, match="Invalid time format"):
        is_unusual_time("12:60")


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


# Tests for validate_operating_hours_basic()

def test_validate_operating_hours_basic_all_normal(sample_itinerary):
    """Test with all normal visiting hours."""
    result = validate_operating_hours_basic(sample_itinerary)

    assert result["is_valid"] is True
    assert len(result["violations"]) == 0
    assert result["total_violations"] == 0
    assert result["total_visits"] == 3


def test_validate_operating_hours_basic_unusual_arrival():
    """Test with unusual arrival time."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Late Night Place",
                        name_address="123 Night St",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="03:00",  # Unusual
                        departure="09:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_basic(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 1
    assert result["violations"][0]["place"] == "Late Night Place"
    assert "03:00" in result["violations"][0]["issue"]


def test_validate_operating_hours_basic_unusual_departure():
    """Test with unusual departure time."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Early Morning Place",
                        name_address="123 Morning St",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="01:00",
                        departure="04:30",  # Unusual
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_basic(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 1
    assert "04:30" in result["violations"][0]["issue"]


def test_validate_operating_hours_basic_multiple_violations():
    """Test with multiple unusual times."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr 1",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="03:00",  # Unusual
                        departure="09:00",
                        travel_time=0
                    ),
                    Visit2(
                        order=2,
                        display_name="Place 2",
                        name_address="Addr 2",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.6,
                        longitude=127.1,
                        arrival="12:00",
                        departure="04:00",  # Unusual
                        travel_time=30
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_operating_hours_basic(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 2
    assert result["total_visits"] == 2


def test_validate_operating_hours_basic_empty_itinerary():
    """Test with empty itinerary."""
    empty_itinerary = ItineraryResponse2(itinerary=[], budget=0)
    result = validate_operating_hours_basic(empty_itinerary)

    assert result["is_valid"] is True
    assert result["total_visits"] == 0


# Tests for validate_travel_time()

def test_validate_travel_time_all_correct():
    """Test with correct travel_time values (last=0, others>0)."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr 1",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=30  # Non-last visit with travel_time > 0
                    ),
                    Visit2(
                        order=2,
                        display_name="Place 2",
                        name_address="Addr 2",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.6,
                        longitude=127.1,
                        arrival="11:30",
                        departure="13:00",
                        travel_time=0  # Last visit with travel_time = 0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is True
    assert len(result["violations"]) == 0
    assert result["total_violations"] == 0
    assert result["total_visits"] == 2


def test_validate_travel_time_last_visit_nonzero():
    """Test when last visit has travel_time != 0 (violation)."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr 1",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=30  # Last visit but travel_time != 0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 1
    assert len(result["violations"]) == 1
    assert result["violations"][0]["place"] == "Place 1"
    assert result["violations"][0]["travel_time"] == 30
    assert "Last visit must have travel_time=0" in result["violations"][0]["issue"]


def test_validate_travel_time_middle_visit_zero():
    """Test when non-last visit has travel_time = 0 (suspicious)."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr 1",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=0  # Non-last visit with travel_time = 0
                    ),
                    Visit2(
                        order=2,
                        display_name="Place 2",
                        name_address="Addr 2",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.6,
                        longitude=127.1,
                        arrival="11:00",
                        departure="13:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 1  # Only first visit is suspicious
    assert result["violations"][0]["place"] == "Place 1"
    assert "Non-last visit has travel_time=0" in result["violations"][0]["issue"]


def test_validate_travel_time_multiple_days():
    """Test validation across multiple days."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Day1 Place1",
                        name_address="Addr",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=20
                    ),
                    Visit2(
                        order=2,
                        display_name="Day1 Place2",
                        name_address="Addr",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.6,
                        longitude=127.1,
                        arrival="11:20",
                        departure="13:00",
                        travel_time=0  # Correct: last visit of day 1
                    )
                ]
            ),
            DayItinerary2(
                day=2,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Day2 Place1",
                        name_address="Addr",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.7,
                        longitude=127.2,
                        arrival="10:00",
                        departure="12:00",
                        travel_time=0  # Correct: only visit of day 2
                    )
                ]
            )
        ],
        budget=200000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is True
    assert result["total_violations"] == 0
    assert result["total_visits"] == 3


def test_validate_travel_time_multiple_violations():
    """Test with multiple travel_time violations."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=0  # Violation: non-last with 0
                    ),
                    Visit2(
                        order=2,
                        display_name="Place 2",
                        name_address="Addr",
                        place_tag=PlaceTag.RESTAURANT,
                        latitude=37.6,
                        longitude=127.1,
                        arrival="11:00",
                        departure="13:00",
                        travel_time=30  # Violation: last with non-zero
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is False
    assert result["total_violations"] == 2
    assert len(result["violations"]) == 2


def test_validate_travel_time_empty_itinerary():
    """Test with empty itinerary."""
    empty_itinerary = ItineraryResponse2(itinerary=[], budget=0)
    result = validate_travel_time(empty_itinerary)

    assert result["is_valid"] is True
    assert result["total_visits"] == 0
    assert len(result["violations"]) == 0


def test_validate_travel_time_single_visit():
    """Test with single visit (should have travel_time=0)."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Only Place",
                        name_address="Addr",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=0  # Correct: single visit = last visit
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_travel_time(itinerary)

    assert result["is_valid"] is True
    assert result["total_visits"] == 1


# Tests for validate_all()

def test_validate_all_everything_passes(sample_itinerary):
    """Test when all validations pass."""
    must_visit = ["Morning Museum", "Park Visit"]
    expected_days = 2

    result = validate_all(sample_itinerary, must_visit, expected_days)

    assert result["all_valid"] is True
    assert result["must_visit"]["is_valid"] is True
    assert result["days"]["is_valid"] is True
    assert result["operating_hours"]["is_valid"] is True
    assert result["travel_time"]["is_valid"] is True


def test_validate_all_must_visit_fails(sample_itinerary):
    """Test when only must_visit validation fails."""
    must_visit = ["Morning Museum", "Missing Place"]
    expected_days = 2

    result = validate_all(sample_itinerary, must_visit, expected_days)

    assert result["all_valid"] is False
    assert result["must_visit"]["is_valid"] is False
    assert result["days"]["is_valid"] is True
    assert result["operating_hours"]["is_valid"] is True
    assert result["travel_time"]["is_valid"] is True


def test_validate_all_days_fails(sample_itinerary):
    """Test when only days validation fails."""
    must_visit = ["Morning Museum"]
    expected_days = 5

    result = validate_all(sample_itinerary, must_visit, expected_days)

    assert result["all_valid"] is False
    assert result["must_visit"]["is_valid"] is True
    assert result["days"]["is_valid"] is False
    assert result["operating_hours"]["is_valid"] is True
    assert result["travel_time"]["is_valid"] is True


def test_validate_all_multiple_failures():
    """Test when multiple validations fail."""
    # Create itinerary with unusual hours and wrong day count
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place A",
                        name_address="Addr A",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="03:00",  # Unusual
                        departure="09:00",
                        travel_time=0
                    )
                ]
            )
        ],
        budget=100000
    )

    must_visit = ["Place A", "Missing Place"]  # One missing
    expected_days = 3  # Wrong count

    result = validate_all(itinerary, must_visit, expected_days)

    assert result["all_valid"] is False
    assert result["must_visit"]["is_valid"] is False
    assert result["days"]["is_valid"] is False
    assert result["operating_hours"]["is_valid"] is False
    assert result["travel_time"]["is_valid"] is True  # Single visit with travel_time=0 is correct


def test_validate_all_empty_requirements(sample_itinerary):
    """Test with minimal requirements."""
    result = validate_all(sample_itinerary, [], 2)

    assert result["all_valid"] is True


def test_validate_all_travel_time_fails():
    """Test when only travel_time validation fails."""
    itinerary = ItineraryResponse2(
        itinerary=[
            DayItinerary2(
                day=1,
                visits=[
                    Visit2(
                        order=1,
                        display_name="Place 1",
                        name_address="Addr 1",
                        place_tag=PlaceTag.TOURIST_SPOT,
                        latitude=37.5,
                        longitude=127.0,
                        arrival="09:00",
                        departure="11:00",
                        travel_time=30  # Last visit but travel_time != 0
                    )
                ]
            )
        ],
        budget=100000
    )

    result = validate_all(itinerary, [], 1)

    assert result["all_valid"] is False
    assert result["must_visit"]["is_valid"] is True
    assert result["days"]["is_valid"] is True
    assert result["operating_hours"]["is_valid"] is True
    assert result["travel_time"]["is_valid"] is False


# =============================================================================
# validate_travel_time_with_grounding() Tests
# =============================================================================

def test_validate_travel_time_with_grounding_valid():
    """
    Test validate_travel_time_with_grounding with valid travel times.

    Note: This test uses real Google Routes API calls.
    It may fail if API key is invalid or API is unavailable.
    """
    from services.validators import validate_travel_time_with_grounding
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

    result = validate_travel_time_with_grounding(itinerary, tolerance_minutes=10)

    # Should be valid (or have minor deviations within tolerance)
    assert "is_valid" in result
    assert "violations" in result
    assert "total_validated" in result
    assert "statistics" in result
    assert result["total_validated"] == 1


def test_validate_travel_time_with_grounding_single_visit():
    """
    Test validate_travel_time_with_grounding with single visit (no routes to validate).
    """
    from services.validators import validate_travel_time_with_grounding
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

    result = validate_travel_time_with_grounding(itinerary, tolerance_minutes=10)

    assert result["is_valid"] is True
    assert result["total_validated"] == 0
    assert len(result["violations"]) == 0


def test_validate_travel_time_with_grounding_multiple_days():
    """
    Test validate_travel_time_with_grounding with multiple days.
    """
    from services.validators import validate_travel_time_with_grounding
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

    result = validate_travel_time_with_grounding(itinerary, tolerance_minutes=10)

    assert result["total_validated"] == 2
    assert "statistics" in result
    assert "avg_deviation" in result["statistics"]
    assert "max_deviation" in result["statistics"]


def test_validate_travel_time_with_grounding_empty_itinerary():
    """
    Test validate_travel_time_with_grounding with empty itinerary.
    """
    from services.validators import validate_travel_time_with_grounding
    from models.schemas2 import ItineraryResponse2

    itinerary = ItineraryResponse2(
        itinerary=[],
        budget=100000
    )

    result = validate_travel_time_with_grounding(itinerary, tolerance_minutes=10)

    assert result["is_valid"] is True
    assert result["total_validated"] == 0
    assert len(result["violations"]) == 0
    assert result["statistics"]["avg_deviation"] == 0
    assert result["statistics"]["max_deviation"] == 0


def test_validate_travel_time_with_grounding_custom_tolerance():
    """
    Test validate_travel_time_with_grounding with custom tolerance.
    """
    from services.validators import validate_travel_time_with_grounding
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
            )
        ],
        budget=100000
    )

    # Test with very strict tolerance (1 minute)
    result_strict = validate_travel_time_with_grounding(itinerary, tolerance_minutes=1)

    # Test with lenient tolerance (30 minutes)
    result_lenient = validate_travel_time_with_grounding(itinerary, tolerance_minutes=30)

    assert result_strict["total_validated"] == 1
    assert result_lenient["total_validated"] == 1
    # Lenient tolerance should have fewer or equal violations
    assert len(result_lenient["violations"]) <= len(result_strict["violations"])


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
