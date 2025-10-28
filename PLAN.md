# triB_python V2 개발 계획

## 개요
기존 V1 시스템을 유지하면서, 장소 이름만으로 Gemini가 일정을 생성하는 V2 시스템을 새로 구축합니다.
**모든 파일에 2를 붙여 새로 생성하며, 기존 파일은 수정하지 않습니다.**

---

## V1과 V2의 차이점

### V1 (기존)
- Google Maps API로 장소 정보 조회 (DB에서)
- 임베딩 기반 유사도 점수 계산
- 지리적 클러스터링 수행
- Google Routes API로 이동시간 매트릭스 계산
- 클러스터/이동시간 정보를 Gemini에 전달하여 일정 생성

### V2 (신규)
- **DB 조회 없음**: 장소 이름만 사용
- **클러스터링 없음**: Gemini가 모든 것을 처리
- **채팅 분석**: 사용자 대화에서 의도 파악
- **Gemini 중심**: 장소 추천, 숙소 추천, 이동시간 추론, 일정 생성 모두 Gemini가 수행
- **간소화된 구조**: 프롬프트 엔지니어링에 집중

---

## 생성할 파일 목록

```
models/schemas2.py           # V2 스키마 정의
services/itinerary_generator2.py  # V2 일정 생성 서비스
main2.py                     # V2 FastAPI 엔드포인트
tests/test_e2e_itinerary2.py # V2 테스트
```

---

## PR #1: V2 스키마 모델 정의

### Commit 1-1: schemas2.py 생성 - 요청 스키마
**파일**: `models/schemas2.py`

**작업 내용**:
```python
# 새로운 Preferences2 클래스
class Preferences2(BaseModel):
    must_visit: Optional[List[str]]  # 필수 방문 장소 이름 (ID 아님)
    accommodation: Optional[str]     # 숙소 이름 (없으면 Gemini가 추천)
    travel_mode: str = "DRIVE"       # 이동 수단

# 새로운 UserRequest2 클래스
class UserRequest2(BaseModel):
    chat: List[str]                  # 사용자 채팅 내용 배열 (추가!)
    rule: Optional[List[str]]        # 반드시 지켜야 할 규칙
    days: int                        # 여행 일수
    start_date: date                 # 시작 날짜
    preferences: Preferences2

# 새로운 ItineraryRequest2 클래스
class ItineraryRequest2(BaseModel):
    places: List[str]                # 장소 이름 리스트 (ID 아님!)
    user_request: UserRequest2
```

**변경 이유**:
- `places`: Google Place ID → 장소 이름으로 변경
- `chat`: 사용자 대화 내용 추가 (일정 생성 의도 파악용)
- `accommodation`: null 가능 (Gemini가 추천)

---

### Commit 1-2: schemas2.py 생성 - 응답 스키마
**파일**: `models/schemas2.py` (계속)

**작업 내용**:
```python
# 새로운 Visit2 클래스
class Visit2(BaseModel):
    order: int                       # 방문 순서
    display_name: str                # 장소명
    latitude: float                  # 위도
    longitude: float                 # 경도
    visit_time: str                  # 방문 시간 (HH:MM)
    travel_time: int                 # 다음 장소로의 이동시간(분) (추가!)

# DayItinerary2, ItineraryResponse2 클래스
class DayItinerary2(BaseModel):
    day: int
    visits: List[Visit2]

class ItineraryResponse2(BaseModel):
    itinerary: List[DayItinerary2]
```

**변경 이유**:
- `travel_time`: 다음 장소로 가는 이동시간 추가 (요구사항 반영)
- `google_place_id`, `place_tag`, `duration_minutes` 제거: 간소화
- Gemini가 latitude/longitude도 추론하여 반환

---

## PR #2: V2 일정 생성 서비스 구현

### Commit 2-1: itinerary_generator2.py 생성 - 기본 구조
**파일**: `services/itinerary_generator2.py`

**작업 내용**:
```python
import logging
import json
from typing import List, Dict
import google.generativeai as genai
from config import settings
from models.schemas2 import UserRequest2, ItineraryResponse2

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.google_api_key)

class ItineraryGeneratorService2:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def generate_itinerary(
        self,
        places: List[str],
        user_request: UserRequest2,
    ) -> ItineraryResponse2:
        """V2 일정 생성 메인 함수"""
        pass

# 싱글톤
itinerary_generator_service2 = ItineraryGeneratorService2()
```

