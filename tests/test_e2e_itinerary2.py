"""
E2E Test for V2 Itinerary Generation API

V2 시스템의 종단간 테스트:
1. API가 올바른 응답 구조를 반환하는지
2. 필수 필드가 모두 포함되어 있는지
3. must_visit 장소가 일정에 포함되었는지
4. travel_time 규칙이 지켜지는지 (마지막 visit = 0)
"""

import pytest
from httpx import AsyncClient
from main2 import app


@pytest.mark.asyncio
async def test_itinerary_generation_v2_e2e():
    """V2 일정 생성 E2E 테스트"""

    # 테스트 요청 데이터 (PLAN.md 예시 활용)
    request_data = {
        "places": [
            "오사카텐만구 (오사카 천만궁)",
            "신사이바시스지",
            "오사카 성",
            "도톤보리",
            "해유관",
            "유니버설 스튜디오 재팬",
            "구로몬 시장",
            "우메다 스카이 빌딩",
            "시텐노지 (사천왕사)",
            "츠텐카쿠",
            "난바 파크스",
            "덴포잔 대관람차",
            "오사카 역사박물관",
            "스미요시 타이샤 (住吉大社)",
            "신세카이",
            "호젠지 요코초",
            "나카노시마 공원",
            "아메리카무라",
            "오사카 시립 과학관",
            "킷코만 스시 체험관"
        ],
        "user_request": {
            "chat": [
                "오사카엔 뭐가 유명하대?",
                "오사카가면 무조건 유니버설 스튜디오 가야돼",
                "해유관도 가보고 싶은데",
                "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
                "둘째날은 유니버설 하루 종일이지?",
                "마지막날은 아침에 일찍 일어나서 여유롭게",
                "음식은 타코야키랑 오코노미야키는 꼭 먹어야지",
                "숙소는 난바 쪽이 좋을까?",
                "렌터카 빌려서 다니면 편할 것 같아"
            ],
            "rule": [
                "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
                "둘째날은 유니버설 하루 종일이지?",
                "마지막날 아침에 일찍 일어나서 여유롭게"
            ],
            "days": 3,
            "start_date": "2025-10-15",
            "preferences": {
                "must_visit": ["유니버설 스튜디오 재팬", "해유관"],
                "accommodation": None,  # Gemini가 추천
                "travel_mode": "DRIVE"
            }
        }
    }

    # API 호출
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v2/itinerary/generate",
            json=request_data,
            timeout=60.0  # Gemini 호출 시간 고려
        )

    # 1. 응답 상태 코드 검증
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    print(f"\n✓ API responded with status 200")

    # 2. 응답 구조 검증
    assert "itinerary" in data, "Response must contain 'itinerary' field"
    assert isinstance(data["itinerary"], list), "itinerary must be a list"
    assert len(data["itinerary"]) == 3, f"Expected 3 days, got {len(data['itinerary'])}"
    print(f"✓ Itinerary contains 3 days")

    # 3. 각 day 검증
    for day_idx, day in enumerate(data["itinerary"], start=1):
        assert "day" in day, f"Day {day_idx} missing 'day' field"
        assert "visits" in day, f"Day {day_idx} missing 'visits' field"
        assert isinstance(day["visits"], list), f"Day {day_idx} visits must be a list"
        assert len(day["visits"]) > 0, f"Day {day_idx} must have at least one visit"

        print(f"\n✓ Day {day['day']}: {len(day['visits'])} visits")

        # 4. 각 visit 검증
        for visit_idx, visit in enumerate(day["visits"], start=1):
            # 필수 필드 존재 확인
            required_fields = ["order", "display_name", "latitude", "longitude", "visit_time", "travel_time"]
            for field in required_fields:
                assert field in visit, f"Day {day_idx}, Visit {visit_idx} missing '{field}' field"

            # 데이터 타입 검증
            assert isinstance(visit["order"], int), f"order must be int"
            assert isinstance(visit["display_name"], str), f"display_name must be str"
            assert isinstance(visit["latitude"], (int, float)), f"latitude must be number"
            assert isinstance(visit["longitude"], (int, float)), f"longitude must be number"
            assert isinstance(visit["visit_time"], str), f"visit_time must be str"
            assert isinstance(visit["travel_time"], int), f"travel_time must be int"

            # visit_time 형식 검증 (HH:MM)
            assert ":" in visit["visit_time"], f"visit_time must be in HH:MM format"

            # travel_time 규칙 검증
            is_last_visit = (visit["order"] == len(day["visits"]))
            if is_last_visit:
                assert visit["travel_time"] == 0, \
                    f"Last visit (order {visit['order']}) must have travel_time = 0, got {visit['travel_time']}"
            else:
                assert visit["travel_time"] >= 0, \
                    f"Non-last visit must have travel_time >= 0, got {visit['travel_time']}"

            print(f"  - Visit {visit['order']}: {visit['display_name']} at {visit['visit_time']} (travel_time: {visit['travel_time']}min)")

    # 5. must_visit 장소 포함 확인
    all_visit_names = []
    for day in data["itinerary"]:
        for visit in day["visits"]:
            all_visit_names.append(visit["display_name"])

    must_visit_places = request_data["user_request"]["preferences"]["must_visit"]
    for must_visit in must_visit_places:
        # 부분 매칭 (Gemini가 약간 다른 이름으로 반환할 수 있음)
        found = any(must_visit in visit_name or visit_name in must_visit for visit_name in all_visit_names)
        assert found, f"Must-visit place '{must_visit}' not found in itinerary. Visits: {all_visit_names}"

    print(f"\n✓ All must-visit places included:")
    for must_visit in must_visit_places:
        print(f"  - {must_visit}")

    # 6. 전체 방문지 수 출력
    total_visits = sum(len(day["visits"]) for day in data["itinerary"])
    print(f"\n✓ Total visits: {total_visits}")

    # 7. 숙소 추천 확인 (accommodation이 null이었으므로 Gemini가 추천했을 것)
    accommodation_visits = [
        visit for day in data["itinerary"]
        for visit in day["visits"]
        if any(keyword in visit["display_name"].lower() for keyword in ["호텔", "게스트하우스", "숙소", "hotel", "hostel", "guesthouse"])
    ]
    if accommodation_visits:
        print(f"\n✓ Gemini recommended accommodation:")
        for acc in accommodation_visits:
            print(f"  - {acc['display_name']}")

    print(f"\n✅ V2 E2E test passed!")
    print(f"=" * 60)
