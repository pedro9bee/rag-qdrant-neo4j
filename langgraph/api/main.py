"""
LangGraph Chat API - OpenAI-compatible FastAPI server.

This server provides OpenAI-compatible chat endpoints using the LangGraph
retrieval workflow for RAG-powered responses.
"""

import logging
import time
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.chat_service import chat_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="LangGraph Chat API",
    version="1.0.0",
    description="OpenAI-compatible chat API using LangGraph RAG workflows"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "langgraph-rag-v1"
    messages: List[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False
    # RAG-specific parameters
    top_k_vector: int = 10
    top_k_graph: int = 5
    rerank_top_k: int = 5


class ChatCompletionResponse(BaseModel):
    id: str = "chatcmpl-langgraph"
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[dict]
    usage: dict


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="LangGraph Chat API",
        version="1.0.0"
    )


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint)."""
    return {
        "object": "list",
        "data": [
            {
                "id": "langgraph-rag-v1",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "langgraph",
                "permission": [],
                "root": "langgraph-rag-v1",
                "parent": None,
                "description": "LangGraph RAG workflow with hybrid vector + graph search"
            }
        ]
    }


@app.get("/models")
async def list_models_alt():
    """Alternative models endpoint."""
    return await list_models()


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint.
    
    Uses LangGraph retrieval workflow for RAG-powered responses.
    """
    try:
        # Extract last message
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        last_message = request.messages[-1]
        if last_message.role != "user":
            raise HTTPException(status_code=400, detail="Last message must be from user")
        
        # Get conversation history (all messages except last)
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages[:-1]
        ]
        
        # Process chat using LangGraph
        result = await chat_service.chat(
            message=last_message.content,
            conversation_history=conversation_history if conversation_history else None,
            top_k_vector=request.top_k_vector,
            top_k_graph=request.top_k_graph,
            rerank_top_k=request.rerank_top_k
        )
        
        # Format as OpenAI-compatible response
        response_content = result["response"]
        
        # Add sources information if requested
        if result.get("sources"):
            response_content += "\n\n---\n**Sources:**\n"
            for i, source in enumerate(result["sources"][:3], 1):
                response_content += f"\n{i}. {source.get('type', 'unknown')} (score: {source.get('score', 0):.2f})"
        
        return ChatCompletionResponse(
            id="chatcmpl-langgraph",
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(last_message.content.split()),
                "completion_tokens": len(response_content.split()),
                "total_tokens": len(last_message.content.split()) + len(response_content.split())
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "LangGraph Chat API",
        "version": "1.0.0",
        "description": "OpenAI-compatible chat API using LangGraph RAG workflows",
        "endpoints": {
            "health": "/health",
            "models": "/v1/models",
            "chat": "/v1/chat/completions",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

