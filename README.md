# triB Travel Itinerary API

AI 기반 여행 일정 생성 API - Gemini를 활용한 스마트 여행 계획 서비스

---

## 📌 버전

### V1 (기존)
- **Google Maps API 기반**: Places API, Routes API 활용
- **클러스터링 및 이동시간 매트릭스 계산**: 지리적 최적화
- **포트**: 8000
- **엔드포인트**: `/api/itinerary/generate`

### V2 (신규) ✨
- **Gemini 중심 설계**: 프롬프트 엔지니어링 기반
- **장소 이름만으로 일정 생성**: Place ID 불필요
- **채팅 분석 기반**: 사용자 대화에서 의도 파악
- **장소/숙소 자동 추천**: Gemini가 필요시 추가 장소 제안
- **포트**: 8001
- **엔드포인트**: `/api/v2/itinerary/generate`

---

## 🚀 V2 사용법

### 요청 예시

```bash
curl -X POST http://localhost:8001/api/v2/itinerary/generate \
  -H "Content-Type: application/json" \
  -d @request.json
```

**request.json**:
```json
{
  "places": [
    "오사카텐만구 (오사카 천만궁)",
    "신사이바시스지",
    "오사카 성",
    "도톤보리",
    "해유관",
    "유니버설 스튜디오 재팬",
    "구로몬 시장",
    "우메다 스카이 빌딩",
    "시텐노지 (사천왕사)",
    "츠텐카쿠"
  ],
  "user_request": {
    "chat": [
      "오사카엔 뭐가 유명하대?",
      "오사카가면 무조건 유니버설 스튜디오 가야돼",
      "해유관도 가보고 싶은데",
      "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
      "둘째날은 유니버설 하루 종일이지?",
      "마지막날은 아침에 일찍 일어나서 여유롭게"
    ],
    "rule": [
      "첫날은 도착하니까 오사카성 정도만 가자. 무리 ㄴㄴ",
      "둘째날은 유니버설 하루 종일이지?",
      "마지막날 아침에 일찍 일어나서 여유롭게"
    ],
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

### 응답 예시

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
          "display_name": "난바 게스트하우스",
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
          "display_name": "간사이 국제공항",
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

### 필드 설명

#### 요청 필드

- **places**: 사용자가 고려 중인 장소 이름 리스트 (장소 ID 아님)
- **chat**: 사용자들이 나눈 대화 내용 배열 (의도 파악용)
- **rule**: 반드시 지켜야 할 규칙 배열
- **days**: 여행 일수
- **start_date**: 여행 시작 날짜 (YYYY-MM-DD)
- **must_visit**: 필수 방문 장소 리스트
- **accommodation**: 숙소 이름 (null이면 Gemini가 추천)
- **travel_mode**: 이동 수단 (DRIVE, TRANSIT, WALK, BICYCLE)

#### 응답 필드

- **order**: 일별 방문 순서 (1부터 시작)
- **display_name**: 장소명
- **latitude**: 위도 (Gemini가 추론)
- **longitude**: 경도 (Gemini가 추론)
- **visit_time**: 방문 시간 (HH:MM 형식)
- **travel_time**: 다음 장소로의 이동시간(분), 마지막 방문지는 0

---

## 📊 V1 vs V2 비교

| 기능 | V1 | V2 |
|-----|----|----|
| **입력** | Place ID | 장소 이름 |
| **DB 조회** | ✅ | ❌ |
| **임베딩 계산** | ✅ | ❌ |
| **클러스터링** | ✅ | ❌ |
| **이동시간 계산** | Google Routes API | Gemini 추론 |
| **장소 추천** | ❌ | ✅ |
| **숙소 추천** | ❌ | ✅ |
| **채팅 분석** | ❌ | ✅ |
| **포트** | 8000 | 8001 |
| **코드 복잡도** | 높음 (~150줄) | 낮음 (~70줄) |
| **서비스 의존성** | 5개 | 1개 |

---

## 💻 실행 방법

### 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에 Google API 키 설정
```