**특징**:
- V1과 달리 places는 문자열 리스트 (장소 이름)
- scores, clusters, matrices 등 모두 제거
- 매개변수 간소화

---

### Commit 2-2: itinerary_generator2.py - 프롬프트 생성 함수
**파일**: `services/itinerary_generator2.py` (계속)

**작업 내용**:
```python
def _create_prompt_v2(
    self,
    places: List[str],
    user_request: UserRequest2,
) -> str:
    """Gemini V2 프롬프트 생성"""

    # 날짜별 요일 계산
    # 프롬프트 구성:
    # 1. 역할 정의
    # 2. 입력 데이터 (places, chat, rule, must_visit, days, start_date)
    # 3. 지시사항:
    #    - 채팅 내용 분석하여 의도 파악
    #    - places에서 적절한 장소 선택
    #    - 부족하면 직접 장소 추천 (이름, 좌표 포함)
    #    - 숙소 없으면 추천
    #    - must_visit 반드시 포함
    #    - rule 반드시 준수
    #    - 이동시간 추론 (지정된 travel_mode 기준)
    #    - 운영시간 고려 (각 장소의 일반적인 운영시간 내 방문)
    # 4. 출력 형식 (JSON)

    return prompt
```

**프롬프트 핵심 요소**:
1. **채팅 분석**: 사용자 대화에서 선호도, 패턴 파악
2. **장소 추천**: places에 없는 장소도 Gemini가 찾아서 추가
3. **숙소 추천**: accommodation이 null이면 적절한 숙소 추천
4. **이동시간 추론**: Gemini가 지리적 거리를 바탕으로 이동시간 계산
5. **운영시간 고려**: 각 장소의 일반적인 운영시간을 고려하여 일정 생성

---

### Commit 2-3: itinerary_generator2.py - 프롬프트 상세 내용
**파일**: `services/itinerary_generator2.py` (계속)

**작업 내용**:
프롬프트에 포함할 주요 지시사항:

```
## 당신의 역할
당신은 여행 일정 생성 전문가입니다.
사용자가 나눈 채팅 내용을 분석하고, 제공된 장소 목록과 함께 최적의 여행 일정을 생성합니다.

## 입력 데이터
- places: {places} (사용자가 고려 중인 장소 이름 목록)
- chat: {chat} (사용자들이 나눈 대화 내용)
- rule: {rule} (반드시 지켜야 할 규칙)
- must_visit: {must_visit} (반드시 방문해야 하는 장소)
- accommodation: {accommodation} (숙소, null이면 추천 필요)
- days: {days}일
- start_date: {start_date}
- travel_mode: {travel_mode}

## 작업 지시사항

### 1. 채팅 분석
- 사용자들의 대화를 읽고 여행 의도, 선호도, 패턴을 파악하세요

### 2. 장소 선택 및 추천
- places 목록에서 적절한 장소를 선택하세요
- **중요**: places에 적합한 장소가 없다면 직접 장소를 찾아 추천하세요
  - 예: 채팅에 "맛있는 라멘 가게 가고 싶다"라고 했는데 places에 라멘집이 없으면
    → 적절한 라멘 가게를 찾아서 일정에 포함 (장소명과 좌표 포함)
- must_visit 장소는 반드시 포함하세요

### 3. 숙소 추천
- accommodation이 제공되지 않았다면:
  - 여행지와 예산에 맞는 적절한 숙소를 추천하세요
  - 위치, 가격대, 편의성을 고려하세요

### 4. 이동시간 계산
- 각 visit의 travel_time은 **현재 장소에서 다음 장소로 가는 이동시간(분)**입니다
- 마지막 visit의 travel_time은 0입니다
- {travel_mode} 기준으로 이동시간을 추론하세요
  - DRIVE: 자동차 (평균 40-60km/h, 도심 기준)
  - TRANSIT: 대중교통 (환승시간 포함)
  - WALK: 도보 (5km/h)

### 5. 규칙 준수
- rule의 모든 항목을 반드시 일정에 반영하세��
- 예: "첫날은 오사카성 정도만 가자" → Day 1에 오사카성만 포함

### 6. 운영시간 고려
- 운영시간 내에 방문하도록 일정을 조정하세요

## 출력 형식
{JSON 형식 예시}
- order: 방문 순서 (1부터)
- display_name: 장소명
- latitude: 위도
- longitude: 경도
- visit_time: 방문 시간 (HH:MM)
- travel_time: 다음 장소로의 이동시간 (분)

**중요**: 순수 JSON만 반환하세요. 설명이나 마크다운 없이.
```

