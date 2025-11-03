"""
Validation utilities for V2 itinerary generation.

This module provides simple post-generation validators to ensure
Gemini-generated itineraries comply with user requirements.
"""

from typing import List, Dict, Any
from datetime import time
from models.schemas2 import ItineraryResponse2, Visit2


def extract_all_place_names(itinerary: ItineraryResponse2) -> List[str]:
    """
    Extract all place display names from the itinerary.

    Args:
        itinerary: The generated itinerary response

    Returns:
        List of all place display names (Visit2.display_name)
    """
    place_names = []
    for day in itinerary.itinerary:
        for visit in day.visits:
            place_names.append(visit.display_name)
    return place_names


def is_unusual_time(time_str: str) -> bool:
    """
    Check if a time string represents an unusual visit time (2:00 AM - 5:00 AM).

    These hours are considered unusual for tourist activities as most places
    are closed during this time.

    Args:
        time_str: Time in "HH:MM" format (e.g., "03:30")

    Returns:
        True if time is between 02:00 and 05:00 (inclusive), False otherwise

    Raises:
        ValueError: If time_str is not in valid "HH:MM" format
    """
    try:
        # Parse time string
        hour, minute = map(int, time_str.split(":"))
        visit_time = time(hour, minute)

        # Check if time is in unusual range (2 AM - 5 AM)
        unusual_start = time(2, 0)
        unusual_end = time(5, 0)

        return unusual_start <= visit_time <= unusual_end
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid time format: {time_str}. Expected 'HH:MM'") from e


def validate_must_visit(
    itinerary: ItineraryResponse2,
    must_visit: List[str]
) -> Dict[str, Any]:
    """
    Validate that all must_visit places are included in the itinerary.

    Args:
        itinerary: The generated itinerary response
        must_visit: List of place names that must be included

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,           # True if all must_visit places are included
            "missing": List[str],        # List of missing place names
            "found": List[str],          # List of found place names
            "total_required": int,       # Total number of must_visit places
            "total_found": int          # Number of must_visit places found
        }
    """
    if not must_visit:
        # No must_visit requirements - always valid
        return {
            "is_valid": True,
            "missing": [],
            "found": [],
            "total_required": 0,
            "total_found": 0
        }

    # Extract all place names from itinerary
    visited_places = extract_all_place_names(itinerary)
    visited_places_lower = [p.lower() for p in visited_places]

    # Check each must_visit place
    missing = []
    found = []

    for place in must_visit:
        place_lower = place.lower()
        # Check for exact match or partial match (case-insensitive)
        if any(place_lower in visited.lower() or visited.lower() in place_lower
               for visited in visited_places):
            found.append(place)
        else:
            missing.append(place)

    return {
        "is_valid": len(missing) == 0,
        "missing": missing,
        "found": found,
        "total_required": len(must_visit),
        "total_found": len(found)
    }


def validate_days_count(
    itinerary: ItineraryResponse2,
    expected_days: int
) -> Dict[str, Any]:
    """
    Validate that the itinerary has the correct number of days.

    Args:
        itinerary: The generated itinerary response
        expected_days: Expected number of days from the request

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,      # True if day count matches
            "actual": int,         # Actual number of days in itinerary
            "expected": int,       # Expected number of days
            "difference": int      # Difference (actual - expected)
        }
    """
    actual_days = len(itinerary.itinerary)

    return {
        "is_valid": actual_days == expected_days,
        "actual": actual_days,
        "expected": expected_days,
        "difference": actual_days - expected_days
    }


