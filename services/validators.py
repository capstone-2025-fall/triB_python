"""
Validation utilities for V2 itinerary generation.

This module provides simple post-generation validators to ensure
Gemini-generated itineraries comply with user requirements.
"""

from typing import List, Dict, Any, Tuple
from datetime import time
from models.schemas2 import ItineraryResponse2, Visit2
import httpx
from config import settings
import json
from google import genai
from google.genai import types


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


def fetch_actual_travel_times(
    itinerary: ItineraryResponse2
) -> Dict[Tuple[int, int], int]:
    """
    Fetch actual travel times from Google Routes API v2.

    This function collects real travel time data from Google Routes API
    for all routes in the itinerary. It does NOT perform validation.

    Args:
        itinerary: The generated itinerary response

    Returns:
        Dictionary mapping (day, from_order) to actual travel time in minutes:
        {
            (1, 1): 15,    # Day 1, from order 1 to order 2: 15 minutes
            (1, 2): 20,    # Day 1, from order 2 to order 3: 20 minutes
            (2, 1): 10,    # Day 2, from order 1 to order 2: 10 minutes
            ...
        }

        If a route fails to fetch (API error, no route found, etc.),
        that route is simply omitted from the result. Returns empty dict
        if no routes could be fetched.

    Note:
        - Uses DRIVE mode with TRAFFIC_AWARE routing preference
        - Skips last visit of each day (no next destination)
        - Requires valid google_maps_api_key in settings
        - Errors are logged but do not prevent other routes from being fetched
    """
    travel_times = {}

    # Routes API v2 endpoint
    routes_api_url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    for day in itinerary.itinerary:
        visits = day.visits

        # Skip if no visits or only one visit
        if len(visits) <= 1:
            continue

        # Fetch travel times for all visits except the last one
        for i in range(len(visits) - 1):
            current_visit = visits[i]
            next_visit = visits[i + 1]

            try:
                # Prepare request body for Google Routes API v2
                request_body = {
                    "origin": {
                        "location": {
                            "latLng": {
                                "latitude": current_visit.latitude,
                                "longitude": current_visit.longitude
                            }
                        }
                    },
                    "destination": {
                        "location": {
                            "latLng": {
                                "latitude": next_visit.latitude,
                                "longitude": next_visit.longitude
                            }
                        }
                    },
                    "travelMode": "DRIVE",
                    "routingPreference": "TRAFFIC_AWARE",
                    "computeAlternativeRoutes": False,
                    "languageCode": "ko-KR",
                    "units": "METRIC"
                }

                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": "routes.duration,routes.distanceMeters"
                }

                # Make API request
                with httpx.Client() as client:
                    response = client.post(
                        routes_api_url,
                        json=request_body,
                        headers=headers,
                        timeout=10.0
                    )

                if response.status_code == 200:
                    data = response.json()

                    if "routes" in data and len(data["routes"]) > 0:
                        # Parse duration (format: "123s")
                        duration_str = data["routes"][0]["duration"]
                        actual_time_seconds = int(duration_str.rstrip("s"))
                        actual_time_minutes = round(actual_time_seconds / 60)

                        # Store the actual travel time
                        key = (day.day, current_visit.order)
                        travel_times[key] = actual_time_minutes

            except Exception as e:
                # Log error but continue with other routes
                # This allows partial success - some routes may succeed even if others fail
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to fetch travel time for Day {day.day}, "
                    f"order {current_visit.order} → {current_visit.order + 1}: {str(e)}"
                )
                continue

    return travel_times


