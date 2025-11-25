"""LangGraph workflow for hybrid RAG retrieval."""

import os
import logging
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END

from langgraph.graphs.shared import RetrievalState
from langgraph.utils.connections import (
    get_qdrant_client,
    get_neo4j_driver,
    neo4j_session,
    get_openai_embeddings
)
from langgraph.utils.neo4j_schema import (
    get_related_chunks_by_entity,
    get_entity_graph
)

logger = logging.getLogger(__name__)


def generate_query_embedding(state: RetrievalState) -> RetrievalState:
    """
    Generate embedding for user query using Ollama (bge-m3).
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with query embedding
    """
    query = state["user_query"]
    logger.info(f"Generating embedding for query: {query[:100]}...")
    
    try:
        embeddings_model = get_openai_embeddings()
        
        # Generate embedding for query
        query_embedding = embeddings_model.embed_query(query)
        
        state["query_embedding"] = query_embedding
        
        logger.info(f"Query embedding generated (dim: {len(query_embedding)})")
        
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        state["error"] = str(e)
    
    return state


def vector_search(state: RetrievalState) -> RetrievalState:
    """
    Search Qdrant for similar vectors.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with vector search results
    """
    if state.get("error"):
        return state
    
    query_embedding = state["query_embedding"]
    top_k = state.get("top_k_vector", 10)
    
    logger.info(f"Searching Qdrant for top {top_k} similar vectors")
    
    try:
        qdrant = get_qdrant_client()
        collection_name = os.getenv("QDRANT_COLLECTION_NAME", "rag_embeddings")
        
        # Search for similar vectors
        search_results = qdrant.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True
        )
        
        # Convert to dict format
        vector_results = []
        for result in search_results:
            vector_results.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "document_key": result.payload.get("document_key", ""),
                "chunk_index": result.payload.get("chunk_index", 0),
                "metadata": result.payload.get("metadata", {}),
                "source": "vector"
            })
        
        state["vector_results"] = vector_results
        
        logger.info(f"Found {len(vector_results)} similar vectors")
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        state["error"] = str(e)
    
    return state


def graph_search(state: RetrievalState) -> RetrievalState:
    """
    Search Neo4J knowledge graph for related entities and chunks.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with graph search results
    """
    if state.get("error"):
        return state
    
    query = state["user_query"]
    top_k = state.get("top_k_graph", 5)
    
    logger.info(f"Searching Neo4J knowledge graph")
    
    try:
        driver = get_neo4j_driver()
        
        with neo4j_session(driver) as session:
            # Extract potential entity names from query (simple keyword extraction)
            # In production, use NER or more sophisticated extraction
            words = query.split()
            potential_entities = [
                word.strip(".,!?") 
                for word in words 
                if len(word) > 3 and word[0].isupper()
            ]
            
            graph_results = []
            
            # Search for each potential entity
            for entity_name in potential_entities[:3]:  # Limit entity searches
                try:
                    related_chunks = get_related_chunks_by_entity(
                        session,
                        entity_name=entity_name,
                        limit=top_k
                    )
                    
                    for item in related_chunks:
                        chunk = dict(item["chunk"])
                        entity = dict(item["entity"])
                        
                        graph_results.append({
                            "text": chunk.get("text", ""),
                            "document_id": chunk.get("document_id", ""),
                            "chunk_index": chunk.get("chunk_index", 0),
                            "entity_name": entity.get("name", ""),
                            "entity_type": entity.get("type", ""),
                            "source": "graph"
                        })
                        
                except Exception as e:
                    logger.debug(f"No results for entity: {entity_name}")
                    continue
            
            # Also perform general full-text search in Neo4J
            try:
                general_query = """
                MATCH (c:Chunk)
                WHERE c.text CONTAINS $search_term
                RETURN c
                LIMIT $limit
                """
                
                result = session.run(
                    general_query,
                    search_term=query[:50],  # Use first 50 chars
                    limit=top_k
                )
                
                for record in result:
                    chunk = dict(record["c"])
                    graph_results.append({
                        "text": chunk.get("text", ""),
                        "document_id": chunk.get("document_id", ""),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "source": "graph"
                    })
                    
            except Exception as e:
                logger.debug(f"General graph search failed: {e}")
        
        driver.close()
        
        # Remove duplicates
        seen_texts = set()
        unique_results = []
        for result in graph_results:
            text = result["text"]
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_results.append(result)
        
        state["graph_results"] = unique_results[:top_k]
        
        logger.info(f"Found {len(state['graph_results'])} graph results")
        
    except Exception as e:
        logger.error(f"Graph search failed: {e}")
        # Non-critical, continue with vector results only
        state["graph_results"] = []
    
    return state


