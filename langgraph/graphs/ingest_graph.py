"""LangGraph workflow for document ingestion."""

import os
import logging
import hashlib
import json
from typing import List, Dict, Any, Set
from langgraph.graph import StateGraph, END

from langgraph.graphs.shared import IngestState
from langgraph.utils.connections import (
    get_minio_client,
    get_qdrant_client,
    get_neo4j_driver,
    neo4j_session,
    get_openai_embeddings,
    get_openai_llm
)
from langgraph.utils.chunking import chunk_text, chunk_markdown
from langgraph.utils.neo4j_schema import (
    create_indexes,
    create_document_node,
    create_chunk_node,
    create_entity_node,
    link_entity_to_chunk
)

logger = logging.getLogger(__name__)

# Load spaCy model (lazy loading)
_nlp = None

def get_spacy_nlp():
    """Lazy load spaCy model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("spaCy model 'en_core_web_sm' not found. Run: python -m spacy download en_core_web_sm")
            raise
    return _nlp


def scan_minio_bucket(state: IngestState) -> IngestState:
    """
    Scan MinIO bucket for text and markdown files.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with document list
    """
    logger.info(f"Scanning MinIO bucket: {state['minio_bucket']}/{state['minio_path']}")
    
    try:
        minio_client = get_minio_client()
        
        # List objects in bucket
        objects = minio_client.list_objects(
            state["minio_bucket"],
            prefix=state["minio_path"],
            recursive=True
        )
        
        documents = []
        for obj in objects:
            # Filter for text and markdown files
            if obj.key.endswith(('.txt', '.md')):
                documents.append({
                    "key": obj.key,
                    "size": obj.size,
                    "etag": obj.etag,
                    "last_modified": obj.last_modified
                })
        
        logger.info(f"Found {len(documents)} documents")
        
        state["documents"] = documents
        state["processed_count"] = 0
        
    except Exception as e:
        logger.error(f"MinIO scan failed: {e}")
        state["error"] = str(e)
    
    return state


def download_document(state: IngestState) -> IngestState:
    """
    Download and read document content from MinIO.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with document content
    """
    if state.get("error"):
        return state
    
    # Get next document to process
    documents = state["documents"]
    processed = state["processed_count"]
    
    if processed >= len(documents):
        logger.info("All documents processed")
        return state
    
    current_doc = documents[processed]
    logger.info(f"Downloading document: {current_doc['key']}")
    
    try:
        minio_client = get_minio_client()
        
        # Download object
        response = minio_client.get_object(
            state["minio_bucket"],
            current_doc["key"]
        )
        
        content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        
        state["current_document"] = current_doc
        state["document_content"] = content
        
        logger.info(f"Downloaded {len(content)} characters")
        
    except Exception as e:
        logger.error(f"Document download failed: {e}")
        state["error"] = str(e)
    
    return state


def chunk_document(state: IngestState) -> IngestState:
    """
    Split document into chunks.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with chunks
    """
    if state.get("error"):
        return state
    
    doc = state["current_document"]
    content = state["document_content"]
    
    logger.info(f"Chunking document: {doc['key']}")
    
    try:
        # Determine chunking strategy based on file extension
        if doc["key"].endswith(".md"):
            chunks = chunk_markdown(
                content,
                metadata={"document_key": doc["key"]}
            )
        else:
            chunks = chunk_text(
                content,
                metadata={"document_key": doc["key"]}
            )
        
        # Convert to dict format
        state["chunks"] = [
            {
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "metadata": chunk.metadata
            }
            for chunk in chunks
        ]
        
        logger.info(f"Created {len(state['chunks'])} chunks")
        
    except Exception as e:
        logger.error(f"Chunking failed: {e}")
        state["error"] = str(e)
    
    return state


def generate_embeddings(state: IngestState) -> IngestState:
    """
    Generate embeddings for chunks using Ollama (bge-m3).
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with embeddings
    """
    if state.get("error"):
        return state
    
    chunks = state["chunks"]
    logger.info(f"Generating embeddings for {len(chunks)} chunks using Ollama bge-m3")
    
    try:
        embeddings_model = get_openai_embeddings()
        
        # Extract chunk texts
        texts = [chunk["text"] for chunk in chunks]
        
        # Generate embeddings (OllamaEmbeddings handles batching internally)
        all_embeddings = embeddings_model.embed_documents(texts)
        
        state["embeddings"] = all_embeddings
        
        logger.info(f"Generated {len(all_embeddings)} embeddings (dim: {len(all_embeddings[0]) if all_embeddings else 0})")
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        state["error"] = str(e)
    
    return state


def extract_relationships(state: IngestState) -> IngestState:
    """
    Extract relationships between entities using Phi-3.5 LLM.
    
    Implementation follows Implementation.md specification:
    Uses exact prompt from spec for relationship extraction.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with relationships
    """
    if state.get("error"):
        return state
    
    chunks = state["chunks"]
    entities = state.get("entities", [])
    
    logger.info(f"Extracting relationships from {len(chunks)} chunks")
    
    if not entities:
        logger.warning("No entities found, skipping relationship extraction")
        state["relationships"] = []
        return state
    
    try:
        llm = get_openai_llm()
        
        # Get allowed entities and relationships from environment
        entities_list_str = os.getenv("ENTITIES_LIST", "")
        relationships_list_str = os.getenv("RELATIONSHIPS_LIST", "")
        
        all_relationships = []
        
        # Process each chunk
        for chunk in chunks:
            chunk_text = chunk["text"]
            chunk_index = chunk["chunk_index"]
            
            # Check if this chunk has any validated entities
            chunk_entities = [e for e in entities if e["chunk_index"] == chunk_index]
            if not chunk_entities:
                continue
            
            # Use exact prompt from Implementation.md
            extraction_prompt = f"""Extract all meaningful relationships between entities from the allowed list that exist in the text.

