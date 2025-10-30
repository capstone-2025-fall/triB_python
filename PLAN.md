# V2 일정 생성 API 개선 작업 계획

## 요구사항 요약

### 1. 응답 구조에 budget 항목 추가
- 일정 전체의 1인당 예상 예산을 응답에 포함
- 단위: 원화 (KRW)

### 2. Visit 모델 구조 변경
- **기존**: `(order, display_name, latitude, longitude, visit_time, travel_time)`
- **변경**: `(order, display_name, place_tag, latitude, longitude, arrival, departure, travel_time)`
- `visit_time` → `arrival` (도착 시간), `departure` (출발 시간)로 세분화
- `place_tag` 필드 추가

### 3. 입력 구조 변경
- **기존**: `places: List[str]`
- **변경**: `places: List[PlaceWithTag]`
  ```json
  {
    "places": [
      {
        "place_name": "도톤보리",
        "place_tag": "TOURIST_SPOT"
      },
      {
        "place_name": "유니버설 스튜디오 재팬",
        "place_tag": "TOURIST_SPOT"
      }
    ]
  }
  ```

### 4. PlaceTag 정의
- `TOURIST_SPOT`: 관광지
- `HOME`: 숙소
- `RESTAURANT`: 식당
- `CAFE`: 카페
- `OTHER`: 기타

### 5. Gemini의 place_tag 할당 규칙
- 사용자가 입력한 장소: 입력받은 `place_tag` 사용
- Gemini가 새로 선택한 장소: 적절한 `place_tag` 자동 할당

---

## PR 구조 및 커밋 단위

### **PR #1: 응답 구조에 budget 항목 추가**
> **목적**: 일정 전체의 1인당 예상 예산을 응답에 포함

#### Commit 1-1: Add budget field to ItineraryResponse2 schema
**파일**: `models/schemas2.py`

**작업**:
- `ItineraryResponse2` 클래스에 `budget: int` 필드 추가
- Field description: "1인당 예상 예산 (원화 기준)"
- 필수 필드로 설정

**코드 예시**:
```python
class ItineraryResponse2(BaseModel):
    """V2 일정 생성 응답"""
    itinerary: List[DayItinerary2] = Field(
        ...,
        description="전체 일정"
    )
    budget: int = Field(
        ...,
        description="1인당 예상 예산 (원화 기준)"
    )
```

#### Commit 1-2: Update Gemini prompt to include budget estimation
**파일**: `services/itinerary_generator2.py`

**작업**:
- `_create_prompt_v2()` 프롬프트에 예산 계산 지시사항 추가
- 출력 형식 예시에 `"budget": 500000` 추가
- 예산 계산 로직 설명 (숙소 + 교통 + 식사 + 입장료 등)

**프롬프트 추가 내용**:
```
### 9. 예산 계산
- 1인당 전체 여행 예산을 계산하세요
- 포함 항목:
  - 숙소 비용 (1박당 평균 가격 × 숙박 일수)
  - 교통 비용 (공항 이동, 시내 교통)
  - 식사 비용 (1일 3식 × 여행 일수)
  - 입장료 (테마파크, 박물관 등)
  - 기타 비용 (쇼핑, 간식 등)
- 원화(KRW) 기준으로 계산하세요
- 합리적인 중간 가격대를 기준으로 산정하세요
```

**출력 형식 변경**:
```json
{
  "itinerary": [...],
  "budget": 500000
}
```

#### Commit 1-3: Update E2E test to validate budget field
**파일**: `tests/test_e2e_itinerary2.py`

**작업**:
- `budget` 필드 존재 여부 검증 추가
- `budget` 데이터 타입 검증 (int, > 0)
- 예산 출력 로그 추가

**테스트 코드 추가**:
```python
# 8. 예산 검증
assert "budget" in data, "Response must contain 'budget' field"
assert isinstance(data["budget"], int), "budget must be int"
assert data["budget"] > 0, f"budget must be positive, got {data['budget']}"
print(f"\n✓ Budget per person: {data['budget']:,} KRW")
```