def validate_operating_hours_basic(itinerary: ItineraryResponse2) -> Dict[str, Any]:
    """
    Perform basic operating hours validation by checking for unusual visit times.

    This is a simple check that flags visits during 2:00 AM - 5:00 AM as unusual,
    since most tourist attractions are closed during these hours.

    Note: This does NOT validate against actual Google Maps operating hours.
    For full operating hours validation, use Google Maps Grounding during generation.

    Args:
        itinerary: The generated itinerary response

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,                    # True if no unusual times found
            "violations": List[Dict],            # List of unusual visits
            "total_violations": int,             # Number of unusual visits
            "total_visits": int                  # Total number of visits checked
        }
    """
    violations = []
    total_visits = 0

    for day in itinerary.itinerary:
        for visit in day.visits:
            total_visits += 1

            # Check arrival time
            if is_unusual_time(visit.arrival):
                violations.append({
                    "day": day.day,
                    "place": visit.display_name,
                    "arrival": visit.arrival,
                    "departure": visit.departure,
                    "issue": f"Unusual arrival time: {visit.arrival}"
                })
            # Check departure time
            elif is_unusual_time(visit.departure):
                violations.append({
                    "day": day.day,
                    "place": visit.display_name,
                    "arrival": visit.arrival,
                    "departure": visit.departure,
                    "issue": f"Unusual departure time: {visit.departure}"
                })

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
        "total_violations": len(violations),
        "total_visits": total_visits
    }


def validate_travel_time(itinerary: ItineraryResponse2) -> Dict[str, Any]:
    """
    Validate travel_time field correctness in the itinerary.

    Checks:
    1. Last visit of each day must have travel_time = 0 (no next place)
    2. Non-last visits should have travel_time >= 0 (preferably > 0)

    Args:
        itinerary: The generated itinerary response

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,                    # True if all checks pass
            "violations": List[Dict],            # List of travel_time violations
            "total_violations": int,             # Number of violations found
            "total_visits": int                  # Total number of visits checked
        }
    """
    violations = []
    total_visits = 0

    for day in itinerary.itinerary:
        visits = day.visits
        if len(visits) == 0:
            continue

        for i, visit in enumerate(visits):
            total_visits += 1
            is_last_visit = (i == len(visits) - 1)

            if is_last_visit:
                # Last visit must have travel_time = 0
                if visit.travel_time != 0:
                    violations.append({
                        "day": day.day,
                        "place": visit.display_name,
                        "order": visit.order,
                        "travel_time": visit.travel_time,
                        "issue": f"Last visit must have travel_time=0, but got {visit.travel_time}"
                    })
            else:
                # Non-last visits: travel_time = 0 is suspicious (but not strictly invalid)
                if visit.travel_time == 0:
                    violations.append({
                        "day": day.day,
                        "place": visit.display_name,
                        "order": visit.order,
                        "travel_time": visit.travel_time,
                        "issue": f"Non-last visit has travel_time=0 (suspicious, should be > 0)"
                    })

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
        "total_violations": len(violations),
        "total_visits": total_visits
    }


def validate_all(
    itinerary: ItineraryResponse2,
    must_visit: List[str],
    expected_days: int
) -> Dict[str, Any]:
    """
    Run all validators and aggregate results.

    This is a convenience function that runs all validation checks
    and returns a comprehensive validation report.

    Args:
        itinerary: The generated itinerary response
        must_visit: List of place names that must be included
        expected_days: Expected number of days from the request

    Returns:
        Dictionary with all validation results:
        {
            "all_valid": bool,                  # True if all validations pass
            "must_visit": {...},                # Must-visit validation results
            "days": {...},                      # Days count validation results
            "operating_hours": {...},           # Operating hours validation results
            "travel_time": {...}                # Travel time validation results
        }
    """
    must_visit_result = validate_must_visit(itinerary, must_visit)
    days_result = validate_days_count(itinerary, expected_days)
    hours_result = validate_operating_hours_basic(itinerary)
    travel_time_result = validate_travel_time(itinerary)

    all_valid = (
        must_visit_result["is_valid"] and
        days_result["is_valid"] and
        hours_result["is_valid"] and
        travel_time_result["is_valid"]
    )

    return {
        "all_valid": all_valid,
        "must_visit": must_visit_result,
        "days": days_result,
        "operating_hours": hours_result,
        "travel_time": travel_time_result
    }