Allowed entities: {entities_list_str}

Text:
{chunk_text}

Return ONLY a valid JSON array of triples (can be empty). 
Predicates must be in English, lowercase, snake_case, infinitive form.

Example:
[
  {{"subject": "AWS", "predicate": "contains", "object": "Bedrock"}},
  {{"subject": "Bedrock", "predicate": "offers", "object": "Claude"}}
]

Do not explain. Do not add extra text."""
            
            try:
                response = llm.invoke(extraction_prompt)
                response_text = response.content.strip()
                
                # Try to parse JSON response
                try:
                    relationships = json.loads(response_text)
                    
                    if isinstance(relationships, list):
                        for rel in relationships:
                            if isinstance(rel, dict) and "subject" in rel and "predicate" in rel and "object" in rel:
                                all_relationships.append({
                                    "subject": rel["subject"],
                                    "predicate": rel["predicate"],
                                    "object": rel["object"],
                                    "chunk_index": chunk_index
                                })
                        
                        logger.debug(f"Chunk {chunk_index}: Extracted {len(relationships)} relationships")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON from LLM for chunk {chunk_index}: {e}")
                    logger.debug(f"Response was: {response_text[:200]}")
                    continue
                    
            except Exception as e:
                logger.warning(f"Relationship extraction failed for chunk {chunk_index}: {e}")
                continue
        
        state["relationships"] = all_relationships
        
        logger.info(f"Extracted {len(all_relationships)} relationships")
        
    except Exception as e:
        logger.error(f"Relationship extraction failed: {e}", exc_info=True)
        state["relationships"] = []
    
    return state


def store_in_qdrant(state: IngestState) -> IngestState:
    """
    Store embeddings in Qdrant vector database.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state
    """
    if state.get("error"):
        return state
    
    doc = state["current_document"]
    chunks = state["chunks"]
    embeddings = state["embeddings"]
    
    logger.info(f"Storing {len(embeddings)} vectors in Qdrant")
    
    try:
        qdrant = get_qdrant_client()
        collection_name = os.getenv("QDRANT_COLLECTION_NAME", "rag_embeddings")
        
        # Ensure collection exists
        from qdrant_client.models import Distance, VectorParams
        
        try:
            qdrant.get_collection(collection_name)
        except:
            # Create collection if it doesn't exist (bge-m3 dimensions = 1024)
            dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
            qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=dimensions,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created Qdrant collection: {collection_name} (dim: {dimensions})")
        
        # Prepare points
        from qdrant_client.models import PointStruct
        
        points = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Generate unique ID for chunk
            chunk_id = hashlib.sha256(
                f"{doc['key']}_{chunk['chunk_index']}".encode()
            ).hexdigest()
            
            point = PointStruct(
                id=chunk_id,
                vector=embedding,
                payload={
                    "document_key": doc["key"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"]
                }
            )
            points.append(point)
        
        # Upsert points
        qdrant.upsert(
            collection_name=collection_name,
            points=points
        )
        
        logger.info(f"Stored {len(points)} vectors in Qdrant")
        
    except Exception as e:
        logger.error(f"Qdrant storage failed: {e}")
        state["error"] = str(e)
    
    return state


def extract_entities(state: IngestState) -> IngestState:
    """
    Extract and validate entities using spaCy NER + Phi-3.5 LLM validation.
    
    Implementation follows Implementation.md specification:
    1. Use spaCy for initial NER detection on each chunk
    2. Filter detected entities against ENTITIES_LIST from env
    3. Validate each entity with Phi-3.5 using validation prompt
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with validated entities
    """
    if state.get("error"):
        return state
    
    chunks = state["chunks"]
    logger.info(f"Extracting entities from {len(chunks)} chunks using spaCy + Phi-3.5 validation")
    
    try:
        # Load spaCy NER model
        nlp = get_spacy_nlp()
        
        # Load Phi-3.5 LLM for validation
        llm = get_openai_llm()
        
        # Get allowed entities list from environment
        entities_list_str = os.getenv("ENTITIES_LIST", "")
        allowed_entities: Set[str] = set(e.strip() for e in entities_list_str.split(",") if e.strip())
        
        if not allowed_entities:
            logger.warning("ENTITIES_LIST is empty, no entities will be extracted")
            state["entities"] = []
            return state
        
        logger.info(f"Allowed entities: {allowed_entities}")
        
        all_entities = []
        
        # Process each chunk
        for chunk in chunks:
            chunk_text = chunk["text"]
            chunk_index = chunk["chunk_index"]
            
            # Step 1: spaCy NER detection
            doc = nlp(chunk_text)
            detected_entities = []
            
            for ent in doc.ents:
                # Map spaCy entity types to our entity list
                entity_text = ent.text.strip()
                
                # Check if entity matches any in our allowed list (case-insensitive partial match)
                for allowed_entity in allowed_entities:
                    if allowed_entity.lower() in entity_text.lower() or entity_text.lower() in allowed_entity.lower():
                        detected_entities.append({
                            "name": allowed_entity,  # Use the canonical name from list
                            "text": entity_text,     # Original text from document
                            "label": ent.label_,     # spaCy label (PERSON, ORG, etc.)
                            "start": ent.start_char,
                            "end": ent.end_char
                        })
                        break
            
            # Also check for exact mentions of allowed entities
            chunk_lower = chunk_text.lower()
            for allowed_entity in allowed_entities:
                if allowed_entity.lower() in chunk_lower:
                    # Avoid duplicates
                    if not any(e["name"] == allowed_entity for e in detected_entities):
                        detected_entities.append({
                            "name": allowed_entity,
                            "text": allowed_entity,
                            "label": "KEYWORD",
                            "start": -1,
                            "end": -1
                        })
            
            logger.debug(f"Chunk {chunk_index}: Detected {len(detected_entities)} candidate entities")
            
            # Step 2: Validate each entity with Phi-3.5
            for entity in detected_entities:
                validation_prompt = f"""You are an expert entity validator. Does the following text contain the entity "{entity['name']}" in a relevant, central, meaningful way (not just a passing mention)?

