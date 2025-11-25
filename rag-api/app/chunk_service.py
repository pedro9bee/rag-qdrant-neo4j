"""
Chunking service for splitting documents into smaller pieces.
Uses the chunking logic from langgraph/utils/chunking.py.
"""

import logging
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from app.config import settings

logger = logging.getLogger(__name__)


class ChunkService:
    """Service for chunking documents."""
    
    def __init__(self):
        """Initialize the chunking service."""
        self.chunk_size = settings.CHUNK_SIZE
        self.chunk_overlap = settings.CHUNK_OVERLAP
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        logger.info(f"ChunkService initialized: size={self.chunk_size}, overlap={self.chunk_overlap}")
    
    async def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk plain text into smaller pieces.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        logger.info(f"Chunking text: {len(text)} characters")
        
        # Split text
        splits = self.text_splitter.split_text(text)
        
        # Create chunk objects
        chunks = []
        current_pos = 0
        
        for idx, chunk_text in enumerate(splits):
            # Find start position in original text
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                start_char = current_pos
            
            end_char = start_char + len(chunk_text)
            current_pos = end_char
            
            chunks.append({
                "text": chunk_text,
                "chunk_index": idx,
                "start_char": start_char,
                "end_char": end_char,
                "metadata": metadata or {}
            })
        
        logger.info(f"Created {len(chunks)} chunks")
        return chunks
    
    async def chunk_markdown(self, markdown: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk markdown text, respecting headers.
        
        Args:
            markdown: Markdown text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        logger.info(f"Chunking markdown: {len(markdown)} characters")
        
        # Headers to split on
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        # First split by headers
        md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_splits = md_splitter.split_text(markdown)
        
        # Then further split large sections
        chunks = []
        chunk_index = 0
        current_pos = 0
        
        for doc in md_splits:
            section_text = doc.page_content
            section_metadata = {**(metadata or {}), **doc.metadata}
            
            # If section is too large, split it further
            if len(section_text) > self.chunk_size:
                subsplits = self.text_splitter.split_text(section_text)
                for subsplit in subsplits:
                    start_char = markdown.find(subsplit, current_pos)
                    if start_char == -1:
                        start_char = current_pos
                    end_char = start_char + len(subsplit)
                    current_pos = end_char
                    
                    chunks.append({
                        "text": subsplit,
                        "chunk_index": chunk_index,
                        "start_char": start_char,
                        "end_char": end_char,
                        "metadata": section_metadata
                    })
                    chunk_index += 1
            else:
                start_char = markdown.find(section_text, current_pos)
                if start_char == -1:
                    start_char = current_pos
                end_char = start_char + len(section_text)
                current_pos = end_char
                
                chunks.append({
                    "text": section_text,
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": end_char,
                    "metadata": section_metadata
                })
                chunk_index += 1
        
        logger.info(f"Created {len(chunks)} markdown chunks")
        return chunks


# Global service instance
chunk_service = ChunkService()

