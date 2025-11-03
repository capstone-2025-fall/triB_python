# 일정 생성 프롬프트 완전 재작성 계획 - V2 시스템

## 개요
**PR #1, #2, #3, #4, #5, #6 완료됨** ✅

기존 3단계 우선순위 시스템을 **5단계 우선순위 시스템**으로 전면 재작성 완료!
travel_time 검증 로직 추가 완료!

### 주요 변경사항
- **5단계 우선순위 시스템** 도입 (기존 3단계 → 5단계)
- **숙소 중심 일정** 강화 (HOME 태그 활용)
- **Gemini 장소 추천** 활성화 (places 후보에 없을 경우)
- **하루 일정 10-12시간** 제약 추가
- **첫/마지막 travel_time 정의** 명확화

---

## 새로운 5단계 우선순위 시스템

### 🔴 Priority 1: 사용자 요청사항 준수 (MANDATORY - 100%)
- 여행 일수(days) 정확히 준수
- 여행 시작일(start_date) 정확히 준수
- 필수 방문 장소(must_visit) 100% 포함
- 규칙(rule) 100% 준수
- 대화 내용(chat) 분석하여 사용자 취향 반영
- 후보 장소(places) 우선 선택, 부족 시 Gemini가 추천

### 🟠 Priority 2: 운영시간 준수 (HIGHLY RECOMMENDED - 90%+)
- 모든 장소는 운영시간 내에만 방문
- 운영시간 없는 요일 방문 금지
- 이동시간 고려하여 운영시간 내 도착
- Google Maps Grounding Tool 활용 필수
- 교통수단 chat에서 추론 (기본값: transit)

### 🟡 Priority 3: 맥락적 순서 배치 (RECOMMENDED - 80%+)
- 체류시간 적절성
- 방문 시간대 적절성 (식사시간 고려)
- 자연스러운 활동 흐름

### 🟢 Priority 4: 효율적인 동선 (OPTIMIZATION - Best Effort)
- 이동시간 최소화
- 효율적인 동선 구성

### 🔵 Priority 5: 평점 우선 선택 (NICE TO HAVE - Best Effort)
- 평점 높은 장소 방문

### 제약사항
- 하루 일정은 기본적으로 **10-12시간**
- 숙소(HOME) 출발/귀가 원칙
- HOME 없을 시 Gemini가 적절한 숙소 추천 및 포함

---

## PR #4: 5단계 우선순위 프롬프트 전면 재작성 ✅

**목표**: 기존 프롬프트를 완전히 제거하고 새로운 5단계 우선순위 시스템 기반으로 재작성

### Commit 4.1: 프롬프트 구조 초기화 및 5단계 우선순위 헤더 작성 ✅
- **커밋**: ed74a7c
- **변경사항**: 기존 3단계 → 5단계 우선순위 시스템 헤더 작성
- **상태**: 완료

### Commit 4.2: Priority 1 - 사용자 요청사항 준수 섹션 작성 ✅
- **커밋**: d161a84
- **변경사항**: 1-A ~ 1-E 상세 섹션 추가 (days, must_visit, rule, chat, places)
- **상태**: 완료

### Commit 4.3: Priority 2 - 운영시간 및 이동시간 준수 섹션 작성 ✅
- **커밋**: 8c8efd2
- **변경사항**: 운영시간 준수, travel_time 계산 규칙 명확화
- **상태**: 완료

### Commit 4.4: Priority 3 - 맥락적 순서 배치 섹션 작성 ✅
- **커밋**: 56797a7
- **변경사항**: 체류시간, 방문 시간대, 활동 흐름 가이드라인
- **상태**: 완료

### Commit 4.5: Priority 4-5 및 제약사항 섹션 작성 ✅
- **커밋**: 18b3bef
- **변경사항**: 동선 최적화, 평점 선택, 10-12시간 제약, HOME 출발/귀가
- **상태**: 완료

### Commit 4.6: 숙소(HOME) 처리 로직 섹션 작성 ✅
- **커밋**: bf0b8a6
- **변경사항**: HOME 태그 식별, 추천 기준 상세화
- **상태**: 완료

### Commit 4.7: Google Maps Grounding 활용 가이드 섹션 작성 ✅
- **커밋**: da811fc
- **변경사항**: 필수 정보 조회, 교통수단 매핑, 사용 예시
- **상태**: 완료

### Commit 4.8: 출력 형식(Output Format) 섹션 재작성 ✅
- **커밋**: 6d2ceb6
- **변경사항**: JSON 필드 상세 설명, travel_time 정의, 예시 JSON
- **상태**: 완료

### Commit 4.9: 검증 체크리스트 및 최종 지침 작성 ✅
- **커밋**: 512d049
- **변경사항**: Gemini 자체 검증 체크리스트, 순수 JSON 출력 요구
- **상태**: 완료