Text:
{chunk_text}

Answer with ONLY "YES" or "NO"."""
                
                try:
                    response = llm.invoke(validation_prompt)
                    answer = response.content.strip().upper()
                    
                    if "YES" in answer:
                        # Entity validated - add to results
                        all_entities.append({
                            "name": entity["name"],
                            "type": entity["label"],
                            "chunk_index": chunk_index,
                            "original_text": entity["text"],
                            "description": f"Entity '{entity['name']}' found in context"
                        })
                        logger.debug(f"Validated entity: {entity['name']} in chunk {chunk_index}")
                    else:
                        logger.debug(f"Rejected entity: {entity['name']} in chunk {chunk_index}")
                        
                except Exception as e:
                    logger.warning(f"Validation failed for entity '{entity['name']}': {e}")
                    continue
        
        state["entities"] = all_entities
        
        logger.info(f"Extracted and validated {len(all_entities)} entities")
        
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}", exc_info=True)
        # Non-critical error, continue without entities
        state["entities"] = []
    
    return state


def store_in_neo4j(state: IngestState) -> IngestState:
    """
    Store document, chunks, and entities in Neo4J.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state
    """
    if state.get("error"):
        return state
    
    doc = state["current_document"]
    chunks = state["chunks"]
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    
    logger.info(f"Storing document graph in Neo4J")
    
    try:
        driver = get_neo4j_driver()
        
        # Ensure indexes exist
        create_indexes(driver)
        
        with neo4j_session(driver) as session:
            # Create document node
            doc_id = hashlib.sha256(doc["key"].encode()).hexdigest()
            create_document_node(
                session,
                document_id=doc_id,
                path=doc["key"],
                content=state["document_content"],
                metadata={
                    "size": doc["size"],
                    "etag": doc["etag"]
                }
            )
            
            # Create chunk nodes
            chunk_id_map = {}
            for chunk in chunks:
                chunk_id = hashlib.sha256(
                    f"{doc['key']}_{chunk['chunk_index']}".encode()
                ).hexdigest()
                
                create_chunk_node(
                    session,
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    start_char=chunk["start_char"],
                    end_char=chunk["end_char"],
                    metadata=chunk["metadata"]
                )
                
                chunk_id_map[chunk["chunk_index"]] = chunk_id
            
            # Create entity nodes
            entity_id_map = {}
            for entity in entities:
                entity_id = hashlib.sha256(
                    f"{entity['name']}_{entity['type']}".encode()
                ).hexdigest()
                
                create_entity_node(
                    session,
                    entity_id=entity_id,
                    name=entity["name"],
                    entity_type=entity["type"],
                    description=entity.get("description")
                )
                
                # Link to chunk
                chunk_idx = entity.get("chunk_index")
                if chunk_idx is not None and chunk_idx in chunk_id_map:
                    link_entity_to_chunk(
                        session,
                        entity_id=entity_id,
                        chunk_id=chunk_id_map[chunk_idx]
                    )
                
                entity_id_map[entity["name"]] = entity_id
            
            # Create entity relationships
            from langgraph.utils.neo4j_schema import create_entity_relationship
            
            for rel in relationships:
                source_id = entity_id_map.get(rel["source"])
                target_id = entity_id_map.get(rel["target"])
                
                if source_id and target_id:
                    create_entity_relationship(
                        session,
                        source_entity_id=source_id,
                        target_entity_id=target_id,
                        relationship_type=rel["type"].upper().replace(" ", "_")
                    )
        
        driver.close()
        
        logger.info(f"Stored document graph in Neo4J")
        
        # Increment processed count
        state["processed_count"] += 1
        
    except Exception as e:
        logger.error(f"Neo4J storage failed: {e}")
        state["error"] = str(e)
    
    return state


def should_continue(state: IngestState) -> str:
    """
    Determine if more documents need processing.
    
    Args:
        state: Current workflow state
        
    Returns:
        Next node name or END
    """
    if state.get("error"):
        return END
    
    if state["processed_count"] < len(state["documents"]):
        return "download_document"
    
    return END


# Build the graph
def build_ingest_graph() -> StateGraph:
    """
    Build and compile the ingestion workflow graph.
    
    Flow:
    1. Scan MinIO for documents
    2. Download each document
    3. Chunk document into smaller pieces
    4. Generate embeddings (Ollama bge-m3)
    5. Store embeddings in Qdrant
    6. Extract entities (spaCy NER + Phi-3.5 validation)
    7. Extract relationships (Phi-3.5 with allowed entities)
    8. Store graph in Neo4j
    9. Loop back for next document or END
    
    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(IngestState)
    
    # Add nodes
    workflow.add_node("scan_minio", scan_minio_bucket)
    workflow.add_node("download_document", download_document)
    workflow.add_node("chunk_document", chunk_document)
    workflow.add_node("generate_embeddings", generate_embeddings)
    workflow.add_node("store_qdrant", store_in_qdrant)
    workflow.add_node("extract_entities", extract_entities)
    workflow.add_node("extract_relationships", extract_relationships)
    workflow.add_node("store_neo4j", store_in_neo4j)
    
    # Define edges
    workflow.set_entry_point("scan_minio")
    workflow.add_edge("scan_minio", "download_document")
    workflow.add_edge("download_document", "chunk_document")
    workflow.add_edge("chunk_document", "generate_embeddings")
    workflow.add_edge("generate_embeddings", "store_qdrant")
    workflow.add_edge("store_qdrant", "extract_entities")
    workflow.add_edge("extract_entities", "extract_relationships")
    workflow.add_edge("extract_relationships", "store_neo4j")
    
    # Conditional edge for processing next document
    workflow.add_conditional_edges(
        "store_neo4j",
        should_continue,
        {
            "download_document": "download_document",
            END: END
        }
    )
    
    return workflow.compile()

