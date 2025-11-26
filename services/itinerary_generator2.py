import logging
import json
import re
import time
import httpx
from typing import List, Dict
from datetime import timedelta
from google import genai
from google.genai import types
from config import settings
from models.schemas2 import ItineraryRequest2, ItineraryResponse2, PlaceWithTag, PlaceTag
# PR#9: adjust_itinerary_with_actual_travel_times import 제거됨
# PR#10: Routes API 및 시간 조정 함수 import 추가
# PR#13: infer_travel_mode import 추가
from services.validators import (
    infer_travel_mode,
    fetch_actual_travel_times,
    update_travel_times_from_routes,
    adjust_schedule_with_new_travel_times
)
# PR#15: Retry helper import 추가
# PR#17: InvalidGeminiResponseError import 추가
from utils.retry_helpers import gemini_generate_retry, InvalidGeminiResponseError
# Prompt imports
from prompts.itinerary_v2_prompts import (
    create_main_prompt_v2,
    create_validation_feedback_prompt
)

logger = logging.getLogger(__name__)


class ItineraryGeneratorService2:
    """V2 일정 생성 서비스 (Gemini 중심)"""

    def __init__(self):
        """Gemini 클라이언트 초기화"""
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model_name = "gemini-2.5-flash"
        logger.info("ItineraryGeneratorService2 initialized with gemini-2.5-flash and Google Maps grounding")

    @gemini_generate_retry
    def _call_gemini_api(self, prompt: str):
        """
        Call Gemini API for content generation with exponential backoff retry.

        This method is separated to enable retry decorator application.
        PR#15: Exponential backoff retry strategy applied with detailed logging.

        This method will automatically retry on:
        - HTTP 5xx errors (server errors)
        - HTTP 429 errors (rate limiting)
        - Network timeouts
        - Connection errors

        Retry strategy:
        - Max attempts: 5
        - Wait time: 2s -> 4s -> 8s -> 16s -> 32s (max 60s)

        Args:
            prompt: The prompt to send to Gemini

        Returns:
            Response from Gemini API

        Raises:
            httpx.HTTPStatusError: For HTTP errors (after all retries exhausted)
            httpx.TimeoutException: For timeout errors (after all retries exhausted)
            Exception: For other API call failures
        """
        # PR#15: Record start time for performance tracking
        start_time = time.time()

        try:
            # PR#15: Structured logging with extra fields
            logger.info(
                "Starting Gemini API call with Google Maps grounding",
                extra={
                    "model": self.model_name,
                    "prompt_length": len(prompt),
                }
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,  # 0.7 해보고 안되면 0.3으로 변경해볼 것
                    # Note: response_mime_type="application/json" is not supported with Google Maps tool
                    tools=[
                        types.Tool(google_search={})  # ✅ Google Search Grounding Tool (includes Maps)
                    ]
                ),
            )

            # PR#15: Log success with timing information
            elapsed_time = time.time() - start_time
            logger.info(
                "Gemini API call successful",
                extra={
                    "elapsed_time": f"{elapsed_time:.2f}s",
                    "response_length": len(response.text) if hasattr(response, 'text') else 0,
                }
            )
            return response

        except httpx.HTTPStatusError as e:
            # PR#15: Log error with timing and details
            elapsed_time = time.time() - start_time
            logger.error(
                f"HTTP error during Gemini API call: {e.response.status_code}",
                extra={
                    "elapsed_time": f"{elapsed_time:.2f}s",
                    "error_type": "HTTPStatusError",
                    "status_code": e.response.status_code,
                }
            )
            raise

        except httpx.TimeoutException as e:
            # PR#15: Log timeout with timing
            elapsed_time = time.time() - start_time
            error_msg = str(e)[:200]  # Truncate to 200 chars
            logger.error(
                f"Timeout during Gemini API call",
                extra={
                    "elapsed_time": f"{elapsed_time:.2f}s",
                    "error_type": "TimeoutException",
                    "error_message": error_msg,
                }
            )
            raise

        except Exception as e:
            # PR#15: Log unexpected error with timing and details
            elapsed_time = time.time() - start_time
            error_msg = str(e)[:200]  # Truncate to 200 chars
            logger.error(
                f"Unexpected error during Gemini API call: {type(e).__name__}",
                extra={
                    "elapsed_time": f"{elapsed_time:.2f}s",
                    "error_type": type(e).__name__,
                    "error_message": error_msg,
                }
            )
            raise

    def _validate_gemini_response(self, response_text: str) -> None:
        """
        PR#17: Validate Gemini response before JSON parsing.

        Detects abnormal responses that should trigger a retry:
        - Too short responses (< 50 characters)
        - Responses with no JSON structure (no braces)
        - Abnormal repeating patterns (e.g., "n6r5o5n6r5o5...")

        Args:
            response_text: Raw response text from Gemini

        Raises:
            InvalidGeminiResponseError: If response appears invalid
        """
        # 1. Check minimum length
        if len(response_text) < 50:
            logger.error(f"Response too short: {len(response_text)} characters")
            raise InvalidGeminiResponseError(
                f"Response too short ({len(response_text)} chars): {response_text[:100]}"
            )

        # 2. Check for JSON structure (must contain at least one '{')
        if '{' not in response_text:
            logger.error("Response contains no JSON structure (no opening brace)")
            raise InvalidGeminiResponseError(
                f"No JSON structure found in response: {response_text[:200]}"
            )

        # 3. Detect abnormal repeating patterns
        # Check if response has too many repeated small substrings (like "n6r5o5")
        # Sample first 500 chars and check for high repetition
        sample = response_text[:500]

        # Count unique 6-character substrings vs total
        if len(sample) >= 100:
            substrings = [sample[i:i+6] for i in range(len(sample) - 5)]
            unique_ratio = len(set(substrings)) / len(substrings)

            # If less than 20% unique, it's likely a repeating pattern
            if unique_ratio < 0.2:
                logger.error(f"Abnormal repeating pattern detected (unique ratio: {unique_ratio:.2%})")
                logger.error(f"Sample: {sample[:200]}")
                raise InvalidGeminiResponseError(
                    f"Repeating pattern detected in response (unique ratio: {unique_ratio:.2%})"
                )

        # 4. Check for reasonable character distribution
        # Valid JSON should have a mix of alphanumeric and special characters
        alphanumeric = sum(c.isalnum() for c in sample)
        if alphanumeric > 0:
            alpha_ratio = alphanumeric / len(sample)
            # JSON typically has 40-80% alphanumeric characters
            # If it's > 95%, it might be gibberish like "n6r5o5..."
            if alpha_ratio > 0.95:
                logger.error(f"Abnormal character distribution (alphanumeric: {alpha_ratio:.2%})")
                raise InvalidGeminiResponseError(
                    f"Abnormal character distribution in response (alphanumeric: {alpha_ratio:.2%})"
                )

        logger.debug("Response validation passed")

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
        return create_main_prompt_v2(request)

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
        생성된 일정이 사용자 요구사항을 준수하는지 검증 (Grounding 기반)

        Args:
            itinerary: 생성된 일정
            request: 원본 요청 (must_visit, days, rules 등 포함)

        Returns:
            검증 결과 딕셔너리:
            {
                "all_valid": bool,
                "must_visit": {...},
                "days": {...},
                "rules": {...},
                "operating_hours": {...},
                "travel_time": {...}
            }
        """
        from services.validators import validate_all_with_grounding

        must_visit_list = request.must_visit if request.must_visit else []
        rules_list = request.rule if request.rule else []

        # validators.validate_all_with_grounding() 호출
        validation_results = validate_all_with_grounding(
            itinerary=itinerary,
            must_visit=must_visit_list,
            expected_days=request.days,
            rules=rules_list
        )

        return validation_results

    def _enhance_prompt_with_violations(
        self,
        request: ItineraryRequest2,
        validation_results: Dict
    ) -> ItineraryRequest2:
        """
        검증 실패 사항을 프롬프트에 추가하여 재시도용 요청 생성 (강화 버전)

        Args:
            request: 원본 요청
            validation_results: 검증 결과 (_validate_response 반환값)

        Returns:
            검증 피드백이 추가된 새로운 요청 객체
        """
        feedback = create_validation_feedback_prompt(request, validation_results)
        enhanced_chat = [feedback] + request.chat
        enhanced_request = request.model_copy(update={"chat": enhanced_chat})

        logger.info(f"Enhanced prompt with validation feedback")

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
                response = self._call_gemini_api(prompt)

                # 응답 텍스트 추출
                response_text = response.text
                logger.info(f"Received response: {len(response_text)} characters")
                logger.debug(f"Response preview: {response_text[:200]}...")

                # PR#17: 응답 사전 검증 (비정상 응답 감지)
                self._validate_gemini_response(response_text)

                # JSON 정리 로직 (더 강력한 처리)
                original_text = response_text

                # 1. 마크다운 코드 블록 제거
                if "```json" in response_text:
                    # ```json으로 시작하고 ```으로 끝나는 부분 추출
                    match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                    if match:
                        response_text = match.group(1).strip()
                        logger.info("Extracted JSON from markdown code block")
                elif "```" in response_text:
                    # 일반 코드 블록 제거
                    match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
                    if match:
                        response_text = match.group(1).strip()
                        logger.info("Extracted content from code block")

                # 2. 첫 번째 { 이전과 마지막 } 이후의 텍스트 제거
                first_brace = response_text.find('{')
                last_brace = response_text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    response_text = response_text[first_brace:last_brace+1]
                    logger.info("Extracted JSON object boundaries")

                # 3. 후행 쉼표 제거 (JSON 표준 위반)
                # 배열이나 객체의 마지막 요소 뒤의 쉼표 제거
                response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)

                if original_text != response_text:
                    logger.info("Cleaned response text for JSON parsing")
                    logger.debug(f"Cleaned response preview: {response_text[:200]}...")

                # JSON 파싱
                try:
                    itinerary_data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {str(e)}")
                    logger.error(f"Error details - line: {e.lineno}, col: {e.colno}, pos: {e.pos}")

                    # 에러 위치 주변 텍스트 표시 (더 넓은 범위)
                    error_pos = e.pos
                    start = max(0, error_pos - 200)
                    end = min(len(response_text), error_pos + 200)
                    logger.error(f"Error context (pos {error_pos}):\n{response_text[start:end]}")

                    # 에러가 발생한 줄 전체 표시
                    lines = response_text.split('\n')
                    if e.lineno <= len(lines):
                        logger.error(f"Error line {e.lineno}: {lines[e.lineno - 1]}")

                    # 원본 응답도 저장 (디버깅용)
                    logger.error(f"Original response length: {len(original_text)}")
                    logger.error(f"Cleaned response length: {len(response_text)}")

                    # 파일로 저장하여 분석 가능하게
                    try:
                        with open("/tmp/gemini_response_error.json", "w", encoding="utf-8") as f:
                            f.write(response_text)
                        logger.error("Full response saved to /tmp/gemini_response_error.json")
                    except:
                        pass

                    raise Exception(f"Gemini returned invalid JSON: {str(e)}")

                # Pydantic 검증
                try:
                    itinerary_response = ItineraryResponse2(**itinerary_data)
                except Exception as e:
                    logger.error(f"Pydantic validation error: {str(e)}")
                    logger.error(f"Data: {json.dumps(itinerary_data, indent=2, ensure_ascii=False)}")
                    raise Exception(f"Invalid itinerary format: {str(e)}")

                # PR#10: Routes API로 실제 이동시간 수집 및 일정 조정
                # Use travel_mode from Gemini response (fallback to inference from chat if not present)
                travel_mode = getattr(itinerary_response, 'travel_mode', None) or infer_travel_mode(request.chat)
                logger.info(f"🚗 Travel mode from Gemini: {travel_mode}")
                logger.info(f"🚗 Fetching actual travel times from Routes API (mode: {travel_mode})...")
                try:
                    actual_travel_times = fetch_actual_travel_times(itinerary_response, travel_mode=travel_mode)

                    if actual_travel_times:
                        logger.info(f"✅ Fetched {len(actual_travel_times)} travel times from Routes API")

                        # travel_time 필드 업데이트
                        itinerary_response = update_travel_times_from_routes(
                            itinerary_response,
                            actual_travel_times
                        )
                        logger.info("✅ Updated travel_time fields with actual Routes API data")

                        # arrival/departure 시간 재조정 (arrival 우선 유지)
                        itinerary_response = adjust_schedule_with_new_travel_times(itinerary_response)
                        logger.info("✅ Adjusted schedule based on new travel times (keeping arrival times fixed)")
                    else:
                        logger.warning("⚠️ No travel times returned from Routes API - proceeding with original schedule")

                except Exception as e:
                    logger.warning(f"⚠️ Routes API call failed: {str(e)} - proceeding with original schedule")

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
                    if attempt == max_retries:
                        # PR#10: 매번 Routes API로 자동 조정하므로 추가 조정 없이 반환
                        logger.warning(
                            f"⚠️ 일정 생성 검증 실패 (최대 재시도 {max_retries}회 초과)"
                        )
                        logger.warning(
                            f"검증 결과: {json.dumps(validation_results, ensure_ascii=False, indent=2)}"
                        )

                        # 각 검증 항목별 상세 로그
                        if not validation_results.get("must_visit", {}).get("is_valid", True):
                            missing = validation_results["must_visit"].get("missing", [])
                            logger.warning(f"❌ must_visit 미충족: 누락된 장소 {len(missing)}개 - {missing}")

                        if not validation_results.get("operating_hours", {}).get("is_valid", True):
                            violations = validation_results["operating_hours"].get("violations", [])
                            logger.warning(f"❌ operating_hours 위반: {len(violations)}건")

                        # if not validation_results.get("rules", {}).get("is_valid", True):  # Disabled: rule validation
                        #     violations = validation_results["rules"].get("violations", [])
                        #     logger.warning(f"❌ rules 위반: {len(violations)}건")

                        # 매번 Routes API로 조정하므로 추가 조정 불필요
                        logger.warning("⚠️ 매번 Routes API로 자동 조정하므로 추가 조정 없이 검증 실패한 일정을 반환합니다")
                        return itinerary_response

                    elif attempt < max_retries:
                        logger.info(f"Retrying with enhanced prompt...")
                        # 위반 사항을 프롬프트에 추가하여 재시도
                        request = self._enhance_prompt_with_violations(request, validation_results)

            except ValueError:
                # 검증 실패 예외는 그대로 전달
                raise
            except Exception as e:
                logger.error(
                    f"V2 itinerary generation failed (attempt {attempt + 1}) after all API retries: {str(e)}",
                    exc_info=True
                )
                # PR#15: API 에러는 이미 _call_gemini_api에서 retry 완료
                # 여기 도달했다면 모든 재시도가 실패한 것이므로 즉시 실패
                raise


# 싱글톤 인스턴스
itinerary_generator_service2 = ItineraryGeneratorService2()