---

### Commit 2-4: itinerary_generator2.py - 일정 생성 구현
**파일**: `services/itinerary_generator2.py` (계속)

**작업 내용**:
```python
async def generate_itinerary(
    self,
    places: List[str],
    user_request: UserRequest2,
) -> ItineraryResponse2:
    """V2 일정 생성"""
    try:
        # 프롬프트 생성
        prompt = self._create_prompt_v2(places, user_request)

        logger.info("Generating V2 itinerary with Gemini...")
        logger.debug(f"Prompt length: {len(prompt)}")

        # Gemini 호출
        response = self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )

        # JSON 파싱
        response_text = response.text
        logger.info(f"Received response: {len(response_text)} chars")

        itinerary_data = json.loads(response_text)

        # Pydantic 검증
        itinerary_response = ItineraryResponse2(**itinerary_data)

        logger.info(f"Successfully generated {len(itinerary_response.itinerary)} days")

        return itinerary_response

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {str(e)}")
        raise Exception("Gemini returned invalid JSON")
    except Exception as e:
        logger.error(f"Generation failed: {str(e)}")
        raise
```

---

## PR #3: V2 메인 엔드포인트 구현

### Commit 3-1: main2.py 생성 - FastAPI 앱 설정
**파일**: `main2.py`

**작업 내용**:
```python
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from models.schemas2 import ItineraryRequest2, ItineraryResponse2
from services.itinerary_generator2 import itinerary_generator_service2
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="triB Travel Itinerary API V2",
    description="Gemini 기반 여행 일정 생성 API (간소화 버전)",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Commit 3-2: main2.py - 엔드포인트 구현
**파일**: `main2.py` (계속)

**작업 내용**:
```python
@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "triB V2 API is running", "version": "2.0.0"}

@app.post("/api/v2/itinerary/generate", response_model=ItineraryResponse2)
async def generate_itinerary_v2(request: ItineraryRequest2):
    """
    V2 여행 일정 생성 엔드포인트

    Args:
        request: 장소 이름 리스트 및 사용자 요청 (채팅 포함)

    Returns:
        생성된 여행 일정
    """
    try:
        logger.info(
            f"V2 request: {len(request.places)} places, {request.user_request.days} days"
        )
        logger.info(f"Chat messages: {len(request.user_request.chat)}")

        # Gemini로 일정 생성
        itinerary = await itinerary_generator_service2.generate_itinerary(
            request.places,
            request.user_request,
        )

        logger.info(
            f"Successfully generated V2 itinerary with {len(itinerary.itinerary)} days"
        )

        return itinerary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"V2 generation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main2:app", host="0.0.0.0", port=8001, reload=True)
```

**특징**:
- 포트 8001 사용 (V1은 8000)
- DB, 임베딩, 클러스터링, 라우팅 서비스 모두 제거
- 단순히 `itinerary_generator_service2.generate_itinerary()` 호출

---

## PR #4: 테스트 및 검증

### Commit 4-1: test_e2e_itinerary2.py 생성
**파일**: `tests/test_e2e_itinerary2.py`

**작업 내용**:
```python
import pytest
from httpx import AsyncClient
from main2 import app

