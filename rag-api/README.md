# RAG API

FastAPI service implementing a 6-stage RAG pipeline with Knowledge Graph integration.

## Features

- **Multi-Stage Pipeline**: Asynchronous document processing through 6 stages
- **Entity Extraction**: GLiNER-based NER via Salad.com GPU
- **Relationship Extraction**: Ollama Qwen2.5-7B for relationship discovery
- **Vector Storage**: Qdrant with 3 collections (chunks, entities, relationships)
- **Knowledge Graph**: Neo4j with dynamic entity labels and relationship edges
- **Redis State**: Job tracking with 48h TTL

## Pipeline Stages

| Stage | Endpoint | Description |
|-------|----------|-------------|
| 1 | `POST /pipeline/process` | Download from MinIO + Markdown chunking |
| 2 | `POST /pipeline/extract-entities` | GLiNER entity extraction |
| 3 | `POST /pipeline/extract-relationships` | LLM relationship extraction |
| 4 | `POST /pipeline/vectorize-chunks` | Embed and store chunks in Qdrant |
| 5 | `POST /pipeline/vectorize-entities` | Embed entities → Qdrant + Neo4j nodes |
| 6 | `POST /pipeline/vectorize-relationships` | Embed relationships → Qdrant + Neo4j edges |

## Models Used

- **Embeddings**: `bge-m3:latest` (1024 dimensions)
- **Entity Extraction**: GLiNER `urchade/gliner_large-v2.1`
- **Relationships**: `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M`

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .

# Copy environment file
cp ../env.example .env

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Configuration

Key environment variables:

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3:latest

# Qdrant
QDRANT_URL=http://localhost:6333

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_password

# Redis
REDIS_URL=redis://localhost:6379
REDIS_JOB_TTL=172800

# MinIO
MINIO_ENDPOINT=localhost:9000
```

## Qdrant Collections

| Collection | Content |
|------------|---------|
| `rag_embeddings_chunks` | Document chunks with entity context |
| `rag_embeddings_entities` | Named entities |
| `rag_embeddings_relationships` | Entity relationships |

## Neo4j Schema

Entities are created with dynamic labels using APOC:

```cypher
(:Entity:AWS_SERVICE {name: "Amazon Bedrock"})
(:Entity:AI_CONCEPT {name: "RAG"})

(a:Entity)-[:PROVIDES]->(b:Entity)
```

## Pipeline Usage

See [../docs/PIPELINE.md](../docs/PIPELINE.md) for complete pipeline documentation with CURL examples.
