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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
