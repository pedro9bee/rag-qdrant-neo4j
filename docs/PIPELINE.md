# RAG Pipeline - Processing Stages

## Overview

The pipeline processes documents through 6 stages, using Redis as temporary storage (48h TTL) and persisting final data to Qdrant (vector search) and Neo4j (graph queries).

**Data Flow**: Source → Redis (Stages 1-3) → Qdrant/Neo4j (Stages 4-6) → Optional Redis Cleanup

**Current Status**: All stages (1-6) implemented and operational.

---

## Stage 1: Document Processing & Chunking

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/process`

**Process**:
- Downloads document from MinIO (book: "Generative AI with Amazon Bedrock.pdf")
- Converts PDF to markdown using Mineru (Master_pdf desktop app)
  - Note: API/container attempts failed without GPU/CUDA
- Splits using rule-based MarkdownChunker (no ML models)
- Preserves header hierarchy and context paths

**Parameters**:
- `bucket`: MinIO bucket name
- `file`: File path in bucket
- `chunk_size`: Maximum chunk size in characters (default: 1000)
- `chunk_overlap`: Overlap between chunks (default: 200)

**Storage**: Redis `job:{job_id}:chunks` (48h TTL)

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/process \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "documents",
    "file": "bedrock_docs.md",
    "chunk_size": 1000,
    "chunk_overlap": 200
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "processing",
  "file_size_mb": 2.5,
  "estimated_chunks": 0
}
```

**Output Structure**:
```json
{
  "index": 0,
  "text": "chunk content...",
  "start_char": 0,
  "end_char": 1000,
  "metadata": {
    "header_hierarchy": ["Chapter 1", "Section 1.1"],
    "section": "Introduction",
    "source": "file.md"
  }
}
```

---

## Stage 2: Entity Extraction

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/extract-entities`

**Process**:
- Loads chunks from Redis
- Extracts entities using GLiNER (GPU-accelerated via Salad.com)
- Model: `urchade/gliner_large-v2.1`
- Processes in parallel batches for performance

**Entity Types**:
`AWS_SERVICE`, `GENAI_MODEL`, `AI_CONCEPT`, `TOOL_LIB`, `ARCH_PATTERN`, `SECURITY`, `PROMPTING`, `ORG`, `PERSON`

**Storage**: Redis `job:{job_id}:entities` (48h TTL)

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/extract-entities \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
    "confidence_threshold": 0.90
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "extracting_entities",
  "chunks_total": 1094,
  "message": "Entity extraction started in background. Use /status to monitor progress."
}
```

**Output Structure**:
```json
{
  "text": "AWS Lambda",
  "type": "AWS_SERVICE",
  "description": "Entity extracted from context",
  "score": 0.95,
  "chunk_index": 0
}
```

---

## Stage 3: Relationship Extraction

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/extract-relationships`

**Process**:
- Loads chunks and entities from Redis
- Analyzes entity connections using Ollama (local inference)
- Model: `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M`
- Creates subject-predicate-object triples
- Saves to Redis ONLY (vectorization in Stage 6)

**Storage**: Redis `job:{job_id}:relationships` (48h TTL)

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/extract-relationships \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e"
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "extracting_relationships",
  "entities_total": 5633,
  "chunks_total": 1094,
  "message": "Relationship extraction started in background. Use /status to monitor progress."
}
```

**Output Structure**:
```json
{
  "source": "AWS Lambda",
  "relation": "invokes",
  "target": "Amazon Bedrock",
  "chunk_index": 10
}
```

**Next Step**: Run Stage 6 `/pipeline/vectorize-relationships` to store in Qdrant + Neo4j

---

## Stage 4: Chunk Vectorization & Enrichment

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/vectorize-chunks`

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/vectorize-chunks \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
    "enrich": true
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "vectorizing_chunks",
  "chunks_count": 1094,
  "enrich": true,
  "message": "Chunk vectorization started in background. Use /status to monitor progress."
}
```

