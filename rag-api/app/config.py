"""
Configuration settings for RAG API.
"""

import os
from typing import List


class Settings:
    """Application settings loaded from environment variables."""
    
    # App Info
    APP_NAME: str = "RAG API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest")
    OLLAMA_ENTITY_MODEL: str = os.getenv("OLLAMA_ENTITY_MODEL", "pedro9bee/uniner-7b-all:gguf-q4")
    OLLAMA_LLM_MODEL: str = os.getenv("OLLAMA_LLM_MODEL", "bartowski/phi-3.5-mini-instruct-q5_k_m:latest")
    
    # MinIO Configuration
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://localhost:9002")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "documents")
    
    # Qdrant Configuration
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "rag_embeddings")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    
    # Neo4j Configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j_password")
    
    # Knowledge Graph Configuration
    ENTITIES_LIST: str = os.getenv(
        "ENTITIES_LIST",
        "Agent,Graph,Node,State,Transition,LLM,Tool,MCP,Gateway,BusinessSystem,BedrockAgentCore,Memory,User,AWS,Bedrock,Lambda,S3,Claude,Haiku,Sonnet,Opus,LangChain,LangGraph,Qdrant,Neo4j,MinIO,Ollama,Kestra,Python,RAG,Embedding,Vector,Chunk,Document"
    )
    RELATIONSHIPS_LIST: str = os.getenv(
        "RELATIONSHIPS_LIST",
        "implemented_by,contains,operates_on,updates,uses_for_reasoning,connects,invokes,uses_protocol,routes_to,accesses,executes_in,persists_data_in,interacts_with,offers,uses,provides,integrates_with,depends_on,supports,requires,enables,manages,processes,stores,retrieves,orchestrates,embedded_by,indexes_in,queries"
    )
    
    # Chunking Configuration
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # Embedding Dimensions
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_JOB_TTL: int = int(os.getenv("REDIS_JOB_TTL", "172800"))  # 48h
    
    # Chunking Configuration (Pipeline)
    MARKDOWN_CHUNK_SIZE: int = int(os.getenv("MARKDOWN_CHUNK_SIZE", "1000"))
    MARKDOWN_CHUNK_OVERLAP: int = int(os.getenv("MARKDOWN_CHUNK_OVERLAP", "200"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    
    # LLM Models
    ENTITY_EXTRACTION_MODEL: str = os.getenv("ENTITY_EXTRACTION_MODEL", "mistral-7b-v0.3:latest")
    ENTITY_VALIDATION_MODEL: str = os.getenv("ENTITY_VALIDATION_MODEL", "pedro9bee/uniner-7b-all:gguf-q4")
    RELATIONSHIP_EXTRACTION_MODEL: str = os.getenv("RELATIONSHIP_EXTRACTION_MODEL", "mistral-7b-v0.3:latest")
    
    # MLX Configuration (Apple Silicon only)
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "auto")  # 'auto', 'mlx', 'ollama'
    MLX_MODEL_PATH: str = os.getenv("MLX_MODEL_PATH", "mlx-community/Phi-3-mini-4k-instruct-4bit")
    ENTITY_VALIDATION_BATCH_SIZE: int = int(os.getenv("ENTITY_VALIDATION_BATCH_SIZE", "10"))
    
    @property
    def entities_list(self) -> List[str]:
        """Get entities as a list."""
        return [e.strip() for e in self.ENTITIES_LIST.split(",") if e.strip()]
    
    @property
    def relationships_list(self) -> List[str]:
        """Get relationships as a list."""
        return [r.strip() for r in self.RELATIONSHIPS_LIST.split(",") if r.strip()]


settings = Settings()

