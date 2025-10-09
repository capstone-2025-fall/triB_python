import logging
import json
from typing import List, Dict
import numpy as np
import google.generativeai as genai
from config import settings
from models.schemas import Place, UserRequest, ItineraryResponse
from utils.json_encoder import numpy_safe_dumps

logger = logging.getLogger(__name__)

# Gemini API 초기화
genai.configure(api_key=settings.google_api_key)


class ItineraryGeneratorService:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def _format_places_for_prompt(
        self, places: List[Place], scores: Dict[str, float]
    ) -> str:
        """장소 정보를 프롬프트용으로 포맷"""
        places_data = []
        for place in places:
            # priceRange 문자열 생성 (price_start와 price_end가 있는 경우)
            price_range = None
            if place.price_start is not None and place.price_end is not None:
                currency = place.price_currency or "KRW"
                price_range = f"{currency} {place.price_start}-{place.price_end}"
            elif place.price_start is not None:
                currency = place.price_currency or "KRW"
                price_range = f"{currency} {place.price_start}+"

            place_info = {
                "id": place.id,
                "name": place.display_name,
                "lat": place.latitude,
                "lon": place.longitude,
                "primaryType": place.primary_type,
                "priceRange": price_range,
                "score": round(scores.get(place.id, 0.0), 3),
                "openingHours": place.opening_hours_desc,
            }
            logger.info(f"Place {place.display_name} opening_hours_desc: {place.opening_hours_desc}")
            places_data.append(place_info)

        return numpy_safe_dumps(places_data, indent=2)

    def _format_clusters_for_prompt(
        self, clusters: Dict[int, List[str]], medoids: Dict[int, str]
    ) -> str:
        """클러스터 정보를 프롬프트용으로 포맷"""
        cluster_data = []
        for cluster_id, place_ids in clusters.items():
            cluster_info = {
                "cluster_id": cluster_id,
                "places": place_ids,
                "medoid": medoids.get(cluster_id),
            }
            cluster_data.append(cluster_info)

        return numpy_safe_dumps(cluster_data, indent=2)

    def _format_matrix_for_prompt(self, matrix: np.ndarray, ids: List[str]) -> str:
        """매트릭스를 프롬프트용으로 포맷"""
        matrix_data = {
            "ids": ids,
            "matrix": matrix.tolist(),
            "description": f"이동시간 매트릭스 (분 단위, {len(ids)}x{len(ids)})",
        }
        return numpy_safe_dumps(matrix_data, indent=2)

    def _format_cluster_matrices_for_prompt(
        self,
        clusters: Dict[int, List[str]],
        cluster_matrices: Dict[int, np.ndarray],
    ) -> str:
        """클러스터별 매트릭스를 프롬프트용으로 포맷"""
        matrices_data = {}
        for cluster_id, place_ids in clusters.items():
            if cluster_id in cluster_matrices:
                matrices_data[str(cluster_id)] = {
                    "place_ids": place_ids,
                    "matrix": cluster_matrices[cluster_id].tolist(),
                }

        return numpy_safe_dumps(matrices_data, indent=2)

    def _create_prompt(
        self,
        places: List[Place],
        scores: Dict[str, float],
        clusters: Dict[int, List[str]],
        medoids: Dict[int, str],
        cluster_matrices: Dict[int, np.ndarray],
        medoid_matrix: np.ndarray,
        user_request: UserRequest,
    ) -> str:
        """Gemini에 전달할 프롬프트 생성"""

        places_json = self._format_places_for_prompt(places, scores)
        clusters_json = self._format_clusters_for_prompt(clusters, medoids)
        cluster_matrices_json = self._format_cluster_matrices_for_prompt(
            clusters, cluster_matrices
        )
        medoid_ids = list(medoids.values())
        medoid_matrix_json = self._format_matrix_for_prompt(medoid_matrix, medoid_ids)

        logger.info(f"Cluster matrices: {cluster_matrices_json}")
        logger.info(f"Medoid matrix: {medoid_matrix_json}")

        prompt = f"""당신은 여행 일정 최적화 전문가입니다.

주어진 장소들과 사용자 요청을 바탕으로 최적의 여행 일정을 생성해주세요.

## 우선순위

**1순위: 사용자 요청 준수 (최우선)**
- query: "{user_request.query}"
- rule: {user_request.rule or "없음"}
- must_visit: {user_request.preferences.must_visit or "없음"}
- accommodation: {user_request.preferences.accommodation or "없음"}
- 여행 일수: {user_request.days}일

**2순위: 운영시간 준수**
- 모든 장소는 반드시 운영시간 내에 방문해야 합니다
- 이동시간을 고려하여 방문 시간을 정하세요
- 클러스터 내 이동: cluster_matrices 사용
- 클러스터 간 이동: medoid_matrix 사용

**3순위: 맥락적 순서 배치**
- primaryType을 분석하여 적절한 체류시간과 방문 시간대를 결정하세요

### 카테고리별 체류시간 가이드라인:

**Entertainment and Recreation (엔터테인먼트 및 레크리에이션)**
- 초대형 시설 (240-600분 = 4-10시간): amusement_park, water_park, theme_park
- 대형 시설 (180-300분 = 3-5시간): aquarium, zoo, wildlife_park, national_park, state_park
- 중형 시설 (120-180분 = 2-3시간): botanical_garden, planetarium, observation_deck, casino, movie_theater, video_arcade
- 소형 시설 (60-180분 = 1-3시간): park, garden, plaza, playground, hiking_area, cycling_park
- 야간 엔터테인먼트 (120-240분 = 2-4시간, 18:00 이후 방문): night_club, karaoke, bar (엔터테인먼트), comedy_club
- 공연/이벤트 (120-180분 = 2-3시간): concert_hall, opera_house, performing_arts_theater, amphitheatre, philharmonic_hall

**Culture (문화)**
- 대형 문화시설 (120-180분 = 2-3시간): museum, art_gallery
- 중형 문화시설 (60-120분 = 1-2시간): cultural_landmark, historical_landmark, historical_place
- 소형 문화시설 (30-60분): monument, sculpture, cultural_center

**Food and Drink (음식 및 음료)**
- 정식 식사 (60-120분 = 1-2시간, 점심 11:00-14:00 또는 저녁 17:00-21:00): 모든 restaurant류 (american_restaurant, chinese_restaurant, japanese_restaurant, korean_restaurant, italian_restaurant, french_restaurant, indian_restaurant, thai_restaurant, mexican_restaurant, seafood_restaurant, steak_house, fine_dining_restaurant 등)
- 캐주얼 식사 (45-90분, 점심/저녁 시간대): diner, buffet_restaurant, brunch_restaurant, breakfast_restaurant
- 패스트푸드 (30-45분): fast_food_restaurant, food_court, hamburger_restaurant, sandwich_shop
- 카페/디저트 (45-90분): cafe, coffee_shop, tea_house, bakery, dessert_shop, ice_cream_shop, juice_shop, cat_cafe, dog_cafe
- 바/펍 (90-180분 = 1.5-3시간, 18:00 이후 방문): bar, wine_bar, pub, bar_and_grill

**Shopping (쇼핑)**
- 대형 쇼핑시설 (120-240분 = 2-4시간): shopping_mall, department_store
- 전통시장 (90-150분 = 1.5-2.5시간, 낮 시간대 10:00-17:00): market
- 중형 매장 (60-120분 = 1-2시간): supermarket, grocery_store, book_store, electronics_store, furniture_store
- 소형 매장 (30-60분): convenience_store, gift_shop, clothing_store, shoe_store, jewelry_store

**Sports (스포츠)**
- 시설 이용 (90-180분 = 1.5-3시간): fitness_center, gym, swimming_pool, sports_complex, ice_skating_rink
- 스포츠 관람 (120-240분 = 2-4시간): stadium, arena
- 야외 스포츠 (180-480분 = 3-8시간): golf_course, ski_resort, hiking_area, adventure_sports_center
- 가벼운 활동 (60-90분): bowling_alley, skateboard_park

**Places of Worship (종교 시설)**
- 30-60분: church, hindu_temple, mosque, synagogue (주로 오전 또는 이른 저녁)

**Health and Wellness (건강 및 웰니스)**
- 스파/웰니스 (120-180분 = 2-3시간): spa, sauna, wellness_center, public_bath
- 미용/마사지 (60-120분 = 1-2시간): massage, beauty_salon, hair_salon, nail_salon, skin_care_clinic
- 운동 (60-90분): yoga_studio, fitness_center

**Services (서비스)**
- 관광 정보 (15-45분): tourist_information_center, visitor_center
- 일반 서비스 (30-90분): 목적에 따라 다름

**Transportation (교통)**
- 환승/대기 (15-45분): airport, train_station, bus_station, subway_station 등

**Natural Features (자연)**
- 해변 (120-240분 = 2-4시간, 낮 시간대): beach

### 방문 시간대 고려사항:
- 야간 시설: night_club, bar, wine_bar, pub, karaoke, casino → 18:00 이후
- 식사 시설: restaurant류 → 점심(12:00-14:00) 또는 저녁(18:00-21:00)
- 카페: 오전~오후 (09:00-18:00)
- 시장: 낮 시간대 (10:00-17:00)
- 박물관/미술관: 오전~오후 (10:00-17:00)
- 해변/공원: 낮 시간대 (10:00-18:00)
- 종교시설: 오전 또는 이른 저녁
- 놀이공원/테마파크: 개장 시간부터

### 일정 순서 배치:
- 일정의 맥락을 고려하여 자연스러운 순서로 배치하세요
  (예: 아침 식사 → 오전 관광 → 점심 → 오후 관광 → 저녁)

**4순위: 점수 최대화 및 이동시간 최소화**
- (방문 장소들의 점수 총합 - 총 이동시간(분)) 을 최대화하세요

## 제약사항

- 하루 일정: 10-12시간
- accommodation이 지정된 경우: 매일 숙소에서 출발하고 숙소로 귀가해야 합니다
- rule 준수: 사용자가 지정한 규칙을 반드시 따르세요
  (예: "11시 기상" → 첫 방문은 11시 이후)
- must_visit 장소는 반드시 일정에 포함되어야 합니다

## 입력 데이터

### 장소 리스트
```json
{places_json}
```

### 클러스터 정보
```json
{clusters_json}
```

### 클러스터 내 이동시간 매트릭스
```json
{cluster_matrices_json}
```

### 메도이드 간 이동시간 매트릭스
```json
{medoid_matrix_json}
```

## 출력 형식

**반드시 아래 JSON 형식으로만 반환하세요. 다른 설명이나 텍스트는 포함하지 마세요.**

```json
{{
  "itinerary": [
    {{
      "day": 1,
      "visits": [
        {{
          "place_id": "place_016",
          "visit_time": "09:30",
          "duration_minutes": 90
        }}
      ]
    }}
  ]
}}
```

이제 최적의 {user_request.days}일 여행 일정을 JSON 형식으로만 생성해주세요.
"""

        return prompt

    async def generate_itinerary(
        self,
        places: List[Place],
        scores: Dict[str, float],
        clusters: Dict[int, List[str]],
        medoids: Dict[int, str],
        cluster_matrices: Dict[int, np.ndarray],
        medoid_matrix: np.ndarray,
        user_request: UserRequest,
    ) -> ItineraryResponse:
        """
        Gemini를 사용하여 여행 일정 생성

        Args:
            places: 전체 장소 리스트
            scores: 장소별 유사도 점수
            clusters: 클러스터 정보
            medoids: 클러스터별 메도이드
            cluster_matrices: 클러스터 내 이동시간 매트릭스
            medoid_matrix: 메도이드 간 이동시간 매트릭스
            user_request: 사용자 요청

        Returns:
            생성된 여행 일정
        """
        try:
            # 프롬프트 생성
            prompt = self._create_prompt(
                places,
                scores,
                clusters,
                medoids,
                cluster_matrices,
                medoid_matrix,
                user_request,
            )

            logger.info("Generating itinerary with Gemini...")
            logger.debug(f"Prompt length: {len(prompt)} characters")

            # Gemini 호출
            response = self.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    response_mime_type="application/json",
                ),
            )

            # 응답 파싱
            response_text = response.text
            logger.info(f"Received response from Gemini: {len(response_text)} characters")

            # JSON 파싱
            itinerary_data = json.loads(response_text)

            # Pydantic 모델로 변환 및 검증
            itinerary_response = ItineraryResponse(**itinerary_data)

            logger.info(
                f"Successfully generated itinerary with {len(itinerary_response.itinerary)} days"
            )

            return itinerary_response

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {str(e)}")
            logger.error(f"Response text: {response_text}")
            raise Exception("Gemini returned invalid JSON format")

        except Exception as e:
            logger.error(f"Failed to generate itinerary: {str(e)}")
            raise


# 싱글톤 인스턴스
itinerary_generator_service = ItineraryGeneratorService()
