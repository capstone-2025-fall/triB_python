import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.schemas2 import ItineraryRequest2, ItineraryResponse2
from services.itinerary_generator3 import itinerary_generator_service3

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="triB Travel Itinerary API V3",
    description="Gemini 3 Pro Preview 기반 여행 일정 생성 API (SOTA 추론 능력)",
    version="3.0.0",
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
        "message": "triB V3 API is running (Gemini 3 Pro Preview)",
        "version": "3.0.0",
        "model": "gemini-3-pro-preview"
    }


@app.post("/api/v3/itinerary/generate", response_model=ItineraryResponse2)
async def generate_itinerary_v3(request: ItineraryRequest2):
    """
    V3 여행 일정 생성 엔드포인트 (Gemini 3 Pro Preview)

    Args:
        request: 장소 이름 리스트 및 사용자 요청 (채팅 내용 포함)

    Returns:
        생성된 여행 일정

    Raises:
        HTTPException: 일정 생성 실패 시

    Note:
        Gemini 3 Pro Preview의 SOTA 추론 능력과 향상된 멀티모달 이해를 활용하여
        복잡한 제약 조건과 다일 일정도 정확하게 생성합니다.
        DB 조회, 임베딩, 클러스터링 없이 Gemini가 모든 작업을 수행합니다.
    """
    try:
        # 요청 정보 로깅
        logger.info(
            f"V3 itinerary generation request: "
            f"{len(request.places)} places, {request.days} days, "
            f"{request.members} members, country: {request.country}"
        )
        logger.info(f"Chat messages: {len(request.chat)}")
        logger.debug(f"Places: {request.places}")

        # Gemini로 일정 생성 (단순!)
        itinerary = await itinerary_generator_service3.generate_itinerary(request)

        # 성공 로깅
        logger.info(
            f"Successfully generated V3 itinerary: "
            f"{len(itinerary.itinerary)} days"
        )

        return itinerary

    except HTTPException:
        # HTTPException은 그대로 전파
        raise
    except Exception as e:
        # 일반 예외는 로깅 후 500 에러로 변환
        logger.error(f"V3 itinerary generation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting triB V3 API server (Gemini 3 Pro Preview) on port 8000...")
    uvicorn.run("main3:app", host="0.0.0.0", port=8000, reload=True)