---

### **PR #2: Visit 모델에 place_tag 필드 추가**
> **목적**: 각 방문지의 장소 유형을 명시

#### Commit 2-1: Add PlaceTag enum to schemas
**파일**: `models/schemas2.py`

**작업**:
- `PlaceTag` Enum 생성 (TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER)
- Import enum 추가

**코드 추가**:
```python
from enum import Enum

class PlaceTag(str, Enum):
    """장소 유형 태그"""
    TOURIST_SPOT = "TOURIST_SPOT"  # 관광지
    HOME = "HOME"  # 숙소
    RESTAURANT = "RESTAURANT"  # 식당
    CAFE = "CAFE"  # 카페
    OTHER = "OTHER"  # 기타
```

#### Commit 2-2: Add place_tag field to Visit2 model
**파일**: `models/schemas2.py`

**작업**:
- `Visit2` 클래스에 `place_tag: PlaceTag` 필드 추가
- Field description: "장소 유형 태그"

**코드 변경**:
```python
class Visit2(BaseModel):
    """V2 방문 장소 정보"""
    order: int = Field(...)
    display_name: str = Field(...)
    place_tag: PlaceTag = Field(
        ...,
        description="장소 유형 태그 (TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER)"
    )
    latitude: float = Field(...)
    longitude: float = Field(...)
    visit_time: str = Field(...)
    travel_time: int = Field(...)
```

#### Commit 2-3: Update Gemini prompt to return place_tag in visits
**파일**: `services/itinerary_generator2.py`

**작업**:
- 프롬프트 출력 형식에 `place_tag` 필드 추가
- 새로운 장소 선택 시 적절한 태그 할당 지시사항 추가

**프롬프트 수정**:
```
### 출력 형식

{
  "order": 1,
  "display_name": "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본",
  "place_tag": "TOURIST_SPOT",
  "latitude": 위도 (float),
  "longitude": 경도 (float),
  "visit_time": "HH:MM",
  "travel_time": 다음 장소로의 이동시간 (분, int)
}

### place_tag 할당 규칙:
- 사용자가 제공한 장소는 해당 장소의 place_tag를 그대로 사용하세요
- Gemini가 새로 추천하는 장소는 다음 기준으로 place_tag를 할당하세요:
  - TOURIST_SPOT: 관광지, 박물관, 테마파크, 사원, 성 등
  - HOME: 호텔, 게스트하우스, 숙소
  - RESTAURANT: 식당, 레스토랑, 음식점
  - CAFE: 카페, 디저트 가게
  - OTHER: 위 분류에 맞지 않는 경우
```

#### Commit 2-4: Update E2E test to validate place_tag
**파일**: `tests/test_e2e_itinerary2.py`

**작업**:
- `place_tag` 필드 검증 추가
- 유효한 PlaceTag enum 값인지 확인

**테스트 코드 추가**:
```python
# visit 검증 부분에 추가
assert "place_tag" in visit, f"Visit {visit_idx} missing 'place_tag' field"
assert visit["place_tag"] in ["TOURIST_SPOT", "HOME", "RESTAURANT", "CAFE", "OTHER"], \
    f"Invalid place_tag: {visit['place_tag']}"
```

---

### **PR #3: Visit 모델 시간 필드 변경 (visit_time → arrival/departure)**
> **목적**: 방문 시간을 도착/출발로 명확히 구분

#### Commit 3-1: Replace visit_time with arrival and departure in Visit2
**파일**: `models/schemas2.py`

**작업**:
- `Visit2` 클래스의 `visit_time` 필드 제거
- `arrival: str` 필드 추가 (description: "장소 도착 시간 HH:MM")
- `departure: str` 필드 추가 (description: "장소 출발 시간 HH:MM")

