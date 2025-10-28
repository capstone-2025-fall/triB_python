import logging
from typing import List, Optional
import pymysql
from pymysql.cursors import DictCursor
from config import settings
from models.schemas import Place

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self.connection_params = {
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "password": settings.db_password,
            "database": settings.db_name,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
        }

    def get_connection(self):
        """MySQL 연결 생성"""
        try:
            return pymysql.connect(**self.connection_params)
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise

    def get_places_by_ids(self, place_ids: List[str]) -> List[Place]:
        """
        Google Place ID 리스트로 장소 상세 정보 조회

        Args:
            place_ids: 조회할 Google Place ID 리스트

        Returns:
            Place 객체 리스트
        """
        if not place_ids:
            return []

        connection = None
        try:
            connection = self.get_connection()
            with connection.cursor() as cursor:
                # IN 절을 위한 플레이스홀더 생성
                placeholders = ", ".join(["%s"] * len(place_ids))
                query = f"""
                    SELECT
                        mpd.google_place_id,
                        mpd.display_name,
                        mpd.latitude,
                        mpd.longitude,
                        mpd.primary_type,
                        mpd.opening_hours_desc,
                        mpd.editorial_summary,
                        mpd.price_start,
                        mpd.price_end,
                        mpd.price_currency
                        -- mp.place_tag
                    FROM message_place_details mpd
                    -- LEFT JOIN message_places mp ON mpd.message_place_id = mp.message_place_id
                    WHERE mpd.google_place_id IN ({placeholders})
                """

                cursor.execute(query, place_ids)
                results = cursor.fetchall()

                if not results:
                    logger.warning(f"No places found for IDs: {place_ids}")
                    return []

                places = []
                for row in results:
                    # place_tag = row.get("place_tag")  # message_places 테이블이 없어서 주석처리
                    place_tag = "LANDMARK"  # 테스트용 임시 값
                    logger.debug(
                        f"Place {row['display_name']} (ID: {row['google_place_id']}): "
                        f"place_tag={place_tag}, "
                        f"mp.message_place_id={row.get('message_place_id')}, "
                        f"mpd.message_place_id={row.get('detail_message_place_id')}"
                    )

                    place = Place(
                        google_place_id=row["google_place_id"],
                        display_name=row["display_name"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        primary_type=row.get("primary_type"),
                        opening_hours_desc=row.get("opening_hours_desc"),
                        editorial_summary=row.get("editorial_summary"),
                        price_start=row.get("price_start"),
                        price_end=row.get("price_end"),
                        price_currency=row.get("price_currency"),
                        place_tag=place_tag,
                    )
                    places.append(place)

                logger.info(f"Successfully retrieved {len(places)} places from database")
                return places

        except Exception as e:
            logger.error(f"Failed to retrieve places from database: {str(e)}")
            raise
        finally:
            if connection:
                connection.close()


# 싱글톤 인스턴스
db_service = DatabaseService()
