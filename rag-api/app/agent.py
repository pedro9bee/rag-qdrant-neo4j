"""
AIjudante Agent - Simple agent that returns "banana" to all queries.
This is a placeholder implementation that will be expanded later.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class AIjudanteAgent:
    """
    AIjudante Agent - A simple agent that returns banana.
    
    This agent is designed to be expanded with RAG capabilities.
    For now, it simply returns "banana" to all queries as a placeholder.
    """
    
    def __init__(self):
        """Initialize the AIjudante agent."""
        logger.info("AIjudante Agent initialized")
    
    async def chat(self, message: str, conversation_id: str = None) -> Dict[str, Any]:
        """
        Process a chat message.
        
        Args:
            message: User message
            conversation_id: Optional conversation ID for context
            
        Returns:
            Dictionary with response and metadata
        """
        logger.info(f"AIjudante received message: {message[:50]}...")
        
        # For now, always return "banana"
        return {
            "response": "banana",
            "conversation_id": conversation_id or "default",
            "model": "aijudante-v1",
            "tokens_used": 1
        }
    
    async def stream_chat(self, message: str, conversation_id: str = None):
        """
        Stream a chat response.
        
        Args:
            message: User message
            conversation_id: Optional conversation ID for context
            
        Yields:
            Response chunks
        """
        logger.info(f"AIjudante streaming response for: {message[:50]}...")
        
        # Stream "banana" letter by letter
        response = "banana"
        for char in response:
            yield {
                "delta": char,
                "conversation_id": conversation_id or "default",
                "finished": False
            }
        
        yield {
            "delta": "",
            "conversation_id": conversation_id or "default",
            "finished": True
        }


# Global agent instance
aijudante = AIjudanteAgent()