**Process**:
1. Load chunks from Redis (`job:{job_id}:chunks`)
2. Load entities from Redis (`job:{job_id}:entities`)
3. Load relationships from Redis (`job:{job_id}:relationships`)
4. For each chunk:
   - Generate embedding using bge-m3 (1024 dims)
   - Enrich payload with related entities and relationships
5. Store in Qdrant collection `rag_embeddings_chunks`
6. Update job status to "chunks_vectorized"

**Qdrant Payload**:
```json
{
  "id": "chunk-uuid",
  "vector": [1024 dimensions],
  "payload": {
    "type": "chunk",
    "text": "chunk content...",
    "chunk_index": 0,
    "document_id": "file.md",
    "entities": ["AWS Lambda", "Amazon Bedrock"],
    "relationships": [
      {"subject": "Lambda", "predicate": "invokes", "object": "Bedrock"}
    ],
    "metadata": {
      "header_hierarchy": ["Chapter 1"],
      "section": "Introduction"
    }
  }
}
```

**Purpose**: Enables semantic search over document content with entity context.

---

## Stage 5: Entity Vectorization & Graph Nodes

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/vectorize-entities`

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/vectorize-entities \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
    "store_graph": true
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "vectorizing_entities",
  "entities_count": 5633,
  "store_graph": true,
  "message": "Entity vectorization started in background. Use /status to monitor progress."
}
```

**Process**:
1. Load entities from Redis (`job:{job_id}:entities`)
2. Load chunks from Redis (for chunk_ids cross-reference)
3. For each entity:
   - Generate embedding using bge-m3 (1024 dims)
   - Store in Qdrant collection `rag_embeddings_entities`
   - Create node in Neo4j (if store_graph=true)
4. Update job status to "entities_vectorized"

**Qdrant Payload**:
```json
{
  "id": "entity-uuid",
  "vector": [1024 dimensions],
  "payload": {
    "type": "entity",
    "name": "AWS Lambda",
    "entity_type": "AWS_SERVICE",
    "description": "Serverless compute service",
    "chunk_ids": ["chunk-uuid-1", "chunk-uuid-2"],
    "chunk_indices": [0, 5, 12],
    "score": 0.95
  }
}
```

**Neo4j Node**:
```cypher
MERGE (e:Entity {name: "AWS Lambda"})
SET e.type = "AWS_SERVICE",
    e.description = "Serverless compute service"
CALL apoc.create.addLabels(e, ["AWS_SERVICE"]) YIELD node
RETURN node
```

**Note**: Entities are created with dynamic labels (e.g., `:Entity:AWS_SERVICE`) using APOC.

**Purpose**: Enables entity-based search and graph traversal with source chunk references.

---

## Stage 6: Relationship Vectorization & Graph Edges

**Status**: ✅ Implemented

**Endpoint**: `POST /pipeline/vectorize-relationships`

**Example CURL Request**:
```bash
curl -X POST http://localhost:8000/pipeline/vectorize-relationships \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
    "store_graph": true,
    "cleanup_redis": false
  }'
```

**Example Response**:
```json
{
  "job_id": "c259afd5-dd5b-4474-b26e-3be7c0b8c15e",
  "status": "vectorizing_relationships",
  "relationships_count": 4421,
  "store_graph": true,
  "cleanup_redis": false,
  "message": "Relationship vectorization started in background. Use /status to monitor progress."
}
```

**Process**:
1. Load relationships from Redis (`job:{job_id}:relationships`)
2. Load chunks from Redis (for chunk_ids)
3. For each relationship:
   - Generate embedding using bge-m3 (1024 dims)
   - Store in Qdrant collection `rag_embeddings_relationships`
   - Create edge in Neo4j (if store_graph=true)
4. If cleanup_redis=true, delete job data from Redis
5. Update job status to "complete"