**코드 변경**:
```python
class Visit2(BaseModel):
    """V2 방문 장소 정보"""
    order: int = Field(...)
    display_name: str = Field(...)
    place_tag: PlaceTag = Field(...)
    latitude: float = Field(...)
    longitude: float = Field(...)
    arrival: str = Field(
        ...,
        description="장소 도착 시간 (HH:MM 형식)"
    )
    departure: str = Field(
        ...,
        description="장소 출발 시간 (HH:MM 형식)"
    )
    travel_time: int = Field(...)
```

#### Commit 3-2: Update Gemini prompt to use arrival/departure
**파일**: `services/itinerary_generator2.py`

**작업**:
- 프롬프트 출력 형식에서 `visit_time` → `arrival`, `departure`로 변경
- 도착/출발 시간 계산 로직 설명 추가
- 체류시간 = departure - arrival 계산 지시

**프롬프트 수정**:
```
### 출력 형식

{
  "order": 1,
  "display_name": "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본",
  "place_tag": "TOURIST_SPOT",
  "latitude": 위도 (float),
  "longitude": 경도 (float),
  "arrival": "09:00",
  "departure": "11:30",
  "travel_time": 20
}

### arrival 및 departure 계산:
- **arrival**: 해당 장소에 도착하는 시간
  - 첫 번째 장소: 하루 일정 시작 시간
  - 이후 장소: 이전 장소의 departure + travel_time
- **departure**: 해당 장소에서 떠나는 시간
  - arrival + 해당 장소 체류시간
  - 체류시간은 장소 특성을 고려하여 설정 (섹션 8 참고)
- 24시간 형식 "HH:MM" 사용 (예: "09:00", "14:30")
```

#### Commit 3-3: Update E2E test for arrival/departure fields
**파일**: `tests/test_e2e_itinerary2.py`

**작업**:
- `visit_time` 검증 제거
- `arrival`, `departure` 필드 검증 추가
- 시간 형식 검증 (HH:MM)
- 출력 로그 업데이트

**테스트 코드 수정**:
```python
# 필수 필드 업데이트
required_fields = ["order", "display_name", "place_tag", "latitude", "longitude", "arrival", "departure", "travel_time"]

# 시간 형식 검증
assert isinstance(visit["arrival"], str), f"arrival must be str"
assert isinstance(visit["departure"], str), f"departure must be str"
assert ":" in visit["arrival"], f"arrival must be in HH:MM format"
assert ":" in visit["departure"], f"departure must be in HH:MM format"

# 출력 로그 수정
print(f"  - Visit {visit['order']}: {visit['display_name']} ({visit['arrival']}-{visit['departure']}, travel: {visit['travel_time']}min)")
```

---

### **PR #4: 입력 구조에 place_tag 추가**
> **목적**: 사용자가 입력한 장소에도 태그 정보 포함

#### Commit 4-1: Add PlaceWithTag model for input structure
**파일**: `models/schemas2.py`

**작업**:
- `PlaceWithTag` Pydantic 모델 생성
  - `place_name: str`
  - `place_tag: PlaceTag`

**코드 추가**:
```python
class PlaceWithTag(BaseModel):
    """태그가 포함된 장소 정보"""
    place_name: str = Field(
        ...,
        description="장소 이름"
    )
    place_tag: PlaceTag = Field(
        ...,
        description="장소 유형 태그 (TOURIST_SPOT, HOME, RESTAURANT, CAFE, OTHER)"
    )
```

#### Commit 4-2: Update ItineraryRequest2 to use PlaceWithTag
**파일**: `models/schemas2.py`

**작업**:
- `ItineraryRequest2`의 `places: List[str]` → `places: List[PlaceWithTag]`로 변경

**코드 수정**:
```python
class ItineraryRequest2(BaseModel):
    """V2 일정 생성 요청"""
    places: List[PlaceWithTag] = Field(
        ...,
        description="태그가 포함된 장소 리스트"
    )
    user_request: UserRequest2
```

#### Commit 4-3: Update service to handle PlaceWithTag input
**파일**: `services/itinerary_generator2.py`

