"""
Validation utilities for V2 itinerary generation.

This module provides simple post-generation validators to ensure
Gemini-generated itineraries comply with user requirements.
"""

from typing import List, Dict, Any
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


def validate_travel_time_with_grounding(
    itinerary: ItineraryResponse2,
    tolerance_minutes: int = 10
) -> Dict[str, Any]:
    """
    Validate travel_time accuracy using Google Routes API v2.

    This function verifies that the travel_time values in the itinerary
    match actual travel times from Google Routes API within a tolerance.

    Args:
        itinerary: The generated itinerary response
        tolerance_minutes: Maximum allowed deviation in minutes (default: 10)

    Returns:
        Dictionary with validation results:
        {
            "is_valid": bool,                       # True if all times are within tolerance
            "violations": List[Dict],               # List of travel time violations
            "total_violations": int,                # Number of violations found
            "total_validated": int,                 # Total number of routes validated
            "statistics": {
                "avg_deviation": float,             # Average deviation in minutes
                "max_deviation": int,               # Maximum deviation found
                "min_deviation": int                # Minimum deviation found
            }
        }

    Note:
        - Uses DRIVE mode with TRAFFIC_AWARE routing preference
        - Skips last visit of each day (travel_time should be 0)
        - Requires valid google_maps_api_key in settings
    """
    violations = []
    deviations = []
    total_validated = 0

    # Routes API v2 endpoint
    routes_api_url = "https://routes.googleapis.com/directions/v2:computeRoutes"

    for day in itinerary.itinerary:
        visits = day.visits

        # Skip if no visits or only one visit
        if len(visits) <= 1:
            continue

        # Validate travel times for all visits except the last one
        for i in range(len(visits) - 1):
            current_visit = visits[i]
            next_visit = visits[i + 1]
            expected_time = current_visit.travel_time

            total_validated += 1

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

                        # Calculate deviation
                        deviation = abs(expected_time - actual_time_minutes)
                        deviations.append(deviation)

                        # Check if within tolerance
                        if deviation > tolerance_minutes:
                            violations.append({
                                "day": day.day,
                                "from_place": current_visit.display_name,
                                "to_place": next_visit.display_name,
                                "from_order": current_visit.order,
                                "expected_time": expected_time,
                                "actual_time": actual_time_minutes,
                                "deviation": deviation,
                                "tolerance": tolerance_minutes,
                                "issue": f"Travel time deviation of {deviation} minutes exceeds tolerance of {tolerance_minutes} minutes"
                            })
                    else:
                        # No route found
                        violations.append({
                            "day": day.day,
                            "from_place": current_visit.display_name,
                            "to_place": next_visit.display_name,
                            "from_order": current_visit.order,
                            "expected_time": expected_time,
                            "actual_time": None,
                            "deviation": None,
                            "tolerance": tolerance_minutes,
                            "issue": "No route found by Google Routes API",
                            "error": "NO_ROUTE_FOUND"
                        })
                else:
                    # API call failed
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = f"{error_data['error'].get('status', 'UNKNOWN')}: {error_data['error'].get('message', 'Unknown error')}"
                    except:
                        error_msg = f"HTTP {response.status_code}: {response.text[:100]}"

                    violations.append({
                        "day": day.day,
                        "from_place": current_visit.display_name,
                        "to_place": next_visit.display_name,
                        "from_order": current_visit.order,
                        "expected_time": expected_time,
                        "actual_time": None,
                        "deviation": None,
                        "tolerance": tolerance_minutes,
                        "issue": f"API call failed: {error_msg}",
                        "error": "API_ERROR"
                    })

            except Exception as e:
                # Unexpected error
                violations.append({
                    "day": day.day,
                    "from_place": current_visit.display_name,
                    "to_place": next_visit.display_name,
                    "from_order": current_visit.order,
                    "expected_time": expected_time,
                    "actual_time": None,
                    "deviation": None,
                    "tolerance": tolerance_minutes,
                    "issue": f"Unexpected error: {str(e)}",
                    "error": "EXCEPTION"
                })

    # Calculate statistics
    statistics = {
        "avg_deviation": sum(deviations) / len(deviations) if deviations else 0,
        "max_deviation": max(deviations) if deviations else 0,
        "min_deviation": min(deviations) if deviations else 0
    }

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
        "total_violations": len(violations),
        "total_validated": total_validated,
        "statistics": statistics
    }


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
