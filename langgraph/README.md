# LangGraph RAG Workflows

This directory contains LangGraph state machines and Kestra flows for the RAG (Retrieval Augmented Generation) system with hybrid search combining vector similarity and knowledge graphs.

## Architecture

```
LangGraph State Machines
  ├── Ingest Graph: Document → Chunks → Embeddings → Storage
  │   ├── Scans MinIO for documents
  │   ├── Chunks documents (markdown-aware)
  │   ├── Generates embeddings via Ollama (bge-m3)
  │   ├── Stores vectors in Qdrant
  │   ├── Extracts entities (spaCy NER + Phi-3.5 validation)
  │   ├── Extracts relationships (Phi-3.5 LLM)
  │   └── Creates knowledge graph in Neo4J
  │
  └── Retrieval Graph: Query → Search → Rerank → Context
      ├── Vector search (Qdrant with bge-m3)
      ├── Graph search (Neo4J entities + full-text)
      ├── Reciprocal rank fusion
      └── Context formatting
```

## Model Configuration

This pipeline uses **Ollama** for local GPU-accelerated inference:

- **Embeddings**: `bge-m3:latest` (1024 dimensions, multilingual)
- **Entity Extraction & Validation**: `bartowski/phi-3.5-mini-instruct-q5_k_m:latest`
- **Relationship Extraction**: Same Phi-3.5 model

### CRITICAL: Ollama Setup for Hybrid Deployment

Since the Docker containers connect to Ollama running on your **host machine** (not in Docker), you **MUST** start Ollama with network access enabled:

```bash
# Before starting Docker services, run:
export OLLAMA_HOST=0.0.0.0
ollama serve

# Or in a single command:
OLLAMA_HOST=0.0.0.0 ollama serve
```

**Why?** By default, Ollama binds to `localhost` only. The Docker containers use `host.docker.internal:11434` to reach your host's Ollama, which requires the server to listen on `0.0.0.0`.

### Required Ollama Models

Pull these models before running ingestion:

```bash
ollama pull bge-m3:latest
ollama create bartowski/phi-3.5-mini-instruct-q5_k_m:latest -f /path/to/Modelfile
```

The Phi-3.5 Modelfile (from Implementation.md):

```dockerfile
FROM hf.co/bartowski/Phi-3.5-mini-instruct-GGUF:Phi-3.5-mini-instruct-Q5_K_M.gguf
TEMPLATE """{{ if .System }}<|system|>{{ .System }}<|end|>{{ end }}{{ if .Prompt }}<|user|>{{ .Prompt }}<|end|>{{ end }}<|assistant|>{{ .Response }}<|end|>"""
PARAMETER num_keep 24
PARAMETER stop "<|end|>"
PARAMETER stop "<|user|>"
PARAMETER stop "<|assistant|>"
PARAMETER temperature 0.3
PARAMETER top_p 0.95
SYSTEM """You are a precise, expert knowledge graph builder. Follow instructions exactly. Never add extra text."""
```

## Connection Details

When running inside Kestra tasks, use these internal hostnames:

- **Ollama** (Host): `http://host.docker.internal:11434`
- **QDrant**: `http://qdrant:6333`
- **Neo4J**: `bolt://neo4j:7687` (user: `neo4j`, password: `neo4j_password`)
- **MinIO**: `http://minio:9000` (access_key: `minioadmin`, secret: `minioadmin`)

## Kestra Flows

### Ingestion Flow (`flows/ingest_rag.yml`)

Processes documents from MinIO and populates the RAG stack:

```bash
# Trigger via Kestra UI or API
curl -X POST http://localhost:8080/api/v1/executions/ai.rag/ingest_rag \
  -H "Content-Type: application/json" \
  -d '{"minio_bucket": "rag-documents", "minio_path": "documents/"}'
```

Workflow:
1. Scans MinIO bucket for `.txt` and `.md` files
2. Downloads and chunks documents (markdown-aware splitter)
3. Generates embeddings using Ollama bge-m3 (1024-dim vectors)
4. Stores vectors in Qdrant with metadata
5. Extracts entities using spaCy NER + Phi-3.5 validation
6. Extracts relationships using Phi-3.5 with entity/relationship lists
7. Creates knowledge graph in Neo4J with validated entities

### Retrieval Flow (`flows/retrieval_rag.yml`)

Performs hybrid search and returns context:

```bash
# Trigger retrieval (usually called by RAG Gateway)
curl -X POST http://localhost:8080/api/v1/executions/ai.rag/retrieval_rag \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "What are the main topics?",
    "top_k_vector": 10,
    "top_k_graph": 5,
    "rerank_top_k": 5
  }'
```

Workflow:
1. Generates embedding for user query (Ollama bge-m3)
2. Parallel execution:
   - Vector search in Qdrant (cosine similarity)
   - Graph search in Neo4J (entity extraction + full-text)
3. Merges results with normalized scores
4. Reranks using reciprocal rank fusion
5. Formats context for LLM augmentation

## Directory Structure

```
langgraph/
├── README.md                    # This file
├── pyproject.toml               # Python dependencies (TOML format)
├── flows/                       # Kestra flow definitions
│   ├── ingest_rag.yml          # Document ingestion workflow
│   └── retrieval_rag.yml       # Hybrid retrieval workflow
├── graphs/                      # LangGraph state machines
│   ├── __init__.py
│   ├── shared.py               # State type definitions
│   ├── ingest_graph.py         # Ingestion state graph
│   └── retrieval_graph.py      # Retrieval state graph
├── utils/                       # Utility functions
│   ├── __init__.py
│   ├── connections.py          # Service connection helpers
│   ├── chunking.py             # Text chunking utilities
│   └── neo4j_schema.py         # Neo4J Cypher templates
└── examples/                    # Example flows
    └── kestra-flow-example.yml
```

