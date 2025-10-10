from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Preferences(BaseModel):
    must_visit: Optional[List[str]] = Field(default=None, description="필수 방문 장소 ID 리스트")
    accommodation: Optional[str] = Field(default=None, description="숙소 장소 ID")
    travel_mode: str = Field(default="TRANSIT", description="이동 수단 (TRANSIT, DRIVE, WALK, BICYCLE)")


class UserRequest(BaseModel):
    query: str = Field(..., description="사용자 여행 취향 쿼리")
    rule: Optional[List[str]] = Field(default=None, description="사용자 규칙 (예: '11시 기상')")
    days: int = Field(..., ge=1, description="여행 일수")
    preferences: Preferences


class ItineraryRequest(BaseModel):
    places: List[str] = Field(..., description="장소 ID 리스트")
    user_request: UserRequest


class Visit(BaseModel):
    order: int = Field(..., description="일별 방문 순서")
    google_place_id: str = Field(..., description="Google Place ID")
    display_name: str = Field(..., description="장소명")
    place_tag: Optional[str] = Field(default=None, description="장소 태그 (LANDMARK, HOME, RESTAURANT, CAFE, OTHER)")
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    visit_time: str = Field(..., description="방문 시간 (HH:MM 형식)")
    duration_minutes: int = Field(..., description="체류 시간 (분)")


class DayItinerary(BaseModel):
    day: int = Field(..., description="일차")
    visits: List[Visit] = Field(..., description="해당 일의 방문 장소 리스트")


class ItineraryResponse(BaseModel):
    itinerary: List[DayItinerary] = Field(..., description="전체 일정")


class Place(BaseModel):
    """DB에서 조회한 장소 정보"""
    google_place_id: str
    display_name: str
    latitude: float
    longitude: float
    primary_type: Optional[str] = None
    opening_hours_desc: Optional[str] = None
    editorial_summary: Optional[str] = None
    price_start: Optional[int] = None
    price_end: Optional[int] = None
    price_currency: Optional[str] = None
    place_tag: Optional[str] = None