def validate_operating_hours_with_grounding(
    itinerary: ItineraryResponse2
) -> Dict[str, Any]:
    """
    Validate operating hours using Google Maps Places API.

    This function verifies that all visits occur during the actual operating hours
    of each place, as reported by Google Maps. It checks day-of-week specific hours
    and identifies visits to closed venues.

    Args:
        itinerary: The generated itinerary response

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,                       # True if all visits are within operating hours
            "violations": List[Dict],               # List of operating hours violations
            "total_violations": int,                # Number of violations found
            "total_validated": int,                 # Total number of visits validated
            "statistics": {
                "closed_visits": int,               # Number of visits to closed places
                "outside_hours_visits": int,        # Number of visits outside operating hours
                "no_hours_data": int                # Number of places without hours data
            }
        }

    Note:
        - Uses Google Maps Places API (New) to fetch operating hours
        - Requires valid google_maps_api_key in settings
        - Some places may not have operating hours data (e.g., outdoor attractions)
    """
    violations = []
    total_validated = 0
    closed_visits = 0
    outside_hours_visits = 0
    no_hours_data = 0

    # Places API (New) endpoint
    places_api_url = "https://places.googleapis.com/v1/places:searchText"

    for day in itinerary.itinerary:
        for visit in day.visits:
            total_validated += 1

            try:
                # Search for place by name and coordinates
                request_body = {
                    "textQuery": visit.display_name,
                    "locationBias": {
                        "circle": {
                            "center": {
                                "latitude": visit.latitude,
                                "longitude": visit.longitude
                            },
                            "radius": 500.0  # 500m radius
                        }
                    }
                }

                headers = {
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": settings.google_maps_api_key,
                    "X-Goog-FieldMask": "places.displayName,places.currentOpeningHours,places.regularOpeningHours"
                }

                with httpx.Client() as client:
                    response = client.post(
                        places_api_url,
                        json=request_body,
                        headers=headers,
                        timeout=10.0
                    )

                if response.status_code == 200:
                    data = response.json()

                    if "places" in data and len(data["places"]) > 0:
                        place_data = data["places"][0]

                        # Check if place has opening hours data
                        if "regularOpeningHours" not in place_data:
                            no_hours_data += 1
                            # Don't flag as violation - some places don't have hours (e.g., parks)
                            continue

                        opening_hours = place_data["regularOpeningHours"]

                        # Check if the place is open during visit time
                        # Note: This is a simplified check. Full implementation would need
                        # to parse the visit date (start_date + day offset) and check day-of-week

                        # For now, check if there are any periods listed
                        if "periods" not in opening_hours or len(opening_hours["periods"]) == 0:
                            no_hours_data += 1
                            continue

                        # TODO: Implement full day-of-week and time range checking
                        # This requires:
                        # 1. Calculate actual date from itinerary start_date and day number
                        # 2. Get day of week
                        # 3. Find matching period for that day
                        # 4. Check if arrival and departure are within open/close times

                        # For now, just check if place appears to be permanently closed
                        if "periods" in opening_hours and len(opening_hours["periods"]) == 0:
                            closed_visits += 1
                            violations.append({
                                "day": day.day,
                                "place": visit.display_name,
                                "order": visit.order,
                                "arrival": visit.arrival,
                                "departure": visit.departure,
                                "issue": "Place appears to be closed (no operating hours listed)",
                                "opening_hours": "Not available"
                            })

                    else:
                        # No place found
                        no_hours_data += 1
                        # Don't flag as violation - place might be outdoor or not in Google Maps

                else:
                    # API call failed - don't flag as violation, just log
                    no_hours_data += 1

            except Exception as e:
                # Unexpected error - don't flag as violation
                no_hours_data += 1

    statistics = {
        "closed_visits": closed_visits,
        "outside_hours_visits": outside_hours_visits,
        "no_hours_data": no_hours_data
    }

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
        "total_violations": len(violations),
        "total_validated": total_validated,
        "statistics": statistics
    }


