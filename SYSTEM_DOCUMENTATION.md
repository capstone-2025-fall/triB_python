# triB 여행 일정 생성 시스템 문서

## 1. 시스템 개요

triB는 AI 기반 여행 일정 자동 생성 시스템입니다. 사용자가 방문하고자 하는 장소 목록과 여행 취향을 입력하면, 시스템이 최적의 여행 일정을 자동으로 생성합니다.

### 주요 특징
- **AI 기반 장소 추천**: Google Gemini API를 사용하여 사용자 취향과 장소의 유사도 계산
- **지능형 클러스터링**: DBSCAN 알고리즘으로 지리적으로 인접한 장소 그룹화
- **실시간 이동시간 계산**: Google Maps Routes Matrix API를 활용한 정확한 이동시간 산출
- **최적 일정 생성**: Gemini AI가 운영시간, 이동시간, 사용자 선호도를 모두 고려한 최적 일정 생성

## 2. 기술 스택

### Backend Framework
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **Python 3.13**: 최신 Python 버전

### Database
- **MySQL**: 장소 정보 저장
- **PyMySQL**: MySQL 연결 드라이버

### AI/ML
- **Google Gemini API**:
  - `embedding-001`: 텍스트 임베딩 생성
  - `gemini-2.5-flash`: 여행 일정 생성
- **scikit-learn**:
  - DBSCAN: 지리 기반 클러스터링
  - K-means: 대형 클러스터 분할

### External APIs
- **Google Maps Routes Matrix API**: 장소 간 이동시간/거리 계산

### 기타 라이브러리
- **Pydantic**: 데이터 검증 및 스키마 정의
- **NumPy**: 수치 계산 및 매트릭스 연산
- **httpx**: 비동기 HTTP 클라이언트

## 3. 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│              FastAPI Application                │
│              (main.py)                          │
└────────────────┬────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ Models  │ │Services │ │  Utils   │
│         │ │         │ │          │
│schemas  │ │database │ │json_enc..│
└─────────┘ │embedding│ │opening_..│
            │clusterin│ └──────────┘
            │routes_ma│
            │itinerary│
            └────┬────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│  MySQL  │ │ Gemini  │ │  Google  │
│Database │ │   API   │ │Maps API  │
└─────────┘ └─────────┘ └──────────┘
```

### 디렉토리 구조
```
triB_python/
├── main.py                    # FastAPI 애플리케이션 엔트리포인트
├── config.py                  # 설정 및 환경 변수 관리
├── requirements.txt           # 패키지 의존성
│
├── models/                    # 데이터 모델
│   └── schemas.py            # Pydantic 스키마 정의
│
├── services/                  # 비즈니스 로직
│   ├── database.py           # DB 연결 및 쿼리
│   ├── embedding.py          # 임베딩 생성 및 유사도 계산
│   ├── clustering.py         # 클러스터링 알고리즘
│   ├── routes_matrix.py      # 이동시간 매트릭스 계산
│   └── itinerary_generator.py # 일정 생성
│
└── utils/                     # 유틸리티 함수
    ├── json_encoder.py       # NumPy 타입 JSON 변환
    └── opening_hours.py      # 운영시간 파싱
```

## 4. 동작 과정 (상세)

### 전체 프로세스 플로우

```
[사용자 요청]
    ↓
[1. DB 장소 조회] ← DatabaseService
    ↓
[2. 유사도 계산] ← EmbeddingService + Gemini API
    ↓
[3. 클러스터링] ← ClusteringService + DBSCAN
    ↓
[4. 클러스터 내 매트릭스] ← RoutesMatrixService + Google Maps API
    ↓
[5. 메도이드 찾기] ← ClusteringService
    ↓
[6. 메도이드 매트릭스] ← RoutesMatrixService + Google Maps API
    ↓
[7. 일정 생성] ← ItineraryGeneratorService + Gemini API
    ↓
