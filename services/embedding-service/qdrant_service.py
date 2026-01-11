import os
import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from logger_config import setup_logger

logger = setup_logger("qdrant-service")

class QdrantService:
    def __init__(self):
        # Qdrant Config
        self.qdrant_host = os.getenv("QDRANT_HOST", "qdrant-vector-db")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        self.collection_name = os.getenv("QDRANT_COLLECTION", "pdf_chunks")
        self.vector_size = int(os.getenv("VECTOR_SIZE", 768)) # Nomic default

        self.qdrant_client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self._ensure_qdrant_collection()

    def _ensure_qdrant_collection(self):
        try:
            collections = self.qdrant_client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {str(e)}")

    def upsert_to_qdrant(self, pdf_id: str, points: List[models.PointStruct]):
        """Upserts vector points to Qdrant."""
        try:
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            logger.info(f"Successfully upserted {len(points)} points to Qdrant for PDF {pdf_id}")
        except Exception as e:
            logger.error(f"Qdrant upsert error: {str(e)}")
            raise


