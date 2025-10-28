import logging
import json
from typing import List
from datetime import timedelta
import google.generativeai as genai
from config import settings
from models.schemas2 import UserRequest2, ItineraryResponse2

logger = logging.getLogger(__name__)

# Gemini API 초기화
genai.configure(api_key=settings.google_api_key)


class ItineraryGeneratorService2:
    """V2 일정 생성 서비스 (Gemini 중심)"""

    def __init__(self):
        """Gemini 모델 초기화"""
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("ItineraryGeneratorService2 initialized with gemini-2.5-flash")

    def _create_prompt_v2(
        self,
        places: List[str],
        user_request: UserRequest2,
    ) -> str:
        """
        Gemini V2 프롬프트 생성

        Args:
            places: 장소 이름 리스트
            user_request: 사용자 요청

        Returns:
            완성된 프롬프트 문자열
        """
        # 날짜별 요일 계산
        weekdays_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        date_info = []
        for day_num in range(user_request.days):
            current_date = user_request.start_date + timedelta(days=day_num)
            weekday = weekdays_kr[current_date.weekday()]
            date_info.append(f"Day {day_num + 1}: {current_date.strftime('%Y-%m-%d')} ({weekday})")

        # 채팅 내용 포맷팅
        chat_text = "\n".join([f"- {msg}" for msg in user_request.chat])

        # 규칙 포맷팅
        rule_text = ""
        if user_request.rule:
            rule_text = "\n".join([f"- {r}" for r in user_request.rule])
        else:
            rule_text = "없음"

        # 필수 방문 장소 포맷팅
        must_visit_text = ""
        if user_request.preferences.must_visit:
            must_visit_text = ", ".join(user_request.preferences.must_visit)
        else:
            must_visit_text = "없음"

        # 숙소 정보 포맷팅
        accommodation_text = user_request.preferences.accommodation or "없음 (추천 필요)"

        # 장소 목록 포맷팅
        places_text = "\n".join([f"- {place}" for place in places])

        # 프롬프트 구성
        prompt = f"""## 당신의 역할
당신은 여행 일정 생성 전문가입니다.
사용자가 나눈 채팅 내용을 분석하고, 제공된 장소 목록과 함께 최적의 여행 일정을 생성합니다.

## 입력 데이터

### 여행 기간
{chr(10).join(date_info)}
총 {user_request.days}일

### 고려 중인 장소 목록 (places)
{places_text}

### 사용자 대화 내용 (chat)
{chat_text}

### 반드시 지켜야 할 규칙 (rule)
{rule_text}

### 필수 방문 장소 (must_visit)
{must_visit_text}

### 숙소 (accommodation)
{accommodation_text}

### 이동 수단 (travel_mode)
{user_request.preferences.travel_mode}

## 작업 지시사항

### 1. 채팅 분석
- 사용자들의 대화를 읽고 여행 의도, 선호도, 패턴을 파악하세요
- 대화에서 언급된 특정 요구사항이나 선호사항을 반영하세요

### 2. 장소 선택 및 추천
- 위의 "고려 중인 장소 목록 (places)"에서 적절한 장소를 선택하세요
- **중요**: places에 적합한 장소가 없거나 부족하다면 직접 장소를 찾아 추천하세요
  - 예: 채팅에 "맛있는 라멘 가게 가고 싶다"라고 했는데 places에 라멘집이 없으면
    → 해당 지역의 유명한 라멘 가게를 찾아서 일정에 포함 (장소명과 좌표 포함)
  - 예: 채팅에 "카페에서 여유롭게"라고 했는데 places에 카페가 없으면
    → 적절한 카페를 추천하세요
- **필수 방문 장소 (must_visit)는 반드시 일정에 포함하세요**
- 장소의 특성, 소요시간, 지리적 위치를 고려하여 합리적으로 배치하세요

### 3. 숙소 추천
- accommodation이 "없음 (추천 필요)"로 표시되어 있다면:
  - 여행지와 예산에 맞는 적절한 숙소를 추천하세요
  - 위치, 가격대, 편의성, 접근성을 고려하세요
  - 숙소는 매일 일정의 마지막 visit으로 포함하세요
- accommodation이 제공되어 있다면 해당 숙소를 사용하세요

### 4. 이동시간 계산
- 각 visit의 `travel_time`은 **현재 장소에서 다음 장소로 가는 이동시간(분)**입니다
- **마지막 visit의 travel_time은 반드시 0으로 설정하세요**
- 이동 수단 "{user_request.preferences.travel_mode}" 기준으로 이동시간을 추론하세요:
  - **DRIVE**: 자동차 (평균 40-60km/h, 도심 기준, 신호등 및 교통 상황 고려)
  - **TRANSIT**: 대중교통 (지하철/버스, 환승시간 포함, 배차간격 고려)
  - **WALK**: 도보 (평균 5km/h)
  - **BICYCLE**: 자전거 (평균 15km/h)
- 지리적 거리와 도로 상황을 고려하여 현실적인 이동시간을 계산하세요

### 5. 규칙 준수
- **"반드시 지켜야 할 규칙 (rule)"의 모든 항목을 일정에 반영하세요**
- 예시:
  - "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ" → Day 1에는 오사카성과 숙소만 포함
  - "둘째날은 유니버설 하루 종일이지?" → Day 2는 유니버설 스튜디오만 포함
  - "11시 기상" → 첫 방문 시간을 11시 이후로 설정
- 규칙이 충돌하면 사용자의 안전과 편의를 최우선으로 고려하세요

### 6. 운영시간 고려
- 각 장소의 일반적인 운영시간을 고려하여 방문 시간을 설정하세요
- 예: 미술관/박물관은 보통 10:00-18:00, 식당은 11:30-14:00 (점심), 17:30-22:00 (저녁)
- 관광지는 개장 시간 내에 방문하도록 일정을 조정하세요

### 7. 체류시간 고려
- 각 장소별 적절한 체류시간을 고려하세요:
  - 대형 테마파크 (유니버설 스튜디오 등): 6-10시간
  - 주요 관광지 (성, 사원 등): 1.5-3시간
  - 수족관/박물관: 2-3시간
  - 쇼핑 거리: 1-2시간
  - 식사: 1-1.5시간
  - 카페/휴식: 0.5-1시간

## 출력 형식

다음 JSON 형식으로 일정을 생성하세요:

```json
{{
  "itinerary": [
    {{
      "day": 1,
      "visits": [
        {{
          "order": 1,
          "display_name": "장소명",
          "latitude": 위도 (float),
          "longitude": 경도 (float),
          "visit_time": "HH:MM",
          "travel_time": 다음 장소로의 이동시간 (분, int)
        }},
        {{
          "order": 2,
          "display_name": "다음 장소",
          "latitude": 위도,
          "longitude": 경도,
          "visit_time": "HH:MM",
          "travel_time": 0
        }}
      ]
    }},
    {{
      "day": 2,
      "visits": [...]
    }}
  ]
}}
```

### 중요 사항:
- **order**: 각 day 내에서 1부터 시작하는 방문 순서
- **display_name**: 장소의 정확한 이름 (한국어 또는 현지어)
- **latitude, longitude**: 소수점 형식의 정확한 좌표
- **visit_time**: 24시간 형식 "HH:MM" (예: "09:00", "14:30")
- **travel_time**: 다음 장소로 가는 이동시간 (분 단위 정수), 마지막 visit는 0
- **순수 JSON만 반환하세요. 마크다운 코드 블록(```)이나 설명 텍스트 없이 JSON만 출력하세요.**
"""

        return prompt

    async def generate_itinerary(
        self,
        places: List[str],
        user_request: UserRequest2,
    ) -> ItineraryResponse2:
        """
        V2 일정 생성 메인 함수

        Args:
            places: 장소 이름 리스트 (Google Place ID 아님)
            user_request: 사용자 요청 (채팅 내용 포함)

        Returns:
            ItineraryResponse2: 생성된 여행 일정

        Note:
            V1과 달리 DB 조회, 클러스터링, 이동시간 매트릭스 계산 없음
            모든 로직을 Gemini에게 위임
        """
        # 구현 예정
        pass


# 싱글톤 인스턴스
itinerary_generator_service2 = ItineraryGeneratorService2()