[최종 일정 반환]
```

### Step-by-Step 상세 설명

#### Step 1: DB에서 장소 정보 조회
**파일**: `services/database.py`
- 사용자가 제공한 Google Place ID 리스트로 MySQL DB 쿼리
- `message_place_details`와 `message_places` 테이블 JOIN
- 조회되는 정보:
  - 기본 정보: ID, 이름, 위도/경도
  - 상세 정보: 카테고리(primary_type), 운영시간, 설명, 가격대, 태그

#### Step 2: 임베딩 생성 및 유사도 점수 계산
**파일**: `services/embedding.py`
- **장소 임베딩 생성**:
  - 각 장소의 `editorial_summary` 또는 `display_name`을 텍스트로 사용
  - Gemini `embedding-001` 모델로 768차원 벡터 생성
  - Task type: `retrieval_document`

- **사용자 쿼리 임베딩**:
  - 사용자의 여행 취향 쿼리(예: "힐링되는 여행")를 임베딩
  - Task type: `retrieval_query`

- **코사인 유사도 계산**:
  - 쿼리 벡터와 각 장소 벡터 간 코사인 유사도 계산
  - 결과: -1~1 범위를 0~1 범위로 정규화
  - 점수가 높을수록 사용자 취향과 일치

#### Step 3: 클러스터링
**파일**: `services/clustering.py`

##### 3-1. DBSCAN 클러스터링
- **목적**: 지리적으로 인접한 장소들을 그룹화하여 이동시간 최소화
- **알고리즘**: DBSCAN (Density-Based Spatial Clustering)
- **파라미터**:
  - `eps`: 7km (반경, `.env`에서 설정 가능)
  - `min_samples`: 2 (최소 장소 수)

- **처리 과정**:
  1. 위도/경도를 킬로미터 단위로 변환
  2. DBSCAN으로 클러스터 생성
  3. 노이즈 포인트(-1 레이블)는 각각 개별 클러스터로 처리

##### 3-2. 대형 클러스터 분할
- **문제**: Google Routes Matrix API는 최대 10x10 매트릭스만 지원
- **해결**: 10개 초과 클러스터를 K-means로 재귀적 분할
  1. 클러스터 크기가 10개 초과인 경우
  2. K-means(k=2)로 2개 서브클러스터로 분할
  3. 각 서브클러스터가 10개 이하가 될 때까지 재귀 반복

#### Step 4: 클러스터 내 이동시간 매트릭스 계산
**파일**: `services/routes_matrix.py`

- **API**: Google Routes Matrix API v2
- **입력**: 각 클러스터 내 장소들의 위도/경도
- **출력**: N×N 이동시간 매트릭스 (분 단위)
  - matrix[i][j] = 장소 i에서 장소 j까지의 이동시간

- **이동 수단**: 사용자 지정 (TRANSIT/DRIVE/WALK/BICYCLE)
- **처리**:
  - 단일 장소 클러스터: [[0]] 매트릭스
  - API 실패 시: 유클리드 거리 기반 근사치 사용 (평균 속도 30km/h)

#### Step 5: 메도이드 찾기
**파일**: `services/clustering.py` → `find_cluster_medoids()`

- **메도이드(Medoid)**: 클러스터의 중심을 대표하는 실제 데이터 포인트
- **선정 기준**: 클러스터 내 모든 장소와의 평균 이동시간이 최소인 장소
- **계산 방법**:
  1. 각 장소 i에 대해 다른 모든 장소와의 이동시간 평균 계산
  2. 평균 이동시간이 가장 작은 장소를 메도이드로 선정

- **용도**: 클러스터 간 이동시간 추정의 기준점

#### Step 6: 메도이드 간 이동시간 매트릭스 계산
**파일**: `services/routes_matrix.py`

- **목적**: 서로 다른 클러스터 간 이동시간 계산
- **입력**: 각 클러스터의 메도이드 장소들
- **출력**: M×M 매트릭스 (M = 클러스터 개수)
  - medoid_matrix[i][j] = 클러스터 i의 메도이드에서 클러스터 j의 메도이드까지의 이동시간

- **활용**:
  - 클러스터 A의 장소1 → 클러스터 B의 장소2 이동시간
  - ≈ 클러스터 A 메도이드 → 클러스터 B 메도이드 이동시간

#### Step 7: Gemini로 일정 생성
**파일**: `services/itinerary_generator.py`

##### 7-1. 프롬프트 구성
시스템은 Gemini에게 다음 정보를 제공합니다:

1. **사용자 요청**:
   - 여행 취향 쿼리 (예: "힐링되는 조용한 여행")
   - 여행 일수 및 시작 날짜
   - 규칙 (예: "11시 기상")
   - 필수 방문 장소
   - 숙소 정보

2. **장소 정보** (JSON):
   - ID, 이름, 위도/경도
   - 카테고리(primaryType)
   - 가격대(priceRange)
   - 유사도 점수(score)
   - 요일별 운영시간(openingHoursByDay)
   - 장소 태그(placeTag: LANDMARK/HOME/RESTAURANT/CAFE/OTHER)

3. **클러스터 정보** (JSON):
   - 각 클러스터에 속한 장소 ID 리스트
   - 각 클러스터의 메도이드

4. **이동시간 정보** (JSON):
   - 클러스터 내 매트릭스
   - 메도이드 간 매트릭스

##### 7-2. Gemini 프롬프트 우선순위 구조

**1순위: 사용자 요청 준수** (최우선)
- 쿼리, 규칙, 필수 방문 장소, 숙소 반영

**2순위: 운영시간 준수** (매우 중요)
- 각 장소의 해당 요일 운영시간 확인
- 이동시간 고려하여 방문 종료 시간이 운영 종료 시간을 넘지 않도록

**3순위: 맥락적 순서 배치**
- 카테고리별 체류시간 가이드라인 (놀이공원 300-600분, 박물관 120-180분 등)
- 시간대별 적절한 활동 배치 (식사 시간, 야간 활동 등)

**4순위: 점수 최대화 및 이동시간 최소화**
- 최적화 목표: (방문 장소 점수 총합) - (총 이동시간)

##### 7-3. 이동시간 계산 로직 (프롬프트 내)

Gemini는 다음 규칙으로 이동시간을 계산합니다:

1. **같은 클러스터 내 이동**:
   ```
   place_A (cluster_0) → place_B (cluster_0)
   = cluster_matrices["0"][A의 인덱스][B의 인덱스]
   ```

2. **다른 클러스터 간 이동**:
   ```
   place_A (cluster_0, medoid: M0) → place_B (cluster_1, medoid: M1)
   = medoid_matrix[M0의 인덱스][M1의 인덱스]
   ```

##### 7-4. Gemini 응답 파싱
- **응답 형식**: JSON (response_mime_type: "application/json")
- **검증**: Pydantic 모델로 자동 검증
- **에러 처리**: JSON 파싱 실패 시 예외 발생

## 5. 주요 서비스 상세

### 5.1 DatabaseService (`services/database.py`)

```python
class DatabaseService:
    def get_places_by_ids(place_ids: List[str]) -> List[Place]
