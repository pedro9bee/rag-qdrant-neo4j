"""
Chat service using LangGraph retrieval workflow.
"""

import logging
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from graphs.retrieval_graph import build_retrieval_graph

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat using LangGraph RAG workflow."""
    
    def __init__(self):
        """Initialize the chat service."""
        self.retrieval_graph = build_retrieval_graph()
        logger.info("ChatService initialized with LangGraph retrieval workflow")
    
    async def chat(
        self,
        message: str,
        conversation_history: List[Dict[str, str]] = None,
        top_k_vector: int = 10,
        top_k_graph: int = 5,
        rerank_top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Process a chat message using RAG retrieval.
        
        Args:
            message: User message
            conversation_history: Previous messages in conversation
            top_k_vector: Number of vector results
            top_k_graph: Number of graph results
            rerank_top_k: Final number of results after reranking
            
        Returns:
            Dictionary with response and metadata
        """
        logger.info(f"Processing chat message: {message[:50]}...")
        
        try:
            # Run retrieval workflow
            result = self.retrieval_graph.invoke({
                "user_query": message,
                "top_k_vector": top_k_vector,
                "top_k_graph": top_k_graph,
                "rerank_top_k": rerank_top_k
            })
            
            # Check for errors
            if result.get("error"):
                logger.error(f"Retrieval error: {result['error']}")
                return {
                    "response": f"I encountered an error while searching: {result['error']}",
                    "context": "",
                    "sources": [],
                    "metadata": {"error": result["error"]}
                }
            
            # Extract context and format response
            context = result.get("context", "")
            metadata = result.get("metadata", {})
            results = result.get("reranked_results", [])
            
            # Build response with context
            if context:
                response = self._build_response_with_context(message, context, metadata)
            else:
                response = "I couldn't find any relevant information to answer your question."
            
            # Extract sources
            sources = []
            for r in results[:rerank_top_k]:
                source = {
                    "type": r.get("type", "unknown"),
                    "score": r.get("final_score", 0),
                    "text": r.get("text", "")[:200]  # Truncate for response
                }
                
                if r.get("document_id"):
                    source["document_id"] = r["document_id"]
                if r.get("entity_name"):
                    source["entity_name"] = r["entity_name"]
                
                sources.append(source)
            
            return {
                "response": response,
                "context": context,
                "sources": sources,
                "metadata": {
                    "num_sources": metadata.get("num_sources", 0),
                    "chunk_count": metadata.get("chunk_count", 0),
                    "entity_count": metadata.get("entity_count", 0),
                    "relationship_count": metadata.get("relationship_count", 0),
                    "graph_count": metadata.get("graph_count", 0)
                }
            }
            
        except Exception as e:
            logger.error(f"Chat processing failed: {e}", exc_info=True)
            return {
                "response": f"I encountered an error: {str(e)}",
                "context": "",
                "sources": [],
                "metadata": {"error": str(e)}
            }
    
    def _build_response_with_context(
        self,
        query: str,
        context: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Build a response using the retrieved context.
        
        For now, this is a simple context-aware response.
        In the future, this could use an LLM to generate a better answer.
        
        Args:
            query: User query
            context: Retrieved context
            metadata: Search metadata
            
        Returns:
            Response string
        """
        # Simple response that includes context
        num_sources = metadata.get("num_sources", 0)
        
        response = f"Based on {num_sources} sources I found:\n\n{context}\n\n"
        response += f"This information comes from {metadata.get('chunk_count', 0)} document chunks"
        
        if metadata.get('entity_count', 0) > 0:
            response += f", {metadata['entity_count']} entities"
        
        if metadata.get('relationship_count', 0) > 0:
            response += f", and {metadata['relationship_count']} relationships"
        
        response += " in the knowledge base."
        
        return response


# Global service instance
chat_service = ChatService()

