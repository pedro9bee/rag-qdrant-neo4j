# RAG + Knowledge Graph Pipeline Build Instructions (MinIO → Qdrant → Neo4j)

## Objective
Build an advanced RAG system with Knowledge Graph from large Markdown documents stored in MinIO, using Qdrant as the vector store, Neo4j as the graph database, and a multi-stage pipeline for processing.

## Model Service Specification

The pipeline uses different models for different tasks:

### Embedding Model (Ollama - Local)
- **Model**: `bge-m3:latest`
- **Dimensions**: 1024
- **Purpose**: All embedding operations (chunks, entities, relationships)

### Entity Extraction (GLiNER - Salad.com GPU)
- **Model**: `urchade/gliner_large-v2.1`
- **Purpose**: Named Entity Recognition with domain-specific entity types
- **Deployment**: GPU-accelerated via Salad.com container

### Relationship Extraction (Ollama - Local)
- **Model**: `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M`
- **Purpose**: Extract relationships between entities using LLM
- **Configuration**: temperature=0.0 for deterministic JSON output

## Environment Variables

```env
# Embedding
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_EMBEDDING_MODEL="bge-m3:latest"
EMBEDDING_DIMENSIONS=1024

# Relationship Extraction
RELATIONSHIP_MODEL="hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M"

# Storage
QDRANT_URL="http://localhost:6333"
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="neo4j_password"
REDIS_URL="redis://localhost:6379"
REDIS_JOB_TTL=172800

# MinIO
MINIO_ENDPOINT="localhost:9000"
MINIO_ACCESS_KEY="minioadmin"
MINIO_SECRET_KEY="minioadmin"

# GLiNER (Salad.com)
GLINER_API_URL="https://your-salad-endpoint.salad.cloud"
```

## Processing Flow

### Stage 2: Entity Extraction (GLiNER)

Entity extraction uses GLiNER model deployed on Salad.com GPU:

```python
# GLiNER extracts entities with confidence scores
entities = gliner_client.extract(
    text=chunk_text,
    labels=["AWS_SERVICE", "GENAI_MODEL", "AI_CONCEPT", "TOOL_LIB", 
            "ARCH_PATTERN", "SECURITY", "PROMPTING", "ORG", "PERSON"]
)
```

### Stage 3: Relationship Extraction (Ollama)

Relationship extraction uses Qwen2.5-7B-Instruct:

```text
Extract all meaningful relationships between entities from the allowed list that exist in the text.

Allowed entities: {ENTITIES_LIST}

Text:
{chunk}

Return ONLY a valid JSON array of triples (can be empty). 
Predicates must be in English, lowercase, snake_case, infinitive form.

Example:
[
  {"subject": "AWS", "predicate": "contains", "object": "Bedrock"},
  {"subject": "Bedrock", "predicate": "offers", "object": "Claude"}
]

Do not explain. Do not add extra text.
```

## Pipeline Summary

The complete RAG pipeline provides:

### Ingestion Pipeline (Stages 1-6)
- **Chunking**: Markdown-aware splitting preserving header hierarchy
- **Entity Extraction**: GLiNER on Salad.com GPU for high accuracy
- **Relationship Extraction**: Qwen2.5-7B for structured JSON output
- **Embeddings**: bge-m3 (1024 dims) for multilingual semantic search
- **Storage**: 3 Qdrant collections + Neo4j Knowledge Graph

### Retrieval Pipeline (Future)
- **Hybrid Search**: Vector similarity (Qdrant) + Graph traversal (Neo4j)
- **LLM Generation**: Claude via AWS Bedrock for final answers

### Benefits
- Excellent multilingual embeddings (bge-m3 is state-of-the-art)
- GPU-accelerated entity extraction via Salad.com
- Cost-efficient local LLM for relationship extraction
- Idempotent pipeline (deterministic UUIDs prevent duplicates)
- 48h Redis TTL for pipeline recovery and debugging

See [PIPELINE.md](PIPELINE.md) for complete API documentation with CURL examples.