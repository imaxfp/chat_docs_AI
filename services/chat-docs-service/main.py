import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional
from search_service import SearchService
from chat_client import ChatClient
from prompts import USER_LOOKING_FOR_PROMPT, USER_WANT_EXPLANATION_PROMPT, RAG_FINAL_ANSWER_TEMPLATE, SYSTEM_ASSISTANT_PROMPT
from logger_config import setup_logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.dev")

logger = setup_logger("text-searcher-api")

# Global service instances
search_service = None
chat_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events to initialize services."""
    global search_service, chat_client
    logger.info("Starting Text Searcher Microservice...")
    try:
        search_service = SearchService()
        chat_client = ChatClient()
        logger.info("Services initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    yield
    logger.info("Shutting down Text Searcher Microservice...")

app = FastAPI(
    title="PDF Text Searcher API",
    description="Semantic search service for PDF documents using Vector Embeddings.",
    version="1.0.0",
    lifespan=lifespan
)

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    debug_flag: bool = False

class SearchResponse(BaseModel):
    score: float
    pdf_id: str
    pdf_name: str
    page_number: int
    chunk_index: int
    full_text: str
    metadata: Dict
    chunk_id: str

class AskLlmResponse(BaseModel):
    final_llm_answer: str
    duration_seconds: float
    sources: Optional[List[SearchResponse]] = None
    debug_info: Optional[Dict] = None

@app.get("/health")
async def health():
    """Basic health check endpoint."""
    if search_service is None:
        raise HTTPException(status_code=503, detail="Search service not initialized")
    return {
        "status": "healthy",
        "service": os.getenv("APP_NAME", "text-searcher-microservice"),
        "qdrant_host": search_service.qdrant_host
    }

@app.post("/search_in_pdf_chunks_by_full_text_similarity", response_model=List[SearchResponse])
async def find_by_text(request: SearchRequest):
    """
    Search for semantically similar text chunks across processed PDFs.
    
    Workflow:
    1. Convert user query to embedding with ollama-llm-embedding-service.
    2. Find the most similar chunks in Qdrant (top 5).
    3. Read context from Postgres (full text, filename, metadata).
    4. Format and return results.
    """
    if search_service is None:
        raise HTTPException(status_code=503, detail="Search service is currently unavailable")
    
    try:
        logger.info(f"Triggering semantic search for query: {request.query}")
        results = search_service.find_by_text(request.query, request.limit)
        return results
    except Exception as e:
        logger.error(f"API Error during search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask_llm_model", response_model=AskLlmResponse, response_model_exclude_none=True)
async def ask_llm_model(request: SearchRequest):
    """
    Complete RAG Workflow with optional debugging:
    1. Refine search intent.
    2. Perform semantic search.
    3. Refine explanation intent.
    4. Construct context and generate final answer.
    """
    if search_service is None or chat_client is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    start_time = time.time()
    try:
        # Step 1: Refine query for searching
        logger.info(f"Step 1: Refining search query for: {request.query}")
        user_looking_for_query = chat_client.generate_response(USER_LOOKING_FOR_PROMPT, request.query)
        logger.info(f"Refined search query: {user_looking_for_query}")
        
        # Step 2 & 3: Search Qdrant and get PostgreSQL context
        logger.info(f"Step 2/3: Searching Qdrant and fetching context for: {user_looking_for_query}")
        search_results = search_service.find_by_text(user_looking_for_query, request.limit)
        logger.info(f"Retrieved {len(search_results)} relevant chunks.")
        
        # Step 4: Refine the specific explanation intent
        logger.info(f"Step 4: Refining explanation intent for: {request.query}")
        user_want_explanation_query = chat_client.generate_response(USER_WANT_EXPLANATION_PROMPT, request.query)
        logger.info(f"Explanation intent: {user_want_explanation_query}")
        
        # Step 5: Combine context and generate final answer
        logger.info("Step 5: Constructing context and generating final response...")
        context_text = "\n\n".join([
            f"Source: {res.get('pdf_name')}\nContent: {res.get('full_text')}" 
            for res in search_results
        ])
        
        final_prompt = RAG_FINAL_ANSWER_TEMPLATE.format(
            query=user_looking_for_query,
            intent=user_want_explanation_query,
            context=context_text
        )
        
        llm_answer = chat_client.generate_response(SYSTEM_ASSISTANT_PROMPT, final_prompt)
        logger.info("Step 6: Final answer generated.")
        
        duration = round(time.time() - start_time, 2)
        
        # Prepare response based on debug_flag
        response = AskLlmResponse(
            final_llm_answer=llm_answer,
            duration_seconds=duration
        )
        
        if request.debug_flag:            
            response.sources = search_results
            response.debug_info = {
                "refined_query": user_looking_for_query,
                "explanation_intent": user_want_explanation_query,                          
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error in RAG flow: {e}")
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