```

**기능**: Google Place ID로 장소 상세 정보 조회

**쿼리**:
```sql
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
    mpd.price_currency,
    mp.place_tag
FROM message_place_details mpd
LEFT JOIN message_places mp ON mpd.message_place_id = mp.message_place_id
WHERE mpd.google_place_id IN (...)
```

### 5.2 EmbeddingService (`services/embedding.py`)

```python
class EmbeddingService:
    def generate_embeddings(texts: List[str]) -> List[List[float]]
    def generate_query_embedding(query: str) -> List[float]
    def calculate_cosine_similarity(vec1, vec2) -> float
    def calculate_place_scores(places, query) -> Dict[str, float]
```

**주요 메서드**:
- `generate_embeddings()`: 장소 설명 → 768차원 벡터
- `generate_query_embedding()`: 사용자 쿼리 → 768차원 벡터
- `calculate_cosine_similarity()`: 코사인 유사도 계산 (0~1)
- `calculate_place_scores()`: 모든 장소에 대한 유사도 점수 딕셔너리 반환

**Gemini API 설정**:
- Model: `models/embedding-001`
- Task types: `retrieval_document` (장소), `retrieval_query` (쿼리)

### 5.3 ClusteringService (`services/clustering.py`)

```python
class ClusteringService:
    def cluster_places(places) -> Dict[int, List[str]]
    def find_medoid(places, distance_matrix) -> str
    def find_cluster_medoids(clusters, places, matrices) -> Dict[int, str]
    # 내부 메서드
    def _split_large_clusters(clusters, places) -> Dict[int, List[str]]
    def _split_cluster_recursive(places) -> List[List[Place]]
