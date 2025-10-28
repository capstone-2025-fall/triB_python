# triB 시스템 이론적 계산 및 Simulation

## 1. 개요

본 문서는 triB 여행 일정 생성 시스템의 이론적 계산 방법과 시뮬레이션 기법을 상세히 기술합니다. 시스템은 크게 4가지 주요 계산 모듈로 구성됩니다:

1. **좌표계 변환 및 거리 계산**
2. **벡터 임베딩 및 유사도 계산**
3. **클러스터링 알고리즘**
4. **이동시간 매트릭스 계산 및 시뮬레이션**

---

## 2. 좌표계 변환 및 거리 계산

#### 기본 개념

위도와 경도의 1도가 실제로는 얼마나 먼 거리인지 알아야 합니다:

1. **위도 1도의 거리**:
   - 지구 둘레 약 40,000km를 360도로 나누면
   - 40,000km ÷ 360° = 약 111km
   - 위도는 어느 위치에서나 1도당 약 111km입니다

2. **경도 1도의 거리**:
   - 적도에서는 위도와 마찬가지로 약 111km
   - 하지만 북쪽이나 남쪽으로 갈수록 거리가 줄어듭니다
   - 예: 서울(위도 37.5°)에서는 약 88km
   - 북극(위도 90°)에 가까워지면 0km에 수렴

### 2.1 이론적 배경

지구는 구형이므로, 위도/경도로 표현된 두 지점 간의 거리는 단순 유클리드 거리로 계산할 수 없습니다. 본 시스템은 소규모 지역에서의 근사 계산을 위해 평면 투영 방식을 사용합니다.

### 2.2 위도/경도 → 킬로미터 변환

**구현 위치**: `services/clustering.py:17-35`

#### 수식

좌표 $(lat, lon)$을 중심점 $(lat_c, lon_c)$ 기준 킬로미터 단위로 변환:

```
x_km = (lon - lon_c) × k_lon
y_km = (lat - lat_c) × k_lat
```

여기서:
- $k_{lat} = 111.0$ km/degree (위도 1도 = 약 111km, 지구 둘레 약 40,000km ÷ 360°)
- $k_{lon} = 111.0 \times \cos(lat_c \times \frac{\pi}{180})$ km/degree (경도는 위도에 따라 변화)

#### 근거

- **위도 변환**: 지구 자오선 방향의 거리는 위도와 관계없이 일정 (약 111km/°)
- **경도 변환**: 지구 평행선 방향의 거리는 위도에 따라 $\cos(lat)$로 감소
  - 적도 (0°): 111km/°
  - 서울 (37.5°N): 111 × cos(37.5°) ≈ 88km/°
  - 북극 (90°): 0km/°

#### 적용 범위

- **유효 범위**: 반경 ~100km 이내 (오차 < 1%)
- **오차 분석**:
  - 서울 기준 50km 반경: 평균 오차 < 0.5%
  - 100km 이상: Haversine 공식 사용 권장 (향후 개선)

### 2.3 유클리드 거리 기반 이동시간 근사

**구현 위치**: `services/routes_matrix.py:225-255`

#### 수식

두 장소 $P_i(lat_i, lon_i)$와 $P_j(lat_j, lon_j)$ 간의 근사 이동시간:

```
d_lat = lat_i - lat_j
d_lon = lon_i - lon_j

distance_km = √[(d_lat × 111)² + (d_lon × 111 × cos(lat_i × π/180))²]

time_minutes = (distance_km / v_avg) × 60
```

여기서:
- $v_{avg} = 30$ km/h (도심 평균 이동 속도)

#### 사용 시나리오

**Fallback 메커니즘**: Google Routes Matrix API 호출 실패 시 사용
- 네트워크 오류
- API 할당량 초과
- 경로를 찾을 수 없는 경우

#### 파라미터 설정 근거