### Commit 4.10: E2E 테스트 실행 및 프롬프트 검증 ✅
- **커밋**: 1be7983
- **변경사항**: 프롬프트 구조 검증, 검증 보고서 생성
- **파일**: `test_prompt_validation.py`, `PROMPT_VALIDATION_REPORT.md`
- **검증 결과**:
  - ✅ 총 1,180줄 (프롬프트 ~870줄, 기존 대비 +470줄)
  - ✅ 12개 주요 섹션 모두 확인
  - ✅ Priority 언급 20회 확인
  - ✅ 핵심 원칙 명시됨
- **상태**: 완료

---

## PR #5: 숙소(HOME) 추천 기능 강화 ✅

**목표**: HOME 없을 때 Gemini가 적절한 숙소를 추천하고 일정에 자동 포함

### Commit 5.1: 숙소 추천 프롬프트 상세화 ✅
- **커밋**: 027aa0d
- **파일**: `services/itinerary_generator2.py`
- **변경사항**:
  - HOME 없을 경우 숙소 추천 섹션 대폭 강화:
    - chat에서 예산/위치 선호도 명시적 추론 가이드 추가
    - 여행지 중심부/교통 허브 추천 기준 상세화 (평균 이동시간, 대중교통 접근성)
    - Google Maps 검색 쿼리 작성 예시 및 평점/리뷰 기준 제시
    - 필수 조회 정보 및 검증 절차 명시
    - 추천 이유 내부 로직 기록 (응답에는 미포함)
    - 2개의 상세 예시 추가 (오사카, 도쿄)
- **상태**: 완료

### Commit 5.2: 숙소 왕복 예외사항 프롬프트 추가 ✅
- **커밋**: 027aa0d (동일 커밋)
- **파일**: `services/itinerary_generator2.py`
- **변경사항**:
  - 숙소 출발/귀가 예외 케이스 우선순위 명확화:
    - rule 필드의 명시적 지시 (최우선)
    - chat의 명시적 요청 (차순위)
    - 기본 원칙 (숙소 왕복) (기본값)
  - 예외 케이스별 인식 패턴 및 예시 추가
  - 예외 적용 가이드라인 상세화 (부분 예외, 모호한 케이스 처리)
  - 3개의 상세 예시 추가 (rule 기반, chat 기반, 기본 원칙)
- **상태**: 완료

---

## PR #6: travel_time 계산 로직 명확화 및 검증 강화 ✅

**목표**: travel_time 필드의 정의를 명확히 하고 검증 로직 추가

### Commit 6.1-6.2: travel_time 검증 함수 추가 및 validate_all 통합 ✅
- **커밋**: 860a6ae
- **파일**: `services/validators.py`, `tests/test_validators.py`
- **변경사항**:
  - `validate_travel_time()` 함수 추가:
    - 마지막 visit의 travel_time = 0 검증
    - 중간 visit들의 travel_time > 0 권장 (0이면 suspicious)
    - 위반 사항 상세 정보 반환
  - `validate_all()` 함수에 travel_time 검증 통합
  - 7개의 단위 테스트 추가:
    - test_validate_travel_time_all_correct
    - test_validate_travel_time_last_visit_nonzero
    - test_validate_travel_time_middle_visit_zero
    - test_validate_travel_time_multiple_days
    - test_validate_travel_time_multiple_violations
    - test_validate_travel_time_empty_itinerary
    - test_validate_travel_time_single_visit
  - validate_all() 테스트 업데이트 (travel_time 검증 포함)
  - sample_itinerary fixture 수정 (올바른 travel_time 값)
- **테스트 결과**: 35/35 통과 ✅
- **상태**: 완료

### Commit 6.3: E2E 테스트에 travel_time 검증 명시적 추가 ✅
- **커밋**: 860a6ae (동일 커밋)
- **파일**: `tests/test_e2e_itinerary2.py`
- **변경사항**:
  - validate_travel_time() import 추가
  - operating hours 검증 후 travel_time 검증 추가:
    - 총 방문지 수 출력
    - 위반 사항 상세 표시 (day, place, order, issue)
    - 검증 결과 (PASS/FAIL)
  - validate_all() 호출에 travel_time 검증 자동 포함
- **테스트 결과**: E2E 테스트 통과 (101.44초) ✅
- **상태**: 완료

---

## PR #7: 하루 일정 10-12시간 제약 검증

**목표**: 하루 일정이 10-12시간 범위 내인지 검증

### Commit 7.1: 하루 일정 시간 계산 유틸리티 추가
- **파일**: `services/validators.py`
- **변경사항**:
  - `calculate_daily_duration()` 함수 추가:
    ```python
    def calculate_daily_duration(day: DayItinerary2) -> float:
        """하루 일정의 총 시간 계산 (시간 단위)"""
        if len(day.visits) == 0:
            return 0.0

        first_arrival = parse_time(day.visits[0].arrival)
        last_departure = parse_time(day.visits[-1].departure)

        duration = (last_departure - first_arrival).total_seconds() / 3600
        return duration
    ```
