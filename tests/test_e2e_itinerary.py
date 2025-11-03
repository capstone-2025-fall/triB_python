"""
E2E Test for Itinerary Generation API

이 테스트는 다음을 검증합니다:
1. API가 올바른 응답 구조를 반환하는지
2. 실제 Google Maps API를 통해 계산된 이동시간이 응답에 제대로 반영되었는지
3. 장소 정보가 정확한지
4. 일정이 논리적으로 구성되었는지
"""

import httpx
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import asyncio
from config import settings
import json
from services.database import db_service
from services.embedding import embedding_service


class GoogleMapsValidator:
    """Google Maps API를 사용하여 응답 데이터를 검증하는 클래스"""

    def __init__(self):
        self.api_key = settings.google_maps_api_key
        self.routes_api_url = (
            "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
        )
        self.places_api_url = "https://places.googleapis.com/v1/places"

    async def get_actual_travel_time(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        travel_mode: str = "DRIVE",
    ) -> Tuple[float, Dict]:
        """
        두 지점 간의 실제 이동시간을 Google Routes API로 조회

        Returns:
            (이동시간(분), 원본 응답 데이터)
        """
        request_body = {
            "origins": [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {"latitude": origin_lat, "longitude": origin_lng}
                        }
                    }
                }
            ],
            "destinations": [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {"latitude": dest_lat, "longitude": dest_lng}
                        }
                    }
                }
            ],
            "travelMode": travel_mode,
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "originIndex,destinationIndex,status,condition,distanceMeters,duration",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.routes_api_url, json=request_body, headers=headers
            )
            response.raise_for_status()
            result = response.json()

            if result and len(result) > 0:
                element = result[0]
                if "duration" in element:
                    duration_str = element["duration"]
                    duration_seconds = int(duration_str.rstrip("s"))
                    duration_minutes = duration_seconds / 60.0
                    return duration_minutes, element
                else:
                    return 0.0, element
            return 0.0, {}

    async def get_place_details(self, place_id: str) -> Dict:
        """
        Google Places API로 장소 상세 정보 조회

        Returns:
            장소 정보 딕셔너리
        """
        url = f"{self.places_api_url}/{place_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,location,currentOpeningHours",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