**Qdrant Payload**:
```json
{
  "id": "rel-uuid",
  "vector": [1024 dimensions],
  "payload": {
    "type": "relationship",
    "document_id": "bedrock_docs.md",
    "source": "AWS Lambda",
    "relation": "invokes",
    "target": "Amazon Bedrock",
    "chunk_index": 10
  }
}
```

**Neo4j Relationship**:
```cypher
MERGE (a:Entity {name: "AWS Lambda"})
MERGE (b:Entity {name: "Amazon Bedrock"})
MERGE (a)-[r:INVOKES]->(b)
SET r.chunk_index = 10,
    r.updated_at = timestamp()
RETURN r
```

**Note**: Relationships create edges between existing entities (or create entities if they don't exist), forming the complete knowledge graph.

**Purpose**: Completes the knowledge graph with vectorized relationships for hybrid retrieval.

---

## Data Persistence Strategy

### Redis (Temporary Storage - 48h TTL)
- Stages 1-3 write intermediate results
- Stages 4-6 read from Redis for vectorization
- Data remains available for debugging/reprocessing
- Optional cleanup in Stage 6 with `cleanup_redis=true`

### Qdrant (Vector Search - Persistent)
- 3 separate collections for chunks, entities, relationships
- All use 1024-dimensional vectors from bge-m3
- Enables semantic similarity search

### Neo4j (Graph Database - Persistent)
- Entities as nodes, relationships as edges
- Enables graph traversal and structural queries
- Linked to Qdrant via IDs for hybrid retrieval

---

## Pipeline Management

### Check Job Status
```bash
curl -X GET http://localhost:8000/pipeline/status/c259afd5-dd5b-4474-b26e-3be7c0b8c15e
```

### List All Jobs
```bash
curl -X GET http://localhost:8000/pipeline/jobs
```

### Delete Job Data
```bash
curl -X DELETE http://localhost:8000/pipeline/job/c259afd5-dd5b-4474-b26e-3be7c0b8c15e
```

---

## Models Used

- **Chunking**: MarkdownChunker (rule-based, no ML)
- **Embeddings**: `bge-m3:latest` (1024 dims, Ollama local)
- **Entity Extraction**: GLiNER `urchade/gliner_large-v2.1` (Salad.com GPU)
- **Relationships**: `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M` (Ollama local)

---

## Complete Pipeline Example

Execute all stages in sequence:

```bash
# Stage 1: Process document
JOB_ID=$(curl -s -X POST http://localhost:8000/pipeline/process \
  -H "Content-Type: application/json" \
  -d '{"bucket": "documents", "file": "bedrock_docs.md", "chunk_size": 1000, "chunk_overlap": 200}' \
  | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# Wait for Stage 1 to complete (check status)
curl -X GET http://localhost:8000/pipeline/status/$JOB_ID

# Stage 2: Extract entities
curl -X POST http://localhost:8000/pipeline/extract-entities \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"confidence_threshold\": 0.90}"

# Wait for Stage 2 to complete
curl -X GET http://localhost:8000/pipeline/status/$JOB_ID

# Stage 3: Extract relationships
curl -X POST http://localhost:8000/pipeline/extract-relationships \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\"}"

# Wait for Stage 3 to complete
curl -X GET http://localhost:8000/pipeline/status/$JOB_ID

# Stage 4: Vectorize chunks
curl -X POST http://localhost:8000/pipeline/vectorize-chunks \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"enrich\": true}"

# Stage 5: Vectorize entities
curl -X POST http://localhost:8000/pipeline/vectorize-entities \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"store_graph\": true}"

# Stage 6: Vectorize relationships (final stage)
curl -X POST http://localhost:8000/pipeline/vectorize-relationships \
  -H "Content-Type: application/json" \
  -d "{\"job_id\": \"$JOB_ID\", \"store_graph\": true, \"cleanup_redis\": false}"

# Check final status
curl -X GET http://localhost:8000/pipeline/status/$JOB_ID
```