**작업**:
- `generate_itinerary()` 파라미터 타입 변경: `List[str]` → `List[PlaceWithTag]`
- `_create_prompt_v2()` 파라미터 타입 변경
- 프롬프트 생성 시 장소명과 태그 함께 포맷팅
- 프롬프트에 "사용자가 제공한 place_tag 참고" 지시사항 추가

**코드 수정**:
```python
from models.schemas2 import UserRequest2, ItineraryResponse2, PlaceWithTag

def _create_prompt_v2(
    self,
    places: List[PlaceWithTag],
    user_request: UserRequest2,
) -> str:
    # ...
    # 장소 목록 포맷팅 수정
    places_text = "\n".join([f"- {place.place_name} ({place.place_tag.value})" for place in places])

    # 프롬프트에 추가
    """
    ### 고려 중인 장소 목록 (places)
    각 장소에는 사용자가 지정한 place_tag가 포함되어 있습니다.
    {places_text}

    ### place_tag 활용:
    - 위 장소들을 일정에 포함할 때 해당 place_tag를 그대로 사용하세요
    - Gemini가 장소 정보를 찾지 못했을 때 place_tag를 참고하세요
    - 예: 장소명만 있고 상세 정보가 없으면 place_tag로 장소 유형을 파악
    """

async def generate_itinerary(
    self,
    places: List[PlaceWithTag],
    user_request: UserRequest2,
) -> ItineraryResponse2:
    # ...
```

#### Commit 4-4: Update E2E test with new input structure
**파일**: `tests/test_e2e_itinerary2.py`

**작업**:
- `places` 배열을 객체 배열로 변경
- 각 장소에 `place_name`, `place_tag` 포함
- 테스트 데이터 예시 업데이트

**테스트 코드 수정**:
```python
request_data = {
    "places": [
        {"place_name": "오사카텐만구 (오사카 천만궁)", "place_tag": "TOURIST_SPOT"},
        {"place_name": "신사이바시스지", "place_tag": "TOURIST_SPOT"},
        {"place_name": "오사카 성", "place_tag": "TOURIST_SPOT"},
        {"place_name": "도톤보리", "place_tag": "TOURIST_SPOT"},
        {"place_name": "해유관", "place_tag": "TOURIST_SPOT"},
        {"place_name": "유니버설 스튜디오 재팬", "place_tag": "TOURIST_SPOT"},
        {"place_name": "구로몬 시장", "place_tag": "RESTAURANT"},
        {"place_name": "우메다 스카이 빌딩", "place_tag": "TOURIST_SPOT"},
        {"place_name": "시텐노지 (사천왕사)", "place_tag": "TOURIST_SPOT"},
        {"place_name": "츠텐카쿠", "place_tag": "TOURIST_SPOT"},
    ],
    "user_request": {
        # ...
    }
}
```

---

## 검증 계획

각 PR 완료 후:

1. **스키마 검증**
   - Pydantic 모델 import 오류 없는지 확인
   - FastAPI swagger docs에서 스키마 확인: `http://localhost:8001/docs`

2. **E2E 테스트 실행**
   ```bash
   pytest tests/test_e2e_itinerary2.py -v -s
   ```

3. **API 수동 테스트**
   ```bash
   # 서버 실행
   python main2.py

   # curl 테스트
   curl -X POST http://localhost:8001/api/v2/itinerary/generate \
     -H "Content-Type: application/json" \
     -d @test_request.json
   ```

4. **응답 검증**
   - 모든 필수 필드 포함 여부
   - 데이터 타입 정확성
   - Gemini가 적절한 값을 생성했는지 (budget, place_tag, arrival/departure)

---

## 예상 입력/출력 예시

### 입력 예시 (최종 형태)
```json
{
  "days": 3,
  "start_date": "2025-10-15",
  "country": "일본",
  "members": 2,
  "places": [
    {
      "place_name": "도톤보리",
      "place_tag": "TOURIST_SPOT"
    },
    {
      "place_name": "유니버설 스튜디오 재팬",
      "place_tag": "TOURIST_SPOT"
    },
    {
      "place_name": "해유관",
      "place_tag": "TOURIST_SPOT"
    }
  ],
  "must_visit": ["유니버설 스튜디오 재팬"],
  "rule": ["첫날은 오사카성만", "둘째날 유니버설 하루종일"],
  "chat": ["오사카 가고 싶다", "유니버설은 필수!"]
}
```