class ItineraryE2ETest:
    """일정 생성 API E2E 테스트"""

    def __init__(self):
        self.api_url = "http://localhost:8001/api/itinerary/generate"
        self.validator = GoogleMapsValidator()
        self.test_payload = {
            "places": [
                "ChIJc7M3_BPnAGARI8OZlTnEXGI",
                "ChIJV0LnVRTnAGARLTeh1yIz86A",
                "ChIJB_qrI7bnAGARUHqfiC1mhQU",
                "ChIJNcHFBPjnAGARD-0MhCqLHEU",
                "ChIJA5demxPnAGAR_GuuFfdBCJ4",
                "ChIJAQBk6xTnAGAR6RmXfp6DVSM",
                "ChIJ8zGjMsjgAGARPIlBMy4yLFs",
                "ChIJz9loiGvnAGARW1TwVyJBooY",
                "ChIJvRX1cBPnAGARzhcHALQCKbw",
                "ChIJdZFNUxPnAGARewk2xIG6bR0",
                "ChIJFzU7uhPnAGARc2Gj8CJhlEA",
                "ChIJ_TooXM3gAGARQR6hXH3QAQ8",
                "ChIJ_fmKgRPnAGARkKWLtCYTu7g",
                "ChIJzakNjPToAGARzCwIriDFg28",
                "ChIJXeLVg9DgAGARqlIyMCX-BTY",
                "ChIJcxIbNhHnAGARl8cKu_vPFMA",
                "ChIJ9_rNIxO5AGARiI-QjZ-ncfE",
                "ChIJ7xwqpNvmAGARsm6fpyLvNaE",
            ],
            "user_request": {
                "query": "일본 오사카 여행으로, 유니버설 스튜디오에서의 액티비티를 즐기고 도톤보리 야경과 우메다 스카이빌딩 야경을 감상하며, 오코노미야키, 부타만, 타코야키, 회전초밥, 미니언 푸드 등 현지 미식을 풍성하게 경험하고 싶다. 또한 신사이바시 거리와 포켓몬 센터에서 쇼핑하는 것을 중요하게 생각하며, 드라이브로 자유롭게 이동하고 적정 예산을 활용하여 첫날은 여유롭게 관광하고 나머지 일정은 액티비티와 쇼핑에 집중하는 여행 스타일이다. 1일차] 텐만구 신사 방문 후 오사카성 이동, 이후 도톤보리에서 야경 감상 및 오코노미야키와 부타만 식사, [2일차] 유니버설 스튜디오 재팬에서 하루 종일 액티비티 즐기고 미니언 푸드 식사, 이후 신사이바시 거리에서 화장품, 기념품, 디즈니 굿즈, 포켓몬 센터 쇼핑, [3일차] 회전초밥 식사 후 아쿠아리움 방문, 이후 공항으로 이동, [계획] 비 올 경우 우메다 스카이빌딩에서 야경 감상. [공항]: 간사이 국제공항(1일차 도착), 간사이 국제공항(마지막날 출발)",
                "rule": [
                    "오사카가면 무조건 유니버설 스튜디오 가야돼",
                    "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
                    "둘째 날은 유니버설 하루 종일이지?",
                    "아 그리고 신사이바시 거리 쇼핑도 넣자",
                    "근데 오사카에 아쿠아리움도 있던데?",
                ],
                "days": 3,
                "start_date": "2025-10-15",
                "preferences": {
                    "must_visit": [
                        "ChIJzakNjPToAGARzCwIriDFg28",
                        "ChIJXeLVg9DgAGARqlIyMCX-BTY"
                    ],
                    "accommodation": "ChIJV0LnVRTnAGARLTeh1yIz86A",
                    "travel_mode": "DRIVE",
                },
            },
        }
        self.report_lines = []
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "travel_time_checks": [],
            "structure_checks": [],
            "logic_checks": [],
        }

    def add_section(self, title: str, level: int = 2):
        """보고서 섹션 추가"""
        prefix = "#" * level
        self.report_lines.append(f"\n{prefix} {title}\n")

    def add_text(self, text: str):
        """보고서 텍스트 추가"""
        self.report_lines.append(f"{text}\n")

    def add_check(self, category: str, name: str, passed: bool, details: str = ""):
        """테스트 체크 결과 추가"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.report_lines.append(f"- **{name}**: {status}")
        if details:
            self.report_lines.append(f"  - {details}")

        if passed:
            self.test_results["passed"] += 1
        else:
            self.test_results["failed"] += 1

    def add_warning(self, message: str):
        """경고 메시지 추가"""
        self.report_lines.append(f"- ⚠️ **WARNING**: {message}")
        self.test_results["warnings"] += 1

    async def run_test(self) -> str:
        """E2E 테스트 실행 및 보고서 생성"""
        self.report_lines = []
        self.add_section("E2E Test Report: Itinerary Generation API", level=1)
        self.add_text(f"**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.add_text(f"**API Endpoint**: `{self.api_url}`")

        # API 호출
        self.add_section("1. API Request")
        response = await self._call_api()

        if response is None:
            return "\n".join(self.report_lines)

        # 응답 구조 검증
        self.add_section("2. Response Structure Validation")
        await self._validate_structure(response)

        # Score 검증
        self.add_section("3. Place Score Validation")
        await self._validate_scores(response)

        # 이동시간 검증
        self.add_section("4. Travel Time Validation")
        await self._validate_travel_times(response)

        # 일정 논리 검증
        self.add_section("5. Itinerary Logic Validation")
        await self._validate_itinerary_logic(response)

        # 요약
        self.add_section("6. Test Summary")
        self._generate_summary()

        return "\n".join(self.report_lines)

    async def _call_api(self) -> Dict | None:
        """API 호출"""
        try:
            self.add_text(f"Sending request with {len(self.test_payload['places'])} places...")

            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(self.api_url, json=self.test_payload)

                self.add_text(f"**Status Code**: {response.status_code}")

                if response.status_code == 200:
                    self.add_check("api", "API Response", True, "API returned 200 OK")
                    result = response.json()

                    # 응답 구조 디버깅
                    self.add_text(f"\n**Response Structure**:")
                    self.add_text(f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)[:1000]}...\n```\n")

                    self.add_text(
                        f"**Generated {len(result.get('itinerary', []))} days of itinerary**"
                    )
                    return result
                else:
                    self.add_check(
                        "api",
                        "API Response",
                        False,
                        f"Status: {response.status_code}, Body: {response.text[:200]}",
                    )
                    return None

        except Exception as e:
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            self.add_check("api", "API Response", False, f"Exception: {error_detail}")
            return None

    async def _validate_structure(self, response: Dict):
        """응답 구조 검증 - 실제 스키마(DayItinerary)에 맞춰 검증"""

        # 필수 필드 존재 확인
        has_itinerary = "itinerary" in response
        self.add_check(
            "structure",
            "Required field 'itinerary'",
            has_itinerary,
            f"Field {'exists' if has_itinerary else 'missing'} in response",
        )

        if not has_itinerary:
            return

        itinerary = response["itinerary"]

        # 일정 일수 확인
        expected_days = self.test_payload["user_request"]["days"]
        actual_days = len(itinerary)
        days_match = actual_days == expected_days
        self.add_check(
            "structure",
            "Number of days",
            days_match,
            f"Expected {expected_days} days, got {actual_days} days",
        )

        # 각 일차별 구조 확인
        for day_idx, day in enumerate(itinerary, 1):
            day_num = day.get("day", day_idx)

            # 필수 필드 확인 (실제 스키마: day, visits)
            has_day = "day" in day
            has_visits = "visits" in day

            self.add_check(
                "structure",
                f"Day {day_num} structure",
                has_day and has_visits,
                f"Has day: {has_day}, Has visits: {has_visits}",
            )

            if has_visits:
                visits = day["visits"]
                self.add_text(f"  - Day {day_num}: {len(visits)} visits")

                # 각 방문의 구조 확인
                for visit_idx, visit in enumerate(visits):
                    has_place_id = "google_place_id" in visit
                    has_name = "display_name" in visit
                    has_coords = "latitude" in visit and "longitude" in visit
                    has_time = "visit_time" in visit
                    has_duration = "duration_minutes" in visit

                    if not (has_place_id and has_name and has_coords and has_time and has_duration):
                        self.add_warning(
                            f"Day {day_num}, Visit {visit_idx + 1}: Missing required fields"
                        )

    async def _validate_scores(self, response: Dict):
        """장소별 유사도 점수 계산 및 보고서 생성"""

        if "itinerary" not in response:
            self.add_text("Cannot calculate scores: no itinerary in response")
            return

        try:
            # DB에서 장소 정보 조회
            places = db_service.get_places_by_ids(self.test_payload["places"])

            if not places:
                self.add_text("⚠️ No places found in database")
                return

            # 사용자 쿼리로 유사도 점수 계산
            query = self.test_payload["user_request"]["query"]
            scores = embedding_service.calculate_place_scores(places, query)

            self.add_text(f"**User Query**: {query[:100]}...")
            self.add_text(f"\n**Calculated Scores for {len(scores)} places:**\n")

            # 점수를 높은 순으로 정렬
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            # 일정에 포함된 장소들 추출
            visited_place_ids = set()
            for day in response["itinerary"]:
                for visit in day.get("visits", []):
                    place_id = visit.get("google_place_id")
                    if place_id:
                        visited_place_ids.add(place_id)

            # 장소 ID -> 이름 매핑
            place_name_map = {p.google_place_id: p.display_name for p in places}

            # Score 테이블 생성
            self.add_text("| Rank | Place | Score | Included in Itinerary |")
            self.add_text("|------|-------|-------|-----------------------|")

            for rank, (place_id, score) in enumerate(sorted_scores, 1):
                place_name = place_name_map.get(place_id, "Unknown")
                included = "✅" if place_id in visited_place_ids else "❌"
                self.add_text(f"| {rank} | {place_name[:30]} | {score:.4f} | {included} |")

            # 통계 계산
            visited_scores = [scores[pid] for pid in visited_place_ids if pid in scores]
            not_visited_ids = set(scores.keys()) - visited_place_ids
            not_visited_scores = [scores[pid] for pid in not_visited_ids]

            if visited_scores:
                avg_visited_score = sum(visited_scores) / len(visited_scores)
                self.add_text(f"\n**Average Score of Visited Places**: {avg_visited_score:.4f}")

            if not_visited_scores:
                avg_not_visited_score = sum(not_visited_scores) / len(not_visited_scores)
                self.add_text(f"**Average Score of Not Visited Places**: {avg_not_visited_score:.4f}")

            # Top 5 점수의 장소가 일정에 얼마나 포함되었는지 확인
            top_5_ids = [pid for pid, _ in sorted_scores[:5]]
            top_5_included = sum(1 for pid in top_5_ids if pid in visited_place_ids)

            self.add_text(f"\n**Top 5 High-Score Places Included**: {top_5_included}/5")

            # Score 관련 체크 추가 (선택적)
            if visited_scores and not_visited_scores:
                score_check_passed = avg_visited_score >= avg_not_visited_score
                self.add_check(
                    "score",
                    "Visited places have higher average score",
                    score_check_passed,
                    f"Visited avg: {avg_visited_score:.4f}, Not visited avg: {avg_not_visited_score:.4f}"
                )

        except Exception as e:
            self.add_warning(f"Failed to calculate scores: {str(e)}")

    async def _validate_travel_times(self, response: Dict):
        """이동시간 검증 - 실제 Google API 호출하여 비교"""

        if "itinerary" not in response:
            self.add_text("Cannot validate travel times: no itinerary in response")
            return

        travel_mode = self.test_payload["user_request"]["preferences"]["travel_mode"]
        self.add_text(f"**Travel Mode**: {travel_mode}")
        self.add_text("\n**Checking travel times between consecutive places...**\n")

        total_checks = 0
        accurate_checks = 0
        tolerance_minutes = 15  # 허용 오차: 15분

        for day in response["itinerary"]:
            day_num = day.get("day", "?")
            visits = day.get("visits", [])

            for i in range(len(visits) - 1):
                current_visit = visits[i]
                next_visit = visits[i + 1]

                # 장소 정보 추출
                current_name = current_visit.get("display_name", "Unknown")
                next_name = next_visit.get("display_name", "Unknown")

                # 위치 정보
                current_lat = current_visit.get("latitude")
                current_lng = current_visit.get("longitude")
                next_lat = next_visit.get("latitude")
                next_lng = next_visit.get("longitude")

                if None in [current_lat, current_lng, next_lat, next_lng]:
                    self.add_warning(
                        f"Day {day_num}: Missing coordinates for travel time validation"
                    )
                    continue

                # visit_time과 duration_minutes를 이용해 현재 방문 종료 시간 계산
                current_time = current_visit.get("visit_time", "")
                current_duration = current_visit.get("duration_minutes", 0)
                next_time = next_visit.get("visit_time", "")

                # 실제 Google API로 이동시간 조회
                try:
                    actual_time, raw_data = await self.validator.get_actual_travel_time(
                        current_lat, current_lng, next_lat, next_lng, travel_mode
                    )

                    # 응답에서 이동시간을 추정 (다음 방문 시작 시간 - 현재 방문 종료 시간)
                    if current_time and next_time and current_duration:
                        # HH:MM 형식 파싱
                        current_hour, current_min = map(int, current_time.split(":"))
                        next_hour, next_min = map(int, next_time.split(":"))

                        # 종료 시간 계산
                        end_hour = current_hour + (current_min + current_duration) // 60
                        end_min = (current_min + current_duration) % 60

                        # 이동시간 계산 (분)
                        reported_travel_time = (next_hour * 60 + next_min) - (end_hour * 60 + end_min)
                    else:
                        self.add_warning(
                            f"Day {day_num}: Cannot calculate travel time from schedule data"
                        )
                        continue

                    total_checks += 1
                    difference = abs(actual_time - reported_travel_time)
                    is_accurate = difference <= tolerance_minutes

                    if is_accurate:
                        accurate_checks += 1

                    status = "✅" if is_accurate else "❌"
                    self.add_text(
                        f"{status} **Day {day_num}**: `{current_name}` → `{next_name}`"
                    )
                    self.add_text(
                        f"   - Schedule gap: {reported_travel_time:.1f} min | Actual travel: {actual_time:.1f} min | Diff: {difference:.1f} min"
                    )

                    if not is_accurate:
                        self.add_text(
                            f"   - ⚠️ Difference exceeds tolerance ({tolerance_minutes} min)"
                        )

                    self.test_results["travel_time_checks"].append(
                        {
                            "day": day_num,
                            "from": current_name,
                            "to": next_name,
                            "reported": reported_travel_time,
                            "actual": actual_time,
                            "difference": difference,
                            "accurate": is_accurate,
                        }
                    )

                except Exception as e:
                    self.add_warning(
                        f"Day {day_num}: Failed to validate travel time - {str(e)}"
                    )

                # API Rate limit 방지
                await asyncio.sleep(0.5)

        # 이동시간 정확도 요약
        if total_checks > 0:
            accuracy_rate = (accurate_checks / total_checks) * 100
            self.add_text(f"\n**Travel Time Accuracy**: {accuracy_rate:.1f}% ({accurate_checks}/{total_checks} checks passed)")

            is_passing = accuracy_rate >= 70  # 70% 이상 정확해야 통과
            self.add_check(
                "travel_time",
                "Overall Travel Time Accuracy",
                is_passing,
                f"{accuracy_rate:.1f}% of travel times are within {tolerance_minutes} min tolerance",
            )
        else:
            self.add_text("\n⚠️ No travel time checks were performed")

    async def _validate_itinerary_logic(self, response: Dict):
        """일정 논리 검증"""

        if "itinerary" not in response:
            return

        itinerary = response["itinerary"]

        # 1. 일차 순서 확인
        days = [day.get("day") for day in itinerary]
        days_sorted = days == sorted(days)
        self.add_check(
            "logic",
            "Day sequence",
            days_sorted,
            f"Days are {'properly ordered' if days_sorted else 'not in order'}: {days}",
        )

        # 2. 각 일차별 시간 논리 확인
        for day in itinerary:
            day_num = day.get("day", "?")
            visits = day.get("visits", [])

            if not visits:
                continue

            # 시간 순서 확인
            visit_times = []
            for visit in visits:
                visit_time = visit.get("visit_time", "")
                duration = visit.get("duration_minutes", 0)

                if visit_time:
                    visit_times.append(visit_time)

                    # 종료 시간 계산
                    hour, minute = map(int, visit_time.split(":"))
                    end_hour = hour + (minute + duration) // 60
                    end_min = (minute + duration) % 60
                    end_time = f"{end_hour:02d}:{end_min:02d}"

            # 시간이 순서대로 증가하는지 확인
            if visit_times:
                times_valid = visit_times == sorted(visit_times)
                if not times_valid:
                    self.add_warning(
                        f"Day {day_num}: Visit times are not in order: {visit_times}"
                    )

        # 3. Must-visit 장소 확인
        must_visit = set(
            self.test_payload["user_request"]["preferences"]["must_visit"]
        )
        visited_places = set()

        for day in itinerary:
            for visit in day.get("visits", []):
                place_id = visit.get("google_place_id")
                if place_id:
                    visited_places.add(place_id)

        must_visit_included = must_visit.issubset(visited_places)
        self.add_check(
            "logic",
            "Must-visit places",
            must_visit_included,
            f"All must-visit places {'included' if must_visit_included else 'NOT included'} in itinerary",
        )

        if not must_visit_included:
            missing = must_visit - visited_places
            self.add_text(f"  - Missing places: {missing}")

        # 4. 장소 개수 확인
        total_visits = sum(len(day.get("visits", [])) for day in itinerary)
        self.add_text(f"\n**Total visits across all days**: {total_visits}")

        # 5. 각 일차별 방문 장소 요약
        self.add_text(f"\n**Daily Visit Summary**:")
        for day in itinerary:
            day_num = day.get("day", "?")
            visits = day.get("visits", [])
            visit_names = [v.get("display_name", "?") for v in visits]
            self.add_text(f"- Day {day_num}: {', '.join(visit_names)}")

    def _generate_summary(self):
        """테스트 요약 생성"""
        total_tests = self.test_results["passed"] + self.test_results["failed"]
        pass_rate = (
            (self.test_results["passed"] / total_tests * 100) if total_tests > 0 else 0
        )

        self.add_text(f"**Total Tests**: {total_tests}")
        self.add_text(f"**Passed**: {self.test_results['passed']} ✅")
        self.add_text(f"**Failed**: {self.test_results['failed']} ❌")
        self.add_text(f"**Warnings**: {self.test_results['warnings']} ⚠️")
        self.add_text(f"**Pass Rate**: {pass_rate:.1f}%")

        # 전체 결과
        if self.test_results["failed"] == 0:
            self.add_text("\n## ✅ Overall Result: **PASSED**")
        else:
            self.add_text("\n## ❌ Overall Result: **FAILED**")

        self.add_text(f"\n---\n*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")


@pytest.mark.asyncio
async def test_itinerary_generation_e2e():
    """E2E 테스트 실행 및 보고서 저장"""
    test = ItineraryE2ETest()
    report = await test.run_test()

    # 보고서 저장
    report_filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n\n{'='*80}")
    print(f"E2E Test Report saved to: {report_filename}")
    print(f"{'='*80}\n")
    print(report)

    # 테스트 실패 시 assertion 에러 발생
    assert (
        test.test_results["failed"] == 0
    ), f"E2E Test failed: {test.test_results['failed']} tests failed"


if __name__ == "__main__":
    # 직접 실행 시
    async def main():
        test = ItineraryE2ETest()
        report = await test.run_test()

        # 보고서 저장
        report_filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n\n{'='*80}")
        print(f"E2E Test Report saved to: {report_filename}")
        print(f"{'='*80}\n")
        print(report)

    asyncio.run(main())
