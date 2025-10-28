from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date


class Preferences2(BaseModel):
    """V2 사용자 선호사항"""
    must_visit: Optional[List[str]] = Field(
        default=None,
        description="필수 방문 장소 이름 리스트 (ID 아님)"
    )
    accommodation: Optional[str] = Field(
        default=None,
        description="숙소 이름 (없으면 Gemini가 추천)"
    )
    travel_mode: str = Field(
        default="DRIVE",
        description="이동 수단 (TRANSIT, DRIVE, WALK, BICYCLE)"
    )


class UserRequest2(BaseModel):
    """V2 사용자 요청"""
    chat: List[str] = Field(
        ...,
        description="사용자 채팅 내용 배열 (의도 파악용)"
    )
    rule: Optional[List[str]] = Field(
        default=None,
        description="반드시 지켜야 할 규칙 (예: '첫날은 오사카성만')"
    )
    days: int = Field(
        ...,
        ge=1,
        description="여행 일수"
    )
    start_date: date = Field(
        ...,
        description="여행 시작 날짜 (YYYY-MM-DD)"
    )
    preferences: Preferences2


class ItineraryRequest2(BaseModel):
    """V2 일정 생성 요청"""
    places: List[str] = Field(
        ...,
        description="장소 이름 리스트 (Google Place ID 아님!)"
    )
    user_request: UserRequest2
