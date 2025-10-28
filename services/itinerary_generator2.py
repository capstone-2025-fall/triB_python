import logging
import json
from typing import List
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
