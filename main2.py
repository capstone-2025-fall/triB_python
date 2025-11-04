import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.schemas2 import ItineraryRequest2, ItineraryResponse2
from services.itinerary_generator2 import itinerary_generator_service2

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="triB Travel Itinerary API V2",
    description="Gemini 기반 여행 일정 생성 API (간소화 버전)",
    version="2.0.0",
)

# CORS 설정
# 로컬 개발 및 프로덕션 서버 주소 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",           # 로컬 개발 환경
        "http://13.209.157.80:8080",       # 프로덕션 Spring Boot 서버
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """
    Health check 엔드포인트

    Returns:
        API 상태 정보
    """
    return {
        "status": "ok",
        "message": "triB V2 API is running",
        "version": "2.0.0"
    }


@app.post("/api/v2/itinerary/generate", response_model=ItineraryResponse2)
async def generate_itinerary_v2(request: ItineraryRequest2):
    """
    V2 여행 일정 생성 엔드포인트

    Args:
        request: 장소 이름 리스트 및 사용자 요청 (채팅 내용 포함)

    Returns:
        생성된 여행 일정

    Raises:
        HTTPException: 일정 생성 실패 시

    Note:
        V1과 달리 DB 조회, 임베딩, 클러스터링, 이동시간 계산 없이
        Gemini가 모든 작업을 수행합니다.
    """
    try:
        # 요청 정보 로깅
        logger.info(
            f"V2 itinerary generation request: "
            f"{len(request.places)} places, {request.days} days, "
            f"{request.members} members, country: {request.country}"
        )
        logger.info(f"Chat messages: {len(request.chat)}")
        logger.debug(f"Places: {request.places}")

        # Gemini로 일정 생성 (단순!)
        itinerary = await itinerary_generator_service2.generate_itinerary(request)

        # 성공 로깅
        logger.info(
            f"Successfully generated V2 itinerary: "
            f"{len(itinerary.itinerary)} days"
        )

        return itinerary

    except HTTPException:
        # HTTPException은 그대로 전파
        raise
    except Exception as e:
        # 일반 예외는 로깅 후 500 에러로 변환
        logger.error(f"V2 itinerary generation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting triB V2 API server on port 8000...")
    uvicorn.run("main2:app", host="0.0.0.0", port=8000, reload=True)