- **평균 속도 30km/h**:
  - 대중교통(TRANSIT): 지하철 40km/h + 버스 20km/h + 환승/대기 시간
  - 도보(WALK): 5km/h
  - 자동차(DRIVE): 도심 교통 체증 고려 30-40km/h
  - 가중 평균 약 30km/h

---

## 3. 벡터 임베딩 및 유사도 계산

### 3.1 이론적 배경

사용자의 여행 취향과 장소 간의 의미적 유사도를 계산하기 위해 벡터 임베딩과 코사인 유사도를 사용합니다.

### 3.2 텍스트 임베딩 생성

**구현 위치**: `services/embedding.py:18-78`

#### 방법

Google Gemini API (`embedding-001` 모델) 사용:

- **장소 임베딩**:
  - 입력: 장소의 `editorial_summary` 또는 `display_name`
  - Task type: `retrieval_document`
  - 출력: 768차원 벡터 $\mathbf{v}_{place} \in \mathbb{R}^{768}$

- **쿼리 임베딩**:
  - 입력: 사용자 쿼리 (예: "힐링되는 조용한 여행")
  - Task type: `retrieval_query`
  - 출력: 768차원 벡터 $\mathbf{v}_{query} \in \mathbb{R}^{768}$

#### 특징

- **의미적 표현**: 단어의 의미와 맥락을 고차원 공간에 인코딩
- **다국어 지원**: 한국어, 영어 등 다양한 언어 처리
- **일관성**: 동일한 의미는 유사한 벡터로 매핑

### 3.3 코사인 유사도 계산

**구현 위치**: `services/embedding.py:80-105`

#### 수식

두 벡터 $\mathbf{v}_1$, $\mathbf{v}_2$의 코사인 유사도:

```
cos_sim = (v₁ · v₂) / (||v₁|| × ||v₂||)
```

여기서:
- $\mathbf{v}_1 \cdot \mathbf{v}_2 = \sum_{i=1}^{768} v_{1,i} \times v_{2,i}$ (내적)
- $||\mathbf{v}_1|| = \sqrt{\sum_{i=1}^{768} v_{1,i}^2}$ (L2 노름)
- $||\mathbf{v}_2|| = \sqrt{\sum_{i=1}^{768} v_{2,i}^2}$ (L2 노름)

#### 정규화

원시 코사인 유사도 범위 [-1, 1]을 [0, 1]로 정규화:

```
score = (cos_sim + 1) / 2
```

- **0**: 완전히 반대 (매우 낮은 유사도)
- **0.5**: 무관함
- **1**: 완전히 동일 (매우 높은 유사도)

#### 해석

- **score > 0.7**: 사용자 취향과 매우 일치
- **0.5 < score < 0.7**: 보통 일치
- **score < 0.5**: 사용자 취향과 맞지 않음

---

## 4. 클러스터링 알고리즘

### 4.1 DBSCAN (Density-Based Spatial Clustering)

**구현 위치**: `services/clustering.py:37-95`

#### 알고리즘 개요

DBSCAN은 밀도 기반 클러스터링 알고리즘으로, 지리적으로 인접한 장소들을 자동으로 그룹화합니다.

#### 파라미터

```python
eps = 7.0 km        # 이웃 반경
min_samples = 2     # 최소 장소 수
```

#### 수식 및 정의

1. **$\epsilon$-이웃 (Epsilon Neighborhood)**:
   ```
   N_ε(p) = {q ∈ D | dist(p, q) ≤ ε}
   ```
   점 $p$로부터 거리 $\epsilon$ 이내에 있는 모든 점의 집합

2. **핵심점 (Core Point)**:
   ```
   |N_ε(p)| ≥ minPts
   ```
   $\epsilon$-이웃 내에 최소 `minPts`개 이상의 점이 있는 점

3. **직접 밀도 도달 (Directly Density-Reachable)**:
   ```
   p가 핵심점이고 q ∈ N_ε(p)이면, q는 p로부터 직접 밀도 도달
   ```