```

**주요 메서드**:
- `cluster_places()`: DBSCAN으로 장소 클러스터링 + 대형 클러스터 분할
- `find_medoid()`: 단일 클러스터의 메도이드 찾기
- `find_cluster_medoids()`: 모든 클러스터의 메도이드 찾기
- `_split_large_clusters()`: 10개 초과 클러스터 감지 및 분할 시작
- `_split_cluster_recursive()`: K-means로 재귀적 이진 분할

**클러스터링 파라미터**:
```python
eps_km = 7.0  # 7km 반경
min_samples = 2  # 최소 2개 장소
max_cluster_size = 10  # API 제한
```

### 5.4 RoutesMatrixService (`services/routes_matrix.py`)

```python
class RoutesMatrixService:
    async def compute_route_matrix(origins, destinations, travel_mode) -> np.ndarray
    async def compute_cluster_matrices(clusters, places, travel_mode) -> Dict[int, np.ndarray]
    async def compute_medoid_matrix(medoids, places, travel_mode) -> np.ndarray
    def _compute_fallback_matrix(places) -> np.ndarray
```

**주요 메서드**:
- `compute_route_matrix()`: Google Routes Matrix API 호출
- `compute_cluster_matrices()`: 각 클러스터의 매트릭스 계산
- `compute_medoid_matrix()`: 메도이드 간 매트릭스 계산
- `_compute_fallback_matrix()`: API 실패 시 유클리드 거리 근사

**API 설정**:
```python
URL: "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
Headers:
  - X-Goog-Api-Key: {GOOGLE_MAPS_API_KEY}
  - X-Goog-FieldMask: "originIndex,destinationIndex,duration,distanceMeters,status"
Travel modes: TRANSIT, DRIVE, WALK, BICYCLE
```

### 5.5 ItineraryGeneratorService (`services/itinerary_generator.py`)

```python
class ItineraryGeneratorService:
    async def generate_itinerary(...) -> ItineraryResponse
    # 내부 메서드
    def _create_prompt(...) -> str
    def _format_places_for_prompt(...) -> str
    def _parse_opening_hours_desc(desc: str) -> Dict[str, str]
```

**주요 메서드**:
- `generate_itinerary()`: 전체 일정 생성 오케스트레이션
- `_create_prompt()`: Gemini용 프롬프트 구성 (3000+ 줄)
- `_format_places_for_prompt()`: 장소 정보 JSON 포맷팅
- `_parse_opening_hours_desc()`: 운영시간 문자열 파싱

**Gemini API 설정**:
```python
Model: "gemini-2.5-flash"
Generation config:
  - temperature: 0.7
  - response_mime_type: "application/json"
