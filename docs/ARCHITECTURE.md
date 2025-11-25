# RAG System Architecture

Complete RAG (Retrieval-Augmented Generation) system with Knowledge Graph integration.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Contabo VPS                              │
│                    62.171.130.110:*                              │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌──────────────────┐    ┌──────────────┐
│   Kestra      │     │   MinIO          │    │   Neo4j      │
│   :8080       │────▶│   :9002 (API)    │    │   :7474      │
│   Orchestrate │     │   :9003 (UI)     │    │   :7687      │
└───────┬───────┘     └──────────────────┘    └──────────────┘
        │                       │                       ▲
        │                       │                       │
        │                       ▼                       │
        │             ┌──────────────────┐              │
        │             │  MinerU          │              │
        │             │  Processor       │              │
        │             │  :8000           │              │
        │             │  (PDF→Markdown)  │              │
        │             └──────────────────┘              │
        │                                               │
        ├───────────────────────────────────────────────┤
        │                                               │
        ▼                       ▼                       │
┌──────────────────┐    ┌──────────────────┐           │
│   Ollama         │    │   Qdrant         │           │
│   :11434         │    │   :6333          │           │
│   ┌────────────┐ │    │   Vector Store   │           │
│   │ bge-m3     │ │    └──────────────────┘           │
│   │ (Embed)    │ │                                   │
│   ├────────────┤ │                                   │
│   │ Phi-3.5    │ │                                   │
│   │ Q5_K_M     │ │                                   │
│   │ (Extract)  │ │                                   │
│   └────────────┘ │                                   │
└──────────────────┘                                   │
        │                                               │
        └───────────────────────────────────────────────┘
                      Knowledge Graph Builder
```

## Data Flow

### 1. Document Ingestion Pipeline

```
User Upload → MinIO (Raw Docs)
                │
                ▼
        MinerU Processor (PDF→MD)
                │
                ▼
        MinIO (Markdown Bucket)
                │
                ▼
        Kestra Trigger (ingest_rag)
                │
        ┌───────┴────────┐
        ▼                ▼
    Document          Document
    Download          Chunking
        │                │
        └────────┬───────┘
                 ▼
         Ollama (bge-m3)
         Generate Embeddings
                 │
        ┌────────┴────────┐
        ▼                 ▼
    Qdrant            Ollama (Phi-3.5)
    Store Vectors     Extract Entities
        │             & Relationships
        │                 │
        │                 ▼
        │             Neo4j Store
        │             Knowledge Graph
        │                 │
        └────────┬────────┘
                 ▼
         Ingestion Complete
```

### 2. Retrieval Pipeline (Hybrid RAG)

```
User Query → Kestra (retrieval_rag)
                    │
            ┌───────┴────────┐
            ▼                ▼
    Ollama (bge-m3)     Neo4j Graph
    Query Embedding      Traversal
            │                │
            ▼                │
    Qdrant Vector        Find Related
    Similarity Search    Entities
            │                │
            └────────┬───────┘
                     ▼
            Reciprocal Rank Fusion
            (Merge & Rerank)
                     │
                     ▼
            Context for LLM
            (Top-K Results)
```

## Components

### Storage Layer

| Component | Purpose | Port | Storage |
|-----------|---------|------|---------|
| **MinIO** | Object storage (S3-compatible) | 9002, 9003 | Raw docs, Markdown |
| **Qdrant** | Vector database | 6333, 6334 | Embeddings (1024-dim) |
| **Neo4j** | Graph database | 7474, 7687 | Knowledge graph |
| **Redis** | Cache | 6379 | YouTube results, temp data |

### Processing Layer

| Component | Purpose | Port | Technology |
|-----------|---------|------|------------|
| **Kestra** | Workflow orchestration | 8080 | Java (H2 DB) |
| **MinerU** | Document conversion | 8000 | Python (FastAPI) |
| **Ollama** | LLM inference | 11434 | C++ (llama.cpp) |

### Models

| Model | Type | Size | Purpose |
|-------|------|------|---------|
| **bge-m3:latest** | Embedding | ~1.8 GB | Generate 1024-dim vectors |
| **Phi-3.5 Q5_K_M** | LLM | ~2.3 GB | Entity/relationship extraction |

## Network Architecture

### Internal Docker Network: `kestra-network`

All services communicate via Docker bridge network with internal DNS:
- `http://minio:9000`
- `http://qdrant:6333`
- `bolt://neo4j:7687`
- `http://ollama:11434`
- `redis://redis:6379`

### External Access (0.0.0.0 binding)

All services exposed for external access:
- Kestra: `http://62.171.130.110:8080`
- MinIO Console: `http://62.171.130.110:9003`
- Neo4j Browser: `http://62.171.130.110:7474`
- Qdrant: `http://62.171.130.110:6333`
- Ollama: `http://62.171.130.110:11434`
- MinerU: `http://62.171.130.110:8000`