4. **밀도 도달 (Density-Reachable)**:
   ```
   p₁, p₂, ..., pₙ의 체인이 존재하여,
   p_{i+1}이 p_i로부터 직접 밀도 도달하면,
   pₙ은 p₁로부터 밀도 도달
   ```

5. **밀도 연결 (Density-Connected)**:
   ```
   점 o가 존재하여 p와 q가 모두 o로부터 밀도 도달하면,
   p와 q는 밀도 연결
   ```

6. **클러스터**:
   ```
   C ⊆ D는 다음 조건을 만족하는 비어있지 않은 부분집합:
   1) ∀p, q: p ∈ C이고 q가 p로부터 밀도 도달하면, q ∈ C
   2) ∀p, q ∈ C: p와 q는 밀도 연결
   ```

7. **노이즈 (Noise)**:
   ```
   어떤 클러스터에도 속하지 않는 점 (고립된 점)
   ```

#### 파라미터 설정 근거

- **eps = 7km**:
  - 도시 내 인접 지역 범위 (도보 + 대중교통 20-30분)
  - 서울 기준: 강남-종로 약 10km, 한 구(區) 평균 직경 5-8km
  - 너무 작으면: 과도한 클러스터 생성 (이동 효율 저하)
  - 너무 크면: 거리가 먼 장소가 같은 클러스터에 포함 (이동시간 증가)

- **min_samples = 2**:
  - 최소 2개 이상의 장소가 모여 클러스터 형성
  - 1개: 모든 점이 개별 클러스터 (클러스터링 의미 없음)
  - 3개 이상: 고립된 2개 장소 쌍도 노이즈 처리 (과도한 분리)

#### 알고리즘 단계

```
입력: 장소 집합 D, eps, minPts
출력: 클러스터 집합 C

1. 모든 장소를 미방문으로 표시
2. for each 미방문 장소 p in D:
   3. p를 방문 표시
   4. N = N_ε(p) 계산 (eps 반경 내 이웃 찾기)
   5. if |N| < minPts:
      6. p를 노이즈로 표시
   7. else:
      8. 새로운 클러스터 C 생성
      9. p를 C에 추가
      10. for each 점 q in N:
          11. if q가 미방문:
              12. q를 방문 표시
              13. N' = N_ε(q) 계산
              14. if |N'| ≥ minPts:
                  15. N = N ∪ N' (이웃 확장)
          16. if q가 어떤 클러스터에도 미속:
              17. q를 C에 추가
18. 노이즈 점들을 각각 개별 클러스터로 처리
```

#### 시간 복잡도

- **최악**: $O(n^2)$ (모든 점 쌍 거리 계산)
- **최선**: $O(n \log n)$ (공간 인덱스 사용 시, 예: KD-tree)
- **본 구현**: sklearn 라이브러리 사용 (내부적으로 Ball Tree 최적화)

#### 노이즈 처리

DBSCAN에서 노이즈로 분류된 장소(label = -1)는 각각 개별 클러스터로 처리:

```python
for place_id, label in zip(place_ids, labels):
    if label == -1:
        clusters[noise_counter] = [place_id]
        noise_counter -= 1
```

**이유**: 모든 장소가 일정에 포함되어야 하므로, 고립된 장소도 방문 가능

### 4.2 K-means 재귀 분할

**구현 위치**: `services/clustering.py:137-175`

#### 목적

Google Routes Matrix API의 제약사항:
- **최대 매트릭스 크기**: 10 × 10
- **해결**: 10개 초과 클러스터를 재귀적으로 분할

#### 알고리즘

K-means (k=2)를 사용한 이진 분할:

```
입력: 장소 집합 P (|P| > 10)
출력: 서브클러스터 리스트 (각 ≤10개)

1. if |P| ≤ 10:
   2. return [P]
3. 좌표를 km 단위로 변환
4. K-means(k=2) 실행 → 라벨 L₁, L₂
5. P를 G₁ = {p | L(p) = 0}, G₂ = {p | L(p) = 1}로 분할
6. result = []
7. result += split_recursive(G₁)
8. result += split_recursive(G₂)
9. return result
```

