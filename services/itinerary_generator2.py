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

## 프롬프트 본문은 다음 커밋에서 추가됩니다
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