```

## 6. API 엔드포인트

### POST `/api/itinerary/generate`

**설명**: 여행 일정 생성 엔드포인트

#### 요청 형식 (Request)

```json
{
  "places": [
    "ChIJAQAAAAAAAAAAA",
    "ChIJBBBBBBBBBBBBBB"
  ],
  "user_request": {
    "query": "힐링되는 조용한 여행",
    "rule": ["11시 기상", "저녁 8시 이후 숙소 복귀"],
    "days": 3,
    "start_date": "2025-01-15",
    "preferences": {
      "must_visit": ["ChIJAQAAAAAAAAAAA"],
      "accommodation": "ChIJXXXXXXXXXXXXXX",
      "travel_mode": "TRANSIT"
    }
  }
}
```

**필드 설명**:
- `places`: 방문 가능한 장소 ID 리스트 (Google Place ID)
- `user_request.query`: 여행 취향 (자연어)
- `user_request.rule`: 사용자 규칙 (선택)
- `user_request.days`: 여행 일수
- `user_request.start_date`: 시작 날짜 (YYYY-MM-DD)
- `preferences.must_visit`: 필수 방문 장소 (선택)
- `preferences.accommodation`: 숙소 ID (선택, 지정 시 매일 출발/귀가)
- `preferences.travel_mode`: 이동 수단 (기본값: TRANSIT)

#### 응답 형식 (Response)

```json
{
  "itinerary": [
    {
      "day": 1,
      "visits": [
        {
          "order": 1,
          "google_place_id": "ChIJAQAAAAAAAAAAA",
          "display_name": "스타벅스 강남점",
          "place_tag": "CAFE",
          "latitude": 37.498095,
          "longitude": 127.027610,
          "visit_time": "09:30",
          "duration_minutes": 60
        },
        {
          "order": 2,
          "google_place_id": "ChIJBBBBBBBBBBBBBB",
          "display_name": "남산타워",
          "place_tag": "LANDMARK",
          "latitude": 37.551169,
          "longitude": 126.988227,
          "visit_time": "11:00",
          "duration_minutes": 120
        }
      ]
    },
    {
      "day": 2,
      "visits": [...]
    }
  ]
}
```

**필드 설명**:
- `itinerary`: 일정 리스트
- `day`: 일차 (1부터 시작)
- `visits`: 해당 일의 방문 장소 리스트
- `order`: 일별 방문 순서
- `visit_time`: 방문 시간 (HH:MM 형식, 24시간)
- `duration_minutes`: 체류 시간 (분)
- `place_tag`: 장소 태그
  - `LANDMARK`: 관광 명소
  - `HOME`: 숙소
  - `RESTAURANT`: 식당
  - `CAFE`: 카페
  - `OTHER`: 기타
  - `null`: 태그 없음

### GET `/`

**설명**: Health check 엔드포인트

**응답**:
```json
{
  "status": "ok",
  "message": "triB Travel Itinerary API is running"
}
```

## 7. 데이터 모델

### 7.1 요청 모델

#### ItineraryRequest
```python
class ItineraryRequest(BaseModel):
    places: List[str]  # Google Place ID 리스트
    user_request: UserRequest
```

#### UserRequest
```python
class UserRequest(BaseModel):
    query: str  # 여행 취향 쿼리
    rule: Optional[List[str]] = None  # 사용자 규칙
    days: int  # 여행 일수 (≥1)
    start_date: date  # 시작 날짜 (YYYY-MM-DD)
    preferences: Preferences
```

#### Preferences
```python
class Preferences(BaseModel):
    must_visit: Optional[List[str]] = None  # 필수 방문 장소 ID
    accommodation: Optional[str] = None  # 숙소 ID
    travel_mode: str = "TRANSIT"  # TRANSIT/DRIVE/WALK/BICYCLE
```

### 7.2 응답 모델

#### ItineraryResponse
```python
class ItineraryResponse(BaseModel):
    itinerary: List[DayItinerary]
```

#### DayItinerary
```python
class DayItinerary(BaseModel):
    day: int  # 일차
    visits: List[Visit]  # 방문 장소 리스트
```

#### Visit
```python
class Visit(BaseModel):
    order: int  # 방문 순서
    google_place_id: str  # Google Place ID
    display_name: str  # 장소명
    place_tag: Optional[str]  # LANDMARK/HOME/RESTAURANT/CAFE/OTHER
    latitude: float  # 위도
    longitude: float  # 경도
    visit_time: str  # 방문 시간 (HH:MM)
    duration_minutes: int  # 체류 시간 (분)
```

### 7.3 내부 모델

#### Place (DB 조회 결과)
```python
class Place(BaseModel):
    google_place_id: str
    display_name: str
    latitude: float
    longitude: float
    primary_type: Optional[str]  # 카테고리 (예: "restaurant", "museum")
    opening_hours_desc: Optional[str]  # 운영시간 설명
    editorial_summary: Optional[str]  # 장소 설명
    price_start: Optional[int]  # 최소 가격
    price_end: Optional[int]  # 최대 가격
    price_currency: Optional[str]  # 통화 (예: "KRW")
    place_tag: Optional[str]  # 장소 태그
```

## 8. 설정 및 환경 변수

### 환경 변수 (.env)

```bash
# Google API
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_MAPS_API_KEY=your_maps_api_key

# Database
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password