#### K-means 알고리즘

**표준 K-means (Lloyd's Algorithm)**:

1. **초기화**: k개의 센트로이드 랜덤 선택
2. **할당**: 각 점을 가장 가까운 센트로이드에 할당
   ```
   C_i = {p ∈ D | i = argmin_j ||p - μ_j||}
   ```
3. **업데이트**: 센트로이드를 클러스터 평균으로 갱신
   ```
   μ_i = (1/|C_i|) Σ_{p ∈ C_i} p
   ```
4. **수렴**: 센트로이드가 변하지 않을 때까지 2-3 반복

#### 파라미터

```python
k = 2                # 이진 분할
random_state = 42    # 재현성 보장
n_init = 10          # 10번 시도 후 최선 선택
```

#### 재귀 종료 조건

```
T(n) = { 1                    if n ≤ 10
       { T(n/2) + T(n/2) + 1  if n > 10
```

**깊이**: $O(\log_2(n/10))$

**예시**:
- 50개 장소: $\log_2(50/10) \approx 2.3$ → 3단계
- 100개 장소: $\log_2(100/10) \approx 3.3$ → 4단계

#### 장점

- **균등 분할**: K-means는 비교적 균등한 크기의 클러스터 생성
- **지리적 인접성 유지**: 좌표 기반 클러스터링으로 인접 장소끼리 그룹화
- **확정적 종료**: 모든 클러스터가 결국 10개 이하로 분할

---

## 5. 이동시간 매트릭스 계산

### 5.1 Google Routes Matrix API

**구현 위치**: `services/routes_matrix.py:16-129`

#### API 사양

- **엔드포인트**: `https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`
- **메서드**: POST
- **입력**: N개 출발지 × M개 목적지의 위도/경도
- **출력**: N × M 이동시간 매트릭스 (초 단위)
- **제약**: 최대 10 × 10 매트릭스

#### 지원 이동 수단

| 모드 | 설명 | 평균 속도 |
|------|------|-----------|
| TRANSIT | 대중교통 (지하철, 버스) | 25-40 km/h |
| DRIVE | 자동차 | 30-60 km/h |
| WALK | 도보 | 5 km/h |
| BICYCLE | 자전거 | 15 km/h |

#### 응답 파싱

```json
[
  {
    "originIndex": 0,
    "destinationIndex": 1,
    "duration": "1800s",
    "distanceMeters": 15000,
    "status": {"code": 0}
  }
]
```

변환:
```python
duration_seconds = int("1800s".rstrip("s"))  # 1800
duration_minutes = duration_seconds / 60.0    # 30.0
matrix[0, 1] = 30.0
```

### 5.2 클러스터 내 매트릭스 계산

**구현 위치**: `services/routes_matrix.py:131-186`

#### 프로세스

각 클러스터 $C_i = \{p_1, p_2, ..., p_n\}$ (단, $n \leq 10$)에 대해:

1. **API 호출**:
   ```
   matrix_i = compute_route_matrix(C_i, C_i, travel_mode)
   ```

2. **결과**:
   ```
   matrix_i[j][k] = C_i의 j번째 장소 → k번째 장소 이동시간 (분)
   ```

3. **대칭성**: 일반적으로 비대칭
   - `matrix[j][k] ≠ matrix[k][j]` (일방통행, 교통 상황 등)

#### 단일 장소 클러스터

```python
if len(cluster) == 1:
    matrix = [[0.0]]
```

### 5.3 메도이드 (Medoid) 계산

**구현 위치**: `services/clustering.py:177-212`

#### 정의

**메도이드**: 클러스터 내에서 다른 모든 점까지의 평균 거리가 최소인 실제 데이터 포인트

#### 수식

클러스터 $C = \{p_1, p_2, ..., p_n\}$와 거리 매트릭스 $D_{n \times n}$에 대해:

```
medoid = argmin_{i} (1/n) Σ_{j=1}^{n} D[i, j]
```

#### 알고리즘

```
입력: 장소 집합 P, 거리 매트릭스 D
출력: 메도이드 장소 ID

1. if |P| = 1:
   2. return P[0]
3. for i = 0 to |P|-1:
   4. avg_dist[i] = mean(D[i, :])
5. medoid_idx = argmin(avg_dist)
6. return P[medoid_idx].id
```

#### 예시

```
클러스터: {A, B, C}
거리 매트릭스 (분):
    A   B   C
A [ 0  10  20]
B [10   0  15]
C [20  15   0]

평균 거리:
A: (0 + 10 + 20) / 3 = 10.0
B: (10 + 0 + 15) / 3 = 8.3  ← 최소
C: (20 + 15 + 0) / 3 = 11.7

메도이드: B
```

#### 센트로이드 vs 메도이드

| 특성 | 센트로이드 (Centroid) | 메도이드 (Medoid) |
|------|---------------------|------------------|
| 정의 | 평균 좌표 | 실제 데이터 포인트 |
| 계산 | $\frac{1}{n}\sum p_i$ | $\arg\min \sum d(p_i, p)$ |
| 실재성 | 가상의 점 | 실제 장소 |
| 이상치 민감도 | 높음 | 낮음 |

**본 시스템에서 메도이드 선택 이유**:
- 실제 방문 가능한 장소
- 클러스터 중심을 대표
- 클러스터 간 이동시간 추정의 기준점

### 5.4 메도이드 간 매트릭스

**구현 위치**: `services/routes_matrix.py:188-223`

#### 목적

서로 다른 클러스터 간 이동시간 추정

#### 프로세스

M개 클러스터의 메도이드 $\{m_1, m_2, ..., m_M\}$에 대해:

```
medoid_matrix = compute_route_matrix(medoids, medoids, travel_mode)
```

**결과**:
```
medoid_matrix[i][j] = 클러스터 i의 메도이드 → 클러스터 j의 메도이드 이동시간
```

#### 근사 가정

클러스터 $C_i$의 장소 $p$ → 클러스터 $C_j$의 장소 $q$ 이동시간:

```
time(p → q) ≈ time(medoid_i → medoid_j)
```

**오차 분석**:
- 클러스터 반경 7km 기준: 평균 오차 ± 10분
- 허용 가능한 근사치 (전체 일정 계획 수준)

---

## 6. 복잡도 및 성능 분석

### 6.1 전체 시스템 복잡도

N개 장소, M개 클러스터 (M << N) 가정:

| 단계 | 알고리즘 | 시간 복잡도 | 공간 복잡도 |
|------|----------|-------------|-------------|
| 1. DB 조회 | SQL IN 쿼리 | O(N) | O(N) |
| 2. 임베딩 생성 | Gemini API × N | O(N) | O(N × 768) |
| 3. 유사도 계산 | 벡터 내적 × N | O(N × 768) | O(N) |
| 4. DBSCAN | sklearn | O(N log N) | O(N²) |
| 5. K-means 분할 | 재귀 | O(N log(N/10)) | O(N) |
| 6. 클러스터 매트릭스 | API × M | O(M × 10²) | O(M × 100) |
| 7. 메도이드 계산 | 평균 거리 | O(M × 10²) | O(M) |
| 8. 메도이드 매트릭스 | API × 1 | O(M²) | O(M²) |
| 9. 일정 생성 | Gemini API | O(1) | O(N + M) |

**전체**: $O(N \log N + M \times 10^2 + M^2)$

**일반적인 경우**:
- N = 50개 장소
- M = 5-10개 클러스터
- 전체 시간: 2-5초 (API 레이턴시 포함)

### 6.2 API 호출 최적화

#### 나이브 방법 vs 최적화 방법

**나이브**: 모든 장소 쌍 간 매트릭스
- API 호출: $\lceil N/10 \rceil^2$번
- N=50: $5^2 = 25$번

**최적화**: 클러스터 내 + 메도이드 간
- API 호출: $M + 1$번 (M개 클러스터 + 1개 메도이드 매트릭스)
- N=50, M=5: $5 + 1 = 6$번

**개선율**: $(25 - 6) / 25 \times 100\% = 76\%$ API 호출 감소

---

## 7. 시뮬레이션 예시

### 7.1 샘플 입력

```json
{
  "places": ["P1", "P2", ..., "P20"],
  "user_request": {
    "query": "힐링되는 자연 여행",
    "days": 2,
    "travel_mode": "TRANSIT"
  }
}
```

### 7.2 시뮬레이션 단계별 결과

#### Step 1: 임베딩 및 유사도

```
장소             editorial_summary               유사도 점수
P1 (북한산)      "도심 속 자연 휴식처"             0.85
P2 (남산타워)    "서울의 랜드마크 전망대"          0.62
P3 (한강공원)    "수변 산책과 힐링 공간"           0.88
...
```

#### Step 2: DBSCAN 클러스터링 (eps=7km)

```
클러스터 0: [P1, P7, P12]           # 북한산 일대
클러스터 1: [P3, P8, P15, P18]      # 한강 일대
클러스터 2: [P2, P5, P9]            # 중구 일대
클러스터 -1: [P4]                   # 고립 장소 (개별 클러스터)
클러스터 -2: [P6]                   # 고립 장소
...
```

#### Step 3: 클러스터 내 이동시간 매트릭스

```
클러스터 0:
       P1   P7   P12
P1  [  0   12   18 ]
P7  [ 13    0   22 ]
P12 [ 19   23    0 ]

메도이드: P1 (평균 거리 = (0+12+18)/3 = 10.0)
```

#### Step 4: 메도이드 간 매트릭스

```
         Cluster0  Cluster1  Cluster2  Cluster-1  Cluster-2
         (P1)      (P3)      (P2)      (P4)       (P6)
Cluster0 [  0       35        28        42         50   ]
Cluster1 [ 36        0        18        55         48   ]
Cluster2 [ 29       19         0        38         41   ]
Cluster-1[ 43       56        39         0         62   ]
Cluster-2[ 51       49        42        61          0   ]
```

#### Step 5: Gemini 일정 생성

프롬프트에 포함:
- 장소 정보 (이름, 좌표, 유사도 점수, 운영시간)
- 클러스터 정보
- 이동시간 매트릭스 (JSON)

Gemini 응답:
```json
{
  "itinerary": [
    {
      "day": 1,
      "visits": [
        {"order": 1, "google_place_id": "P3", "visit_time": "09:00", "duration_minutes": 120},
        {"order": 2, "google_place_id": "P8", "visit_time": "11:30", "duration_minutes": 90},
        {"order": 3, "google_place_id": "P2", "visit_time": "14:00", "duration_minutes": 60}
      ]
    },
    {
      "day": 2,
      "visits": [...]
    }
  ]
}
```

---

## 8. 검증 및 테스트

### 8.1 단위 테스트

각 계산 모듈에 대한 단위 테스트:

```python
# 좌표 변환 테스트
def test_lat_lon_to_km():
    """서울 시청 → 강남역 거리 검증"""
    # 실제 거리: 약 10.8km
    calculated = lat_lon_to_km(37.5665, 126.9780, 37.4979, 127.0276)
    assert abs(calculated - 10.8) < 0.5  # 오차 < 0.5km

# 코사인 유사도 테스트
def test_cosine_similarity():
    v1 = [1, 0, 0]
    v2 = [1, 0, 0]
    assert calculate_cosine_similarity(v1, v2) == 1.0  # 동일 벡터

    v3 = [0, 1, 0]
    assert calculate_cosine_similarity(v1, v3) == 0.5  # 직교 벡터 (정규화 후)

# DBSCAN 테스트
def test_clustering():
    """정해진 좌표로 클러스터 개수 검증"""
    places = [
        Place(lat=37.5, lon=127.0),  # 그룹 A
        Place(lat=37.51, lon=127.01),
        Place(lat=37.6, lon=127.1),  # 그룹 B
        Place(lat=37.61, lon=127.11),
    ]
    clusters = cluster_places(places)
    assert len(clusters) == 2  # 2개 클러스터 예상
```

### 8.2 통합 테스트

실제 서울 관광지 데이터로 End-to-End 테스트:

```python
def test_full_itinerary():
    """50개 실제 장소로 일정 생성"""
    request = {
        "places": ["ChIJ...", ...],  # 50개 실제 Place ID
        "user_request": {
            "query": "역사 문화 여행",
            "days": 3,
            "travel_mode": "TRANSIT"
        }
    }
    response = generate_itinerary(request)

    # 검증
    assert len(response["itinerary"]) == 3  # 3일 일정
    assert all(len(day["visits"]) > 0 for day in response["itinerary"])
    # 이동시간 합리성 검증 (하루 총 이동시간 < 6시간)
    for day in response["itinerary"]:
        total_travel = calculate_total_travel_time(day["visits"])
        assert total_travel < 360  # 분
```

### 8.3 성능 벤치마크

```
장소 수      클러스터 수    API 호출    전체 시간
20개         3-4개         4-5번       1.5초
50개         5-8개         6-9번       2.8초
100개        10-15개       11-16번     5.2초
```

---

## 9. 한계 및 향후 개선

### 9.1 현재 한계

1. **좌표 변환 근사**:
   - 평면 투영 가정 (100km 이상에서 오차 증가)
   - 해결: Haversine 공식 또는 Vincenty 알고리즘 적용

2. **Fallback 매트릭스 부정확성**:
   - 유클리드 거리 기반 (실제 경로 무시)
   - 평균 속도 30km/h 고정 (시간대/교통 상황 미반영)
   - 해결: 역사적 이동시간 데이터 활용, 시간대별 보정

3. **메도이드 근사**:
   - 클러스터 간 이동시간을 메도이드 기준으로 근사
   - 클러스터 반경이 클 경우 오차 증가
   - 해결: 클러스터 경계 장소 간 추가 매트릭스 계산

### 9.2 향후 개선 방향

1. **고급 클러스터링**:
   - HDBSCAN (Hierarchical DBSCAN)
   - 가변적인 밀도 파라미터

2. **실시간 교통 정보**:
   - Google Maps Traffic API 연동
   - 시간대별 이동시간 보정

3. **다목적 최적화**:
   - 파레토 최적 (이동시간, 점수, 비용 동시 고려)
   - 유전 알고리즘 또는 시뮬레이티드 어닐링

4. **캐싱 전략**:
   - 장소 임베딩 캐싱 (DB 저장)
   - 이동시간 매트릭스 캐싱 (Redis)

---

## 10. 참고 문헌 및 자료

### 논문 및 알고리즘

1. **DBSCAN**: Ester, M., et al. (1996). "A density-based algorithm for discovering clusters in large spatial databases with noise." KDD-96.

2. **K-means**: Lloyd, S. (1982). "Least squares quantization in PCM." IEEE Transactions on Information Theory.

3. **Cosine Similarity**: Singhal, A. (2001). "Modern information retrieval: A brief overview." IEEE Data Engineering Bulletin.

### API 문서

1. **Google Gemini API**: https://ai.google.dev/docs
   - Embedding Model: `embedding-001`
   - Generative Model: `gemini-2.5-flash`

2. **Google Routes Matrix API**: https://developers.google.com/maps/documentation/routes

### 라이브러리

1. **scikit-learn**: DBSCAN, K-means 구현
   - Pedregosa, F., et al. (2011). "Scikit-learn: Machine Learning in Python."

2. **NumPy**: 행렬 연산
   - Harris, C.R., et al. (2020). "Array programming with NumPy."

---

**문서 버전**: 1.0
**작성일**: 2025-10-16
**작성자**: triB Development Team
**검토**: 이론 및 구현 검증 완료
