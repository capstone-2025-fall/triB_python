from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date
from enum import Enum


class PlaceTag(str, Enum):
    """장소 유형 태그"""
    TOURIST_SPOT = "TOURIST_SPOT"  # 관광지
    HOME = "HOME"  # 숙소
    RESTAURANT = "RESTAURANT"  # 식당
    CAFE = "CAFE"  # 카페
    OTHER = "OTHER"  # 기타


class PlaceWithTag(BaseModel):
    """태그가 포함된 장소 정보"""
    place_name: str = Field(
        ...,
        description="장소 이름"
    )
    place_tag: PlaceTag = Field(
        ...,
        description="장소 유형 태그 (TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER)"
    )


class ItineraryRequest2(BaseModel):
    """V2 일정 생성 요청"""
    days: int = Field(
        ...,
        ge=1,
        description="여행 일수"
    )
    start_date: date = Field(
        ...,
        description="여행 시작 날짜 (YYYY-MM-DD)"
    )
    country: str = Field(
        ...,
        description="여행 국가 및 도시 (예: '일본, 오사카')"
    )
    members: int = Field(
        ...,
        ge=1,
        description="여행 인원 수"
    )
    places: List[PlaceWithTag] = Field(
        ...,
        description="태그가 포함된 장소 리스트 (place_tag='HOME'인 장소가 있으면 사용자 지정 숙소)"
    )
    must_visit: Optional[List[str]] = Field(
        default=None,
        description="필수 방문 장소 이름 리스트 (ID 아님)"
    )
    rule: Optional[List[str]] = Field(
        default=None,
        description="반드시 지켜야 할 규칙 (예: '첫날은 오사카성만')"
    )
    chat: List[str] = Field(
        ...,
        description="사용자 채팅 내용 배열 (의도 파악용, 숙소 및 이동수단 추론 가능)"
    )


class Visit2(BaseModel):
    """V2 방문 장소 정보"""
    order: int = Field(
        ...,
        description="방문 순서"
    )
    display_name: str = Field(
        ...,
        description="표시용 장소명 (예: 오사카 성, 유니버설 스튜디오 재팬)"
    )
    name_address: str = Field(
        ...,
        description="장소명 + 주소 (예: 오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본)"
    )
    place_tag: PlaceTag = Field(
        ...,
        description="장소 유형 태그 (TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER)"
    )
    latitude: Optional[float] = Field(
        default=None,
        description="위도 (Gemini가 생성하지 않으면 None, 백엔드에서 Places API로 채움)"
    )
    longitude: Optional[float] = Field(
        default=None,
        description="경도 (Gemini가 생성하지 않으면 None, 백엔드에서 Places API로 채움)"
    )
    arrival: str = Field(
        ...,
        description="장소 도착 시간 (HH:MM 형식)"
    )
    departure: str = Field(
        ...,
        description="장소 출발 시간 (HH:MM 형식)"
    )
    travel_time: int = Field(
        ...,
        description="다음 장소로의 이동시간 (분), 마지막 방문지는 0"
    )


class DayItinerary2(BaseModel):
    """V2 일별 일정"""
    day: int = Field(
        ...,
        description="일차"
    )
    visits: List[Visit2] = Field(
        ...,
        description="해당 일의 방문 장소 리스트"
    )


class ItineraryResponse2(BaseModel):
    """V2 일정 생성 응답"""
    itinerary: List[DayItinerary2] = Field(
        ...,
        description="전체 일정"
    )
    travel_mode: str = Field(
        ...,
        description="이동 수단 (DRIVE, TRANSIT, WALK, BICYCLE)"
    )
    budget: int = Field(
        ...,
        description="1인당 예상 예산 (원화 기준)"
    )
