"""
Ingestion service for processing documents into the RAG system.
"""

import logging
import hashlib
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.config import settings
from app.chunk_service import chunk_service
from app.embed_service import embed_service
from app.graph_service import graph_service

logger = logging.getLogger(__name__)


class IngestService:
    """Service for ingesting documents into the RAG system."""
    
    def __init__(self):
        """Initialize the ingest service."""
        self.qdrant = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            timeout=60  # Increase timeout to 60 seconds
        )
        
        # Collection names for different data types
        self.chunks_collection = f"{settings.QDRANT_COLLECTION_NAME}_chunks"
        self.entities_collection = f"{settings.QDRANT_COLLECTION_NAME}_entities"
        self.relationships_collection = f"{settings.QDRANT_COLLECTION_NAME}_relationships"
        
        logger.info("IngestService initialized")
    
    async def ensure_collections(self):
        """
        Ensure all 3 Qdrant collections exist:
        1. chunks - for document chunk embeddings
        2. entities - for entity embeddings
        3. relationships - for relationship embeddings
        """
        collections = [
            (self.chunks_collection, "Document chunks"),
            (self.entities_collection, "Entities"),
            (self.relationships_collection, "Relationships")
        ]
        
        for collection_name, description in collections:
            try:
                self.qdrant.get_collection(collection_name)
                logger.debug(f"Collection exists: {collection_name} ({description})")
            except:
                # Create collection if it doesn't exist
                self.qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIMENSIONS,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {collection_name} ({description})")
    
    async def ingest_document(
        self,
        document_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        is_markdown: bool = False
    ) -> Dict[str, Any]:
        """
        Ingest a document into the RAG system.
        
        Steps:
        1. Chunk the document
        2. Generate embeddings
        3. Store in Qdrant
        4. Create graph structure in Neo4j
        
        Args:
            document_id: Unique document identifier
            content: Document content
            metadata: Optional metadata
            is_markdown: Whether content is markdown
            
        Returns:
            Ingestion statistics
        """
        logger.info(f"Ingesting document: {document_id}")
        
        # Ensure collections exist
        await self.ensure_collections()
        
        # Step 1: Chunk document
        if is_markdown:
            chunks = await chunk_service.chunk_markdown(content, metadata)
        else:
            chunks = await chunk_service.chunk_text(content, metadata)
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 2: Generate embeddings
        texts = [chunk["text"] for chunk in chunks]
        embeddings = await embed_service.embed_documents(texts)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # Step 3: Store in Qdrant (chunks collection)
        points = []
        chunk_ids = []
        
        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = hashlib.sha256(
                f"{document_id}_{chunk['chunk_index']}".encode()
            ).hexdigest()
            chunk_ids.append(chunk_id)
            
            point = PointStruct(
                id=chunk_id,
                vector=embedding,
                payload={
                    "type": "chunk",
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                    "start_char": chunk["start_char"],
                    "end_char": chunk["end_char"],
                    "metadata": chunk["metadata"]
                }
            )
            points.append(point)
        
        self.qdrant.upsert(
            collection_name=self.chunks_collection,
            points=points
        )
        
        logger.info(f"Stored {len(points)} chunk vectors in Qdrant")
        
        # Step 4: Create graph structure in Neo4j
        await graph_service.create_indexes()
        
        # Create document node
        doc_id_hash = hashlib.sha256(document_id.encode()).hexdigest()
        await graph_service.create_document_node(
            document_id=doc_id_hash,
            path=document_id,
            content=content,
            metadata=metadata or {}
        )
        
        # Create chunk nodes
        for chunk, chunk_id in zip(chunks, chunk_ids):
            await graph_service.create_chunk_node(
                chunk_id=chunk_id,
                document_id=doc_id_hash,
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                start_char=chunk["start_char"],
                end_char=chunk["end_char"],
                metadata=chunk["metadata"]
            )
        
        logger.info(f"Created graph structure in Neo4j")
        
        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "embeddings_generated": len(embeddings),
            "vectors_stored": len(points),
            "graph_nodes_created": len(chunks) + 1  # chunks + document
        }
    
    async def ingest_entities(
        self,
        document_id: str,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingest entities extracted from a document.
        
        Stores entities in both Neo4j (graph) and Qdrant (vector embeddings).
        
        Args:
            document_id: Document identifier
            entities: List of entity dictionaries with 'name', 'type', 'description'
            
        Returns:
            Ingestion statistics
        """
        logger.info(f"Ingesting {len(entities)} entities for document: {document_id}")
        
        # Ensure collections exist
        await self.ensure_collections()
        
        doc_id_hash = hashlib.sha256(document_id.encode()).hexdigest()
        
        # Prepare entity texts for embedding
        entity_texts = []
        entity_data = []
        
        for entity in entities:
            # Create entity text for embedding (name + type + description)
            entity_text = f"{entity['name']} ({entity.get('type', 'UNKNOWN')})"
            if entity.get('description'):
                entity_text += f": {entity['description']}"
            
            entity_texts.append(entity_text)
            entity_data.append(entity)
        
        # Generate embeddings for entities
        if entity_texts:
            embeddings = await embed_service.embed_documents(entity_texts)
            
            # Store in Qdrant (entities collection)
            points = []
            for entity, entity_text, embedding in zip(entity_data, entity_texts, embeddings):
                entity_id = hashlib.sha256(
                    f"{entity['name']}_{entity.get('type', 'UNKNOWN')}".encode()
                ).hexdigest()
                
                point = PointStruct(
                    id=entity_id,
                    vector=embedding,
                    payload={
                        "type": "entity",
                        "document_id": document_id,
                        "name": entity["name"],
                        "entity_type": entity.get("type", "UNKNOWN"),
                        "description": entity.get("description", ""),
                        "text": entity_text,
                        "chunk_index": entity.get("chunk_index")
                    }
                )
                points.append(point)
                
                # Create entity node in Neo4j
                await graph_service.create_entity_node(
                    entity_id=entity_id,
                    name=entity["name"],
                    entity_type=entity.get("type", "UNKNOWN"),
                    description=entity.get("description")
                )
                
                # Link to chunk if chunk_index provided
                if "chunk_index" in entity:
                    chunk_id = hashlib.sha256(
                        f"{document_id}_{entity['chunk_index']}".encode()
                    ).hexdigest()
                    await graph_service.link_entity_to_chunk(entity_id, chunk_id)
            
            self.qdrant.upsert(
                collection_name=self.entities_collection,
                points=points
            )
            
            logger.info(f"Stored {len(points)} entity vectors in Qdrant")
        
        logger.info(f"Ingested {len(entities)} entities")
        
        return {
            "document_id": document_id,
            "entities_created": len(entities),
            "vectors_created": len(entity_texts)
        }
    
    async def ingest_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingest relationships between entities.
        
        Stores relationships in both Neo4j (graph) and Qdrant (vector embeddings).
        
        Args:
            relationships: List of relationship dictionaries with 'subject', 'predicate', 'object'
            
        Returns:
            Ingestion statistics
        """
        logger.info(f"Ingesting {len(relationships)} relationships")
        
        # Ensure collections exist
        await self.ensure_collections()
        
        # Prepare relationship texts for embedding
        rel_texts = []
        rel_data = []
        
        for rel in relationships:
            # Create relationship text for embedding (subject - predicate -> object)
            rel_text = f"{rel['subject']} {rel['predicate']} {rel['object']}"
            rel_texts.append(rel_text)
            rel_data.append(rel)
        
        # Generate embeddings for relationships
        if rel_texts:
            embeddings = await embed_service.embed_documents(rel_texts)
            
            # Store in Qdrant (relationships collection)
            points = []
            for rel, rel_text, embedding in zip(rel_data, rel_texts, embeddings):
                rel_id = hashlib.sha256(
                    f"{rel['subject']}_{rel['predicate']}_{rel['object']}".encode()
                ).hexdigest()
                
                point = PointStruct(
                    id=rel_id,
                    vector=embedding,
                    payload={
                        "type": "relationship",
                        "subject": rel["subject"],
                        "predicate": rel["predicate"],
                        "object": rel["object"],
                        "subject_type": rel.get("subject_type", "UNKNOWN"),
                        "object_type": rel.get("object_type", "UNKNOWN"),
                        "text": rel_text,
                        "chunk_index": rel.get("chunk_index")
                    }
                )
                points.append(point)
                
                # Create relationship in Neo4j
                source_id = hashlib.sha256(
                    f"{rel['subject']}_{rel.get('subject_type', 'UNKNOWN')}".encode()
                ).hexdigest()
                target_id = hashlib.sha256(
                    f"{rel['object']}_{rel.get('object_type', 'UNKNOWN')}".encode()
                ).hexdigest()
                
                await graph_service.create_entity_relationship(
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relationship_type=rel["predicate"]
                )
            
            self.qdrant.upsert(
                collection_name=self.relationships_collection,
                points=points
            )
            
            logger.info(f"Stored {len(points)} relationship vectors in Qdrant")
        
        logger.info(f"Ingested {len(relationships)} relationships")
        
        return {
            "relationships_created": len(relationships),
            "vectors_created": len(rel_texts)
        }


# Global service instance
ingest_service = IngestService()

