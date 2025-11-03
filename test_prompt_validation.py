#!/usr/bin/env python3
"""
프롬프트 검증 스크립트
PR #4의 5단계 우선순위 프롬프트가 올바르게 작성되었는지 검증
"""

from datetime import date
from models.schemas2 import ItineraryRequest2, PlaceWithTag, PlaceTag
from services.itinerary_generator2 import ItineraryGeneratorService2


def test_prompt_structure():
    """프롬프트 구조 검증"""

    # 테스트용 요청 데이터 생성
    request = ItineraryRequest2(
        country="일본, 오사카",
        days=3,
        start_date=date(2025, 11, 15),
        members=2,
        chat=[
            "오사카 3일 여행 계획 중이에요",
            "유니버설 스튜디오는 꼭 가고 싶어요",
            "맛집 투어도 하고 싶어요",
            "대중교통 이용할 예정입니다"
        ],
        rule=[
            "첫날은 늦게 도착해서 저녁부터 시작",
            "둘째날은 유니버설 스튜디오 하루 종일"
        ],
        must_visit=["유니버설 스튜디오 재팬"],
        places=[
            PlaceWithTag(place_name="유니버설 스튜디오 재팬", place_tag=PlaceTag.TOURIST_SPOT),
            PlaceWithTag(place_name="오사카 성", place_tag=PlaceTag.TOURIST_SPOT),
            PlaceWithTag(place_name="도톤보리", place_tag=PlaceTag.TOURIST_SPOT),
            PlaceWithTag(place_name="쿠로몬 시장", place_tag=PlaceTag.RESTAURANT),
        ]
    )

    # ItineraryGeneratorService2 인스턴스 생성
    service = ItineraryGeneratorService2()

    # 프롬프트 생성
    prompt = service._create_prompt_v2(request)

    print("=" * 80)
    print("프롬프트 검증 결과")
    print("=" * 80)

    # 1. 프롬프트 길이 확인
    print(f"\n1. 프롬프트 길이: {len(prompt)} 문자")
    print(f"   - 줄 수: {len(prompt.splitlines())} 줄")

    # 2. 필수 섹션 존재 확인
    required_sections = [
        "# 여행 일정 생성 시스템 - 5단계 우선순위",
        "## 우선순위 체계",
        "### 🔴 Priority 1: 사용자 요청사항 준수 (MANDATORY - 100%)",
        "### 🟠 Priority 2: 운영시간 준수 (HIGHLY RECOMMENDED - 90%+)",
        "### 🟡 Priority 3: 맥락적 순서 배치 (RECOMMENDED - 80%+)",
        "### 🟢 Priority 4: 효율적인 동선 (OPTIMIZATION - Best Effort)",
        "### 🔵 Priority 5: 평점 우선 선택 (NICE TO HAVE - Best Effort)",
        "**핵심 원칙**: Priority N은 Priority N-1을 절대 위반할 수 없습니다",
        "## 🔴 Priority 1: 사용자 요청사항 준수 (MANDATORY - 100%)",
        "### 1-A. 여행 일수(days) 및 시작일(start_date) 정확히 준수",
        "### 1-B. 필수 방문 장소(must_visit) 100% 포함",
        "### 1-C. 규칙(rule) 100% 준수",
        "### 1-D. 대화 내용(chat) 분석 및 사용자 취향 반영",
        "### 1-E. 후보 장소(places) 우선 선택, 부족 시 Gemini 추천",
        "## 🟠 Priority 2: 운영시간 및 이동시간 준수 (HIGHLY RECOMMENDED - 90%+)",
        "### 2-A. 운영시간 준수",
        "### 2-B. 이동시간 정확성 및 Google Maps Grounding Tool 활용",
        "**travel_time 계산 규칙** (매우 중요):",
        "## 🟡 Priority 3: 맥락적 순서 배치 (RECOMMENDED - 80%+)",
        "### 3-A. 체류시간 적절성",
        "### 3-B. 방문 시간대 적절성",
        "### 3-C. 자연스러운 활동 흐름",
        "## 🟢 Priority 4: 효율적인 동선 (OPTIMIZATION - Best Effort)",
        "### 4-A. 이동시간 최소화",
        "### 4-B. 지역별 클러스터링",
        "## 🔵 Priority 5: 평점 우선 선택 (NICE TO HAVE - Best Effort)",
        "## 제약사항",
        "### 하루 일정 길이",
        "### 숙소(HOME) 출발/귀가 원칙",
        "### HOME 없을 시 Gemini가 숙소 추천",
        "## 숙소(HOME) 처리 로직",
        "### HOME 태그 장소 식별 및 활용",
        "### 하루 일정 시작/종료를 숙소로 설정",
        "### HOME 없을 경우 숙소 추천 상세 기준",
        "## Google Maps Grounding 활용 가이드",
        "### 필수 정보 조회",
        "### 교통수단 매핑",
        "### Google Maps 사용 예시",
        "## 출력 형식 (Output Format)",
        "### JSON 구조",
        "### JSON 필드 상세 설명",
        "### travel_time 필드 정의 (매우 중요)",
        "### 예시 JSON (2일 일정, HOME 포함)",
        "### 필수 준수 사항",
        "## 검증 체크리스트",
        "### 🔴 Priority 1 검증 (MANDATORY - 절대 위반 불가)",
        "### 🟠 Priority 2 검증 (HIGHLY RECOMMENDED - 최대한 준수)",
        "### 제약사항 검증",
        "### JSON 형식 검증",
        "## 최종 지침",
        "### 응답 전 최종 확인",
        "### 응답 생성",
    ]

    print(f"\n2. 필수 섹션 존재 확인:")
    missing_sections = []
    for section in required_sections:
        if section in prompt:
            print(f"   ✅ {section[:60]}...")
        else:
            print(f"   ❌ {section[:60]}...")
            missing_sections.append(section)

    # 3. 검증 결과
    print(f"\n3. 검증 결과:")
    if missing_sections:
        print(f"   ❌ 누락된 섹션: {len(missing_sections)}개")
        for section in missing_sections:
            print(f"      - {section}")
    else:
        print(f"   ✅ 모든 필수 섹션 존재")

    # 4. 입력 데이터 포함 확인
    print(f"\n4. 입력 데이터 포함 확인:")
    input_data_checks = [
        ("여행 국가/도시", "일본, 오사카" in prompt),
        ("여행 인원", "2명" in prompt),
        ("여행 기간", "총 3일" in prompt),
        ("대화 내용", "오사카 3일 여행 계획 중이에요" in prompt),
        ("규칙", "첫날은 늦게 도착해서 저녁부터 시작" in prompt),
        ("필수 방문 장소", "유니버설 스튜디오 재팬" in prompt),
        ("장소 목록", "오사카 성" in prompt and "도톤보리" in prompt),
    ]

    for check_name, check_result in input_data_checks:
        status = "✅" if check_result else "❌"
        print(f"   {status} {check_name}")

    # 5. 핵심 키워드 확인
    print(f"\n5. 핵심 키워드 확인:")
    keywords = [
        ("5단계 우선순위", "5단계 우선순위"),
        ("Google Maps Grounding", "Google Maps Grounding Tool"),
        ("travel_time 계산 규칙", "첫 번째 방문의 travel_time"),
        ("숙소(HOME)", "place_tag=HOME"),
        ("10-12시간", "10-12시간"),
        ("검증 체크리스트", "검증 체크리스트"),
        ("순수 JSON", "순수 JSON만 출력"),
    ]

    for keyword_name, keyword in keywords:
        if keyword in prompt:
            print(f"   ✅ {keyword_name}")
        else:
            print(f"   ❌ {keyword_name}")

    print("\n" + "=" * 80)
    print("검증 완료!")
    print("=" * 80)

    # 6. 프롬프트 미리보기 (처음 500자)
    print(f"\n6. 프롬프트 미리보기 (처음 500자):")
    print("-" * 80)
    print(prompt[:500] + "...")
    print("-" * 80)

    return len(missing_sections) == 0


if __name__ == "__main__":
    success = test_prompt_structure()
    if success:
        print("\n✅ 모든 검증 통과!")
        exit(0)
    else:
        print("\n❌ 검증 실패!")
        exit(1)
