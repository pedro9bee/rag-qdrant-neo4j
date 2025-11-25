"""
Pipeline routes for staged RAG processing.

Multi-stage document processing pipeline:
1. Process         - Download from MinIO + Chunking → Redis
2. Extract Entities - GLiNER (Salad.com GPU) → Redis
3. Extract Relationships - Ollama qwen2.5:7b → Redis
4. Vectorize Chunks - bge-m3 + enrichment → Qdrant
5. Vectorize Entities - bge-m3 → Qdrant + Neo4j nodes
6. Vectorize Relationships - bge-m3 → Qdrant + Neo4j edges

Data Flow: MinIO → Stages 1-3 → Redis (48h) → Stages 4-6 → Qdrant + Neo4j
"""

import logging
import uuid
import boto3
from typing import Optional
from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel

from app.config import settings
from app.redis_state import redis_state
from app.markdown_chunker import markdown_chunker, MarkdownChunker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pipeline",
    tags=["🚀 Pipeline"]
)


# Pydantic models
class ProcessRequest(BaseModel):
    bucket: str
    file: str
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class ProcessResponse(BaseModel):
    job_id: str
    status: str
    file_size_mb: float
    estimated_chunks: int


class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: dict
    stats: dict
    created_at: str
    updated_at: str
    error: Optional[str] = None


class ExtractEntitiesRequest(BaseModel):
    job_id: str
    confidence_threshold: float = 0.90


class ValidateEntitiesRequest(BaseModel):
    job_id: str


class EmbeddingsRequest(BaseModel):
    job_id: str
    enrich: bool = True  # Enrich chunks with entities and relationships


class VectorizeEntitiesRequest(BaseModel):
    job_id: str
    store_graph: bool = True  # Also create Neo4j nodes


class RelationshipsRequest(BaseModel):
    job_id: str


class VectorizeRelationshipsRequest(BaseModel):
    job_id: str
    store_graph: bool = True  # Also create Neo4j edges
    cleanup_redis: bool = False  # Delete Redis data after success


