import logging
from typing import List, Dict
import numpy as np
import google.generativeai as genai
from config import settings
from models.schemas import Place

logger = logging.getLogger(__name__)

# Gemini API 초기화
genai.configure(api_key=settings.google_api_key)


class EmbeddingService:
    def __init__(self):
        self.model_name = "models/embedding-001"

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        텍스트 리스트의 임베딩 생성

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            임베딩 벡터 리스트
        """
        if not texts:
            return []

        try:
            embeddings = []
            # 배치 처리 (한 번에 여러 텍스트 임베딩)
            for text in texts:
                if not text:
                    # 빈 텍스트는 0 벡터로 처리
                    embeddings.append([0.0] * 768)  # embedding-001의 차원
                    continue

                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type="retrieval_document",
                )
                embeddings.append(result["embedding"])

            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {str(e)}")
            raise

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        쿼리 텍스트의 임베딩 생성

        Args:
            query: 쿼리 텍스트

        Returns:
            임베딩 벡터
        """
        if not query:
            return [0.0] * 768

        try:
            result = genai.embed_content(
                model=self.model_name,
                content=query,
                task_type="retrieval_query",
            )
            logger.info("Successfully generated query embedding")
            return result["embedding"]

        except Exception as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            raise

    def calculate_cosine_similarity(
        self, vec1: List[float], vec2: List[float]
    ) -> float:
        """
        두 벡터 간의 코사인 유사도 계산

        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터

        Returns:
            코사인 유사도 (0~1 범위)
        """
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # -1 ~ 1 범위를 0 ~ 1 범위로 변환
        return (similarity + 1) / 2

    def calculate_place_scores(
        self, places: List[Place], query: str
    ) -> Dict[str, float]:
        """
        장소들과 쿼리 간의 유사도 점수 계산

        Args:
            places: 장소 리스트
            query: 사용자 쿼리

        Returns:
            {place_id: score} 딕셔너리
        """
        try:
            # 장소들의 editorial_summary 추출
            summaries = []
            place_ids = []
            for place in places:
                summary = place.editorial_summary or place.display_name or ""
                summaries.append(summary)
                place_ids.append(place.id)

            # 임베딩 생성
            logger.info(f"Generating embeddings for {len(summaries)} places")
            place_embeddings = self.generate_embeddings(summaries)
            query_embedding = self.generate_query_embedding(query)

            # 유사도 계산
            scores = {}
            for place_id, place_embedding in zip(place_ids, place_embeddings):
                similarity = self.calculate_cosine_similarity(
                    query_embedding, place_embedding
                )
                scores[place_id] = similarity

            logger.info(f"Calculated similarity scores for {len(scores)} places")
            logger.info(
                f"Score range: {min(scores.values()):.3f} ~ {max(scores.values()):.3f}"
            )

            return scores

        except Exception as e:
            logger.error(f"Failed to calculate place scores: {str(e)}")
            raise


# 싱글톤 인스턴스
embedding_service = EmbeddingService()
