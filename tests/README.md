# E2E Tests for triB Travel Itinerary API

이 디렉토리에는 일정 생성 API에 대한 End-to-End 테스트가 포함되어 있습니다.

## 테스트 개요

### `test_e2e_itinerary.py`

일정 생성 API의 종합적인 E2E 테스트로, 다음을 검증합니다:

1. **API 응답 검증**
   - 200 OK 상태 코드 확인
   - 응답 구조가 올바른지 확인 (itinerary, visits 등)

2. **이동시간 검증**
   - 실제 Google Routes API를 호출하여 이동시간 계산
   - 응답에 포함된 일정 간 시간 간격과 실제 이동시간 비교
   - 15분 이내 오차 허용

3. **일정 논리 검증**
   - 일차가 순서대로 정렬되어 있는지 확인
   - 방문 시간이 순서대로 증가하는지 확인
   - Must-visit 장소가 모두 포함되었는지 확인

4. **마크다운 보고서 생성**
   - 테스트 실행 후 자동으로 마크다운 보고서 생성
   - 각 검증 항목에 대한 상세한 결과 포함
   - 이동시간 비교 상세 내역 포함

## 사전 요구사항

1. **API 서버 실행**
   ```bash
   python main.py
   ```
   서버가 `http://localhost:8000`에서 실행되어야 합니다.

2. **환경 변수 설정**
   `.env` 파일에 다음 설정이 필요합니다:
   ```
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key
   DB_HOST=your_db_host
   DB_PORT=3306
   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   ```

3. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

## 테스트 실행

### pytest로 실행 (권장)

```bash
# 기본 실행
pytest tests/test_e2e_itinerary.py

# 상세 출력
pytest tests/test_e2e_itinerary.py -v

# 출력 캡처 없이 실행 (print문 확인)
pytest tests/test_e2e_itinerary.py -v -s

# 특정 테스트만 실행
pytest tests/test_e2e_itinerary.py::test_itinerary_generation_e2e
```

### Python으로 직접 실행

```bash
python tests/test_e2e_itinerary.py
```

## 테스트 결과

테스트 실행 후 루트 디렉토리에 `test_report_YYYYMMDD_HHMMSS.md` 형식의 마크다운 보고서가 생성됩니다.

### 보고서 구조

```markdown
# E2E Test Report: Itinerary Generation API

## 1. API Request
- API 호출 결과 및 상태 코드
- 응답 구조 샘플

## 2. Response Structure Validation
- 필수 필드 존재 여부
- 일정 일수 확인
- 각 일차별 구조 검증

## 3. Travel Time Validation
- 연속된 장소 간 이동시간 검증
- 실제 Google API 결과와 비교
- 15분 허용 오차 내 정확도 측정

## 4. Itinerary Logic Validation
- 일차 순서 검증
- 시간 순서 검증
- Must-visit 장소 포함 여부

## 5. Test Summary
- 전체 테스트 통계
- Pass/Fail 비율
- 최종 결과
```

## 예상 실행 시간

- 전체 테스트: 약 2-3분
  - API 일정 생성: 약 1-2분
  - 이동시간 검증 (Google API 호출): 약 30-60초

## 주의사항

1. **타임아웃**: API 응답이 늦을 수 있으므로 테스트 타임아웃이 600초(10분)로 설정되어 있습니다.

2. **Google API 할당량**: 이동시간 검증 시 Google Routes API를 호출하므로, API 할당량에 주의하세요.

3. **Rate Limiting**: 연속된 Google API 호출 사이에 0.5초 딜레이가 있습니다.

4. **데이터베이스**: 테스트 페이로드에 포함된 장소 ID들이 데이터베이스에 존재해야 합니다.

## 테스트 커스터마이징

`ItineraryE2ETest` 클래스의 `test_payload`를 수정하여 다른 장소나 조건으로 테스트할 수 있습니다:

```python
self.test_payload = {
    "places": ["ChIJ...", "ChIJ...", ...],  # 테스트할 장소 ID 리스트
    "user_request": {
        "query": "...",
        "days": 3,
        "start_date": "2025-10-15",
        "preferences": {
            "must_visit": ["ChIJ...", "ChIJ..."],
            "accommodation": "ChIJ...",
            "travel_mode": "DRIVE"  # DRIVE, TRANSIT, WALK, BICYCLE
        }
    }
}
```

## 트러블슈팅

### API 타임아웃
```
httpcore.ReadTimeout
```
- API 서버가 응답하는데 시간이 오래 걸리는 경우
- `AsyncClient(timeout=600.0)`의 timeout 값을 늘려보세요

### Google API 에러
```
Failed to validate travel time
```
- Google Maps API 키 확인
- API 할당량 확인
- 네트워크 연결 확인

### 데이터베이스 에러
```
No places found
```
- 테스트 페이로드의 장소 ID들이 DB에 존재하는지 확인
- DB 연결 설정 확인
