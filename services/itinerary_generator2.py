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
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        logger.info("ItineraryGeneratorService2 initialized with gemini-2.5-pro")

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

### 3. 숙소 추천 및 관리
- accommodation이 "없음 (추천 필요)"로 표시되어 있다면:
  - **사용자 대화(chat)에서 숙소 관련 선호사항을 우선 반영하세요** (예: "깨끗한 호텔", "게스트하우스", "역 근처")
  - 선호사항 중에서 위치, 접근성, 가격대, 편의성을 종합적으로 고려하여 추천하세요
  - 관광지들의 중심에 위치하거나 대중교통 접근이 좋은 숙소를 선택하세요
- accommodation이 제공되어 있다면 해당 숙소를 사용하고, Gemini가 정확한 좌표를 추론하세요

### 4. 숙소 왕복 일정 구성
- **기본 원칙**: 일반적인 상황에서 하루 일정의 시작과 끝은 숙소여야 합니다
  - 구조: **숙소 (출발) → 관광지1 → 관광지2 → ... → 숙소 (귀환)**
  - 첫 visit은 숙소 출발, 마지막 visit은 숙소 귀환으로 설정하세요
  - 숙소 출발 시 visit_time은 첫 관광지 방문에 적절한 시간으로 설정 (예: 첫 관광지가 10시 개장이면 09:30 출발)
  - 숙소 귀환 시 visit_time은 마지막 관광지 방문 후 이동시간을 고려하여 설정
- **하루 일정 길이**: 일반적으로 10-12시간 정도가 적절합니다
- **예외 처리** (우선순위가 높음):
  - 사용자 대화나 규칙(rule)에 숙소 왕복과 다른 패턴이 명시되어 있으면 그것을 따르세요
  - 예: "마지막날 공항으로 이동" → 마지막날은 "숙소 → 관광지 → 공항"으로 구성
  - 예: "첫날 공항에서 출발" → 첫날은 "공항 → 관광지 → 숙소"로 구성
  - 규칙이 숙소 왕복과 충돌하면 **규칙을 우선**하되, 가능한 경우 숙소 왕복을 유지하세요

### 5. 이동시간 계산
- 각 visit의 `travel_time`은 **현재 장소에서 다음 장소로 가는 이동시간(분)**입니다
- **마지막 visit의 travel_time은 반드시 0으로 설정하세요**
- 이동 수단 "{user_request.preferences.travel_mode}" 기준으로 이동시간을 추론하세요:
  - **DRIVE**: 자동차 (평균 40-60km/h, 도심 기준, 신호등 및 교통 상황 고려)
  - **TRANSIT**: 대중교통 (지하철/버스, 환승시간 포함, 배차간격 고려)
  - **WALK**: 도보 (평균 5km/h)
  - **BICYCLE**: 자전거 (평균 15km/h)
- 지리적 거리와 도로 상황을 고려하여 현실적인 이동시간을 계산하세요

### 6. 규칙 준수 (최우선)
- **"반드시 지켜야 할 규칙 (rule)"의 모든 항목을 일정에 반영하세요**
- **우선순위**: 규칙(rule) > 숙소 왕복 > 기본 패턴
- 예시:
  - "둘째날은 유니버설 하루 종일이지?" → Day 2는 유니버설 스튜디오만 포함 (숙소 왕복 제외 가능)
  - "11시 기상" → 첫 방문 시간을 11시 이후로 설정
  - "마지막날 공항으로" → 마지막날은 숙소 대신 공항으로 종료
- 규칙이 충돌하면 사용자의 안전과 편의를 최우선으로 고려하세요

### 7. 운영시간 고려
- 각 장소의 운영시간을 고려하여 방문 시간을 설정하세요
- 관광지는 개장 시간 내에 방문하도록 일정을 조정하세요

### 8. 체류시간 고려
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
          "display_name": "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본",
          "latitude": 위도 (float),
          "longitude": 경도 (float),
          "visit_time": "HH:MM",
          "travel_time": 다음 장소로의 이동시간 (분, int)
        }},
        {{
          "order": 2,
          "display_name": "도톤보리 Dotonbori, Chuo Ward, Osaka, 542-0071 일본",
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
- **display_name**: 장소명 + 한칸 공백 + 상세 주소 형식
  - 형식: "장소명 주소"
  - 예시: "유니버설 스튜디오 재팬 2 Chome-1-33 Sakurajima, Konohana Ward, Osaka, 554-0031 일본"
  - 예시: "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본"
  - **반드시 장소명과 주소 사이에 한칸 공백을 넣으세요**
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

        Raises:
            Exception: Gemini API 호출 실패 또는 JSON 파싱 실패 시

        Note:
            V1과 달리 DB 조회, 클러스터링, 이동시간 매트릭스 계산 없음
            모든 로직을 Gemini에게 위임
        """
        try:
            # 프롬프트 생성
            prompt = self._create_prompt_v2(places, user_request)

            logger.info(
                f"Generating V2 itinerary: {len(places)} places, "
                f"{user_request.days} days, {len(user_request.chat)} chat messages"
            )
            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Gemini API 호출
            logger.info("Calling Gemini API...")
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )

            # 응답 텍스트 추출
            response_text = response.text
            logger.info(f"Received response: {len(response_text)} characters")
            logger.debug(f"Response preview: {response_text[:200]}...")

            # JSON 파싱
            try:
                itinerary_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {str(e)}")
                logger.error(f"Response text: {response_text}")
                raise Exception(f"Gemini returned invalid JSON: {str(e)}")

            # Pydantic 검증
            try:
                itinerary_response = ItineraryResponse2(**itinerary_data)
            except Exception as e:
                logger.error(f"Pydantic validation error: {str(e)}")
                logger.error(f"Data: {json.dumps(itinerary_data, indent=2, ensure_ascii=False)}")
                raise Exception(f"Invalid itinerary format: {str(e)}")

            # 성공 로그
            total_visits = sum(len(day.visits) for day in itinerary_response.itinerary)
            logger.info(
                f"Successfully generated V2 itinerary: "
                f"{len(itinerary_response.itinerary)} days, {total_visits} total visits"
            )

            # 각 일차별 요약 로그
            for day in itinerary_response.itinerary:
                visit_names = [v.display_name for v in day.visits]
                logger.info(f"  Day {day.day}: {len(day.visits)} visits - {', '.join(visit_names)}")

            return itinerary_response

        except Exception as e:
            logger.error(f"V2 itinerary generation failed: {str(e)}", exc_info=True)
            raise


# 싱글톤 인스턴스
itinerary_generator_service2 = ItineraryGeneratorService2()
