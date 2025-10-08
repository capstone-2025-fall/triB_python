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
        장소 ID 리스트로 장소 상세 정보 조회

        Args:
            place_ids: 조회할 장소 ID 리스트

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
                        id,
                        display_name,
                        latitude,
                        longitude,
                        primary_type,
                        opening_hours_desc,
                        editorial_summary,
                        price_start,
                        price_end,
                        price_currency
                    FROM places
                    WHERE id IN ({placeholders})
                """

                cursor.execute(query, place_ids)
                results = cursor.fetchall()

                if not results:
                    logger.warning(f"No places found for IDs: {place_ids}")
                    return []

                places = []
                for row in results:
                    place = Place(
                        id=row["id"],
                        display_name=row["display_name"],
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        primary_type=row.get("primary_type"),
                        opening_hours_desc=row.get("opening_hours_desc"),
                        editorial_summary=row.get("editorial_summary"),
                        price_start=row.get("price_start"),
                        price_end=row.get("price_end"),
                        price_currency=row.get("price_currency"),
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
