import logging
from typing import List, Dict, Tuple
import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from config import settings
from models.schemas import Place

logger = logging.getLogger(__name__)


class ClusteringService:
    def __init__(self):
        self.eps_km = settings.dbscan_eps_km
        self.min_samples = settings.dbscan_min_samples
        self.max_cluster_size = 10  # Routes Matrix API 제한

    def lat_lon_to_km(self, lat: float, lon: float, center_lat: float, center_lon: float) -> Tuple[float, float]:
        """
        위도/경도를 중심점 기준 킬로미터 단위로 변환

        Args:
            lat, lon: 변환할 좌표
            center_lat, center_lon: 중심점 좌표

        Returns:
            (x_km, y_km) 튜플
        """
        # 간단한 근사 계산 (작은 영역에서는 충분히 정확)
        lat_km_per_degree = 111.0  # 위도 1도 = 약 111km
        lon_km_per_degree = 111.0 * np.cos(np.radians(center_lat))  # 경도는 위도에 따라 달라짐

        x_km = (lon - center_lon) * lon_km_per_degree
        y_km = (lat - center_lat) * lat_km_per_degree

        return x_km, y_km

    def cluster_places(self, places: List[Place]) -> Dict[int, List[str]]:
        """
        DBSCAN 알고리즘으로 장소 클러스터링

        Args:
            places: 장소 리스트

        Returns:
            {cluster_id: [place_ids]} 딕셔너리
            cluster_id가 -1인 경우는 노이즈 (개별 클러스터로 처리)
        """
        if not places:
            return {}

        try:
            # 위도/경도 추출
            coords = np.array([[p.latitude, p.longitude] for p in places])
            place_ids = [p.google_place_id for p in places]

            # 중심점 계산
            center_lat = np.mean(coords[:, 0])
            center_lon = np.mean(coords[:, 1])

            # km 단위로 변환
            coords_km = np.array([
                self.lat_lon_to_km(lat, lon, center_lat, center_lon)
                for lat, lon in coords
            ])

            # DBSCAN 클러스터링
            dbscan = DBSCAN(eps=self.eps_km, min_samples=self.min_samples)
            labels = dbscan.fit_predict(coords_km)

            # 클러스터별로 장소 ID 그룹화
            clusters = {}
            noise_counter = -1  # 노이즈 포인트들은 개별 클러스터로 처리

            for place_id, label in zip(place_ids, labels):
                if label == -1:
                    # 노이즈는 각각 별도의 클러스터로
                    clusters[noise_counter] = [place_id]
                    noise_counter -= 1
                else:
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append(place_id)

            logger.info(f"Clustered {len(places)} places into {len(clusters)} clusters")
            for cluster_id, place_ids_in_cluster in clusters.items():
                logger.info(f"Cluster {cluster_id}: {len(place_ids_in_cluster)} places")

            # 10개 초과 클러스터를 서브클러스터로 분할
            clusters = self._split_large_clusters(clusters, places)

            return clusters

        except Exception as e:
            logger.error(f"Failed to cluster places: {str(e)}")
            raise

    def _split_large_clusters(
        self, clusters: Dict[int, List[str]], places: List[Place]
    ) -> Dict[int, List[str]]:
        """
        10개 초과 클러스터를 서브클러스터로 분할

        Args:
            clusters: 원본 클러스터
            places: 전체 장소 리스트

        Returns:
            분할된 클러스터 (10개 이하 보장)
        """
        place_dict = {p.google_place_id: p for p in places}
        new_clusters = {}
        new_cluster_id = 0

        for cluster_id, place_ids in clusters.items():
            if len(place_ids) <= self.max_cluster_size:
                # 10개 이하는 그대로 유지
                new_clusters[new_cluster_id] = place_ids
                new_cluster_id += 1
            else:
                # 10개 초과는 재귀적으로 분할
                logger.info(
                    f"Splitting cluster {cluster_id} with {len(place_ids)} places"
                )
                cluster_places = [place_dict[pid] for pid in place_ids]
                sub_clusters = self._split_cluster_recursive(cluster_places)

                for sub_cluster_places in sub_clusters:
                    sub_cluster_ids = [p.google_place_id for p in sub_cluster_places]
                    new_clusters[new_cluster_id] = sub_cluster_ids
                    logger.info(
                        f"  Created sub-cluster {new_cluster_id} with {len(sub_cluster_ids)} places"
                    )
                    new_cluster_id += 1

        return new_clusters

    def _split_cluster_recursive(self, places: List[Place]) -> List[List[Place]]:
        """
        클러스터를 재귀적으로 분할하여 각 서브클러스터가 ≤10개가 되도록 함

        Args:
            places: 분할할 장소 리스트

        Returns:
            서브클러스터 리스트
        """
        if len(places) <= self.max_cluster_size:
            return [places]

        # K-means로 2개로 분할
        coords = np.array([[p.latitude, p.longitude] for p in places])

        # 중심점 계산
        center_lat = np.mean(coords[:, 0])
        center_lon = np.mean(coords[:, 1])

        # km 단위로 변환
        coords_km = np.array(
            [self.lat_lon_to_km(lat, lon, center_lat, center_lon) for lat, lon in coords]
        )

        # K-means로 2개 클러스터로 분할
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        labels = kmeans.fit_predict(coords_km)

        # 두 그룹으로 분리
        group_0 = [places[i] for i in range(len(places)) if labels[i] == 0]
        group_1 = [places[i] for i in range(len(places)) if labels[i] == 1]

        # 각 그룹을 재귀적으로 분할
        result = []
        result.extend(self._split_cluster_recursive(group_0))
        result.extend(self._split_cluster_recursive(group_1))

        return result

    def find_medoid(self, places: List[Place], distance_matrix: np.ndarray) -> str:
        """
        클러스터의 메도이드(medoid) 찾기
        메도이드: 클러스터 내 다른 모든 점과의 평균 거리가 최소인 실제 데이터 포인트

        Args:
            places: 클러스터 내 장소 리스트
            distance_matrix: 장소 간 거리 매트릭스 (분 단위)

        Returns:
            메도이드 장소의 ID
        """
        if len(places) == 1:
            return places[0].google_place_id

        try:
            # 각 장소에 대해 다른 모든 장소와의 평균 거리 계산
            avg_distances = []
            for i in range(len(places)):
                # i번째 장소의 다른 모든 장소와의 거리 합
                distances = distance_matrix[i, :]
                avg_distance = np.mean(distances)
                avg_distances.append(avg_distance)

            # 평균 거리가 최소인 장소의 인덱스
            medoid_idx = np.argmin(avg_distances)
            medoid_place_id = places[medoid_idx].google_place_id

            logger.info(f"Found medoid: {medoid_place_id} with avg distance {avg_distances[medoid_idx]:.2f} min")

            return medoid_place_id

        except Exception as e:
            logger.error(f"Failed to find medoid: {str(e)}")
            # 에러 발생 시 첫 번째 장소 반환
            return places[0].google_place_id

    def find_cluster_medoids(
        self,
        clusters: Dict[int, List[str]],
        places: List[Place],
        cluster_matrices: Dict[int, np.ndarray],
    ) -> Dict[int, str]:
        """
        각 클러스터의 메도이드 찾기

        Args:
            clusters: {cluster_id: [place_ids]} 딕셔너리
            places: 전체 장소 리스트
            cluster_matrices: {cluster_id: distance_matrix} 딕셔너리

        Returns:
            {cluster_id: medoid_place_id} 딕셔너리
        """
        place_dict = {p.google_place_id: p for p in places}
        medoids = {}

        for cluster_id, place_ids in clusters.items():
            cluster_places = [place_dict[pid] for pid in place_ids]

            if cluster_id in cluster_matrices:
                distance_matrix = cluster_matrices[cluster_id]
                medoid_id = self.find_medoid(cluster_places, distance_matrix)
            else:
                # 매트릭스가 없으면 첫 번째 장소를 메도이드로
                medoid_id = place_ids[0]

            medoids[cluster_id] = medoid_id
            logger.info(f"Cluster {cluster_id} medoid: {medoid_id}")

        return medoids


# 싱글톤 인스턴스
clustering_service = ClusteringService()