@pytest.mark.asyncio
async def test_itinerary_generation_v2_e2e():
    """V2 일정 생성 E2E 테스트"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        request_data = {
            "places": [
                "오사카텐만구 (오사카 천만궁)",
                "신사이바시스지",
                "오사카 성",
                "도톤보리",
                "해유관",
                "유니버설 스튜디오 재팬",
                # ... 요구사항의 예시 장소들
            ],
            "user_request": {
                "chat": [
                    "오사카엔 뭐가 유명하대?",
                    "오사카가면 무조건 유니버설 스튜디오 가야돼",
                    # ... 요구사항의 예시 채팅들
                ],
                "rule": [
                    "오사카가면 무조건 유니버설 스튜디오 가야돼",
                    "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
                    "둘째 날은 유니버설 하루 종일이지?",
                ],
                "days": 3,
                "start_date": "2025-10-15",
                "preferences": {
                    "must_visit": ["유니버설 스튜디오 재팬", "해유관"],
                    "accommodation": None,  # Gemini가 추천
                    "travel_mode": "DRIVE"
                }
            }
        }

        response = await client.post("/api/v2/itinerary/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # 검증
        assert "itinerary" in data
        assert len(data["itinerary"]) == 3  # 3일

        for day in data["itinerary"]:
            assert "day" in day
            assert "visits" in day
            assert len(day["visits"]) > 0

            for visit in day["visits"]:
                # 필수 필드 검증
                assert "order" in visit
                assert "display_name" in visit
                assert "latitude" in visit
                assert "longitude" in visit
                assert "visit_time" in visit
                assert "travel_time" in visit

                # travel_time은 마지막 방문지만 0
                if visit["order"] == len(day["visits"]):
                    assert visit["travel_time"] == 0
                else:
                    assert visit["travel_time"] > 0

        # must_visit 포함 확인
        all_visits = []
        for day in data["itinerary"]:
            all_visits.extend([v["display_name"] for v in day["visits"]])

        assert "유니버설 스튜디오 재팬" in all_visits
        assert "해유관" in all_visits

        print("V2 E2E test passed!")
```

---

### Commit 4-2: README 업데이트
**파일**: `README.md` (기존 파일 수정)

**작업 내용**:
```markdown
# triB Travel Itinerary API

## 버전

### V1 (기존)
- Google Maps API 기반
- 클러스터링 및 이동시간 매트릭스 계산
- 포트: 8000
- 엔드포인트: `/api/itinerary/generate`

### V2 (신규) ✨
- Gemini 중심 설계
- 장소 이름만으로 일정 생성
- 채팅 분석 기반
- 장소/숙소 자동 추천
- 포트: 8001
- 엔드포인트: `/api/v2/itinerary/generate`

## V2 사용법

### 요청 예시
{요구사항의 JSON 예시}

### 응답 예시
{요구사항의 응답 JSON 예시}

### 실행 방법
```bash
# V2 서버 실행
python main2.py

# 테스트
pytest tests/test_e2e_itinerary2.py -v
```

## V1 vs V2 비교

| 기능 | V1 | V2 |
|-----|----|----|
| 입력 | Place ID | 장소 이름 |
| DB 조회 | O | X |
| 클러스터링 | O | X |
| 이동시간 계산 | Google Routes API | Gemini 추론 |
| 장소 추천 | X | O |
| 숙소 추천 | X | O |
| 채팅 분석 | X | O |
```

---

## 작업 순서 요약

1. **PR #1**: 스키마 정의
   - Commit 1-1: 요청 스키마 (schemas2.py)
   - Commit 1-2: 응답 스키마 (schemas2.py 계속)

2. **PR #2**: 일정 생성 서비스
   - Commit 2-1: 기본 구조 (itinerary_generator2.py)
   - Commit 2-2: 프롬프트 함수 (itinerary_generator2.py)
   - Commit 2-3: 프롬프트 상세 (itinerary_generator2.py)
   - Commit 2-4: 일정 생성 구현 (itinerary_generator2.py)

3. **PR #3**: 엔드포인트 구현
   - Commit 3-1: FastAPI 앱 (main2.py)
   - Commit 3-2: 엔드포인트 (main2.py)

4. **PR #4**: 테스트 및 문서
   - Commit 4-1: E2E 테스트 (test_e2e_itinerary2.py)
   - Commit 4-2: README 업데이트

---

## 핵심 설계 포인트

### 1. 파일 명명 규칙
- 모든 새 파일에 `2` 접미사 붙임
- 기존 파일은 절대 수정하지 않음

### 2. 의존성 제거
V2에서 사용하지 않는 서비스:
- `database.py` (DB 조회 불필요)
- `embedding.py` (유사도 계산 불필요)
- `clustering.py` (클러스터링 불필요)
- `routes_matrix.py` (이동시간 API 불필요)

V2에서 사용하는 것:
- `config.py` (Google API 키)
- `models/schemas2.py` (새로 생성)
- `services/itinerary_generator2.py` (새로 생성)

### 3. Gemini 프롬프트 전략
- **채팅 분석**: 전체 대화 내용을 컨텍스트로 제공
- **장소 추천**: "places에 없으면 직접 찾아서 추가" 명시
- **숙소 추천**: "accommodation이 null이면 추천" 명시
- **이동시간**: "DRIVE 기준 40-60km/h로 추론" 가이드라인 제공
- **출력 강제**: `response_mime_type="application/json"` 사용

### 4. 응답 형식 차이
V1:
```json
{
  "order": 1,
  "google_place_id": "ChIJ...",
  "duration_minutes": 90,
  "place_tag": "LANDMARK"
}
```

V2:
```json
{
  "order": 1,
  "display_name": "오사카 성",
  "latitude": 34.6873,
  "longitude": 135.5262,
  "visit_time": "10:00",
  "travel_time": 25
}
```

### 5. 에러 핸들링
- JSON 파싱 실패 시 명확한 에러 메시지
- Gemini API 오류 시 재시도 로직 (선택사항)
- 로깅 강화 (프롬프트 길이, 응답 길이 등)

---

## 예상 결과

### 입력
```json
{
  "places": ["오사카 성", "도톤보리", "유니버설 스튜디오 재팬", "해유관"],
  "user_request": {
    "chat": ["첫날은 가볍게", "유니버설 하루 종일", "마지막날 아쿠아리움"],
    "rule": ["첫날은 오사카성만", "둘째날 유니버설 하루종일"],
    "days": 3,
    "start_date": "2025-10-15",
    "preferences": {
      "must_visit": ["유니버설 스튜디오 재팬", "해유관"],
      "accommodation": null,
      "travel_mode": "DRIVE"
    }
  }
}
```

### 출력
```json
{
  "itinerary": [
    {
      "day": 1,
      "visits": [
        {
          "order": 1,
          "display_name": "오사카 성",
          "latitude": 34.6873,
          "longitude": 135.5262,
          "visit_time": "10:00",
          "travel_time": 20
        },
        {
          "order": 2,
          "display_name": "도톤보리",
          "latitude": 34.6686,
          "longitude": 135.5008,
          "visit_time": "14:00",
          "travel_time": 15
        },
        {
          "order": 3,
          "display_name": "난바 게스트하우스 (Gemini 추천 숙소)",
          "latitude": 34.6659,
          "longitude": 135.5019,
          "visit_time": "19:00",
          "travel_time": 0
        }
      ]
    },
    {
      "day": 2,
      "visits": [
        {
          "order": 1,
          "display_name": "유니버설 스튜디오 재팬",
          "latitude": 34.6654,
          "longitude": 135.4321,
          "visit_time": "09:00",
          "travel_time": 25
        },
        {
          "order": 2,
          "display_name": "난바 게스트하우스",
          "latitude": 34.6659,
          "longitude": 135.5019,
          "visit_time": "21:00",
          "travel_time": 0
        }
      ]
    },
    {
      "day": 3,
      "visits": [
        {
          "order": 1,
          "display_name": "해유관",
          "latitude": 34.6547,
          "longitude": 135.4290,
          "visit_time": "10:00",
          "travel_time": 10
        },
        {
          "order": 2,
          "display_name": "간사이 국제공항 (Gemini 추가)",
          "latitude": 34.4347,
          "longitude": 135.2441,
          "visit_time": "15:00",
          "travel_time": 0
        }
      ]
    }
  ]
}
```

---

## 주의사항

1. **기존 파일 보호**: V1 파일들은 절대 수정하지 않음
2. **포트 분리**: V1(8000), V2(8001)
3. **Gemini 의존성**: V2는 완전히 Gemini에 의존하므로 API 키 필수
4. **프롬프트 최적화**: 초기 버전 후 프롬프트 지속 개선 필요
5. **좌표 정확도**: Gemini가 추론한 좌표는 실제와 다를 수 있음 (향후 개선)

---

## 향후 개선 사항 (V3?)

1. Gemini가 추천한 장소의 좌표를 Google Places API로 검증
2. 이동시간을 Google Routes API로 재계산 (옵션)
3. 프롬프트 A/B 테스트
4. 사용자 피드백 기반 프롬프트 개선
5. 다국어 지원

---

**총 커밋 수**: 9개 (스키마 2 + 서비스 4 + 엔드포인트 2 + 테스트 1)
**총 PR 수**: 4개
**예상 소요 시간**: 8-12시간
