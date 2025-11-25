"""
Query service for RAG retrieval.
"""

import logging
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from app.config import settings
from app.embed_service import embed_service
from app.graph_service import graph_service

logger = logging.getLogger(__name__)


class QueryService:
    """Service for querying the RAG system."""
    
    def __init__(self):
        """Initialize the query service."""
        self.qdrant = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None
        )
        
        # Collection names for different data types
        self.chunks_collection = f"{settings.QDRANT_COLLECTION_NAME}_chunks"
        self.entities_collection = f"{settings.QDRANT_COLLECTION_NAME}_entities"
        self.relationships_collection = f"{settings.QDRANT_COLLECTION_NAME}_relationships"
        
        logger.info("QueryService initialized")
    
    async def search_chunks(
        self,
        query: str,
        top_k: int = 10,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks in Qdrant.
        
        Args:
            query: Search query
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            List of chunk search results
        """
        logger.info(f"Chunk search: '{query[:50]}...' (top_k={top_k})")
        
        # Generate query embedding
        query_embedding = await embed_service.embed_text(query)
        
        # Search chunks collection
        try:
            search_results = self.qdrant.search(
                collection_name=self.chunks_collection,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "type": "chunk",
                    "text": result.payload.get("text", ""),
                    "document_id": result.payload.get("document_id", ""),
                    "chunk_index": result.payload.get("chunk_index", 0),
                    "metadata": result.payload.get("metadata", {}),
                    "source": "vector_chunks"
                })
            
            logger.info(f"Found {len(results)} chunk results")
            return results
        except Exception as e:
            logger.warning(f"Chunk search failed: {e}")
            return []
    
    async def search_entities(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar entities in Qdrant.
        
        Args:
            query: Search query
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            List of entity search results
        """
        logger.info(f"Entity search: '{query[:50]}...' (top_k={top_k})")
        
        # Generate query embedding
        query_embedding = await embed_service.embed_text(query)
        
        # Search entities collection
        try:
            search_results = self.qdrant.search(
                collection_name=self.entities_collection,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "type": "entity",
                    "name": result.payload.get("name", ""),
                    "entity_type": result.payload.get("entity_type", ""),
                    "description": result.payload.get("description", ""),
                    "text": result.payload.get("text", ""),
                    "document_id": result.payload.get("document_id", ""),
                    "source": "vector_entities"
                })
            
            logger.info(f"Found {len(results)} entity results")
            return results
        except Exception as e:
            logger.warning(f"Entity search failed: {e}")
            return []
    
    async def search_relationships(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar relationships in Qdrant.
        
        Args:
            query: Search query
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            
        Returns:
            List of relationship search results
        """
        logger.info(f"Relationship search: '{query[:50]}...' (top_k={top_k})")
        
        # Generate query embedding
        query_embedding = await embed_service.embed_text(query)
        
        # Search relationships collection
        try:
            search_results = self.qdrant.search(
                collection_name=self.relationships_collection,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "type": "relationship",
                    "subject": result.payload.get("subject", ""),
                    "predicate": result.payload.get("predicate", ""),
                    "object": result.payload.get("object", ""),
                    "text": result.payload.get("text", ""),
                    "source": "vector_relationships"
                })
            
            logger.info(f"Found {len(results)} relationship results")
            return results
        except Exception as e:
            logger.warning(f"Relationship search failed: {e}")
            return []
    
    async def vector_search(
        self,
        query: str,
        top_k: int = 10,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search across all vector collections (chunks, entities, relationships).
        
        Args:
            query: Search query
            top_k: Number of results per collection
            score_threshold: Minimum similarity score
            
        Returns:
            Combined list of search results
        """
        logger.info(f"Vector search (all collections): '{query[:50]}...' (top_k={top_k})")
        
        # Search all collections
        chunks = await self.search_chunks(query, top_k, score_threshold)
        entities = await self.search_entities(query, top_k // 2, score_threshold)
        relationships = await self.search_relationships(query, top_k // 2, score_threshold)
        
        # Combine results
        all_results = chunks + entities + relationships
        
        # Sort by score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        logger.info(f"Found {len(all_results)} total vector results")
        return all_results[:top_k]
    
    async def graph_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge graph.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of graph search results
        """
        logger.info(f"Graph search: '{query[:50]}...' (top_k={top_k})")
        
        # Extract potential entity names (simple approach)
        words = query.split()
        potential_entities = [
            word.strip(".,!?") 
            for word in words 
            if len(word) > 3 and word[0].isupper()
        ]
        
        results = []
        
        # Search for entities
        for entity_name in potential_entities[:3]:
            entities = await graph_service.search_entities(entity_name, limit=top_k)
            for entity in entities:
                results.append({
                    "entity_id": entity["id"],
                    "entity_name": entity["name"],
                    "entity_type": entity["type"],
                    "description": entity.get("description", ""),
                    "source": "graph"
                })
        
        logger.info(f"Found {len(results)} graph results")
        return results
    
    async def hybrid_search(
        self,
        query: str,
        top_k_vector: int = 10,
        top_k_graph: int = 5,
        rerank_top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Perform hybrid search combining vector and graph search.
        
        Args:
            query: Search query
            top_k_vector: Number of vector results
            top_k_graph: Number of graph results
            rerank_top_k: Final number of results after reranking
            
        Returns:
            Hybrid search results with metadata
        """
        logger.info(f"Hybrid search: '{query[:50]}...'")
        
        # Perform both searches
        vector_results = await self.vector_search(query, top_k=top_k_vector)
        graph_results = await self.graph_search(query, top_k=top_k_graph)
        
        # Combine and rerank using reciprocal rank fusion
        combined = vector_results + graph_results
        
        # Simple RRF scoring
        k = 60
        for idx, result in enumerate(combined):
            rrf_score = 1.0 / (k + idx + 1)
            
            # Boost by source
            if result.get("source") == "vector":
                source_boost = result.get("score", 0.5) * 0.5
            else:
                source_boost = 0.3
            
            result["final_score"] = rrf_score + source_boost
        
        # Sort and limit
        reranked = sorted(combined, key=lambda x: x.get("final_score", 0), reverse=True)[:rerank_top_k]
        
        # Build context string
        context_parts = []
        for idx, result in enumerate(reranked, 1):
            result_type = result.get("type", "unknown")
            source = result.get("source", "unknown")
            
            if result_type == "chunk":
                context_parts.append(
                    f"[Source {idx}] (type: chunk, score: {result['final_score']:.3f})\n"
                    f"Document: {result.get('document_id', 'unknown')}\n"
                    f"Content: {result.get('text', '')}\n"
                )
            elif result_type == "entity":
                context_parts.append(
                    f"[Source {idx}] (type: entity, score: {result['final_score']:.3f})\n"
                    f"Entity: {result.get('name', '')} ({result.get('entity_type', '')})\n"
                    f"Description: {result.get('description', '')}\n"
                )
            elif result_type == "relationship":
                context_parts.append(
                    f"[Source {idx}] (type: relationship, score: {result['final_score']:.3f})\n"
                    f"Relationship: {result.get('subject', '')} --[{result.get('predicate', '')}]--> {result.get('object', '')}\n"
                )
            elif source == "graph":
                context_parts.append(
                    f"[Source {idx}] (type: graph_entity, score: {result['final_score']:.3f})\n"
                    f"Entity: {result.get('entity_name', '')} ({result.get('entity_type', '')})\n"
                    f"Description: {result.get('description', '')}\n"
                )
        
        context = "\n---\n".join(context_parts)
        
        return {
            "query": query,
            "context": context,
            "results": reranked,
            "metadata": {
                "num_sources": len(reranked),
                "chunk_count": len([r for r in reranked if r.get("type") == "chunk"]),
                "entity_count": len([r for r in reranked if r.get("type") == "entity" or r.get("source") == "graph"]),
                "relationship_count": len([r for r in reranked if r.get("type") == "relationship"]),
                "graph_count": len([r for r in reranked if r.get("source") == "graph"])
            }
        }


# Global service instance
query_service = QueryService()