def validate_rules_with_gemini(
    itinerary: ItineraryResponse2,
    rules: List[str]
) -> Dict[str, Any]:
    """
    Validate rule compliance using Gemini API.

    This function uses Gemini to verify that the generated itinerary
    follows all user-specified rules. Gemini evaluates whether the
    intent of each rule is satisfied, not just literal matching.

    Args:
        itinerary: The generated itinerary response
        rules: List of rules that must be followed

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,                       # True if all rules are followed
            "violations": List[Dict],               # List of rule violations
            "total_violations": int,                # Number of rules violated
            "total_rules": int,                     # Total number of rules checked
            "rule_results": List[Dict]              # Detailed results for each rule
        }

    Example rule:
        "첫날은 오사카성 정도만 가자" -> Checks if Day 1 includes Osaka Castle
                                       and doesn't have too many activities

    Note:
        - Uses Gemini 2.5-pro for rule validation
        - Requires valid google_api_key in settings
        - Temperature is set to 0.3 for consistent validation
    """
    if not rules:
        return {
            "is_valid": True,
            "violations": [],
            "total_violations": 0,
            "total_rules": 0,
            "rule_results": []
        }

    # Initialize Gemini client
    client = genai.Client(api_key=settings.google_api_key)

    # Convert itinerary to readable text format
    itinerary_text = ""
    for day in itinerary.itinerary:
        itinerary_text += f"\n=== Day {day.day} ===\n"
        for visit in day.visits:
            itinerary_text += f"{visit.order}. {visit.display_name} ({visit.arrival}-{visit.departure})\n"

    # Format rules
    rules_text = "\n".join([f"{i+1}. {rule}" for i, rule in enumerate(rules)])

    # Construct validation prompt
    prompt = f"""다음 여행 일정이 주어진 규칙들을 모두 따르고 있는지 검증해주세요.

**여행 일정:**
{itinerary_text}

**따라야 할 규칙:**
{rules_text}

각 규칙에 대해 다음 형식의 JSON으로 응답해주세요:
{{
    "rule_results": [
        {{
            "rule": "규칙 원문",
            "followed": true 또는 false,
            "explanation": "규칙이 지켜졌는지/안 지켜졌는지에 대한 간단한 설명"
        }}
    ]
}}

규칙 검증 기준:
- 정확히 일치할 필요는 없고, 규칙의 의도가 지켜졌는지 확인
- 예: "첫날은 오사카성 정도만 가자"는 첫날에 오사카성이 포함되고 무리하지 않은 일정이면 OK
- 예: "둘째날 유니버설 하루 종일"은 둘째날에 유니버설이 대부분의 시간을 차지하면 OK"""

    try:
        # Call Gemini API
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Low temperature for consistent validation
                response_mime_type="application/json"
            )
        )

        result_text = response.text.strip()

        # Parse JSON response
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()

        result = json.loads(result_text)

        # Extract violations
        violations = []
        for rule_result in result["rule_results"]:
            if not rule_result["followed"]:
                violations.append({
                    "rule": rule_result["rule"],
                    "explanation": rule_result["explanation"],
                    "issue": f"Rule not followed: {rule_result['rule']}"
                })

        return {
            "is_valid": len(violations) == 0,
            "violations": violations,
            "total_violations": len(violations),
            "total_rules": len(rules),
            "rule_results": result["rule_results"]
        }

    except Exception as e:
        # If validation fails, mark all rules as violated
        violations = [
            {
                "rule": rule,
                "explanation": f"Validation error: {str(e)}",
                "issue": f"Failed to validate rule: {rule}"
            }
            for rule in rules
        ]

        return {
            "is_valid": False,
            "violations": violations,
            "total_violations": len(rules),
            "total_rules": len(rules),
            "rule_results": [
                {
                    "rule": rule,
                    "followed": False,
                    "explanation": f"Validation error: {str(e)}"
                }
                for rule in rules
            ]
        }