async def _process_document_background(
    job_id: str,
    bucket: str,
    file: str,
    chunk_size: int = None,
    chunk_overlap: int = None
):
    """Background task for document processing."""
    try:
        logger.info(f"Background processing started: {job_id}")
        
        # Update status
        redis_state.update_job(job_id, status="downloading")
        
        # Create MinIO client
        s3 = boto3.client(
            's3',
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # Download file
        file_obj = s3.get_object(Bucket=bucket, Key=file)
        content = file_obj['Body'].read().decode('utf-8')
        
        # Update status
        redis_state.update_job(job_id, status="chunking")
        
        # Chunk document
        chunker = MarkdownChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        ) if chunk_size or chunk_overlap else markdown_chunker
        
        chunks = chunker.chunk(content, metadata={"source": file})
        
        # Save chunks to Redis
        redis_state.save_chunks(job_id, chunks)
        
        # Update job
        redis_state.update_job(
            job_id,
            status="chunks_ready",
            progress={"current": len(chunks), "total": len(chunks)},
            stats={"chunks": len(chunks)}
        )
        
        logger.info(f"Job {job_id}: Completed with {len(chunks)} chunks")
        
    except Exception as e:
        logger.error(f"Background processing failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, error=str(e))
        except:
            pass


@router.post("/process", response_model=ProcessResponse, summary="📥 1. Process Document", tags=["Pipeline - Stage 1: Processing"])
async def process_document(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    **Stage 1: Start pipeline processing (Asynchronous)**
    
    Returns immediately with `job_id`. Processing continues in background.
    
    ### Flow (Background):
    1. Download file from MinIO
    2. Intelligent chunking preserving markdown hierarchy
    3. Save chunks to Redis (48h TTL)
    
    ### Parameters:
    - **bucket**: MinIO bucket name
    - **file**: File path in bucket
    - **chunk_size**: Chunk size in characters (default: 1000)
    - **chunk_overlap**: Overlap between chunks (default: 200)
    
    ### Returns Immediately:
    - `job_id`: Unique ID to track the pipeline
    - `status`: "processing" (use /status/{job_id} to monitor)
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to track progress.
    """
    try:
        logger.info(f"Creating job: {request.bucket}/{request.file}")
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create MinIO client for validation only
        s3 = boto3.client(
            's3',
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            region_name='us-east-1'
        )
        
        # Quick validation: check if file exists
        try:
            response = s3.head_object(Bucket=request.bucket, Key=request.file)
            file_size = response['ContentLength']
            file_size_mb = file_size / (1024 * 1024)
            
            # Check size limit
            max_size_mb = getattr(settings, 'MAX_FILE_SIZE_MB', 50)
            if file_size_mb > max_size_mb:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large: {file_size_mb:.2f}MB (max: {max_size_mb}MB)"
                )
        except s3.exceptions.NoSuchKey:
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {request.bucket}/{request.file}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"MinIO connection error: {str(e)}"
            )
        
        # Create job in Redis
        redis_state.create_job(
            job_id=job_id,
            bucket=request.bucket,
            file=request.file,
            file_size_mb=file_size_mb,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            status="processing"
        )
        
        # Start background processing
        background_tasks.add_task(
            _process_document_background,
            job_id=job_id,
            bucket=request.bucket,
            file=request.file,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        
        logger.info(f"Job {job_id}: Created and queued for processing")
        
        return ProcessResponse(
            job_id=job_id,
            status="processing",
            file_size_mb=file_size_mb,
            estimated_chunks=0  # Will be calculated in background
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=StatusResponse, summary="📊 Check Job Status", tags=["Pipeline - Management"])
async def get_status(job_id: str):
    """
    **Check job status and progress**
    
    Returns detailed information about the current processing state.
    
    ### Possible States:
    - `created` - Job created
    - `downloading` - Downloading from MinIO
    - `chunking` - Processing chunks
    - `chunks_ready` - Chunks ready
    - `extracting_entities` - Extracting entities
    - `entities_extracted` - Entities extracted
    - `validating_entities` - Validating entities
    - `entities_validated` - Entities validated
    - `embedding` - Generating embeddings
    - `embedded` - Embeddings created
    - `complete` - Pipeline complete
    - `error` - Processing error
    """
    try:
        metadata = redis_state.get_job(job_id)
        
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return StatusResponse(**metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get status failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", summary="📋 List All Jobs", tags=["Pipeline - Management"])
async def list_jobs():
    """
    **List all active jobs**
    
    Returns list of all jobs in Redis (48h TTL).
    """
    try:
        jobs = redis_state.list_jobs()
        return {
            "jobs": jobs,
            "total": len(jobs)
        }
    except Exception as e:
        logger.error(f"List jobs failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/job/{job_id}", summary="🗑️ Delete Job", tags=["Pipeline - Management"])
async def delete_job(job_id: str):
    """
    **Delete job and all associated data**
    
    Removes from Redis: metadata, chunks, entities and relationships.
    """
    try:
        deleted = redis_state.delete_job(job_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return {
            "job_id": job_id,
            "deleted": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete job failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _extract_entities_background(job_id: str, confidence_threshold: float):
    """
    Background task for entity extraction.
    Uses GLiNER model (urchade/gliner_large-v2.1) via Salad.com GPU.
    """
    try:
        from app.entity_processor import entity_processor
        
        logger.info(f"Background entity extraction started: {job_id}")
        logger.info(f"Using GLiNER model to extract entities from chunks")
        
        # Get chunks
        chunks = redis_state.get_chunks(job_id)
        if not chunks:
            redis_state.update_job(job_id, error="No chunks found")
            return
        
        redis_state.update_job(job_id, status="extracting_entities")
        
        # Extract entities using GLiNER
        # Model: urchade/gliner_large-v2.1 via Salad.com GPU
        entities = await entity_processor.extract_entities_batch_parallel(chunks)
        
        # Save entities
        redis_state.save_entities(job_id, entities)
        
        # Update job - entities are extracted and ready
        redis_state.update_job(
            job_id,
            status="entities_validated",  # Skip validation step, entities are ready
            stats={
                "entities_raw": len(entities),
                "entities_validated": len(entities)  # All validated
            }
        )
        
        logger.info(f"Job {job_id}: Extracted {len(entities)} entities via GLiNER")
        
    except Exception as e:
        logger.error(f"❌ Background entity extraction failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, error=str(e))
        except:
            pass


@router.post("/extract-entities", summary="🤖 2. Extract Entities (GLiNER) - ASYNC", tags=["Pipeline - Stage 2: Entities"])
async def extract_entities(request: ExtractEntitiesRequest, background_tasks: BackgroundTasks):
    """
    **Stage 2: Extract entities using GLiNER (Asynchronous)**
    
    Returns immediately. Extraction continues in background.
    
    ### Process (Background):
    1. Load chunks from Redis
    2. Extract entities using GLiNER `urchade/gliner_large-v2.1` (Salad.com GPU)
    3. Process in parallel batches for performance
    4. Save entities to Redis with status "entities_validated"
    
    ### Parameters:
    - **job_id**: Job ID (from `/process`)
    - **confidence_threshold**: [OBSOLETE - ignored, kept for compatibility]
    
    ### Entity Types (GLiNER):
    - AWS_SERVICE, GENAI_MODEL, AI_CONCEPT, TOOL_LIB, ARCH_PATTERN, SECURITY, PROMPTING, ORG, PERSON
    
    ### Returns Immediately:
    - `job_id`: Job ID
    - `status`: "extracting_entities"
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to check when status = "entities_validated"
    
    ### Model:
    - GLiNER `urchade/gliner_large-v2.1` via Salad.com (GPU-accelerated)
    """
    try:
        # Get job
        metadata = redis_state.get_job(request.job_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        
        # Get chunks
        chunks = redis_state.get_chunks(request.job_id)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks found. Run /process first.")
        
        # Start background extraction
        background_tasks.add_task(
            _extract_entities_background,
            job_id=request.job_id,
            confidence_threshold=request.confidence_threshold
        )
        
        logger.info(f"Job {request.job_id}: Started entity extraction in background")
        
        return {
            "job_id": request.job_id,
            "status": "extracting_entities",
            "chunks_to_process": len(chunks),
            "message": "Entity extraction started in background. Use /status to monitor progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extract entities failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# OLD FUNCTION (COMMENTED) - spaCy entity validation
# ============================================================================
# No longer needed: GLiNER extracts entities directly without validation step
# async def _validate_entities_background(job_id: str):
#     """[ANTIGO] Background task for entity validation with parallel batching."""
#     try:
#         from app.entity_processor import entity_processor
#         
#         logger.info(f"Background validation started: {job_id}")
#         
#         # Get entities and chunks
#         entities = redis_state.get_entities(job_id)
#         chunks = redis_state.get_chunks(job_id)
#         
#         if not entities:
#             redis_state.update_job(job_id, error="No entities to validate")
#             return
#         
#         total = len(entities)
#         redis_state.update_job(
#             job_id,
#             status="validating_entities",
#             progress={"current": 0, "total": total}
#         )
#         
#         # Use parallel batch validation (novo método - 10x speedup)
#         validated = await entity_processor.validate_entities_batch_parallel(entities, chunks)
#         
#         # Save validated entities
#         redis_state.save_entities(job_id, validated)
#         
#         # Update job
#         redis_state.update_job(
#             job_id,
#             status="entities_validated",
#             progress={"current": total, "total": total},
#             stats={
#                 "entities_raw": total,
#                 "entities_validated": len(validated)
#             }
#         )
#         
#         logger.info(f"Job {job_id}: Validation complete - {len(validated)}/{total} valid")
#         
#     except Exception as e:
#         logger.error(f"❌ Background validation failed for {job_id}: {e}", exc_info=True)
#         try:
#             redis_state.update_job(job_id, error=str(e))
#         except:
#             pass


# ============================================================================
# OLD ENDPOINT (COMMENTED) - Separate validation no longer needed
# ============================================================================
# NEW APPROACH: /extract-entities returns validated entities from GLiNER
#
# @router.post("/validate-entities", summary="✅ 3. Validate Entities (LLM) - ASYNC", tags=["Pipeline - Stage 2: Entities"])
# async def validate_entities(request: ValidateEntitiesRequest, background_tasks: BackgroundTasks):
#     """
#     [OLD] Step 2b: Validate entities using LLM (Asynchronous)
#     OBSOLETE: GLiNER now extracts AND validates in a single step in /extract-entities
#     """
#     try:
#         from app.entity_processor import entity_processor
#         
#         metadata = redis_state.get_job(request.job_id)
#         if not metadata:
#             raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
#         
#         entities = redis_state.get_entities(request.job_id)
#         
#         if not entities:
#             raise HTTPException(status_code=400, detail="No entities found. Run /extract-entities first.")
#         
#         total = len(entities)
#         
#         redis_state.update_job(
#             request.job_id,
#             status="validating_entities",
#             progress={"current": 0, "total": total}
#         )
#         
#         background_tasks.add_task(_validate_entities_background, job_id=request.job_id)
#         
#         logger.info(f"Job {request.job_id}: Started validation of {total} entities in background")
#         
#         return {
#             "job_id": request.job_id,
#             "status": "validating_entities",
#             "entities_total": total,
#             "message": f"Validation started in background. This may take ~{total * 3} seconds ({total * 3 / 60:.1f} minutes). Use /status to monitor progress."
#         }
#         
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Validate entities failed: {e}", exc_info=True)
#         raise HTTPException(status_code=500, detail=str(e))


async def _generate_embeddings_background(job_id: str, enrich: bool = True):
    """Background task for embedding generation."""
    try:
        from app.embed_service import embed_service
        from app.ingest_service import ingest_service
        from app.validators import validate_embedding_dimensions
        import hashlib
        from qdrant_client.models import PointStruct
        
        logger.info(f"Background embedding generation started: {job_id} (enrich={enrich})")
        
        # Get job metadata
        metadata = redis_state.get_job(job_id)
        
        # Get chunks, entities, and relationships
        chunks = redis_state.get_chunks(job_id)
        entities = redis_state.get_entities(job_id)
        relationships = redis_state.get_relationships(job_id)
        
        if not chunks:
            redis_state.update_job(job_id, error="No chunks found")
            return
        
        redis_state.update_job(job_id, status="embedding")
        
        # Ensure collections
        await ingest_service.ensure_collections()
        
        # Map entities and relationships by chunk_index for enrichment
        entities_by_chunk = {}
        rels_by_chunk = {}
        
        if enrich:
            logger.info(f"Job {job_id}: Mapping entities and relationships for enrichment")
            
            # Map entities by chunk
            if entities:
                for entity in entities:
                    chunk_idx = entity.get("chunk_index")
                    if chunk_idx is not None:
                        if chunk_idx not in entities_by_chunk:
                            entities_by_chunk[chunk_idx] = []
                        entities_by_chunk[chunk_idx].append(entity["text"])
                logger.info(f"Job {job_id}: Mapped {len(entities)} entities across {len(entities_by_chunk)} chunks")
            
            # Map relationships by chunk
            if relationships:
                for rel in relationships:
                    chunk_idx = rel.get("chunk_index")
                    if chunk_idx is not None:
                        if chunk_idx not in rels_by_chunk:
                            rels_by_chunk[chunk_idx] = []
                        rels_by_chunk[chunk_idx].append({
                            "subject": rel.get("subject", ""),
                            "predicate": rel.get("predicate", ""),
                            "object": rel.get("object", "")
                        })
                logger.info(f"Job {job_id}: Mapped {len(relationships)} relationships across {len(rels_by_chunk)} chunks")
        
        # Generate chunk embeddings
        chunk_texts = [c["text"] for c in chunks]
        logger.info(f"Job {job_id}: Starting embedding of {len(chunk_texts)} chunks")
        
        chunk_embeddings = await embed_service.embed_documents(chunk_texts)
        
        logger.info(f"Job {job_id}: Validating embedding dimensions")
        validate_embedding_dimensions(chunk_embeddings, settings.EMBEDDING_DIMENSIONS)
        logger.info(f"Job {job_id}: ✅ All chunk embeddings validated (dim={settings.EMBEDDING_DIMENSIONS})")
        
        # Store chunks in Qdrant
        document_id = metadata["file"]
        
        points = []
        for chunk, embedding in zip(chunks, chunk_embeddings):
            # Deterministic UUID based on content - prevents duplicates on re-run
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:chunk:{chunk['index']}"))
            
            # Build payload
            payload = {
                "type": "chunk",
                "document_id": document_id,
                "chunk_index": chunk["index"],
                "text": chunk["text"],
                "metadata": chunk["metadata"]
            }
            
            # Enrich with entities and relationships if requested
            if enrich:
                chunk_idx = chunk["index"]
                payload["entities"] = entities_by_chunk.get(chunk_idx, [])
                payload["relationships"] = rels_by_chunk.get(chunk_idx, [])
            
            point = PointStruct(
                id=chunk_id,
                vector=embedding,
                payload=payload
            )
            points.append(point)
        
        # Upsert to Qdrant in batches to avoid timeout
        BATCH_SIZE = 50
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i + BATCH_SIZE]
            ingest_service.qdrant.upsert(
                collection_name=ingest_service.chunks_collection,
                points=batch
            )
            logger.info(f"Job {job_id}: Stored chunk batch {i//BATCH_SIZE + 1} ({len(batch)} chunks)")
        
        logger.info(f"Job {job_id}: ✅ Stored {len(points)} chunks in Qdrant")
        
        # Update job - ready for entity vectorization (Stage 5)
        redis_state.update_job(
            job_id,
            status="chunks_vectorized",
            stats={
                "chunks_vectorized": len(chunks),
                "chunks_enriched": enrich
            }
        )
        
        logger.info(f"✅ Job {job_id}: Chunk vectorization complete ({len(chunks)} chunks)")
        
    except Exception as e:
        logger.error(f"Background embedding failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, error=str(e))
        except:
            pass


@router.post("/vectorize-chunks", summary="🎯 4. Vectorize Chunks - ASYNC", tags=["Pipeline - Stage 4: Chunk Vectorization"])
async def vectorize_chunks(request: EmbeddingsRequest, background_tasks: BackgroundTasks):
    """
    **Stage 4: Vectorize chunks and store in Qdrant (Asynchronous)**
    
    Returns immediately. Vectorization continues in background.
    
    ### Process (Background):
    1. Load chunks, entities, and relationships from Redis
    2. If enrich=True, map entities and relationships by chunk_index
    3. Generate embeddings with `bge-m3:latest` (1024 dims)
    4. **Validate dimensions** (ensures 1024 dims)
    5. Store in Qdrant collection `rag_embeddings_chunks`
    
    ### Parameters:
    - **job_id**: Job ID
    - **enrich**: Enrich chunks with entities and relationships (default: True)
    
    ### Embedding Model:
    - `bge-m3:latest` (1024 dimensions)
    
    ### Qdrant Payload (enriched):
    - `type`: "chunk"
    - `text`: Chunk content
    - `entities`: Related entity names (if enrich=True)
    - `relationships`: Related triples (if enrich=True)
    
    ### Returns Immediately:
    - `job_id`: Job ID
    - `status`: "embedding"
    
    ### Automatic Validation:
    ✅ Verifies embeddings have exactly 1024 dimensions
    ❌ Fails if incorrect dimension (model error)
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to check when status = "chunks_vectorized"
    
    ### Next Step:
    Run Stage 5 `/pipeline/vectorize-entities` to vectorize entities
    """
    try:
        # Get job
        metadata = redis_state.get_job(request.job_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        
        # Get chunks
        chunks = redis_state.get_chunks(request.job_id)
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks found. Run /process first.")
        
        # Start background task
        background_tasks.add_task(
            _generate_embeddings_background, 
            job_id=request.job_id,
            enrich=request.enrich
        )
        
        logger.info(f"Job {request.job_id}: Started embedding generation in background")
        
        return {
            "job_id": request.job_id,
            "status": "embedding",
            "chunks_to_vectorize": len(chunks),
            "enrich": request.enrich,
            "message": "Chunk vectorization started in background. Use /status to monitor progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate embeddings failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _vectorize_entities_background(job_id: str, store_graph: bool = True):
    """
    Background task for entity vectorization and graph storage.
    """
    try:
        from app.embed_service import embed_service
        from app.ingest_service import ingest_service
        from app.graph_service import graph_service
        from app.validators import validate_embedding_dimensions
        from qdrant_client.models import PointStruct
        
        logger.info(f"Background entity vectorization started: {job_id} (store_graph={store_graph})")
        
        # Get entities and chunks
        entities = redis_state.get_entities(job_id)
        chunks = redis_state.get_chunks(job_id)
        
        if not entities:
            redis_state.update_job(job_id, error="No entities found")
            return
        
        redis_state.update_job(job_id, status="vectorizing_entities")
        
        # Ensure collections
        await ingest_service.ensure_collections()
        
        # Map chunk_ids for each entity (for cross-reference)
        logger.info(f"Job {job_id}: Mapping chunk_ids for entities")
        
        # Create a mapping of chunk_index to chunk UUID (we'll need to generate consistent IDs)
        # For now, we'll store chunk_indices since we don't have chunk UUIDs in Redis
        entities_with_refs = []
        for entity in entities:
            chunk_idx = entity.get("chunk_index")
            entity_data = {
                "text": entity["text"],
                "type": entity["type"],
                "description": entity.get("description", ""),
                "score": entity.get("score", 0.0),
                "chunk_index": chunk_idx,
                "chunk_indices": [chunk_idx] if chunk_idx is not None else []
            }
            entities_with_refs.append(entity_data)
        
        # Generate entity embeddings
        logger.info(f"Job {job_id}: Starting embedding of {len(entities_with_refs)} entities")
        entity_texts = [f"{e['text']} ({e['type']})" for e in entities_with_refs]
        entity_embeddings = await embed_service.embed_documents(entity_texts)
        
        logger.info(f"Job {job_id}: Validating entity embedding dimensions")
        validate_embedding_dimensions(entity_embeddings, settings.EMBEDDING_DIMENSIONS)
        logger.info(f"Job {job_id}: ✅ All entity embeddings validated (dim={settings.EMBEDDING_DIMENSIONS})")
        
        # Get job metadata for document_id
        metadata = redis_state.get_job(job_id)
        document_id = metadata["file"]
        
        # Store in Qdrant
        entity_points = []
        entity_nodes = []  # For Neo4j
        
        for entity, embedding in zip(entities_with_refs, entity_embeddings):
            # Deterministic UUID based on entity name + type - prevents duplicates on re-run
            entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:entity:{entity['text']}:{entity['type']}"))
            
            entity_point = PointStruct(
                id=entity_id,
                vector=embedding,
                payload={
                    "type": "entity",
                    "document_id": document_id,
                    "name": entity["text"],
                    "entity_type": entity["type"],
                    "description": entity["description"],
                    "chunk_indices": entity["chunk_indices"],
                    "score": entity["score"]
                }
            )
            entity_points.append(entity_point)
            
            # Prepare Neo4j node data
            if store_graph:
                entity_nodes.append({
                    "name": entity["text"],
                    "type": entity["type"],
                    "description": entity["description"],
                    "qdrant_id": entity_id,
                    "document_id": document_id,
                    "chunk_indices": entity["chunk_indices"]
                })
        
        # Upsert to Qdrant in batches to avoid timeout
        BATCH_SIZE = 50
        for i in range(0, len(entity_points), BATCH_SIZE):
            batch = entity_points[i:i + BATCH_SIZE]
            ingest_service.qdrant.upsert(
                collection_name=ingest_service.entities_collection,
                points=batch
            )
            logger.info(f"Job {job_id}: Stored batch {i//BATCH_SIZE + 1} ({len(batch)} entities)")
        
        logger.info(f"Job {job_id}: ✅ Stored {len(entity_points)} entities in Qdrant")
        
        # Store in Neo4j if requested
        neo4j_count = 0
        if store_graph:
            try:
                logger.info(f"Job {job_id}: Creating {len(entity_nodes)} nodes in Neo4j")
                for node in entity_nodes:
                    await graph_service.create_entity_node(
                        entity_id=node["qdrant_id"],
                        name=node["name"],
                        entity_type=node["type"],
                        description=node["description"]
                    )
                neo4j_count = len(entity_nodes)
                logger.info(f"Job {job_id}: ✅ Created {neo4j_count} nodes in Neo4j")
            except Exception as neo_error:
                logger.warning(f"Job {job_id}: Neo4j storage failed: {neo_error}")
                # Continue even if Neo4j fails
        
        # Update job status
        redis_state.update_job(
            job_id,
            status="entities_vectorized",
            stats={
                "entities_vectorized": len(entity_points),
                "neo4j_nodes": neo4j_count
            }
        )
        
        logger.info(f"✅ Job {job_id}: Entity vectorization complete ({len(entity_points)} vectors, {neo4j_count} nodes)")
        
    except Exception as e:
        logger.error(f"❌ Background entity vectorization failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, status="error", error=str(e))
        except:
            pass


@router.post("/vectorize-entities", summary="🎯 5. Vectorize Entities - ASYNC", tags=["Pipeline - Stage 5: Entity Vectorization"])
async def vectorize_entities(request: VectorizeEntitiesRequest, background_tasks: BackgroundTasks):
    """
    **Stage 5: Vectorize entities and store in Qdrant + Neo4j (Asynchronous)**
    
    Returns immediately. Vectorization continues in background.
    
    ### Process (Background):
    1. Load entities from Redis
    2. Load chunks from Redis (for chunk_ids cross-reference)
    3. Generate embeddings using bge-m3 (1024 dims)
    4. Store in Qdrant collection `rag_embeddings_entities`
    5. Create nodes in Neo4j (if store_graph=true)
    
    ### Parameters:
    - **job_id**: Job ID
    - **store_graph**: Also create Neo4j nodes (default: True)
    
    ### Qdrant Payload:
    - `name`: Entity name
    - `entity_type`: Entity type (AWS_SERVICE, GENAI_MODEL, etc.)
    - `description`: Entity description
    - `chunk_indices`: List of source chunk indices
    - `score`: Confidence score
    
    ### Neo4j Node:
    ```cypher
    CREATE (e:Entity {
      name: "AWS Lambda",
      type: "AWS_SERVICE",
      description: "...",
      qdrant_id: "entity-uuid"
    })
    ```
    
    ### Returns Immediately:
    - `job_id`: Job ID
    - `status`: "vectorizing_entities"
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to check when status = "entities_vectorized"
    """
    try:
        # Get job
        metadata = redis_state.get_job(request.job_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        
        # Get entities
        entities = redis_state.get_entities(request.job_id)
        if not entities:
            raise HTTPException(status_code=400, detail="No entities found. Run /extract-entities first.")
        
        # Start background task
        background_tasks.add_task(
            _vectorize_entities_background,
            job_id=request.job_id,
            store_graph=request.store_graph
        )
        
        logger.info(f"Job {request.job_id}: Started entity vectorization in background")
        
        return {
            "job_id": request.job_id,
            "status": "vectorizing_entities",
            "entities_count": len(entities),
            "store_graph": request.store_graph,
            "message": "Entity vectorization started in background. Use /status to monitor progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vectorize entities failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-relationships", summary="🔗 3. Extract Relationships - ASYNC", tags=["Pipeline - Stage 3: Extract Relationships"])
async def extract_relationships(request: RelationshipsRequest, background_tasks: BackgroundTasks):
    """
    **Stage 3: Extract relationships between entities (Asynchronous)**
    
    Returns immediately. Extraction continues in background.
    Saves extracted relationships to Redis ONLY. Vectorization happens in Stage 6.
    
    ### Process (Background):
    1. Load validated entities and chunks from Redis
    2. For each chunk, LLM analyzes relationships between entities
    3. Extract triples: BELONGS_TO, PART_OF, KNOWS, RELATED_TO, DEPENDS_ON, USES, etc.
    4. Save relationships to Redis (48h TTL)
    
    ### Parameters:
    - **job_id**: Job ID
    
    ### Model:
    - Ollama `qwen2.5:7b` (local inference)
    
    ### Returns Immediately:
    - `job_id`: Job ID
    - `status`: "extracting_relationships"
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to check when status = "relationships_extracted"
    
    ### Next Step:
    After extraction, run Stage 6 `/pipeline/vectorize-relationships` to store in Qdrant + Neo4j
    """
    try:
        # Get job
        metadata = redis_state.get_job(request.job_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        
        # Get entities and chunks
        entities = redis_state.get_entities(request.job_id)
        chunks = redis_state.get_chunks(request.job_id)
        
        if not entities:
            raise HTTPException(status_code=400, detail="No entities found. Run /extract-entities first.")
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks found. Run /process first.")
        
        # Update status
        redis_state.update_job(request.job_id, status="extracting_relationships")
        
        # Start background relationship extraction
        background_tasks.add_task(_extract_relationships_background, job_id=request.job_id)
        
        logger.info(f"Job {request.job_id}: Started relationship extraction in background ({len(entities)} entities, {len(chunks)} chunks)")
        
        return {
            "job_id": request.job_id,
            "status": "extracting_relationships",
            "entities_total": len(entities),
            "chunks_total": len(chunks),
            "message": f"Relationship extraction started in background. Use /status to monitor progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Extract relationships failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BACKGROUND TASK - Relationship Extraction
# ============================================================================

async def _extract_relationships_background(job_id: str):
    """
    Background task for relationship extraction.
    Uses Ollama (qwen2.5:7b) to extract relationships between entities.
    Only extracts and saves to Redis - vectorization is done in Stage 6.
    """
    try:
        from app.entity_processor import entity_processor
        
        logger.info(f"Background relationship extraction started: {job_id}")
        
        # Get entities and chunks
        entities = redis_state.get_entities(job_id)
        chunks = redis_state.get_chunks(job_id)
        
        if not entities or not chunks:
            redis_state.update_job(job_id, error="No entities or chunks found")
            return
        
        redis_state.update_job(job_id, status="extracting_relationships")
        
        # Extract relationships using LLM
        relationships = await entity_processor.extract_relationships_batch_parallel(chunks, entities)
        
        # Save relationships to Redis ONLY (vectorization in Stage 6)
        redis_state.save_relationships(job_id, relationships)
        
        # Update job status - ready for vectorization
        redis_state.update_job(
            job_id,
            status="relationships_extracted",
            stats={
                "relationships_extracted": len(relationships)
            }
        )
        
        logger.info(f"✅ Job {job_id}: Extracted {len(relationships)} relationships to Redis")
        
    except Exception as e:
        logger.error(f"❌ Background relationship extraction failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, status="error", error=str(e))
        except:
            pass


# ============================================================================
# STAGE 6: VECTORIZE RELATIONSHIPS
# ============================================================================

async def _vectorize_relationships_background(job_id: str, store_graph: bool = True, cleanup_redis: bool = False):
    """
    Background task for relationship vectorization and graph storage.
    """
    try:
        from app.embed_service import embed_service
        from app.ingest_service import ingest_service
        from app.graph_service import graph_service
        from app.validators import validate_embedding_dimensions
        from qdrant_client.models import PointStruct
        
        logger.info(f"Background relationship vectorization started: {job_id} (store_graph={store_graph}, cleanup_redis={cleanup_redis})")
        
        # Get relationships and metadata
        relationships = redis_state.get_relationships(job_id)
        metadata = redis_state.get_job(job_id)
        
        if not relationships:
            redis_state.update_job(job_id, error="No relationships found")
            return
        
        redis_state.update_job(job_id, status="vectorizing_relationships")
        
        # Ensure collections
        await ingest_service.ensure_collections()
        
        # Generate relationship embeddings
        # Fields: source, target, relation (from entity_processor)
        logger.info(f"Job {job_id}: Starting embedding of {len(relationships)} relationships")
        rel_texts = [f"{r.get('source', '')} {r.get('relation', '')} {r.get('target', '')}" for r in relationships]
        rel_embeddings = await embed_service.embed_documents(rel_texts)
        
        logger.info(f"Job {job_id}: Validating relationship embedding dimensions")
        validate_embedding_dimensions(rel_embeddings, settings.EMBEDDING_DIMENSIONS)
        logger.info(f"Job {job_id}: ✅ All relationship embeddings validated (dim={settings.EMBEDDING_DIMENSIONS})")
        
        # Get document_id
        document_id = metadata.get("file", "unknown")
        
        # Store in Qdrant
        rel_points = []
        for rel, embedding in zip(relationships, rel_embeddings):
            # Deterministic UUID based on source+relation+target - prevents duplicates on re-run
            source = rel.get("source", "")
            relation = rel.get("relation", "")
            target = rel.get("target", "")
            rel_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:rel:{source}:{relation}:{target}"))
            
            rel_point = PointStruct(
                id=rel_id,
                vector=embedding,
                payload={
                    "type": "relationship",
                    "document_id": document_id,
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "chunk_index": rel.get("chunk_index", -1)
                }
            )
            rel_points.append(rel_point)
        
        # Upsert to Qdrant in batches to avoid timeout
        BATCH_SIZE = 50
        for i in range(0, len(rel_points), BATCH_SIZE):
            batch = rel_points[i:i + BATCH_SIZE]
            ingest_service.qdrant.upsert(
                collection_name=ingest_service.relationships_collection,
                points=batch
            )
            logger.info(f"Job {job_id}: Stored relationship batch {i//BATCH_SIZE + 1} ({len(batch)} rels)")
        
        logger.info(f"Job {job_id}: ✅ Stored {len(rel_points)} relationships in Qdrant")
        
        # Store in Neo4j if requested
        neo4j_count = 0
        if store_graph:
            try:
                logger.info(f"Job {job_id}: Creating {len(relationships)} edges in Neo4j")
                for rel in relationships:
                    graph_service.create_relationship(
                        source=rel.get('source', ''),
                        relation=rel.get('relation', ''),
                        target=rel.get('target', ''),
                        chunk_index=rel.get('chunk_index', -1)
                    )
                neo4j_count = len(relationships)
                logger.info(f"Job {job_id}: ✅ Created {neo4j_count} edges in Neo4j")
            except Exception as neo_error:
                logger.warning(f"Job {job_id}: Neo4j storage failed: {neo_error}")
                # Continue even if Neo4j fails
        
        # Cleanup Redis if requested
        if cleanup_redis:
            try:
                redis_state.delete_job(job_id)
                logger.info(f"Job {job_id}: ✅ Cleaned up Redis data")
            except Exception as cleanup_error:
                logger.warning(f"Job {job_id}: Redis cleanup failed: {cleanup_error}")
        
        # Update job status
        redis_state.update_job(
            job_id,
            status="complete",
            stats={
                "relationships_vectorized": len(rel_points),
                "neo4j_edges": neo4j_count,
                "redis_cleaned": cleanup_redis
            }
        )
        
        logger.info(f"✅ Job {job_id}: Pipeline complete! ({len(rel_points)} relationship vectors, {neo4j_count} Neo4j edges)")
        
    except Exception as e:
        logger.error(f"❌ Background relationship vectorization failed for {job_id}: {e}", exc_info=True)
        try:
            redis_state.update_job(job_id, status="error", error=str(e))
        except:
            pass


@router.post("/vectorize-relationships", summary="🔗 6. Vectorize Relationships - ASYNC", tags=["Pipeline - Stage 6: Relationship Vectorization"])
async def vectorize_relationships(request: VectorizeRelationshipsRequest, background_tasks: BackgroundTasks):
    """
    **Stage 6: Vectorize relationships and store in Qdrant + Neo4j (Asynchronous)**
    
    Returns immediately. Vectorization continues in background.
    This is the final stage of the pipeline.
    
    ### Process (Background):
    1. Load relationships from Redis
    2. Generate embeddings using bge-m3 (1024 dims)
    3. Store in Qdrant collection `rag_embeddings_relationships`
    4. Create edges in Neo4j (if store_graph=true)
    5. Optionally cleanup Redis data (if cleanup_redis=true)
    
    ### Parameters:
    - **job_id**: Job ID
    - **store_graph**: Create Neo4j edges (default: True)
    - **cleanup_redis**: Delete Redis data after success (default: False)
    
    ### Qdrant Payload:
    - `subject`: Source entity
    - `predicate`: Relationship type
    - `object`: Target entity
    - `description`: Relationship description
    - `chunk_index`: Source chunk index
    
    ### Neo4j Edge:
    ```cypher
    MATCH (a:Entity {name: "Lambda"})
    MATCH (b:Entity {name: "Bedrock"})
    CREATE (a)-[r:INVOKES {description: "..."}]->(b)
    ```
    
    ### Returns Immediately:
    - `job_id`: Job ID
    - `status`: "vectorizing_relationships"
    
    ### Monitoring:
    Use `GET /pipeline/status/{job_id}` to check when status = "complete"
    """
    try:
        # Get job
        metadata = redis_state.get_job(request.job_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        
        # Get relationships
        relationships = redis_state.get_relationships(request.job_id)
        if not relationships:
            raise HTTPException(status_code=400, detail="No relationships found. Run /extract-relationships first.")
        
        # Start background task
        background_tasks.add_task(
            _vectorize_relationships_background,
            job_id=request.job_id,
            store_graph=request.store_graph,
            cleanup_redis=request.cleanup_redis
        )
        
        logger.info(f"Job {request.job_id}: Started relationship vectorization in background")
        
        return {
            "job_id": request.job_id,
            "status": "vectorizing_relationships",
            "relationships_count": len(relationships),
            "store_graph": request.store_graph,
            "cleanup_redis": request.cleanup_redis,
            "message": "Relationship vectorization started in background. Use /status to monitor progress."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vectorize relationships failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

