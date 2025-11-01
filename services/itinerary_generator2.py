import logging
import json
from typing import List, Dict
from datetime import timedelta
from google import genai
from google.genai import types
from config import settings
from models.schemas2 import ItineraryRequest2, ItineraryResponse2, PlaceWithTag, PlaceTag

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

## 작업 지시사항

### 1. 채팅 분석 및 이동 수단 추론
- 사용자들의 대화를 읽고 여행 의도, 선호도, 패턴을 파악하세요
- 대화에서 언급된 특정 요구사항이나 선호사항을 반영하세요
- **이동 수단 추론**: 사용자 대화에서 이동 수단을 파악하세요
  - 대화에서 명시적으로 언급된 경우:
    - "렌터카", "차 빌려서", "자동차" → **DRIVE** (자동차)
    - "지하철", "버스", "대중교통" → **TRANSIT** (대중교통)
    - "걸어서", "도보", "산책" → **WALK** (도보)
    - "자전거" → **BICYCLE** (자전거)
  - **대화에 이동 수단 언급이 없으면 기본값으로 TRANSIT (대중교통)을 사용하세요**
  - 추론한 이동 수단을 travel_time 계산에 반영하세요

### 2. Google Maps 데이터 활용 (필수)
- **중요**: Google Maps 도구를 활용하여 모든 장소의 정보를 실시간으로 조회하세요
- **조회 항목**:
  - 정확한 좌표 (latitude, longitude): 소수점 6자리까지 정확한 좌표 사용
  - 운영시간 (opening hours): 각 장소의 영업/개장 시간 확인
  - 이동시간 (travel time): 실제 도로/대중교통 기반 이동시간 계산
  - 상세 주소 (address): name_address 필드에 사용할 정확한 주소
- **적용 방법**:
  - 사용자가 입력한 장소명 → Google Maps로 검색하여 정확한 정보 조회
  - Gemini가 추천하는 새로운 장소 → Google Maps로 검색하여 실존 여부 및 정보 확인
  - 운영시간을 고려하여 방문 시간(arrival/departure) 조정
  - 실제 이동시간을 기반으로 travel_time 계산 (교통 상황 고려)

### 3. 장소 선택 및 추천
- 위의 "고려 중인 장소 목록 (places)"에서 적절한 장소를 선택하세요
- **중요**: places에 적합한 장소가 없거나 부족하다면 직접 장소를 찾아 추천하세요
  - 예: 채팅에 "맛있는 라멘 가게 가고 싶다"라고 했는데 places에 라멘집이 없으면
    → Google Maps로 해당 지역의 유명한 라멘 가게를 찾아서 일정에 포함 (장소명과 좌표 포함)
  - 예: 채팅에 "카페에서 여유롭게"라고 했는데 places에 카페가 없으면
    → Google Maps로 적절한 카페를 추천하세요
- **필수 방문 장소 (must_visit)는 반드시 일정에 포함하세요**
- 장소의 특성, 소요시간, 지리적 위치를 고려하여 합리적으로 배치하세요
- **place_tag 활용**:
  - places에 포함된 장소를 일정에 사용할 때는 해당 place_tag를 그대로 사용하세요
  - Gemini가 장소 정보를 찾지 못했을 때 place_tag를 참고하세요
  - 예: 장소명만 있고 상세 정보가 없으면 place_tag로 장소 유형을 파악
  - Gemini가 새로 추천하는 장소는 가장 적절한 place_tag를 선택하세요

### 4. 숙소 추천 및 관리
- **숙소 결정 방법**:
  - **우선순위 1**: places 필드에 place_tag가 "HOME"인 장소가 있다면, 그것이 사용자가 지정한 숙소입니다
    - 이 경우 accommodation 필드에 해당 숙소명이 표시되어 있습니다
    - 해당 숙소를 사용하고, Gemini가 정확한 좌표와 주소를 추론하세요
  - **우선순위 2**: accommodation이 "없음 (추천 필요)"로 표시되어 있다면 숙소 추천이 필요합니다:
    - **사용자 대화(chat)를 분석하여 숙소 관련 선호사항을 반영하세요**
      - 예: "난바 쪽이 좋을까?", "호텔", "게스트하우스", "역 근처", "저렴한", "깨끗한" 등
    - **비용 고려**: 대화에서 언급된 예산이나 가격 민감도를 파악하세요
    - **사용자 취향 고려**: 대화 톤과 내용에서 여행 스타일을 파악하세요 (럭셔리/가성비/배낭여행 등)
    - **접근성과 동선 효율성**을 최우선으로 고려하세요:
      - 관광지들의 중심에 위치하거나 대중교통 접근이 좋은 숙소
      - 주요 관광지까지의 평균 이동시간이 짧은 위치
      - 이동 수단(travel_mode)을 고려한 최적 위치 선택
    - 위 모든 요소를 종합하여 가장 적합한 숙소를 추천하세요

