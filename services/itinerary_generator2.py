import logging
import json
from typing import List, Dict
from datetime import timedelta
from google import genai
from google.genai import types
from config import settings
from models.schemas2 import ItineraryRequest2, ItineraryResponse2, PlaceWithTag, PlaceTag
from services.validators import validate_all

logger = logging.getLogger(__name__)


class ItineraryGeneratorService2:
    """V2 일정 생성 서비스 (Gemini 중심)"""

    def __init__(self):
        """Gemini 클라이언트 초기화"""
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model_name = "gemini-2.5-pro"
        logger.info("ItineraryGeneratorService2 initialized with gemini-2.5-pro and Google Maps grounding")

    def _create_prompt_v2(
        self,
        request: ItineraryRequest2,
    ) -> str:
        """
        Gemini V2 프롬프트 생성

        Args:
            request: 일정 생성 요청

        Returns:
            완성된 프롬프트 문자열
        """
        # 날짜별 요일 계산
        weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        date_info = []
        for day_num in range(request.days):
            current_date = request.start_date + timedelta(days=day_num)
            weekday = weekdays_kr[current_date.weekday()]
            date_info.append(f"Day {day_num + 1}: {current_date.strftime('%Y-%m-%d')} ({weekday})")

        # 채팅 내용 포맷팅
        chat_text = "\n".join([f"- {msg}" for msg in request.chat])

        # 규칙 포맷팅
        rule_text = ""
        if request.rule:
            rule_text = "\n".join([f"- {r}" for r in request.rule])
        else:
            rule_text = "없음"

        # 필수 방문 장소 포맷팅
        must_visit_text = ""
        if request.must_visit:
            must_visit_text = ", ".join(request.must_visit)
        else:
            must_visit_text = "없음"

        # 숙소 정보 추출: places에서 place_tag가 HOME인 장소 찾기
        home_places = [place for place in request.places if place.place_tag == PlaceTag.HOME]
        if home_places:
            # 사용자가 지정한 숙소가 있는 경우
            accommodation_text = home_places[0].place_name
            if len(home_places) > 1:
                # 여러 숙소가 있는 경우 모두 표시
                accommodation_text = ", ".join([place.place_name for place in home_places])
        else:
            # 숙소가 없는 경우 Gemini에게 추천 요청
            accommodation_text = "없음 (추천 필요)"

        # 장소 목록 포맷팅 (place_name과 place_tag 포함)
        places_text = "\n".join([f"- {place.place_name} ({place.place_tag.value})" for place in request.places])

        # 프롬프트 구성
        prompt = f"""## 당신의 역할
당신은 여행 일정 생성 전문가입니다.
사용자가 나눈 채팅 내용을 분석하고, 제공된 장소 목록과 함께 최적의 여행 일정을 생성합니다.

## 입력 데이터

### 여행 국가/도시
{request.country}

### 여행 인원
{request.members}명

### 여행 기간
{chr(10).join(date_info)}
총 {request.days}일

### 고려 중인 장소 목록 (places)
각 장소에는 사용자가 지정한 place_tag가 포함되어 있습니다.
{places_text}

### 사용자 대화 내용 (chat)
{chat_text}

### 반드시 지켜야 할 규칙 (rule)
{rule_text}

### 필수 방문 장소 (must_visit)
{must_visit_text}

### 숙소 (accommodation)
{accommodation_text}

# 여행 일정 생성 시스템 - 5단계 우선순위

## 우선순위 체계

### 🔴 Priority 1: 사용자 요청사항 준수 (MANDATORY - 100%)
- 여행 일수(days) 정확히 준수
- 여행 시작일(start_date) 정확히 준수
- 필수 방문 장소(must_visit) 100% 포함
- 규칙(rule) 100% 준수
- 대화 내용(chat) 분석하여 사용자 취향 반영
- 후보 장소(places) 우선 선택, 부족 시 Gemini가 추천

### 🟠 Priority 2: 운영시간 준수 (HIGHLY RECOMMENDED - 90%+)
- 모든 장소는 운영시간 내에만 방문
- 운영시간 없는 요일 방문 금지
- 이동시간 고려하여 운영시간 내 도착
- Google Maps Grounding Tool 활용 필수
- 교통수단 chat에서 추론 (기본값: transit)

### 🟡 Priority 3: 맥락적 순서 배치 (RECOMMENDED - 80%+)
- 체류시간 적절성
- 방문 시간대 적절성 (식사시간 고려)
- 자연스러운 활동 흐름

### 🟢 Priority 4: 효율적인 동선 (OPTIMIZATION - Best Effort)
- 이동시간 최소화
- 효율적인 동선 구성

### 🔵 Priority 5: 평점 우선 선택 (NICE TO HAVE - Best Effort)
- 평점 높은 장소 방문

**핵심 원칙**: Priority N은 Priority N-1을 절대 위반할 수 없습니다.

---

## 🔴 Priority 1: 사용자 요청사항 준수 (MANDATORY - 100%)

이 우선순위의 요구사항들은 **절대적으로 준수**해야 하며, 어떤 상황에서도 위반할 수 없습니다.

### 1-A. 여행 일수(days) 및 시작일(start_date) 정확히 준수

**필수 사항**:
- 요청된 `days` 값과 정확히 동일한 개수의 day 객체를 생성해야 합니다
- 각 day의 날짜는 `start_date`부터 시작하여 하루씩 증가해야 합니다
- day 번호는 1부터 시작하여 1씩 증가합니다

**검증 방법**:
- len(itinerary) == days
- day.day: 1, 2, 3, ..., days
- day.date: start_date, start_date+1일, ..., start_date+(days-1)일

**예시**:
- 요청: days=3, start_date=2025-10-15
- 생성: Day 1 (2025-10-15), Day 2 (2025-10-16), Day 3 (2025-10-17)

**금지사항**:
- ❌ 일수를 늘리거나 줄이는 것 절대 불가
- ❌ 날짜를 건너뛰는 것 절대 불가

### 1-B. 필수 방문 장소(must_visit) 100% 포함

**필수 사항**:
- `must_visit`에 명시된 모든 장소는 반드시 일정에 포함되어야 합니다
- 일정이 부족하면 다른 추천 장소를 제거하더라도 must_visit는 반드시 유지하세요
- 운영시간이 맞지 않으면 다른 날짜로 이동하세요

**검증 방법**:
- must_visit의 각 장소명이 itinerary의 어느 day에든 display_name으로 존재해야 함

**절대 규칙**:
- 어떤 상황에서도 must_visit 장소를 생략할 수 없습니다

### 1-C. 규칙(rule) 100% 준수

**필수 사항**:
- `rule`에 명시된 모든 항목은 반드시 일정에 정확히 반영되어야 합니다
- 규칙이 모호하면 사용자의 의도를 최대한 추론하여 적용하세요

**규칙 해석 및 적용**:
- **시간 제약**: "11시 기상" → 첫 방문(arrival)은 11:00 이후
- **활동 요구**: "점심은 현지 맛집에서" → 점심시간(12:00-14:00)에 RESTAURANT 방문
- **장소 우선순위**: "둘째날은 유니버설 하루 종일" → Day 2는 유니버설만 포함
- **이동 제약**: "마지막날 공항으로 직행" → 마지막날은 숙소 대신 공항으로 종료

**우선순위**: 규칙(rule) > 숙소 왕복 > 기본 패턴

### 1-D. 대화 내용(chat) 분석 및 사용자 취향 반영

**필수 사항**:
- 채팅 내용을 분석하여 여행 스타일, 선호도, 패턴을 파악하세요
- 여행 의도와 구체적인 요구사항을 일정에 반영하세요

**분석 항목**:
1. **여행 스타일 파악**:
   - "여유롭게", "느긋하게" → 체류시간 길게, 이동 적게
   - "알차게", "많이 보고 싶어" → 방문 장소 많게, 이동시간 최소화
   - "로컬 음식", "맛집 투어" → RESTAURANT 타입 장소 우선 포함

2. **특정 요구사항 추출**:
   - "카페에서 여유롭게" → CAFE 장소 포함, 충분한 체류시간 할당
   - "맛있는 라멘 가게 가고 싶다" → Google Maps로 라멘집 검색하여 추가
   - "쇼핑 많이 하고 싶어" → 쇼핑 장소 비중 높이기

3. **이동 수단 추론** (travel_time 계산에 반영):
   - "렌터카", "차 빌려서", "자동차" → **DRIVE**
   - "지하철", "버스", "대중교통" → **TRANSIT**
   - "걸어서", "도보", "산책" → **WALK**
   - "자전거" → **BICYCLE**
   - 언급 없음 → **TRANSIT (기본값)**

### 1-E. 후보 장소(places) 우선 선택, 부족 시 Gemini 추천

**필수 사항**:
- places 리스트의 장소를 **전체 방문 장소의 70% 이상** 사용하세요
- places 장소는 사용자가 관심 있어하는 장소이므로 최대한 포함하세요

**장소 선택 프로세스**:
1. **places 리스트 우선 선택 (70% 이상)**:
   - "고려 중인 장소 목록 (places)"에서 적절한 장소를 우선 선택
   - 채팅 내용에서 파악한 여행 스타일에 맞는 장소를 places에서 선택
   - 예: "여유로운 여행" + places에 CAFE/PARK → 이 장소들 우선 포함

2. **부족한 장소는 Gemini가 추천 (30% 이하)**:
   - places에 적합한 장소가 없거나 부족하면 Google Maps로 새 장소 검색
   - 예: "맛있는 라멘 가게" 요청 + places에 라멘집 없음
     → Google Maps로 해당 지역 유명 라멘 가게 추천

3. **place_tag 활용**:
   - places의 장소를 일정에 사용할 때는 해당 place_tag 그대로 사용
   - Gemini가 새로 추천하는 장소는 가장 적절한 place_tag 선택
   - 가능한 값: TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER

**검증**:
- (places에서 선택한 장소 수 / 전체 방문 장소 수) ≥ 70%

---

## 🟠 Priority 2: 운영시간 및 이동시간 준수 (HIGHLY RECOMMENDED - 90%+)

이 우선순위는 **Priority 1과 충돌하지 않는 한 최대한 준수**해야 합니다.

### 2-A. 운영시간 준수

**필수 사항**:
- 모든 방문은 운영시간 내에만 이루어져야 합니다
- arrival ≥ opening_time AND departure ≤ closing_time
- 휴무일(closed) 방문 절대 금지
- Google Maps Grounding Tool로 실제 운영시간 확인 필수

**요일별 운영시간 확인**:
여행 일정의 각 날짜와 요일 정보는 상단의 "여행 기간" 섹션에 명시되어 있습니다.
- 예: "Day 1: 2025-10-15 (수요일)" → 해당 날짜는 수요일
- **중요**: Google Maps에서 각 장소의 해당 요일 운영시간을 확인하세요
  - Day 1이 수요일이면 Wednesday 운영시간 사용
  - Day 2가 목요일이면 Thursday 운영시간 사용
- 해당 요일에 휴무(closed)이면 그 날짜에는 절대 방문하지 마세요

**예시**:
- 박물관이 월요일 휴무 → 월요일에는 일정에 포함하지 않음
- 테마파크 운영시간 09:00-21:00 → arrival은 09:00 이후, departure는 21:00 이전
- 레스토랑 영업시간 11:30-22:00 → 점심 방문 시 arrival은 11:30 이후

**Priority 1 충돌 시**:
- must_visit 우선, 날짜 재조정으로 운영시간 맞춤

### 2-B. 이동시간 정확성 및 Google Maps Grounding Tool 활용

**필수 사항**:
- Google Maps Grounding Tool을 사용하여 실제 이동시간을 계산하세요
- 교통수단을 고려하세요 (DRIVE/TRANSIT/WALK/BICYCLE)
- visit[i+1].arrival = visit[i].departure + visit[i].travel_time

**교통수단 선택** (1-D에서 추론):
- **DRIVE**: 자동차 경로 기반 이동시간
- **TRANSIT**: 대중교통 경로 기반 이동시간 (환승 포함) - **기본값**
- **WALK**: 도보 경로 기반 이동시간
- **BICYCLE**: 자전거 경로 기반 이동시간

**travel_time 계산 규칙** (매우 중요):
- **첫 번째 방문의 travel_time**: 첫 번째 장소 → 두 번째 장소 이동시간
- **중간 방문의 travel_time**: 현재 장소 → 다음 장소 이동시간
- **마지막 방문의 travel_time**: 0 (다음 장소가 없음)

**계산 공식**:
```
next_place.arrival = current_place.departure + travel_time
```

**예시**:
- Visit 1 (오사카 성): departure "11:30", travel_time 30분
- Visit 2 (도톤보리): arrival "12:00" (11:30 + 30분)
- Visit 2 (도톤보리): departure "14:00", travel_time 0 (마지막 방문)

**검증**:
- 각 연속된 방문 사이: visit[i+1].arrival = visit[i].departure + visit[i].travel_time
- 실시간 교통 상황, 대중교통 배차 간격을 고려한 현실적인 이동시간 반영

---

## 🟡 Priority 3: 맥락적 순서 배치 (RECOMMENDED - 80%+)

이 우선순위는 **Priority 1, 2를 만족한 후 추가 개선 사항**입니다.

### 3-A. 체류시간 적절성

각 장소별 적절한 체류시간을 고려하세요:
- **대형 테마파크** (유니버설 스튜디오 등): 6-10시간
- **주요 관광지** (성, 사원 등): 1.5-3시간
- **수족관/박물관**: 2-3시간
- **쇼핑 거리**: 1-2시간
- **식사**: 1-1.5시간
- **카페/휴식**: 0.5-1시간

**적용 방법**:
- departure = arrival + 적절한 체류시간
- 장소의 특성과 사용자 취향(chat)을 고려하여 조정
- 예: "여유롭게" 선호 → 체류시간 길게 설정

### 3-B. 방문 시간대 적절성

**식사시간 고려**:
- **점심**: 11:30-13:30 사이에 RESTAURANT 방문
- **저녁**: 18:00-20:00 사이에 RESTAURANT 방문
- 식사 시간을 고려하여 관광지 방문 순서 조정

**시간대별 적절한 활동**:
- **아침 (09:00-12:00)**: 관광지 방문, 박물관
- **점심 (12:00-14:00)**: 식사, 맛집 탐방
- **오후 (14:00-18:00)**: 관광지 방문, 쇼핑
- **저녁 (18:00-20:00)**: 식사, 야경 감상
- **밤 (20:00-22:00)**: 카페, 야시장, 숙소 복귀

### 3-C. 자연스러운 활동 흐름

**권장 패턴**:
- 관광 → 식사 → 카페 → 관광
- 실내 → 실외 → 실내 (날씨/체력 고려)
- 활동적 → 휴식 → 활동적 (체력 분산)

**예시**:
- 오전: 오사카 성 (관광, 2.5시간)
- 점심: 현지 맛집 (식사, 1시간)
- 오후: 도톤보리 산책 (관광, 2시간)
- 저녁: 카페 휴식 (카페, 1시간)
- 저녁: 저녁 식사 (식사, 1.5시간)

---

## 🟢 Priority 4: 효율적인 동선 (OPTIMIZATION - Best Effort)

이 우선순위는 **Priority 1-3을 만족한 후 최적화 사항**입니다.

### 4-A. 이동시간 최소화

**권장 사항**:
- 지리적으로 가까운 장소들을 묶어서 배치하세요
- 같은 지역/구역 내 장소들을 연속으로 방문하세요
- 불필요한 왕복 이동을 피하세요

**예시**:
- ⭕ 좋은 동선: 오사카 성 → 도톤보리 → 난바 (남쪽 방향으로 이동)
- ❌ 나쁜 동선: 오사카 성 → 우메다 → 도톤보리 → 난바 (북쪽 갔다가 다시 남쪽)

### 4-B. 지역별 클러스터링

**권장 사항**:
- 동일 지역 내 장소들을 하루에 묶어서 방문하세요
- 예: Day 1은 오사카 남부, Day 2는 오사카 북부
- 지역 간 대이동은 하루에 1회 이하로 제한하세요

---

## 🔵 Priority 5: 평점 우선 선택 (NICE TO HAVE - Best Effort)

이 우선순위는 **Priority 1-4를 만족한 후 추가 개선 사항**입니다.

### 5-A. 평점 높은 장소 우선 선택

**권장 사항**:
- 동일 조건(위치, 시간, 유형)의 장소가 여러 개 있을 경우, 평점이 높은 곳을 선택하세요
- Google Maps의 평점(rating)과 리뷰 수(user_ratings_total)를 참고하세요
- 단, Priority 1-4를 위반하면서까지 평점을 우선하지 마세요

**예시**:
- 두 개의 라멘집이 동일 지역에 있고, 운영시간도 동일한 경우
  → 평점 4.5 (리뷰 1000개) vs 평점 4.0 (리뷰 500개)
  → 평점 4.5 선택

---

## 제약사항

### 하루 일정 길이
- **기본값**: 하루 일정은 10-12시간 정도가 적절합니다
- **계산 방법**: 첫 visit의 arrival ~ 마지막 visit의 departure
- **예외**: 사용자 대화(chat)나 규칙(rule)에 다른 요청이 있으면 그에 따르세요
  - 예: "여유롭게" → 8-10시간
  - 예: "알차게 많이 보고 싶어" → 12-14시간

### 숙소(HOME) 출발/귀가 원칙
- **기본 원칙**: 하루 일정의 시작과 끝은 숙소여야 합니다
  - 첫 visit: 숙소 출발
  - 마지막 visit: 숙소 귀가
- **예외**: 규칙(rule)에 다른 패턴이 명시되어 있으면 그것을 따르세요
  - 예: "마지막날 공항으로 이동" → 마지막날은 공항으로 종료
  - 예: "첫날 공항에서 출발" → 첫날은 공항에서 시작

### HOME 없을 시 Gemini가 숙소 추천
- **상황**: accommodation이 "없음 (추천 필요)"로 표시된 경우
- **필수 사항**: Gemini가 적절한 숙소를 추천하고 일정에 포함해야 합니다
- **추천 기준**:
  - 사용자 대화(chat)에서 숙소 관련 선호사항 추론
  - 접근성 높은 위치 (대중교통 허브, 관광지 중심부)
  - 합리적인 가격대 (chat에서 예산 파악)
  - Google Maps로 실제 숙소 검색 및 정보 확인
- **일정 포함**: 추천한 숙소를 place_tag=HOME으로 일정 첫/마지막 visit에 포함

---

## 숙소(HOME) 처리 로직

### HOME 태그 장소 식별 및 활용

**우선순위 1**: places 필드에 place_tag=HOME인 장소가 있는 경우
- 이것이 사용자가 지정한 숙소입니다
- accommodation 필드에 해당 숙소명이 표시되어 있습니다
- 해당 숙소를 사용하고, Google Maps로 정확한 좌표와 주소를 조회하세요

**우선순위 2**: accommodation이 "없음 (추천 필요)"인 경우
- Gemini가 적절한 숙소를 추천해야 합니다 (아래 상세 기준 참고)

### 하루 일정 시작/종료를 숙소로 설정

**기본 패턴**:
```
숙소 (출발) → 관광지1 → 관광지2 → ... → 숙소 (귀가)
```

**구현 방법**:
- 각 day의 첫 번째 visit: 숙소 출발 (place_tag=HOME)
- 각 day의 마지막 visit: 숙소 귀가 (place_tag=HOME)
- 숙소 출발 시간: 첫 관광지 방문에 적절한 시간으로 설정
  - 예: 첫 관광지가 10:00 개장이면 09:30 출발
- 숙소 귀가 시간: 마지막 관광지 방문 후 이동시간 고려

**예외 처리**:
- 규칙(rule)이나 대화(chat)에 다른 패턴이 명시된 경우 우선 적용
- 예: "마지막날 공항으로 이동" → 마지막날은 숙소 귀가 대신 공항으로 종료
- 예: "첫날 공항에서 출발" → 첫날은 숙소 출발 대신 공항에서 시작

### HOME 없을 경우 숙소 추천 상세 기준

**1. 사용자 요구사항 분석** (chat에서 추론):
- **위치 선호도**: "난바 쪽", "역 근처", "중심가", "조용한 곳"
- **숙소 유형**: "호텔", "게스트하우스", "에어비앤비", "리조트"
- **가격대**: "저렴한", "가성비", "깨끗한", "럭셔리"
- **편의 시설**: "조식 포함", "역에서 가까운", "편의점 근처"

**2. 접근성 우선 고려** (최우선 기준):
- **관광지 중심부 또는 대중교통 허브 근처** 숙소 선택
- 주요 관광지까지 평균 이동시간이 짧은 위치
- 지하철역/버스 정류장 도보 5-10분 이내
- 교통수단(1-D에서 추론한 travel_mode)을 고려한 위치

**3. 합리적인 가격대**:
- chat에서 예산 파악 (예: "저렴하게", "가성비", "럭셔리")
- 여행 스타일에 맞는 가격대 선택
- 예: 배낭여행 → 게스트하우스/호스텔, 가족여행 → 중급 호텔

**4. Google Maps로 숙소 검색 및 정보 조회**:
- 숙소 유형 + 지역명으로 검색 (예: "오사카 난바 호텔")
- 평점, 리뷰, 위치, 가격대 확인
- 실제 좌표(latitude, longitude) 조회
- 정확한 주소(name_address) 조회

**5. 일정에 포함**:
- 추천한 숙소를 place_tag=HOME으로 설정
- 각 day의 첫 번째 visit과 마지막 visit에 포함
- display_name: 숙소명 (예: "오사카 난바 호텔")
- name_address: 숙소명 + 주소 (예: "오사카 난바 호텔 1-2-3 Nanba, Chuo Ward, Osaka, Japan")

**예시**:
- 요청: "오사카 여행, 난바 쪽이 좋을까?, 가성비 좋은 곳으로"
- 분석: 위치(난바), 가격대(가성비)
- 추천: "난바 지역의 평점 4.0+ 게스트하우스 또는 비즈니스 호텔"
- Google Maps 검색: "Namba Osaka guesthouse" or "Namba business hotel"
- 선택: 평점, 위치, 가격을 종합하여 최적 숙소 선택
- 일정 포함: Day 1-3 모두 첫/마지막 visit으로 해당 숙소 포함

---
"""

        return prompt

    def _infer_location_from_country(self, country: str) -> Dict[str, float]:
        """
        country 텍스트에서 중심 좌표 추론

        Args:
            country: 여행 국가/도시 텍스트 (예: "일본, 오사카", "도쿄")

        Returns:
            Dict[str, float]: latitude, longitude를 포함한 딕셔너리

        Note:
            간단한 매핑 테이블 사용. 매칭되지 않으면 기본값 (0.0, 0.0) 반환
            (Gemini가 텍스트 기반으로 추론)
        """
        location_map = {
            "오사카": {"latitude": 34.6937, "longitude": 135.5023},
            "osaka": {"latitude": 34.6937, "longitude": 135.5023},
            "도쿄": {"latitude": 35.6762, "longitude": 139.6503},
            "tokyo": {"latitude": 35.6762, "longitude": 139.6503},
            "교토": {"latitude": 35.0116, "longitude": 135.7681},
            "kyoto": {"latitude": 35.0116, "longitude": 135.7681},
            "후쿠오카": {"latitude": 33.5904, "longitude": 130.4017},
            "fukuoka": {"latitude": 33.5904, "longitude": 130.4017},
            "서울": {"latitude": 37.5665, "longitude": 126.9780},
            "seoul": {"latitude": 37.5665, "longitude": 126.9780},
            "부산": {"latitude": 35.1796, "longitude": 129.0756},
            "busan": {"latitude": 35.1796, "longitude": 129.0756},
            "제주": {"latitude": 33.4996, "longitude": 126.5312},
            "jeju": {"latitude": 33.4996, "longitude": 126.5312},
        }

        country_lower = country.lower()
        for key, coords in location_map.items():
            if key in country_lower:
                logger.info(f"Location center inferred: {country} → ({coords['latitude']}, {coords['longitude']})")
                return coords

        # 기본값 (Gemini가 텍스트 기반 추론)
        logger.warning(f"Location not found in map, using default (0.0, 0.0): {country}")
        return {"latitude": 0.0, "longitude": 0.0}

    def _validate_response(
        self,
        itinerary: ItineraryResponse2,
        request: ItineraryRequest2
    ) -> Dict:
        """
        생성된 일정이 사용자 요구사항을 준수하는지 검증

        Args:
            itinerary: 생성된 일정
            request: 원본 요청 (must_visit, days 등 포함)

        Returns:
            검증 결과 딕셔너리:
            {
                "all_valid": bool,
                "must_visit": {...},
                "days": {...},
                "operating_hours": {...}
            }
        """
        must_visit_list = request.must_visit if request.must_visit else []

        # validators.validate_all() 호출
        validation_results = validate_all(
            itinerary=itinerary,
            must_visit=must_visit_list,
            expected_days=request.days
        )

        return validation_results

    def _enhance_prompt_with_violations(
        self,
        request: ItineraryRequest2,
        validation_results: Dict
    ) -> ItineraryRequest2:
        """
        검증 실패 사항을 프롬프트에 추가하여 재시도용 요청 생성

        Args:
            request: 원본 요청
            validation_results: 검증 결과 (_validate_response 반환값)

        Returns:
            검증 피드백이 추가된 새로운 요청 객체
        """
        feedback = ["⚠️ 이전 시도에서 다음 문제가 발생했습니다. 반드시 수정해주세요:"]

        # Must-visit 위반
        if not validation_results.get("must_visit", {}).get("is_valid", True):
            missing = validation_results["must_visit"].get("missing", [])
            if missing:
                feedback.append(
                    f"🔴 누락된 must_visit 장소: {', '.join(missing)} "
                    f"→ 이 장소들을 반드시 일정에 포함시켜야 합니다!"
                )

        # Days 위반
        if not validation_results.get("days", {}).get("is_valid", True):
            actual = validation_results["days"].get("actual", 0)
            expected = validation_results["days"].get("expected", 0)
            feedback.append(
                f"🔴 일수 불일치: {actual}일 생성됨 (예상: {expected}일) "
                f"→ 정확히 {expected}개의 day를 생성해야 합니다!"
            )

        # Operating hours 위반
        if not validation_results.get("operating_hours", {}).get("is_valid", True):
            violations = validation_results["operating_hours"].get("violations", [])
            if violations:
                violation_details = []
                for v in violations[:3]:  # 최대 3개만 표시
                    violation_details.append(
                        f"Day {v['day']}: {v['place']} ({v['arrival']}-{v['departure']})"
                    )
                feedback.append(
                    f"🔴 비정상 방문시간 (새벽 2-5시): {', '.join(violation_details)} "
                    f"→ 일반적인 운영시간(오전 9시~저녁 10시)에 방문하도록 조정하세요!"
                )

        # 기존 chat에 피드백 추가하여 새 요청 생성
        # Pydantic 모델은 불변이므로 model_copy 사용
        enhanced_chat = feedback + request.chat

        enhanced_request = request.model_copy(update={"chat": enhanced_chat})

        logger.info(f"Enhanced prompt with {len(feedback)} violation feedback messages")

        return enhanced_request

    async def generate_itinerary(
        self,
        request: ItineraryRequest2,
        max_retries: int = 2
    ) -> ItineraryResponse2:
        """
        V2 일정 생성 메인 함수 (재시도 로직 포함)

        Args:
            request: 일정 생성 요청 (장소, 채팅 내용 등 포함)
            max_retries: 최대 재시도 횟수 (기본값: 2, 즉 총 3번 시도)

        Returns:
            ItineraryResponse2: 생성된 여행 일정

        Raises:
            ValueError: 최대 재시도 횟수 초과 시 검증 실패 상세 정보와 함께 발생
            Exception: Gemini API 호출 실패 또는 JSON 파싱 실패 시

        Note:
            - V1과 달리 DB 조회, 클러스터링, 이동시간 매트릭스 계산 없음
            - 모든 로직을 Gemini에게 위임
            - 검증 실패 시 위반 사항을 프롬프트에 추가하여 재시도
        """
        # 위치 기준점 추론 (재시도 시 재사용)
        center_coords = self._infer_location_from_country(request.country)

        logger.info(
            f"Generating V2 itinerary: {len(request.places)} places, "
            f"{request.days} days, {len(request.chat)} chat messages, "
            f"{request.members} members, country: {request.country}"
        )
        logger.info(f"Location center: ({center_coords['latitude']}, {center_coords['longitude']})")

        # 재시도 루프
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries + 1}: Generating itinerary...")

                # 프롬프트 생성 (재시도 시 업데이트된 request 사용)
                prompt = self._create_prompt_v2(request)
                logger.debug(f"Prompt length: {len(prompt)} characters")

                # Gemini API 호출 (Google Maps Grounding 활성화)
                logger.info("Calling Gemini API with Google Maps grounding...")
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        # Note: response_mime_type="application/json" is not supported with Google Maps tool
                        tools=[
                            types.Tool(google_maps=types.GoogleMaps())  # ✅ Google Maps Grounding Tool
                        ],
                        tool_config=types.ToolConfig(
                            retrieval_config=types.RetrievalConfig(
                                lat_lng=types.LatLng(
                                    latitude=center_coords["latitude"],
                                    longitude=center_coords["longitude"]
                                )
                            )
                        )
                    ),
                )

                # 응답 텍스트 추출
                response_text = response.text
                logger.info(f"Received response: {len(response_text)} characters")
                logger.debug(f"Response preview: {response_text[:200]}...")

                # 마크다운 코드 블록 제거 (Google Maps tool 사용 시 response_mime_type 미지원)
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json\n", "").replace("```", "").strip()
                    logger.info("Removed markdown code block from response")
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```\n", "").replace("```", "").strip()
                    logger.info("Removed markdown code block from response")

                # JSON 파싱
                try:
                    itinerary_data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {str(e)}")
                    logger.error(f"Full response text:\n{response_text}")

                    # 에러 위치 주변 텍스트 표시 (디버깅용)
                    error_pos = e.pos
                    start = max(0, error_pos - 100)
                    end = min(len(response_text), error_pos + 100)
                    logger.error(f"Error context (pos {error_pos}):\n...{response_text[start:end]}...")

                    raise Exception(f"Gemini returned invalid JSON: {str(e)}")

                # Pydantic 검증
                try:
                    itinerary_response = ItineraryResponse2(**itinerary_data)
                except Exception as e:
                    logger.error(f"Pydantic validation error: {str(e)}")
                    logger.error(f"Data: {json.dumps(itinerary_data, indent=2, ensure_ascii=False)}")
                    raise Exception(f"Invalid itinerary format: {str(e)}")

                # 사후 검증 (must_visit, days, operating_hours)
                validation_results = self._validate_response(itinerary_response, request)

                if validation_results["all_valid"]:
                    # 성공 로그
                    total_visits = sum(len(day.visits) for day in itinerary_response.itinerary)
                    logger.info(
                        f"✅ Successfully generated V2 itinerary (attempt {attempt + 1}): "
                        f"{len(itinerary_response.itinerary)} days, {total_visits} total visits"
                    )

                    # 각 일차별 요약 로그
                    for day in itinerary_response.itinerary:
                        visit_names = [v.display_name for v in day.visits]
                        logger.info(f"  Day {day.day}: {len(day.visits)} visits - {', '.join(visit_names)}")

                    return itinerary_response
                else:
                    # 검증 실패
                    logger.warning(
                        f"⚠️ Validation failed (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{json.dumps(validation_results, ensure_ascii=False)}"
                    )

                    # 재시도 가능 여부 확인
                    if attempt < max_retries:
                        logger.info(f"Retrying with enhanced prompt...")
                        # 위반 사항을 프롬프트에 추가하여 재시도
                        request = self._enhance_prompt_with_violations(request, validation_results)
                    else:
                        # 최대 재시도 횟수 초과
                        logger.error(
                            f"❌ Maximum retries ({max_retries}) exceeded. "
                            f"Final validation results: {json.dumps(validation_results, indent=2, ensure_ascii=False)}"
                        )
                        raise ValueError(
                            f"일정 생성 검증 실패 (최대 재시도 {max_retries}회 초과): "
                            f"{json.dumps(validation_results, ensure_ascii=False)}"
                        )

            except ValueError:
                # 검증 실패 예외는 그대로 전달
                raise
            except Exception as e:
                logger.error(f"V2 itinerary generation failed (attempt {attempt + 1}): {str(e)}", exc_info=True)
                # API/JSON 에러는 재시도하지 않고 즉시 실패
                raise


# 싱글톤 인스턴스
itinerary_generator_service2 = ItineraryGeneratorService2()
