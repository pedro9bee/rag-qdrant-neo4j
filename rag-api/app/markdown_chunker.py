"""
Markdown-aware chunking with hierarchy preservation.
"""

import logging
import re
from typing import List, Dict, Any, Tuple
from app.config import settings

logger = logging.getLogger(__name__)


class MarkdownChunker:
    """Intelligent markdown chunker that preserves context and hierarchy."""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size or getattr(settings, 'MARKDOWN_CHUNK_SIZE', 1000)
        self.chunk_overlap = chunk_overlap or getattr(settings, 'MARKDOWN_CHUNK_OVERLAP', 200)
        logger.info(f"MarkdownChunker initialized: size={self.chunk_size}, overlap={self.chunk_overlap}")
    
    def extract_hierarchy(self, text: str) -> List[Tuple[str, str, int]]:
        """
        Extract markdown header hierarchy.
        
        Args:
            text: Markdown text
            
        Returns:
            List of (level, title, position) tuples
        """
        headers = []
        pattern = r'^(#{1,6})\s+(.+)$'
        
        for match in re.finditer(pattern, text, re.MULTILINE):
            level = len(match.group(1))  # Number of # characters
            title = match.group(2).strip()
            position = match.start()
            headers.append((level, title, position))
        
        return headers
    
    def build_context_path(
        self,
        headers: List[Tuple[str, str, int]],
        position: int
    ) -> List[str]:
        """
        Build hierarchical context path for a given position.
        
        Args:
            headers: List of headers from extract_hierarchy
            position: Character position in text
            
        Returns:
            List of header titles from H1 to current level
        """
        # Find headers before this position
        relevant_headers = [h for h in headers if h[2] < position]
        if not relevant_headers:
            return []
        
        # Build hierarchy stack
        context = []
        stack_levels = []
        
        for level, title, _ in relevant_headers:
            # Pop headers of equal or higher level
            while stack_levels and stack_levels[-1] >= level:
                stack_levels.pop()
                context.pop()
            
            stack_levels.append(level)
            context.append(title)
        
        return context
    
    def chunk(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk markdown text intelligently.
        
        Args:
            text: Markdown text to chunk
            metadata: Optional metadata to include
            
        Returns:
            List of chunk dictionaries
        """
        if not text or not text.strip():
            return []
        
        # Extract headers for context
        headers = self.extract_hierarchy(text)
        logger.debug(f"Found {len(headers)} headers in text")
        
        chunks = []
        current_pos = 0
        chunk_index = 0
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        current_chunk = ""
        current_start = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph exceeds chunk size
            test_chunk = current_chunk + ("\n\n" if current_chunk else "") + para
            
            if len(test_chunk) <= self.chunk_size or not current_chunk:
                # Add to current chunk
                if current_chunk:
                    current_chunk += "\n\n"
                else:
                    current_start = text.find(para, current_pos)
                current_chunk += para
            else:
                # Save current chunk and start new one
                if current_chunk:
                    end_pos = current_start + len(current_chunk)
                    context_path = self.build_context_path(headers, current_start)
                    
                    chunks.append({
                        "index": chunk_index,
                        "text": current_chunk,
                        "start_char": current_start,
                        "end_char": end_pos,
                        "metadata": {
                            "header_hierarchy": context_path,
                            "section": context_path[-1] if context_path else "Root",
                            **(metadata or {})
                        }
                    })
                    chunk_index += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and current_chunk:
                    # Take last overlap characters
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_start = max(0, end_pos - len(overlap_text))
                else:
                    current_chunk = para
                    current_start = text.find(para, current_pos)
                
                current_pos = current_start
        
        # Save final chunk
        if current_chunk:
            end_pos = current_start + len(current_chunk)
            context_path = self.build_context_path(headers, current_start)
            
            chunks.append({
                "index": chunk_index,
                "text": current_chunk,
                "start_char": current_start,
                "end_char": end_pos,
                "metadata": {
                    "header_hierarchy": context_path,
                    "section": context_path[-1] if context_path else "Root",
                    **(metadata or {})
                }
            })
        
        logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
        return chunks
    
    def chunk_large_file(
        self,
        text: str,
        batch_size: int = 100,
        metadata: Dict[str, Any] = None
    ) -> List[List[Dict[str, Any]]]:
        """
        Chunk large files in batches.
        
        Args:
            text: Markdown text
            batch_size: Number of chunks per batch
            metadata: Optional metadata
            
        Returns:
            List of chunk batches
        """
        all_chunks = self.chunk(text, metadata)
        
        # Split into batches
        batches = []
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            batches.append(batch)
        
        logger.info(f"Split {len(all_chunks)} chunks into {len(batches)} batches")
        return batches


# Global instance
markdown_chunker = MarkdownChunker()

