import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from models.schemas import ItineraryRequest, ItineraryResponse
from services.database import db_service
from services.embedding import embedding_service
from services.clustering import clustering_service
from services.routes_matrix import routes_matrix_service
from services.itinerary_generator import itinerary_generator_service
from utils.json_encoder import NumpyJSONEncoder
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# NumPy 타입을 처리하는 커스텀 JSONResponse
class NumpyJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            cls=NumpyJSONEncoder,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


# FastAPI 앱 생성
app = FastAPI(
    title="triB Travel Itinerary API",
    description="AI 기반 여행 일정 생성 API",
    version="1.0.0",
    default_response_class=NumpyJSONResponse,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check 엔드포인트"""
    return {"status": "ok", "message": "triB Travel Itinerary API is running"}


@app.post("/api/itinerary/generate", response_model=ItineraryResponse)
async def generate_itinerary(request: ItineraryRequest):
    """
    여행 일정 생성 엔드포인트

    Args:
        request: 일정 생성 요청 (장소 ID 리스트 및 사용자 요청)

    Returns:
        생성된 여행 일정
    """
    try:
        logger.info(
            f"Received itinerary generation request: {len(request.places)} places, {request.user_request.days} days"
        )

        # 1. DB에서 장소 정보 조회
        logger.info("Step 1: Fetching place data from database")
        places = db_service.get_places_by_ids(request.places)

        if not places:
            raise HTTPException(status_code=404, detail="No places found")

        logger.info(f"Retrieved {len(places)} places from database")

        # 2. 임베딩 생성 및 유사도 점수 계산
        logger.info("Step 2: Calculating similarity scores")
        scores = embedding_service.calculate_place_scores(
            places, request.user_request.query
        )

        # 3. 클러스터링
        logger.info("Step 3: Clustering places")
        clusters = clustering_service.cluster_places(places)
        logger.info(f"Created {len(clusters)} clusters")

        # 4. 클러스터 내 이동시간 매트릭스 계산
        logger.info("Step 4: Computing cluster matrices")
        travel_mode = request.user_request.preferences.travel_mode
        cluster_matrices = await routes_matrix_service.compute_cluster_matrices(
            clusters, places, travel_mode
        )

        # 5. 각 클러스터의 메도이드 찾기
        logger.info("Step 5: Finding cluster medoids")
        medoids = clustering_service.find_cluster_medoids(
            clusters, places, cluster_matrices
        )

        # 6. 메도이드 간 이동시간 매트릭스 계산
        logger.info("Step 6: Computing medoid matrix")
        medoid_matrix = await routes_matrix_service.compute_medoid_matrix(
            medoids, places, travel_mode
        )

        # 7. Gemini로 일정 생성
        logger.info("Step 7: Generating itinerary with Gemini")
        itinerary = await itinerary_generator_service.generate_itinerary(
            places,
            scores,
            clusters,
            medoids,
            cluster_matrices,
            medoid_matrix,
            request.user_request,
        )

        logger.info(
            f"Successfully generated itinerary with {len(itinerary.itinerary)} days"
        )

        return itinerary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate itinerary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