def validate_all_with_grounding(
    itinerary: ItineraryResponse2,
    must_visit: List[str],
    expected_days: int,
    rules: List[str]
) -> Dict[str, Any]:
    """
    Run all validators with grounding and aggregate results.

    This function runs all validation checks including grounding-based
    validators and returns a comprehensive validation report.

    Args:
        itinerary: The generated itinerary response
        must_visit: List of place names that must be included
        expected_days: Expected number of days from the request
        rules: List of rules that must be followed

    Returns:
        Dictionary with all validation results:
        {
            "all_valid": bool,                      # True if all validations pass
            "must_visit": {...},                    # Must-visit validation results
            "days": {...},                          # Days count validation results
            "rules": {...},                         # Rules validation results (with Gemini)
            "operating_hours": {...}                # Operating hours validation results (with grounding)
        }

    Note:
        - This function uses grounding-based validators (API calls)
        - May be slower than validate_all() due to external API calls
        - Requires valid API keys in settings
        - travel_time validation has been removed (now handled by fetch_actual_travel_times)
    """
    must_visit_result = validate_must_visit(itinerary, must_visit)
    days_result = validate_days_count(itinerary, expected_days)
    rules_result = validate_rules_with_gemini(itinerary, rules)
    hours_result = validate_operating_hours_with_grounding(itinerary)

    all_valid = (
        must_visit_result["is_valid"] and
        days_result["is_valid"] and
        rules_result["is_valid"] and
        hours_result["is_valid"]
    )

    return {
        "all_valid": all_valid,
        "must_visit": must_visit_result,
        "days": days_result,
        "rules": rules_result,
        "operating_hours": hours_result
    }


# ==================== Time Utility Functions ====================

def time_to_minutes(time_str: str) -> int:
    """
    Convert time string "HH:MM" to total minutes from midnight.

    Args:
        time_str: Time in "HH:MM" format (e.g., "14:30")

    Returns:
        Total minutes from midnight (e.g., 14*60 + 30 = 870)

    Example:
        >>> time_to_minutes("14:30")
        870
        >>> time_to_minutes("00:00")
        0
    """
    try:
        hour, minute = map(int, time_str.split(":"))
        return hour * 60 + minute
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid time format: {time_str}. Expected 'HH:MM'") from e


def minutes_to_time(minutes: int) -> str:
    """
    Convert total minutes from midnight to time string "HH:MM".

    Handles overflow beyond 24 hours by wrapping to next day.

    Args:
        minutes: Total minutes from midnight

    Returns:
        Time string in "HH:MM" format

    Example:
        >>> minutes_to_time(870)
        "14:30"
        >>> minutes_to_time(1440)  # 24 hours -> wraps to 00:00
        "00:00"
    """
    # Handle day overflow (wrap to next day if >= 24 hours)
    minutes = minutes % 1440  # 1440 = 24 * 60

    hour = minutes // 60
    minute = minutes % 60

    return f"{hour:02d}:{minute:02d}"


# ==================== Itinerary Adjustment Functions ====================
# (기존 adjust_itinerary_with_actual_travel_times 함수는 PR#9에서 제거됨)
# 새로운 함수들은 아래에 추가됩니다.


def update_travel_times_from_routes(
    itinerary: ItineraryResponse2,
    routes_data: Dict[Tuple[int, int], int]
) -> ItineraryResponse2:
    """
    Update travel_time fields in itinerary with actual Routes API data.

    This function only updates the travel_time field values and does NOT
    adjust arrival/departure times. Time adjustment should be done separately
    using adjust_schedule_with_new_travel_times().

    Args:
        itinerary: The itinerary to update
        routes_data: Dictionary mapping (day, from_order) to actual travel time (minutes)
                    Example: {(1, 1): 15, (1, 2): 20, (2, 1): 10}
                    This is the return value from fetch_actual_travel_times()

    Returns:
        Updated itinerary with travel_time fields replaced (deep copy)

    Note:
        - Creates a deep copy to avoid modifying the original itinerary
        - Only updates visits that exist in routes_data
        - Visits not in routes_data keep their original travel_time
        - Does NOT modify arrival/departure times
    """
    import copy

    # Create deep copy to avoid modifying original
    updated = copy.deepcopy(itinerary)

    # Update travel_time values from routes_data
    for day in updated.itinerary:
        for visit in day.visits:
            key = (day.day, visit.order)

            if key in routes_data:
                # Replace with actual travel time from Routes API
                visit.travel_time = routes_data[key]

    return updated