### 5. 숙소 왕복 일정 구성
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

### 6. 이동시간 계산 (Google Maps 기반)
- **중요**: Google Maps 도구를 사용하여 실제 이동시간을 조회하세요
- 각 visit의 `travel_time`은 **현재 장소에서 다음 장소로 가는 이동시간(분)**입니다
- **마지막 visit의 travel_time은 반드시 0으로 설정하세요**
- **섹션 1에서 추론한 이동 수단**을 기준으로 Google Maps에 이동시간을 조회하세요:
  - **DRIVE**: 자동차 경로 기반 이동시간
  - **TRANSIT**: 대중교통 경로 기반 이동시간 (환승 포함) - **기본값**
  - **WALK**: 도보 경로 기반 이동시간
  - **BICYCLE**: 자전거 경로 기반 이동시간
- 실시간 교통 상황, 대중교통 배차 간격을 고려한 현실적인 이동시간을 반영하세요

### 7. 규칙 준수 (최우선)
- **"반드시 지켜야 할 규칙 (rule)"의 모든 항목을 일정에 반영하세요**
- **우선순위**: 규칙(rule) > 숙소 왕복 > 기본 패턴
- 예시:
  - "둘째날은 유니버설 하루 종일이지?" → Day 2는 유니버설 스튜디오만 포함 (숙소 왕복 제외 가능)
  - "11시 기상" → 첫 방문 시간을 11시 이후로 설정
  - "마지막날 공항으로" → 마지막날은 숙소 대신 공항으로 종료
- 규칙이 충돌하면 사용자의 안전과 편의를 최우선으로 고려하세요

### 8. 운영시간 고려 (Google Maps 기반)
- **중요**: Google Maps 도구를 사용하여 각 장소의 정확한 운영시간을 조회하세요
- 관광지는 개장 시간 내에 방문하도록 일정을 조정하세요
- 휴무일(정기 휴무, 공휴일 등)을 고려하여 방문 가능한 날짜에만 포함하세요
- 예시:
  - 박물관이 월요일 휴무 → 월요일에는 일정에 포함하지 않음
  - 테마파크 운영시간 09:00-21:00 → arrival은 09:00 이후, departure는 21:00 이전

### 9. 체류시간 고려
- 각 장소별 적절한 체류시간을 고려하세요:
  - 대형 테마파크 (유니버설 스튜디오 등): 6-10시간
  - 주요 관광지 (성, 사원 등): 1.5-3시간
  - 수족관/박물관: 2-3시간
  - 쇼핑 거리: 1-2시간
  - 식사: 1-1.5시간
  - 카페/휴식: 0.5-1시간

### 10. 예산 계산
- 1인당 전체 여행 예산을 계산하세요
- 포함 항목:
  - 숙소 비용: 1박당 평균 가격 × 숙박 일수 (예: 중급 호텔 기준 1박 80,000원)
  - 교통 비용: 공항 이동 + 시내 교통 (예: 공항 왕복 30,000원, 시내 교통 1일 10,000원)
  - 식사 비용: 1일 3식 × 여행 일수 (예: 아침 8,000원, 점심 15,000원, 저녁 20,000원)
  - 입장료: 테마파크, 박물관, 관광지 입장료 합계
  - 기타 비용: 쇼핑, 간식, 기념품 등 (1일 약 30,000원)
- 원화(KRW) 기준으로 계산하세요
- 합리적인 중간 가격대를 기준으로 산정하세요
- 환율 고려: 해외 여행인 경우 현지 화폐를 원화로 환산하세요

## 출력 형식

**중요**: 다음 JSON 구조를 정확히 따르세요. budget은 itinerary 배열 밖에 있어야 합니다!

```json
{{
  "itinerary": [
    {{
      "day": 1,
      "visits": [
        {{
          "order": 1,
          "display_name": "오사카 성",
          "name_address": "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본",
          "place_tag": "TOURIST_SPOT",
          "latitude": 34.6873,
          "longitude": 135.5262,
          "arrival": "09:00",
          "departure": "11:30",
          "travel_time": 30
        }},
        {{
          "order": 2,
          "display_name": "도톤보리",
          "name_address": "도톤보리 Dotonbori, Chuo Ward, Osaka, 542-0071 일본",
          "place_tag": "TOURIST_SPOT",
          "latitude": 34.6687,
          "longitude": 135.5013,
          "arrival": "12:00",
          "departure": "14:00",
          "travel_time": 0
        }}
      ]
    }},
    {{
      "day": 2,
      "visits": [...]
    }}
  ],
  "budget": 500000
}}
```