## Development Workflow

1. **Develop locally**: Write your LangChain/LangGraph code in this directory
2. **Test in Kestra**: Create a flow that references this code via volume mount
3. **Deploy**: The `./langgraph` folder is mounted at `/app/langgraph` inside Kestra

## Environment Variables

Store configuration as Kestra Secrets (or in `.env` for local testing):

```yaml
# In Kestra UI: Settings > Secrets

# Ollama Configuration
OLLAMA_URL: http://host.docker.internal:11434
EMBEDDING_MODEL: bge-m3:latest
LLM_MODEL: bartowski/phi-3.5-mini-instruct-q5_k_m:latest
EMBEDDING_DIMENSIONS: 1024

# Entity & Relationship Lists
ENTITIES_LIST: AWS,Bedrock,Lambda,S3,Neo4j,Qdrant,MinIO,Ollama,LangChain,Python
RELATIONSHIPS_LIST: contains,offers,uses,provides,integrates_with,depends_on

# Service Configuration
NEO4J_PASSWORD: neo4j_password
MINIO_SECRET_KEY: minioadmin
CHUNK_SIZE: 1000
CHUNK_OVERLAP: 200
```

Access in Python tasks:

```python
import os
ollama_url = os.getenv("OLLAMA_URL")
entities = os.getenv("ENTITIES_LIST").split(",")
```

## Best Practices

1. **Always use try/finally**: Ensure connections are closed
2. **Async when possible**: Use `aiohttp` for non-blocking I/O
3. **Type hints**: Full typing for maintainability
4. **Logging**: Use Kestra's logger, not `print()`
5. **Error handling**: Graceful degradation if services are unavailable

## Usage Examples

### Using Connection Helpers

```python
import sys
sys.path.insert(0, '/app/langgraph')

from utils.connections import (
    get_qdrant_client,
    get_neo4j_driver,
    get_minio_client,
    get_ollama_embeddings,
    get_ollama_llm
)

# Connect to services
qdrant = get_qdrant_client()
neo4j = get_neo4j_driver()
minio = get_minio_client()

# Get Ollama clients (reads from env vars)
embeddings = get_ollama_embeddings()  # bge-m3
llm = get_ollama_llm()  # Phi-3.5-mini
```

### Chunking Text

```python
from utils.chunking import chunk_text, chunk_markdown

# Chunk plain text
text = "Your long document text here..."
chunks = chunk_text(text, chunk_size=1000, chunk_overlap=200)

for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.text[:100]}...")

# Chunk markdown (preserves structure)
markdown = "# Title\n\n## Section\n\nContent..."
chunks = chunk_markdown(markdown)
```

### Neo4J Operations

```python
from utils.neo4j_schema import (
    create_document_node,
    create_chunk_node,
    create_entity_node,
    link_entity_to_chunk
)
from utils.connections import get_neo4j_driver, neo4j_session

driver = get_neo4j_driver()

with neo4j_session(driver) as session:
    # Create document
    doc = create_document_node(
        session,
        document_id="doc123",
        path="documents/myfile.txt",
        content="Full document text..."
    )
    
    # Create entity
    entity = create_entity_node(
        session,
        entity_id="entity456",
        name="Python",
        entity_type="Technology",
        description="Programming language"
    )
```

## Extending the System

### Adding Custom Processing Nodes

Create custom nodes for the LangGraph state machines:

```python
# In graphs/ingest_graph.py

def custom_processing_node(state: IngestState) -> IngestState:
    """Add custom document processing logic."""
    chunks = state["chunks"]
    
    # Your custom logic here
    processed_chunks = []
    for chunk in chunks:
        # Process each chunk
        processed = custom_transform(chunk)
        processed_chunks.append(processed)
    
    state["chunks"] = processed_chunks
    return state

# Add to workflow
workflow.add_node("custom_processing", custom_processing_node)
workflow.add_edge("chunk_document", "custom_processing")
workflow.add_edge("custom_processing", "generate_embeddings")
```

### Custom Retrieval Strategies

Extend the retrieval graph with custom ranking:

```python
# In graphs/retrieval_graph.py

def custom_reranker(state: RetrievalState) -> RetrievalState:
    """Apply custom reranking logic."""
    combined = state["combined_results"]
    
    # Your reranking algorithm
    reranked = custom_rank(combined)
    
    state["reranked_results"] = reranked
    return state
```

## Environment Configuration

All workflows respect environment variables from `.env`:

```bash
# Ollama Configuration (Local GPU)
OLLAMA_URL=http://host.docker.internal:11434
EMBEDDING_MODEL=bge-m3:latest
LLM_MODEL=bartowski/phi-3.5-mini-instruct-q5_k_m:latest
EMBEDDING_DIMENSIONS=1024

# Knowledge Graph Configuration
ENTITIES_LIST=AWS,Bedrock,Lambda,S3,EC2,Neo4j,Qdrant,MinIO,Ollama,LangChain
RELATIONSHIPS_LIST=contains,offers,uses,provides,integrates_with,depends_on
```

## Monitoring and Debugging

1. **Kestra UI**: Monitor flow executions at http://localhost:8080
2. **Logs**: View detailed logs for each task in the execution view
3. **Qdrant Dashboard**: Inspect collections at http://localhost:6333/dashboard
4. **Neo4J Browser**: Query graph at http://localhost:7474

## Next Steps

1. Upload documents to MinIO bucket `rag-documents/documents/`
2. Trigger ingestion flow via Kestra UI
3. Query via OpenAI-compatible API at http://localhost:8000/v1
4. Integrate with OpenWebUI or other LLM applications

