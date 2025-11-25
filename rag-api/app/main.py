"""
RAG API - FastAPI application for RAG operations.

Provides endpoints for:
- Multi-stage pipeline processing
- Embedding generation
- Graph operations
- RAG query/retrieval
- OpenAI-compatible chat completions (AIjudante agent)
"""

import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.agent import aijudante
from app.chunk_service import chunk_service
from app.embed_service import embed_service
from app.graph_service import graph_service
from app.ingest_service import ingest_service
from app.query_service import query_service
from app.pipeline_routes import router as pipeline_router

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Pydantic models
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    total_embeddings: int
    dimensions: int


class GraphSearchRequest(BaseModel):
    query: str
    limit: int = 10


class QueryRequest(BaseModel):
    query: str
    top_k_vector: int = 10
    top_k_graph: int = 5
    rerank_top_k: int = 5


class QueryResponse(BaseModel):
    query: str
    context: str
    results: List[Dict[str, Any]]
    metadata: Dict[str, Any]


# OpenAI-compatible models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "aijudante-v1"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-aijudante"
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Connect to services
    graph_service.connect()
    
    yield
    
    # Cleanup
    logger.info("Shutting down application")
    graph_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
# RAG Pipeline API

Complete RAG processing system with multi-stage pipeline and hybrid retrieval.

---

## 🚀 Multi-Stage Pipeline (Current: Stages 1-3 Implemented)

### Data Flow: Redis (48h temp storage) → Qdrant/Neo4j (persistent) → Optional cleanup

### Stage 1: Document Processing & Chunking
- **Endpoint**: `POST /pipeline/process`
- **Process**: Downloads from MinIO, splits using MarkdownChunker (configurable size/overlap)
- **Storage**: Redis (48h TTL)
- **Parameters**: bucket, file, chunk_size (default: 1000), chunk_overlap (default: 200)

### Stage 2: Entity Extraction
- **Endpoint**: `POST /pipeline/extract-entities`
- **Model**: GLiNER `urchade/gliner_large-v2.1` via Salad.com (GPU-accelerated)
- **Entities**: AWS_SERVICE, GENAI_MODEL, AI_CONCEPT, TOOL_LIB, ARCH_PATTERN, SECURITY, PROMPTING, ORG, PERSON
- **Storage**: Redis (48h TTL)

### Stage 3: Relationship Extraction
- **Endpoint**: `POST /pipeline/extract-relationships`
- **Model**: Ollama `qwen2.5:7b` (local inference)
- **Output**: Subject-Predicate-Object triples
- **Storage**: Redis (48h TTL) - vectorization in Stage 6

### Stage 4: Chunk Vectorization
- **Endpoint**: `POST /pipeline/vectorize-chunks`
- **Input**: Redis (chunks + entities + relationships)
- **Output**: Qdrant (chunks enriched with entities/relationships)
- **Parameter**: `enrich` (default: True)

### Stage 5: Entity Vectorization
- **Endpoint**: `POST /pipeline/vectorize-entities`
- **Input**: Redis (entities)
- **Output**: Qdrant (entity vectors) + Neo4j (nodes)
- **Parameter**: `store_graph` (default: True)

### Stage 6: Relationship Vectorization
- **Endpoint**: `POST /pipeline/vectorize-relationships`
- **Input**: Redis (relationships)
- **Output**: Qdrant (relationship vectors) + Neo4j (edges)
- **Parameters**: `store_graph` (default: True), `cleanup_redis` (default: False)

### Pipeline Management:
- `GET /pipeline/status/{job_id}` - Real-time job progress
- `GET /pipeline/jobs` - List all active jobs
- `DELETE /pipeline/job/{job_id}` - Delete job data

---

## 📊 Qdrant Collections (3 Separate Collections)

All collections use 1024-dimensional vectors from `bge-m3:latest`:

- **`rag_embeddings_chunks`** - Document chunks enriched with entities and relationships
- **`rag_embeddings_entities`** - Extracted entities with chunk references
- **`rag_embeddings_relationships`** - Entity relationships with source chunk IDs

---

## 🔍 Query & Retrieval

- `POST /query` - Hybrid search (vector + graph with RRF)
- `POST /graph/search` - Graph-only entity search
- `GET /graph/entity/{entity_name}` - Get entity subgraph

**Features**: Reciprocal Rank Fusion, configurable score thresholds, adjustable top-k

---

## 🤖 AIjudante Agent (OpenAI-Compatible)

- `POST /v1/chat/completions` - Chat completions endpoint
- `GET /models` - Available models list

---

## 🛠️ Utilities

- `POST /embed` - Generate embeddings (bge-m3)
- `GET /health` - Health check

---

## 📚 Models

- **Embeddings**: `bge-m3:latest` (1024 dims, Ollama)
- **Entity Extraction**: GLiNER `urchade/gliner_large-v2.1` (Salad.com GPU)
- **Relationships**: `qwen2.5:7b` (Ollama local)

---

## 📖 Documentation

See `/docs/PIPELINE.md` for complete pipeline specifications and Stage 4-6 details.
    """,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include pipeline routes
app.include_router(pipeline_router)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION
    )


@app.post("/embed", response_model=EmbedResponse)
async def generate_embeddings(request: EmbedRequest):
    """
    Generate embeddings for a list of texts.
    
    Uses Ollama bge-m3 model.
    """
    try:
        embeddings = await embed_service.embed_documents(request.texts)
        
        return EmbedResponse(
            embeddings=embeddings,
            total_embeddings=len(embeddings),
            dimensions=len(embeddings[0]) if embeddings else 0
        )
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/search")
async def search_graph(request: GraphSearchRequest):
    """
    Search the knowledge graph for entities.
    """
    try:
        results = await graph_service.search_entities(
            request.query,
            limit=request.limit
        )
        
        return {
            "query": request.query,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        logger.error(f"Graph search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/entity/{entity_name}")
async def get_entity_graph(entity_name: str, depth: int = 2):
    """
    Get the subgraph around an entity.
    """
    try:
        graph = await graph_service.get_entity_graph(entity_name, depth=depth)
        
        return {
            "entity_name": entity_name,
            "depth": depth,
            "graph": graph
        }
    except Exception as e:
        logger.error(f"Failed to get entity graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Query the RAG system using hybrid search.
    
    Combines vector search (Qdrant) and graph search (Neo4j).
    """
    try:
        result = await query_service.hybrid_search(
            query=request.query,
            top_k_vector=request.top_k_vector,
            top_k_graph=request.top_k_graph,
            rerank_top_k=request.rerank_top_k
        )
        
        return QueryResponse(**result)
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.
    
    Uses the AIjudante agent which currently returns "banana" to all queries.
    """
    try:
        import time
        
        # Extract last message
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        last_message = request.messages[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="Last message must be from user")
        
        # Get response from AIjudante
        response = await aijudante.chat(last_message.content)
        
        # Format as OpenAI-compatible response
        return ChatCompletionResponse(
            id="chatcmpl-aijudante",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response["response"]
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(last_message.content.split()),
                "completion_tokens": response.get("tokens_used", 1),
                "total_tokens": len(last_message.content.split()) + response.get("tokens_used", 1)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models")
async def list_models():
    """
    List available models (OpenAI-compatible endpoint).
    """
    import time
    
    return {
        "object": "list",
        "data": [
            {
                "id": "aijudante-v1",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "rag-api",
                "permission": [],
                "root": "aijudante-v1",
                "parent": None
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