def merge_results(state: RetrievalState) -> RetrievalState:
    """
    Merge vector and graph results.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with combined results
    """
    if state.get("error"):
        return state
    
    vector_results = state.get("vector_results", [])
    graph_results = state.get("graph_results", [])
    
    logger.info(f"Merging {len(vector_results)} vector + {len(graph_results)} graph results")
    
    # Combine results
    combined = []
    
    # Add vector results with normalized scores
    max_vector_score = max([r["score"] for r in vector_results], default=1.0)
    for result in vector_results:
        result["normalized_score"] = result["score"] / max_vector_score
        combined.append(result)
    
    # Add graph results with default score
    for result in graph_results:
        result["normalized_score"] = 0.7  # Moderate score for graph results
        combined.append(result)
    
    # Remove duplicates based on text content
    seen_texts = set()
    unique_combined = []
    for result in combined:
        text = result["text"]
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_combined.append(result)
    
    state["combined_results"] = unique_combined
    
    logger.info(f"Combined to {len(unique_combined)} unique results")
    
    return state


def rerank_results(state: RetrievalState) -> RetrievalState:
    """
    Rerank combined results using reciprocal rank fusion.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with reranked results
    """
    if state.get("error"):
        return state
    
    combined = state.get("combined_results", [])
    rerank_top_k = state.get("rerank_top_k", 5)
    
    logger.info(f"Reranking {len(combined)} results")
    
    # Reciprocal Rank Fusion
    # Score each result by its reciprocal rank plus source-specific boost
    k = 60  # Constant for RRF
    
    for idx, result in enumerate(combined):
        rrf_score = 1.0 / (k + idx + 1)
        
        # Boost by source
        if result.get("source") == "vector":
            source_boost = result.get("normalized_score", 0.5) * 0.5
        else:  # graph
            source_boost = 0.3
        
        result["final_score"] = rrf_score + source_boost
    
    # Sort by final score
    reranked = sorted(combined, key=lambda x: x["final_score"], reverse=True)
    
    state["reranked_results"] = reranked[:rerank_top_k]
    
    logger.info(f"Reranked to top {len(state['reranked_results'])} results")
    
    return state


def format_context(state: RetrievalState) -> RetrievalState:
    """
    Format reranked results into context string.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with formatted context
    """
    if state.get("error"):
        return state
    
    reranked = state.get("reranked_results", [])
    
    logger.info(f"Formatting {len(reranked)} results into context")
    
    context_parts = []
    
    for idx, result in enumerate(reranked, 1):
        source = result.get("source", "unknown")
        score = result.get("final_score", 0.0)
        text = result.get("text", "")
        doc_key = result.get("document_key", result.get("document_id", "unknown"))
        
        context_part = f"""[Source {idx}] (score: {score:.3f}, type: {source})
Document: {doc_key}
Content: {text}
"""
        context_parts.append(context_part)
    
    context = "\n---\n".join(context_parts)
    
    state["context"] = context
    state["metadata"] = {
        "num_sources": len(reranked),
        "vector_count": len([r for r in reranked if r.get("source") == "vector"]),
        "graph_count": len([r for r in reranked if r.get("source") == "graph"])
    }
    
    logger.info(f"Context formatted: {len(context)} characters")
    
    return state


# Build the graph
def build_retrieval_graph() -> StateGraph:
    """
    Build and compile the retrieval workflow graph.
    
    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(RetrievalState)
    
    # Add nodes
    workflow.add_node("generate_embedding", generate_query_embedding)
    workflow.add_node("vector_search", vector_search)
    workflow.add_node("graph_search", graph_search)
    workflow.add_node("merge_results", merge_results)
    workflow.add_node("rerank_results", rerank_results)
    workflow.add_node("format_context", format_context)
    
    # Define edges
    workflow.set_entry_point("generate_embedding")
    workflow.add_edge("generate_embedding", "vector_search")
    workflow.add_edge("generate_embedding", "graph_search")
    workflow.add_edge("vector_search", "merge_results")
    workflow.add_edge("graph_search", "merge_results")
    workflow.add_edge("merge_results", "rerank_results")
    workflow.add_edge("rerank_results", "format_context")
    workflow.add_edge("format_context", END)
    
    return workflow.compile()

