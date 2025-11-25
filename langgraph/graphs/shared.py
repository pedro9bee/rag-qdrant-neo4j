"""Shared state definitions for LangGraph workflows."""

from typing import TypedDict, List, Dict, Any, Optional


class IngestState(TypedDict):
    """State for document ingestion workflow."""
    # Input
    minio_bucket: str
    minio_path: str
    
    # Document processing
    documents: List[Dict[str, Any]]  # List of document metadata
    current_document: Optional[Dict[str, Any]]
    document_content: Optional[str]
    
    # Chunking
    chunks: List[Dict[str, Any]]
    
    # Embeddings
    embeddings: List[List[float]]
    
    # Entity extraction
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    # Status
    processed_count: int
    error: Optional[str]


class RetrievalState(TypedDict):
    """State for retrieval workflow."""
    # Input
    user_query: str
    top_k_vector: int
    top_k_graph: int
    rerank_top_k: int
    
    # Query processing
    query_embedding: Optional[List[float]]
    
    # Vector search results
    vector_results: List[Dict[str, Any]]
    
    # Graph search results
    graph_results: List[Dict[str, Any]]
    
    # Combined and reranked results
    combined_results: List[Dict[str, Any]]
    reranked_results: List[Dict[str, Any]]
    
    # Final context
    context: str
    
    # Metadata
    metadata: Dict[str, Any]
    
    # Status
    error: Optional[str]