### V1 서버 실행

```bash
python main.py
```

서버 실행 후: http://localhost:8000

### V2 서버 실행

```bash
python main2.py
```

서버 실행 후: http://localhost:8001

### 테스트 실행

```bash
# V1 테스트
pytest tests/test_e2e_itinerary.py -v -s

# V2 테스트
pytest tests/test_e2e_itinerary2.py -v -s

# 모든 테스트
pytest tests/ -v
```

---

## ⚡ V2 주요 특징

### 1. 프롬프트 엔지니어링 중심

V2는 정교한 프롬프트를 통해 Gemini가 모든 작업을 수행합니다:
- 채팅 내용 분석 → 여행 의도 파악
- 장소 목록 검토 → 적절한 장소 선택
- 부족한 장소 → 직접 찾아서 추천 (좌표 포함)
- 숙소 미지정 → 적절한 숙소 추천
- 이동시간 추론 → travel_mode 기준으로 계산

### 2. 극단적 간소화

V1 대비 제거된 컴포넌트:
- ❌ 데이터베이스 조회
- ❌ 임베딩 벡터 계산
- ❌ DBSCAN 클러스터링
- ❌ Google Routes API 호출

V2에서 사용하는 것:
- ✅ Gemini API (단일 호출)
- ✅ Pydantic 검증

### 3. 채팅 기반 의도 파악

사용자들의 대화 내용을 분석하여:
- 선호도 파악 ("타코야키 먹고 싶다" → 구로몬 시장 추천)
- 제약사항 이해 ("첫날은 가볍게" → 방문지 수 조절)
- 패턴 인식 ("유니버설 하루종일" → Day 2 전체를 유니버설로)

### 4. 동적 장소/숙소 추천

- places 리스트에 없는 장소도 필요시 Gemini가 추가
- accommodation이 null이면 여행지에 맞는 숙소 자동 추천
- 위치, 가격대, 접근성을 고려한 추천

---

## ⚠️ 주의사항 및 제약사항

### V2 사용 시 주의사항

1. **Gemini API 키 필수**: `.env` 파일에 Google API 키 설정 필요
2. **좌표 정확도**: Gemini가 추론한 좌표는 실제와 약간 다를 수 있음
3. **이동시간 추정**: 실제 교통 상황과 다를 수 있음 (Routes API 미사용)
4. **응답 시간**: Gemini API 호출 시간이 필요 (보통 5-15초)
5. **프롬프트 의존성**: 결과 품질이 프롬프트에 크게 의존

### 향후 개선 방향

- Gemini 추천 장소의 좌표를 Google Places API로 검증
- 이동시간을 Google Routes API로 재계산 (옵션)
- 프롬프트 A/B 테스트
- 사용자 피드백 기반 프롬프트 개선
- 다국어 지원

---

## 📁 프로젝트 구조

```
triB_python/
├── main.py                          # V1 FastAPI 엔드포인트
├── main2.py                         # V2 FastAPI 엔드포인트
├── config.py                        # 설정 파일
├── models/
│   ├── schemas.py                   # V1 스키마
│   └── schemas2.py                  # V2 스키마
├── services/
│   ├── database.py                  # V1: DB 조회
│   ├── embedding.py                 # V1: 임베딩
│   ├── clustering.py                # V1: 클러스터링
│   ├── routes_matrix.py             # V1: 이동시간 계산
│   ├── itinerary_generator.py      # V1: 일정 생성
│   └── itinerary_generator2.py     # V2: 일정 생성 (Gemini 중심)
└── tests/
    ├── test_e2e_itinerary.py        # V1 E2E 테스트
    └── test_e2e_itinerary2.py       # V2 E2E 테스트
```

---

## 🤝 기여

버그 리포트 및 기능 제안은 이슈로 등록해주세요.

---

## 📄 라이선스

MIT License

---

## 👨‍💻 개발자

triB Team - AI 기반 여행 일정 생성 서비스

**V2 개발**: 2025년 10월