- **상태**: 대기 중

### Commit 7.2: 하루 일정 시간 검증 함수 추가
- **파일**: `services/validators.py`
- **변경사항**:
  - `validate_daily_duration()` 함수 추가:
    ```python
    def validate_daily_duration(itinerary: ItineraryResponse2,
                                min_hours=10, max_hours=12) -> dict:
        """하루 일정이 10-12시간 범위 내인지 검증"""
        violations = []
        for day in itinerary.itinerary:
            duration = calculate_daily_duration(day)
            if duration < min_hours or duration > max_hours:
                violations.append({
                    "day": day.day,
                    "duration": round(duration, 1),
                    "expected_range": f"{min_hours}-{max_hours}시간"
                })

        return {"is_valid": len(violations) == 0, "violations": violations}
    ```
- **테스트**: 단위 테스트 추가
- **상태**: 대기 중

### Commit 7.3: validate_all에 일정 시간 검증 통합 (경고 수준)
- **파일**: `services/validators.py`
- **변경사항**:
  - `validate_all()`에 `validate_daily_duration()` 추가
  - 단, 이 검증은 경고(warning) 수준으로 처리 (재시도 트리거 안 함)
  - 검증 결과에 `severity: "warning"` 추가
- **상태**: 대기 중

---

## 구현 순서

1. **PR #4** (핵심) ✅ - 5단계 우선순위 프롬프트 전면 재작성
2. **PR #5** (기능 강화) ✅ - 숙소 추천 기능 강화
3. **PR #6** (검증) ✅ - travel_time 검증 강화
4. **PR #7** (검증) - 하루 일정 시간 검증

---

## 각 작업별 예상 소요 시간

### PR #4: 프롬프트 재작성 (약 2-3시간)
- Commit 4.1-4.9: 프롬프트 작성 (90분)
- Commit 4.10: 테스트 및 검증 (60분)

### PR #5: 숙소 추천 강화 (약 30분)
- Commit 5.1-5.2: 프롬프트 추가 (30분)

### PR #6: travel_time 검증 (약 1시간)
- Commit 6.1-6.3: 검증 함수 및 테스트 (60분)

### PR #7: 일정 시간 검증 (약 1시간)
- Commit 7.1-7.3: 계산/검증 함수 및 테스트 (60분)

**총 예상 소요 시간: 약 4.5-5.5시간**

---

## 성공 기준

### PR #4 검증 기준
- [ ] 5단계 우선순위가 프롬프트에 명확히 표현됨
- [ ] 기존 E2E 테스트 모두 통과
- [ ] 생성된 일정이 days, must_visit, rule 준수
- [ ] HOME 태그 장소가 일정에 적절히 배치됨

### PR #5 검증 기준
- [ ] HOME 없는 요청에 대해 Gemini가 숙소 추천
- [ ] 추천된 숙소가 일정 첫/마지막 방문에 포함
- [ ] 숙소 정보(좌표, 주소)가 정확함

### PR #6 검증 기준
- [x] travel_time 검증 단위 테스트 통과
- [x] 마지막 방문의 travel_time이 0임을 검증
- [x] E2E 테스트에 travel_time 검증 통합

### PR #7 검증 기준
- [ ] 하루 일정 시간 계산 정확함
- [ ] 10-12시간 범위 검증 작동
- [ ] 경고 수준으로 처리되어 재시도 트리거 안 함

---

## 이전 완료된 작업 (PR #1-3)

### PR #1: 프롬프트 개선 - 운영시간 & 이동시간 강제 적용 ✅
- Commit 1.1: 운영시간 준수 프롬프트 강화
- Commit 1.2: 이동시간 계산 프롬프트 강화
- Commit 1.3: 요일별 운영시간 처리 프롬프트 추가
- Commit 1.4: 프롬프트 통합 및 우선순위 재정렬

### PR #2: 사용자 요청사항 프롬프트 강화 ✅
- Commit 2.1: must_visit 강제 적용 프롬프트 추가
- Commit 2.2: rules 준수 프롬프트 강화
- Commit 2.3: days 및 start_date 준수 프롬프트 강화
- Commit 2.4: chat 및 places 선호도 프롬프트 강화
- Commit 2.5: 전체 우선순위 체계 프롬프트에 명시

### PR #3: 사후 검증 & 재시도 로직 구현 ✅
- Commit 3.1: 사후 검증 유틸리티 추가
- Commit 3.2: 재시도 로직 추가
- Commit 3.3: 검증 실패 시 프롬프트 강화 로직
- Commit 3.4: E2E 테스트 추가
- Commit 3.5: 검증 보고서 생성 개선