def adjust_schedule_with_new_travel_times(
    itinerary: ItineraryResponse2,
    min_stay_minutes: int = 30
) -> ItineraryResponse2:
    """
    Adjust arrival/departure times based on updated travel_time values.

    This function should be called AFTER update_travel_times_from_routes().
    It recalculates arrival/departure times to ensure consistency with the
    new travel_time values while prioritizing keeping arrival times fixed.

    Strategy:
    1. Keep arrival times fixed when possible (Priority #1)
    2. Adjust only departure times to match travel_time
    3. If stay duration becomes too short (< min_stay_minutes):
       - Push forward the next visit's arrival time
       - Propagate changes to all subsequent visits (cascade adjustment)

    Args:
        itinerary: The itinerary with updated travel_time values
        min_stay_minutes: Minimum stay duration at each place (default: 30)

    Returns:
        Adjusted itinerary with recalculated arrival/departure times (deep copy)

    Note:
        - Creates a deep copy to avoid modifying the original itinerary
        - Processes each day independently
        - Ensures stay_duration = departure - arrival >= min_stay_minutes
        - Cascades adjustments forward when arrival times must be changed
    """
    import copy

    # Create deep copy to avoid modifying original
    adjusted = copy.deepcopy(itinerary)

    # Process each day independently
    for day in adjusted.itinerary:
        visits = day.visits

        if len(visits) <= 1:
            # Single visit or empty - no adjustment needed
            continue

        # Process visits in forward order
        for i in range(len(visits)):
            current_visit = visits[i]

            # Calculate stay duration
            arrival_min = time_to_minutes(current_visit.arrival)
            departure_min = time_to_minutes(current_visit.departure)
            stay_duration = departure_min - arrival_min

            # Ensure minimum stay duration
            if stay_duration < min_stay_minutes:
                # Adjust departure to meet minimum stay
                departure_min = arrival_min + min_stay_minutes
                current_visit.departure = minutes_to_time(departure_min)

            # If this is not the last visit, adjust next visit's arrival
            if i < len(visits) - 1:
                next_visit = visits[i + 1]

                # Calculate expected arrival at next visit
                expected_next_arrival_min = departure_min + current_visit.travel_time

                # Get current next arrival
                next_arrival_min = time_to_minutes(next_visit.arrival)

                # Check if adjustment is needed
                if expected_next_arrival_min != next_arrival_min:
                    # Calculate required departure to arrive on time
                    required_departure_min = next_arrival_min - current_visit.travel_time

                    # Check if we can maintain minimum stay
                    if required_departure_min >= arrival_min + min_stay_minutes:
                        # Can maintain arrival - just adjust departure
                        current_visit.departure = minutes_to_time(required_departure_min)
                    else:
                        # Cannot maintain minimum stay - must push forward next arrival
                        # Set departure to minimum stay
                        current_visit.departure = minutes_to_time(arrival_min + min_stay_minutes)

                        # Push forward next visit and cascade
                        new_next_arrival_min = arrival_min + min_stay_minutes + current_visit.travel_time
                        next_visit.arrival = minutes_to_time(new_next_arrival_min)

                        # Cascade adjustment to all subsequent visits
                        for j in range(i + 1, len(visits)):
                            cascade_visit = visits[j]
                            cascade_arrival_min = time_to_minutes(cascade_visit.arrival)

                            # Ensure minimum stay at this visit
                            cascade_departure_min = cascade_arrival_min + min_stay_minutes
                            cascade_visit.departure = minutes_to_time(cascade_departure_min)

                            # Update next visit's arrival if not the last
                            if j < len(visits) - 1:
                                cascade_next = visits[j + 1]
                                cascade_next_arrival_min = cascade_departure_min + cascade_visit.travel_time
                                cascade_next.arrival = minutes_to_time(cascade_next_arrival_min)

    return adjusted