# Clustering
DBSCAN_EPS_KM=7.0  # DBSCAN 반경 (km)
DBSCAN_MIN_SAMPLES=2  # 최소 샘플 수
```

### 설정 파일 (config.py)

- 환경 변수 로드 (`python-dotenv`)
- Pydantic Settings로 타입 안전한 설정 관리
- 환경 구분: `local` (기본값) / `prod`

## 9. 에러 처리

### HTTP 예외
- **404 Not Found**: 장소를 찾을 수 없음
- **500 Internal Server Error**: 서버 내부 오류
  - 임베딩 생성 실패
  - 클러스터링 실패
  - Routes Matrix API 실패
  - Gemini 응답 파싱 실패

### 로깅
- 모든 서비스는 Python `logging` 모듈 사용
- 로그 레벨: INFO
- 포맷: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### Fallback 메커니즘
- **Routes Matrix API 실패 시**: 유클리드 거리 기반 근사 매트릭스 사용
- **임베딩 실패 시**: 빈 텍스트는 0 벡터로 처리

## 10. 성능 최적화

### 비동기 처리
- FastAPI의 비동기 지원 활용
- Routes Matrix API 호출 비동기 처리 (`httpx.AsyncClient`)
- Gemini API 호출 비동기 처리

### 클러스터링 최적화
- 10개 초과 클러스터 자동 분할로 API 호출 최소화
- 메도이드 기반 클러스터 간 이동시간 추정으로 API 호출 절감
  - 전체 장소 간 매트릭스: O(N²) → 클러스터 내 + 메도이드 간: O(N + M²)
  - 예: 50개 장소 → 2,500번 API 호출 대신 ~100번 API 호출

### NumPy 활용
- 매트릭스 연산에 NumPy 사용으로 계산 속도 향상
- 커스텀 JSON 인코더로 NumPy 타입 자동 변환

## 11. 확장 가능성

### 향후 개선 사항
1. **캐싱**:
   - 장소 임베딩 캐싱 (동일 장소 재사용)
   - Routes Matrix 결과 캐싱

2. **배치 처리**:
   - 여러 사용자 요청 동시 처리

3. **다국어 지원**:
   - 프롬프트 및 응답 다국어화

4. **추가 제약사항**:
   - 예산 제약
   - 접근성 고려 (휠체어, 어린이 동반 등)

5. **실시간 정보**:
   - 실시간 혼잡도 반영
   - 날씨 정보 고려

## 12. 실행 방법

### 설치
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 및 DB 정보 입력
```

### 실행
```bash
# 개발 서버 실행 (자동 리로드)
python main.py

# 또는
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API 테스트
```bash
curl -X POST http://localhost:8000/api/itinerary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "places": ["ChIJAQAAAAAAAAAAA", "ChIJBBBBBBBBBBBBBB"],
    "user_request": {
      "query": "힐링되는 여행",
      "days": 2,
      "start_date": "2025-01-15",
      "preferences": {
        "travel_mode": "TRANSIT"
      }
    }
  }'
```

## 13. 기술적 의사결정

### 왜 DBSCAN을 선택했나?
- **밀도 기반 클러스터링**: 지리적으로 밀집된 장소 자동 감지
- **클러스터 개수 자동 결정**: K-means와 달리 사전 설정 불필요
- **노이즈 처리**: 고립된 장소를 별도 클러스터로 분리

### 왜 메도이드를 사용하나?
- **실제 장소 기반**: 센트로이드(평균 좌표)는 실제 장소가 아닐 수 있음
- **대표성**: 클러스터 중심에 가장 가까운 실제 장소
- **API 효율성**: N²개 대신 M²개 API 호출 (M = 클러스터 수 << N)

### 왜 Gemini를 사용하나?
- **멀티태스킹**: 임베딩 생성 + 복잡한 일정 생성을 하나의 API로
- **JSON 응답 보장**: `response_mime_type` 설정으로 파싱 안정성
- **한국어 지원**: 한국 여행지 및 한국어 쿼리 처리 우수
- **컨텍스트 이해**: 운영시간, 이동시간, 맥락 등 복잡한 제약사항 이해

---

**문서 버전**: 1.0
**최종 수정일**: 2025-10-14
**작성자**: triB Development Team