**JSON 구조 주의사항**:
- 최상위 객체에는 두 개의 필드만 있습니다: "itinerary"와 "budget"
- "itinerary"는 배열이며, 각 요소는 day 객체입니다
- "budget"은 "itinerary" 배열이 닫힌 후 객체의 속성으로 와야 합니다 (배열 안에 들어가면 안 됩니다)

### 중요 사항:
- **order**: 각 day 내에서 1부터 시작하는 방문 순서
- **display_name**: 표시용 장소명만 (주소 제외)
  - 형식: "장소명"
  - 예시: "오사카 성", "유니버설 스튜디오 재팬", "도톤보리"
  - 간결하고 명확한 이름 사용
- **name_address**: 장소명 + 한칸 공백 + 상세 주소
  - 형식: "장소명 주소"
  - 예시: "유니버설 스튜디오 재팬 2 Chome-1-33 Sakurajima, Konohana Ward, Osaka, 554-0031 일본"
  - 예시: "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본"
  - **반드시 장소명과 주소 사이에 한칸 공백을 넣으세요**
- **place_tag**: 장소 유형 태그 (문자열, 대문자)
  - 가능한 값: "TOURIST_SPOT", "HOME", "RESTAURANT", "CAFE", "OTHER"
  - 할당 규칙:
    - **TOURIST_SPOT**: 관광지, 박물관, 테마파크, 사원, 성, 전망대 등
    - **HOME**: 호텔, 게스트하우스, 숙소, 리조트 등
    - **RESTAURANT**: 식당, 레스토랑, 음식점, 시장 (음식 중심) 등
    - **CAFE**: 카페, 디저트 가게, 베이커리 등
    - **OTHER**: 위 분류에 맞지 않는 경우 (공항, 역 등)
  - Gemini가 새로 추천하는 장소는 가장 적절한 태그를 선택하세요
- **latitude, longitude**: 소수점 형식의 정확한 좌표
- **arrival**: 해당 장소에 도착하는 시간 (24시간 형식 "HH:MM", 예: "09:00", "14:30")
  - 첫 번째 visit: 하루 일정 시작 시간 (예: 09:00)
  - 이후 visit: 이전 장소의 departure + travel_time으로 계산
- **departure**: 해당 장소에서 떠나는 시간 (24시간 형식 "HH:MM")
  - arrival + 해당 장소 체류시간으로 계산
  - 체류시간은 섹션 8의 가이드라인을 참고하세요
  - 예: 오사카 성 arrival "09:00" → 2.5시간 체류 → departure "11:30"
- **travel_time**: 다음 장소로 가는 이동시간 (분 단위 정수), 마지막 visit는 0
  - 현재 장소의 departure부터 다음 장소의 arrival까지 소요되는 시간
  - 예: 현재 장소 departure "11:30", travel_time 30분 → 다음 장소 arrival "12:00"
- **budget**: 1인당 예상 예산 (정수, 원화 기준)
  - 숙소, 교통, 식사, 입장료, 기타 비용을 모두 포함한 총 예산
  - 예시: 2박 3일 오사카 여행 = 약 500,000원 (중급 호텔, 대중교통 이용 기준)

## 필수 준수 사항
- **순수 JSON만 반환하세요. 마크다운 코드 블록(```)이나 설명 텍스트 없이 JSON만 출력하세요.**
- **JSON 구조를 정확히 지키세요**: 최상위는 객체이며, "itinerary" 배열과 "budget" 숫자 두 개의 속성만 가집니다
- **budget은 itinerary 배열 밖에 위치해야 합니다** - 배열 안에 넣지 마세요
- **유효한 JSON 형식**: 쉼표, 중괄호, 대괄호를 정확히 사용하세요
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

    async def generate_itinerary(
        self,
        request: ItineraryRequest2,
    ) -> ItineraryResponse2:
        """
        V2 일정 생성 메인 함수

        Args:
            request: 일정 생성 요청 (장소, 채팅 내용 등 포함)

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
            prompt = self._create_prompt_v2(request)

            # 위치 기준점 추론
            center_coords = self._infer_location_from_country(request.country)

            logger.info(
                f"Generating V2 itinerary: {len(request.places)} places, "
                f"{request.days} days, {len(request.chat)} chat messages, "
                f"{request.members} members, country: {request.country}"
            )
            logger.info(f"Location center: ({center_coords['latitude']}, {center_coords['longitude']})")
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