### 출력 예시 (최종 형태)
```json
{
  "itinerary": [
    {
      "day": 1,
      "visits": [
        {
          "order": 1,
          "display_name": "오사카 성 1-1 Osakajo, Chuo Ward, Osaka, 540-0002 일본",
          "place_tag": "TOURIST_SPOT",
          "latitude": 34.6873,
          "longitude": 135.5262,
          "arrival": "09:00",
          "departure": "11:30",
          "travel_time": 0
        }
      ]
    },
    {
      "day": 2,
      "visits": [...]
    }
  ],
  "budget": 500000
}
```

---

## 주의사항

1. **Gemini 프롬프트 변경**
   - 프롬프트가 너무 길어지지 않도록 주의
   - 명확한 지시사항 작성 (예시 포함)
   - JSON 출력 형식 정확히 명시

2. **하위 호환성**
   - 기존 V1 API(`main.py`, `models/schemas.py`)는 건드리지 않음
   - V2는 완전히 독립적인 API

3. **타입 안정성**
   - Pydantic 모델 검증 활용
   - Enum 사용으로 유효하지 않은 값 방지

4. **테스트 데이터**
   - 다양한 place_tag 조합 테스트
   - 예산 계산 합리성 검증
   - arrival/departure 시간 순서 검증

---

## 작업 순서

1. PR #1 → PR #2 → PR #3 → PR #4 순서로 진행
2. 각 PR은 독립적으로 병합 가능
3. 각 커밋은 원자적(atomic)으로 유지
4. 커밋 메시지는 conventional commits 형식 사용
   - `feat:`, `test:`, `refactor:` 등

---

## 예상 소요 시간

- **PR #1**: 30분 (budget 추가는 비교적 단순)
- **PR #2**: 45분 (enum 추가 + 프롬프트 수정)
- **PR #3**: 45분 (필드 이름 변경 + 로직 수정)
- **PR #4**: 1시간 (입력 구조 변경은 영향 범위가 넓음)
- **총 예상 시간**: 약 3시간

---

## 완료 체크리스트

- [x] PR #1: budget 항목 추가
  - [x] Commit 1-1: Schema 수정
  - [x] Commit 1-2: Gemini 프롬프트 수정
  - [x] Commit 1-3: E2E 테스트 수정
  - [x] E2E 테스트 통과 (2025-01-30 검증 완료 - Budget: 650,000 KRW)

- [x] PR #2: place_tag 필드 추가 (Visit)
  - [x] Commit 2-1: PlaceTag enum 추가
  - [x] Commit 2-2: Visit2 모델 수정
  - [x] Commit 2-3: Gemini 프롬프트 수정
  - [x] Commit 2-4: E2E 테스트 수정
  - [x] E2E 테스트 통과 (2025-01-30 검증 완료)

- [x] PR #3: arrival/departure 필드 변경
  - [x] Commit 3-1: Visit2 모델 수정
  - [x] Commit 3-2: Gemini 프롬프트 수정
  - [x] Commit 3-3: E2E 테스트 수정
  - [x] E2E 테스트 통과 (2025-01-30 검증 완료)

- [x] PR #4: 입력 구조 변경
  - [x] Commit 4-1: PlaceWithTag 모델 추가
  - [x] Commit 4-2: ItineraryRequest2 수정
  - [x] Commit 4-3: Service 수정
  - [x] Commit 4-4: E2E 테스트 수정
  - [x] E2E 테스트 통과 (2025-01-30 검증 완료)

- [ ] 최종 검증
  - [ ] API 문서 확인 (Swagger)
  - [ ] 수동 테스트 실행
  - [x] 모든 E2E 테스트 통과 (2025-01-30 검증 완료)
