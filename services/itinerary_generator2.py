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
