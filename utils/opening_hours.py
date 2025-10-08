from typing import Dict, Any, Optional
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


def parse_opening_hours(opening_hours: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Google Places API의 currentOpeningHours 구조 파싱

    Args:
        opening_hours: currentOpeningHours JSON 객체

    Returns:
        파싱된 운영시간 정보
    """
    if not opening_hours:
        return {
            "open_now": False,
            "weekday_text": [],
            "periods": [],
        }

    return {
        "open_now": opening_hours.get("openNow", False),
        "weekday_text": opening_hours.get("weekdayDescriptions", []),
        "periods": opening_hours.get("periods", []),
    }


def is_open_at_time(opening_hours: Optional[Dict[str, Any]], check_datetime: datetime) -> bool:
    """
    특정 날짜/시간에 영업 중인지 확인

    Args:
        opening_hours: currentOpeningHours JSON 객체
        check_datetime: 확인할 날짜/시간

    Returns:
        영업 중이면 True, 아니면 False
    """
    if not opening_hours:
        logger.warning("No opening hours information available")
        return True  # 운영시간 정보 없으면 일단 True (보수적 접근)

    periods = opening_hours.get("periods", [])
    if not periods:
        # periods가 비어있으면 24시간 영업으로 간주
        return True

    # 요일 (0: 월요일, 6: 일요일)
    weekday = check_datetime.weekday()
    check_time = check_datetime.time()

    for period in periods:
        open_info = period.get("open", {})
        close_info = period.get("close", {})

        # Google Places API는 일요일=0, 월요일=1 형식 사용
        # Python datetime은 월요일=0, 일요일=6 형식
        # 변환: (weekday + 1) % 7
        google_weekday = (weekday + 1) % 7

        if open_info.get("day") == google_weekday:
            open_hour = open_info.get("hour", 0)
            open_minute = open_info.get("minute", 0)
            open_time_obj = time(open_hour, open_minute)

            # close가 없으면 24시간 영업
            if not close_info:
                if check_time >= open_time_obj:
                    return True
            else:
                close_hour = close_info.get("hour", 0)
                close_minute = close_info.get("minute", 0)
                close_time_obj = time(close_hour, close_minute)

                # 영업시간이 자정을 넘어가는 경우 처리
                if close_time_obj < open_time_obj:
                    # 예: 18:00 ~ 02:00
                    if check_time >= open_time_obj or check_time <= close_time_obj:
                        return True
                else:
                    # 일반적인 경우: 09:00 ~ 18:00
                    if open_time_obj <= check_time <= close_time_obj:
                        return True

    return False


def get_opening_closing_times(opening_hours: Optional[Dict[str, Any]], weekday: int) -> Optional[tuple]:
    """
    특정 요일의 영업 시작/종료 시간 반환

    Args:
        opening_hours: currentOpeningHours JSON 객체
        weekday: 요일 (0: 월요일, 6: 일요일)

    Returns:
        (open_time, close_time) 튜플, 없으면 None
    """
    if not opening_hours:
        return None

    periods = opening_hours.get("periods", [])
    if not periods:
        return None

    google_weekday = (weekday + 1) % 7

    for period in periods:
        open_info = period.get("open", {})
        if open_info.get("day") == google_weekday:
            open_hour = open_info.get("hour", 0)
            open_minute = open_info.get("minute", 0)
            open_time_obj = time(open_hour, open_minute)

            close_info = period.get("close", {})
            if close_info:
                close_hour = close_info.get("hour", 23)
                close_minute = close_info.get("minute", 59)
                close_time_obj = time(close_hour, close_minute)
            else:
                close_time_obj = time(23, 59)

            return (open_time_obj, close_time_obj)

    return None
