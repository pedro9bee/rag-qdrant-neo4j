"""Text chunking utilities for document processing."""

import os
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """Text chunk with metadata."""
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    metadata: Optional[dict] = None
) -> List[Chunk]:
    """
    Split text into overlapping chunks using LangChain.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters
        chunk_overlap: Overlap between chunks in characters
        metadata: Additional metadata to attach to chunks
        
    Returns:
        List of Chunk objects with text and metadata
        
    Raises:
        ImportError: If langchain is not installed
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        raise ImportError(
            "langchain not installed. Run: pip install langchain"
        )
    
    chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "200"))
    metadata = metadata or {}
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = splitter.split_text(text)
    
    result = []
    current_pos = 0
    
    for idx, chunk_text in enumerate(chunks):
        # Find the position in original text
        start_char = text.find(chunk_text, current_pos)
        if start_char == -1:
            start_char = current_pos
        
        end_char = start_char + len(chunk_text)
        
        chunk = Chunk(
            text=chunk_text,
            chunk_index=idx,
            start_char=start_char,
            end_char=end_char,
            metadata={
                **metadata,
                "chunk_size": len(chunk_text),
                "chunk_index": idx
            }
        )
        
        result.append(chunk)
        current_pos = end_char
    
    return result


def chunk_markdown(
    markdown_text: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    metadata: Optional[dict] = None
) -> List[Chunk]:
    """
    Split markdown text preserving structure.
    
    Args:
        markdown_text: Markdown text to chunk
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        metadata: Additional metadata
        
    Returns:
        List of Chunk objects
        
    Raises:
        ImportError: If langchain is not installed
    """
    try:
        from langchain.text_splitter import MarkdownTextSplitter
    except ImportError:
        raise ImportError(
            "langchain not installed. Run: pip install langchain"
        )
    
    chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "200"))
    metadata = metadata or {}
    
    splitter = MarkdownTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    chunks = splitter.split_text(markdown_text)
    
    result = []
    current_pos = 0
    
    for idx, chunk_text in enumerate(chunks):
        start_char = markdown_text.find(chunk_text, current_pos)
        if start_char == -1:
            start_char = current_pos
        
        end_char = start_char + len(chunk_text)
        
        chunk = Chunk(
            text=chunk_text,
            chunk_index=idx,
            start_char=start_char,
            end_char=end_char,
            metadata={
                **metadata,
                "chunk_size": len(chunk_text),
                "chunk_index": idx,
                "format": "markdown"
            }
        )
        
        result.append(chunk)
        current_pos = end_char
    
    return result