## Resource Requirements

### Minimum (Development)

- **RAM**: 8 GB
- **CPU**: 4 vCPUs
- **Storage**: 50 GB SSD
- **Network**: 100 Mbps

### Recommended (Production)

- **RAM**: 16 GB
- **CPU**: 8 vCPUs
- **Storage**: 100 GB NVMe SSD
- **Network**: 1 Gbps

### Resource Breakdown

```
Service          RAM Usage    CPU Usage
─────────────────────────────────────────
Ollama           3-4 GB       1-2 cores
Neo4j            1-2 GB       0.5-1 core
Qdrant           1-2 GB       0.5-1 core
MinIO            512 MB       0.2 core
Kestra           512 MB       0.2 core
MinerU           1-2 GB       1-2 cores
Redis            256 MB       0.1 core
─────────────────────────────────────────
TOTAL            7-12 GB      4-7 cores
```

## Workflows

### Workflow 1: `ai.rag.ingest_rag`

**Purpose**: Ingest documents from MinIO into RAG system

**Inputs**:
- `minio_bucket`: Bucket name (default: "rag-documents")
- `minio_path`: Path prefix (default: "documents/")

**Process**:
1. Scan MinIO for `.txt` and `.md` files
2. Download document content
3. Chunk documents (1000 chars, 200 overlap)
4. Generate embeddings with bge-m3
5. Store vectors in Qdrant
6. Extract entities with spaCy + Phi-3.5 validation
7. Extract relationships with Phi-3.5
8. Store graph in Neo4j

**Outputs**:
- `processed_count`: Number of documents processed
- `total_documents`: Total documents found
- `status`: "completed"

### Workflow 2: `ai.rag.retrieval_rag`

**Purpose**: Hybrid retrieval (vector + graph)

**Inputs**:
- `user_query`: Natural language query
- `top_k_vector`: Number of vector results (default: 10)
- `top_k_graph`: Number of graph results (default: 5)
- `rerank_top_k`: Final results after reranking (default: 5)

**Process**:
1. Generate query embedding with bge-m3
2. Search Qdrant for similar vectors
3. Search Neo4j for related entities
4. Merge results with reciprocal rank fusion
5. Return top-K context

**Outputs**:
- `context`: Formatted context string for LLM
- `num_sources`: Number of unique sources
- `query`: Original user query
- `status`: "completed"

## Security Considerations

### Default Credentials (⚠️ CHANGE IN PRODUCTION)

```yaml
MinIO:       minioadmin / minioadmin
Neo4j:       neo4j / neo4j_password
Kestra:      (auth disabled)
Redis:       (no auth)
Qdrant:      (no auth)
Ollama:      (no auth)
```

### Production Hardening

1. **Change all default passwords**
2. **Enable Kestra basic auth**
3. **Set up reverse proxy (nginx/traefik) with HTTPS**
4. **Configure firewall (ufw)**
5. **Use secrets manager (not env vars)**
6. **Enable Neo4j SSL/TLS**
7. **Restrict Docker socket access**

## Scaling Strategies

### Horizontal Scaling

- **Ollama**: Deploy multiple instances behind load balancer
- **Qdrant**: Cluster mode with sharding
- **Neo4j**: Enterprise Edition clustering
- **Kestra**: Postgres backend with multiple executors

### Vertical Scaling

- **Increase RAM**: Allows larger models (Q6, Q8)
- **Add GPU**: 10-100x faster inference with CUDA
- **NVMe Storage**: Faster model loading and database I/O

## Monitoring

### Health Checks

All services include Docker health checks:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Logs

```bash
# Real-time logs
docker-compose logs -f

# Service-specific
docker logs ollama
docker logs kestra
```

### Metrics

```bash
# Resource usage
docker stats

# Disk usage
df -h
docker system df
```

## Backup Strategy

### Critical Data

1. **Qdrant vectors**: `qdrant_storage` volume
2. **Neo4j graph**: `neo4j_data` volume  
3. **MinIO objects**: `minio_data` volume
4. **Ollama models**: `ollama_data` volume (can be regenerated)
5. **Kestra workflows**: `kestra_data` volume

### Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

for volume in kestra_data minio_data neo4j_data qdrant_storage ollama_data; do
  docker run --rm \
    -v ${volume}:/data \
    -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/${volume}.tar.gz /data
done
```

## Technology Stack

- **Languages**: Python 3.11, Bash
- **Frameworks**: LangChain, LangGraph, FastAPI
- **Databases**: Qdrant (vectors), Neo4j (graph), Redis (cache)
- **Storage**: MinIO (S3-compatible)
- **Orchestration**: Kestra, Docker Compose
- **ML/AI**: Ollama, spaCy, bge-m3, Phi-3.5
- **Infrastructure**: Docker, Ubuntu/Debian Linux

