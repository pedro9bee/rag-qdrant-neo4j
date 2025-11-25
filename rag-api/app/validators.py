"""
Validators for RAG API.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


def validate_embedding_dimensions(
    embeddings: List[List[float]],
    expected_dim: int = 1024
) -> bool:
    """
    Valida que embeddings têm a dimensão esperada.
    
    Args:
        embeddings: Lista de vetores de embedding
        expected_dim: Dimensão esperada (default: 1024 para bge-m3:latest)
        
    Returns:
        True se válido
        
    Raises:
        ValueError: Se algum embedding tiver dimensão incorreta
    """
    if not embeddings:
        return True
    
    for i, emb in enumerate(embeddings):
        actual_dim = len(emb)
        if actual_dim != expected_dim:
            raise ValueError(
                f"Embedding {i} tem dimensão {actual_dim}, esperado {expected_dim}. "
                f"Verifique se o modelo correto está sendo usado (bge-m3:latest = 1024 dims). "
                f"Atualize EMBEDDING_DIMENSIONS no .env se necessário."
            )
    
    logger.debug(f"Validated {len(embeddings)} embeddings with dimension {expected_dim}")
    return True


def validate_embedding_single(embedding: List[float], expected_dim: int = 1024) -> bool:
    """
    Valida um único embedding.
    
    Args:
        embedding: Vetor de embedding
        expected_dim: Dimensão esperada
        
    Returns:
        True se válido
        
    Raises:
        ValueError: Se dimensão incorreta
    """
    return validate_embedding_dimensions([embedding], expected_dim)

