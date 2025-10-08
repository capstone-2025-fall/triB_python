import logging
from typing import List, Dict
import httpx
import numpy as np
from config import settings
from models.schemas import Place

logger = logging.getLogger(__name__)


class RoutesMatrixService:
    def __init__(self):
        self.api_url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
        self.api_key = settings.google_maps_api_key

    async def compute_route_matrix(
        self,
        origins: List[Place],
        destinations: List[Place],
        travel_mode: str = "TRANSIT",
    ) -> np.ndarray:
        """
        Google Routes Matrix API를 사용하여 이동시간 매트릭스 계산

        Args:
            origins: 출발지 장소 리스트
            destinations: 목적지 장소 리스트
            travel_mode: 이동 수단 (TRANSIT, DRIVE, WALK, BICYCLE)

        Returns:
            이동시간 매트릭스 (분 단위) - shape: (len(origins), len(destinations))
        """
        try:
            # 요청 본문 구성
            origins_data = [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {
                                "latitude": place.latitude,
                                "longitude": place.longitude,
                            }
                        }
                    }
                }
                for place in origins
            ]

            destinations_data = [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {
                                "latitude": place.latitude,
                                "longitude": place.longitude,
                            }
                        }
                    }
                }
                for place in destinations
            ]

            request_body = {
                "origins": origins_data,
                "destinations": destinations_data,
                "travelMode": travel_mode,
                "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
            }

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,status",
            }

            # API 호출
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    json=request_body,
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Routes Matrix API failed with status {response.status_code}: {response.text}"
                    )
                    raise Exception(
                        f"Routes Matrix API failed: {response.status_code} - {response.text}"
                    )

                result = response.json()

            # 응답 파싱
            matrix = np.zeros((len(origins), len(destinations)))

            for element in result:
                origin_idx = element.get("originIndex", 0)
                dest_idx = element.get("destinationIndex", 0)

                # duration은 초 단위 문자열 (예: "300s")
                duration_str = element.get("duration", "0s")
                duration_seconds = int(duration_str.rstrip("s"))
                duration_minutes = duration_seconds / 60.0

                matrix[origin_idx, dest_idx] = duration_minutes

            logger.info(
                f"Successfully computed route matrix: {len(origins)}x{len(destinations)}"
            )

            return matrix

        except Exception as e:
            logger.error(f"Failed to compute route matrix: {str(e)}")
            raise

    async def compute_cluster_matrices(
        self,
        clusters: Dict[int, List[str]],
        places: List[Place],
        travel_mode: str = "TRANSIT",
    ) -> Dict[int, np.ndarray]:
        """
        각 클러스터 내의 이동시간 매트릭스 계산

        Args:
            clusters: {cluster_id: [place_ids]} 딕셔너리
            places: 전체 장소 리스트
            travel_mode: 이동 수단

        Returns:
            {cluster_id: distance_matrix} 딕셔너리
        """
        place_dict = {p.id: p for p in places}
        cluster_matrices = {}

        for cluster_id, place_ids in clusters.items():
            if len(place_ids) == 1:
                # 단일 장소 클러스터는 0 매트릭스
                cluster_matrices[cluster_id] = np.array([[0.0]])
                continue

            cluster_places = [place_dict[pid] for pid in place_ids]

            try:
                matrix = await self.compute_route_matrix(
                    cluster_places, cluster_places, travel_mode
                )
                cluster_matrices[cluster_id] = matrix
                logger.info(
                    f"Cluster {cluster_id}: computed {len(place_ids)}x{len(place_ids)} matrix"
                )

            except Exception as e:
                logger.error(
                    f"Failed to compute matrix for cluster {cluster_id}: {str(e)}"
                )
                # 실패 시 유클리드 거리 기반 근사치 사용
                matrix = self._compute_fallback_matrix(cluster_places)
                cluster_matrices[cluster_id] = matrix

        return cluster_matrices

    async def compute_medoid_matrix(
        self,
        medoids: Dict[int, str],
        places: List[Place],
        travel_mode: str = "TRANSIT",
    ) -> np.ndarray:
        """
        메도이드 간 이동시간 매트릭스 계산

        Args:
            medoids: {cluster_id: medoid_place_id} 딕셔너리
            places: 전체 장소 리스트
            travel_mode: 이동 수단

        Returns:
            메도이드 간 이동시간 매트릭스
        """
        place_dict = {p.id: p for p in places}
        medoid_places = [place_dict[medoid_id] for medoid_id in medoids.values()]

        if len(medoid_places) == 1:
            return np.array([[0.0]])

        try:
            matrix = await self.compute_route_matrix(
                medoid_places, medoid_places, travel_mode
            )
            logger.info(
                f"Computed medoid matrix: {len(medoid_places)}x{len(medoid_places)}"
            )
            return matrix

        except Exception as e:
            logger.error(f"Failed to compute medoid matrix: {str(e)}")
            # 실패 시 유클리드 거리 기반 근사치 사용
            return self._compute_fallback_matrix(medoid_places)

    def _compute_fallback_matrix(self, places: List[Place]) -> np.ndarray:
        """
        API 실패 시 유클리드 거리 기반 근사 매트릭스 생성

        Args:
            places: 장소 리스트

        Returns:
            거리 매트릭스 (분 단위, 평균 속도 30km/h 가정)
        """
        n = len(places)
        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue

                # 유클리드 거리 계산 (km)
                lat_diff = places[i].latitude - places[j].latitude
                lon_diff = places[i].longitude - places[j].longitude
                distance_km = np.sqrt(
                    (lat_diff * 111) ** 2 + (lon_diff * 111 * np.cos(np.radians(places[i].latitude))) ** 2
                )

                # 평균 속도 30km/h로 시간 계산 (분)
                time_minutes = (distance_km / 30) * 60
                matrix[i, j] = time_minutes

        logger.warning(f"Using fallback distance matrix for {n} places")
        return matrix


# 싱글톤 인스턴스
routes_matrix_service = RoutesMatrixService()
