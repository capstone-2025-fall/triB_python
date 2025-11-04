# triB FastAPI V2 Deployment Guide

이 문서는 FastAPI V2 애플리케이션을 AWS EC2에 배포하는 방법을 설명합니다.

## 목차
- [사전 준비](#사전-준비)
- [EC2 서버 초기 설정](#ec2-서버-초기-설정)
- [GitHub Secrets 설정](#github-secrets-설정)
- [로컬에서 Docker 테스트](#로컬에서-docker-테스트)
- [자동 배포 (GitHub Actions)](#자동-배포-github-actions)
- [수동 배포](#수동-배포)
- [Spring Boot 연동](#spring-boot-연동)
- [트러블슈팅](#트러블슈팅)

---

## 사전 준비

### 필수 항목
- AWS EC2 인스턴스 (Ubuntu 22.04 이상)
- EC2 SSH 키 파일 (`triB-server-key.pem`)
- Google API 키 (Gemini, Maps API)
- Docker 및 Docker Compose 설치
- GitHub 저장소 액세스 권한

### EC2 정보
- **호스트**: `ec2-13-209-232-107.ap-northeast-2.compute.amazonaws.com`
- **IP**: `13.209.232.107`
- **포트**: `8000`
- **사용자**: `ubuntu`
- **접속 명령어**:
  ```bash
  ssh -i "triB-server-key.pem" ubuntu@ec2-13-209-232-107.ap-northeast-2.compute.amazonaws.com
  ```

---

## EC2 서버 초기 설정

### 1. EC2 인스턴스 접속
```bash
ssh -i "triB-server-key.pem" ubuntu@ec2-13-209-232-107.ap-northeast-2.compute.amazonaws.com
```

### 2. 시스템 업데이트
```bash
sudo apt update && sudo apt upgrade -y
```

### 3. Docker 설치
```bash
# Docker 설치
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Docker Compose 설치
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 재로그인 필요 (또는 newgrp docker)
newgrp docker
```

### 4. Git 설치 및 저장소 클론
```bash
sudo apt install -y git
cd /home/ubuntu
git clone https://github.com/your-username/triB_python.git
cd triB_python
```

### 5. .env 파일 생성 (GitHub Actions가 자동으로 생성하지만, 수동 배포 시 필요)
```bash
nano .env
```

다음 내용 입력:
```env
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
DBSCAN_EPS_KM=7.0
DBSCAN_MIN_SAMPLES=2
```

### 6. 인바운드 규칙 확인
EC2 보안 그룹에서 다음 포트가 열려있는지 확인:
- **포트 8000**: FastAPI 애플리케이션
- **포트 22**: SSH 접속

---

## GitHub Secrets 설정

GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 secrets를 추가하세요:

### API 키
- `GOOGLE_API_KEY`: Google Gemini API 키
- `GOOGLE_MAPS_API_KEY`: Google Maps API 키

### DBSCAN 파라미터
- `DBSCAN_EPS_KM`: `7.0`
- `DBSCAN_MIN_SAMPLES`: `2`

### EC2 접속 정보
- `EC2_HOST`: `13.209.232.107`
- `EC2_USER`: `ubuntu`
- `EC2_SSH_KEY`: SSH 개인 키 전체 내용 (triB-server-key.pem 파일의 내용)
  ```
  -----BEGIN RSA PRIVATE KEY-----
  (키 내용)
  -----END RSA PRIVATE KEY-----
  ```

---

## 로컬에서 Docker 테스트

배포 전에 로컬에서 Docker 컨테이너가 정상 작동하는지 테스트하세요:

### 1. .env 파일 생성
```bash
cp .env.example .env
# .env 파일을 편집하여 실제 API 키 입력
```

### 2. Docker 이미지 빌드
```bash
docker-compose build
```

### 3. 컨테이너 실행
```bash
docker-compose up -d
```

### 4. 로그 확인
```bash
docker-compose logs -f
```

### 5. Health Check
```bash
curl http://localhost:8000/
```

**예상 응답:**
```json
{
  "status": "ok",
  "message": "triB V2 API is running",
  "version": "2.0.0"
}
```

### 6. API 테스트
```bash
curl -X POST http://localhost:8000/api/v2/itinerary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "places": ["경복궁", "명동", "남산타워"],
    "days": 1,
    "members": 2,
    "country": "대한민국",
    "chat": []
  }'
```

### 7. 컨테이너 중지
```bash
docker-compose down
```

---

## 자동 배포 (GitHub Actions)

### 배포 트리거
`main` 브랜치에 푸시하면 자동으로 배포가 시작됩니다:

```bash
git add .
git commit -m "Deploy FastAPI V2"
git push origin main
```

### 배포 과정
1. GitHub Actions가 코드를 체크아웃
2. EC2에 SSH 연결
3. `.env` 파일 생성 (GitHub Secrets 사용)
4. 저장소에서 최신 코드 pull
5. `scripts/deploy.sh` 실행
6. Docker 이미지 빌드 및 컨테이너 시작
7. Health Check 수행

### 배포 상태 확인
- GitHub 저장소의 **Actions** 탭에서 배포 로그 확인
- 녹색 체크마크: 배포 성공
- 빨간색 X: 배포 실패 (로그를 확인하여 원인 파악)

### 수동 배포 트리거
GitHub Actions 탭에서 **Deploy to EC2** 워크플로우를 선택하고 **Run workflow** 버튼 클릭

---

## 수동 배포

자동 배포가 작동하지 않거나 긴급 배포가 필요한 경우:

### 1. EC2 접속
```bash
ssh -i "triB-server-key.pem" ubuntu@ec2-13-209-232-107.ap-northeast-2.compute.amazonaws.com
```

### 2. 애플리케이션 디렉토리로 이동
```bash
cd /home/ubuntu/triB_python
```

### 3. 최신 코드 가져오기
```bash
git pull origin main
```

### 4. 배포 스크립트 실행
```bash
bash scripts/deploy.sh
```

### 5. 상태 확인
```bash
docker-compose ps
docker-compose logs --tail=50
curl http://localhost:8000/
```

---

## Spring Boot 연동

### FastAPI 엔드포인트
- **Base URL**: `http://13.209.232.107:8000`
- **일정 생성**: `POST /api/v2/itinerary/generate`
- **Health Check**: `GET /`

### Spring Boot에서 호출 예시 (Java)

```java
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

public class ItineraryService {

    private static final String FASTAPI_URL = "http://13.209.232.107:8000/api/v2/itinerary/generate";

    public ItineraryResponse generateItinerary(ItineraryRequest request) {
        RestTemplate restTemplate = new RestTemplate();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<ItineraryRequest> entity = new HttpEntity<>(request, headers);

        ResponseEntity<ItineraryResponse> response = restTemplate.exchange(
            FASTAPI_URL,
            HttpMethod.POST,
            entity,
            ItineraryResponse.class
        );

        return response.getBody();
    }
}
```

### CORS 설정
FastAPI는 다음 Origin을 허용합니다:
- `http://localhost:8080` (로컬 개발)
- `http://13.209.157.80:8080` (프로덕션 Spring Boot 서버)

---

## 트러블슈팅

### 1. 포트 8000이 이미 사용 중
```bash
# 실행 중인 컨테이너 확인
docker ps

# 컨테이너 중지
docker-compose down

# 포트를 사용하는 프로세스 확인
sudo lsof -i :8000

# 프로세스 종료
sudo kill -9 <PID>
```

### 2. Docker 권한 오류
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 3. Git pull 실패
```bash
# 로컬 변경사항 제거
git reset --hard HEAD
git pull origin main
```

### 4. API 키 오류
```bash
# .env 파일 확인
cat .env

# .env 파일 재생성
nano .env
```

### 5. 컨테이너가 시작되지 않음
```bash
# 로그 확인
docker-compose logs --tail=100

# 이미지 재빌드
docker-compose build --no-cache
docker-compose up -d
```

### 6. Health Check 실패
```bash
# 컨테이너 내부 접속
docker exec -it trib-fastapi-v2 bash

# 컨테이너 내부에서 테스트
curl http://localhost:8000/

# Python 프로세스 확인
ps aux | grep python
```

### 7. CORS 오류
`main2.py`의 CORS 설정에 Spring Boot 서버 주소가 포함되어 있는지 확인:
```python
allow_origins=[
    "http://localhost:8080",
    "http://13.209.157.80:8080",
]
```

---

## 유용한 명령어

### Docker 관련
```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 실시간 확인
docker-compose logs -f

# 컨테이너 재시작
docker-compose restart

# 컨테이너 중지 및 삭제
docker-compose down

# 이미지 재빌드
docker-compose build --no-cache

# 디스크 공간 확보 (사용하지 않는 이미지 삭제)
docker system prune -a
```

### 시스템 모니터링
```bash
# CPU 및 메모리 사용량
docker stats

# 디스크 사용량
df -h

# 네트워크 연결 확인
netstat -tuln | grep 8000
```

---

## 배포 완료 확인

배포가 완료되면 다음 URL에서 API가 정상 작동하는지 확인하세요:

- **Health Check**: http://13.209.232.107:8000/
- **API 문서**: http://13.209.232.107:8000/docs
- **Redoc**: http://13.209.232.107:8000/redoc

---

## 참고 자료

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [Docker 공식 문서](https://docs.docker.com/)
- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [AWS EC2 사용 가이드](https://docs.aws.amazon.com/ec2/)

---

**문의사항이나 문제가 발생하면 팀원에게 연락하세요.**
