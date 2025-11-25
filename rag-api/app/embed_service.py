"""
Embedding service using Ollama bge-m3 model.
"""

import asyncio
import logging
from typing import List
from langchain_ollama import OllamaEmbeddings
from app.config import settings

logger = logging.getLogger(__name__)

# Batch size para embeddings (evitar OOM no Ollama)
EMBEDDING_BATCH_SIZE = 50  # Processar 50 documentos por vez


class EmbedService:
    """Service for generating embeddings using Ollama."""
    
    def __init__(self):
        """Initialize the embedding service."""
        self.embeddings = OllamaEmbeddings(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_EMBEDDING_MODEL
        )
        logger.info(f"EmbedService initialized: model={settings.OLLAMA_EMBEDDING_MODEL}")
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        logger.debug(f"Embedding text: {len(text)} characters")
        embedding = await self.embeddings.aembed_query(text)
        return embedding
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        total = len(texts)
        logger.info(f"Embedding {total} documents in batches of {EMBEDDING_BATCH_SIZE}")
        
        all_embeddings = []
        
        # Process in batches to avoid OOM
        for i in range(0, total, EMBEDDING_BATCH_SIZE):
            batch = texts[i:i+EMBEDDING_BATCH_SIZE]
            batch_num = i // EMBEDDING_BATCH_SIZE + 1
            total_batches = (total + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} docs)")
            
            try:
                batch_embeddings = await self.embeddings.aembed_documents(batch)
                all_embeddings.extend(batch_embeddings)
                
                progress = len(all_embeddings)
                logger.info(f"✅ Batch {batch_num}/{total_batches} complete: {progress}/{total} embeddings ({progress/total*100:.1f}%)")
                
                # Small delay between batches to avoid overwhelming Ollama
                if i + EMBEDDING_BATCH_SIZE < total:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"❌ Batch {batch_num} failed: {e}")
                logger.error(f"Retrying batch {batch_num} with smaller size...")
                
                # Retry with smaller batches if failed
                mini_batch_size = 10
                for j in range(0, len(batch), mini_batch_size):
                    mini_batch = batch[j:j+mini_batch_size]
                    try:
                        mini_embeddings = await self.embeddings.aembed_documents(mini_batch)
                        all_embeddings.extend(mini_embeddings)
                        logger.info(f"✅ Mini-batch {j//mini_batch_size + 1} recovered")
                        await asyncio.sleep(0.2)
                    except Exception as retry_error:
                        logger.error(f"❌ Mini-batch failed: {retry_error}")
                        # Add zero embeddings as fallback
                        for _ in mini_batch:
                            all_embeddings.append([0.0] * settings.EMBEDDING_DIMENSIONS)
        
        logger.info(f"✅ Embedding complete: {len(all_embeddings)}/{total} embeddings (dim: {len(all_embeddings[0]) if all_embeddings else 0})")
        return all_embeddings


# Global service instance
embed_service = EmbedService()

