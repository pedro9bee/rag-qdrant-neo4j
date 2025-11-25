"""
Redis State Manager for pipeline jobs.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import redis
from app.config import settings

logger = logging.getLogger(__name__)


class RedisStateManager:
    """Manages job state in Redis."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        self.ttl = getattr(settings, 'REDIS_JOB_TTL', 172800)  # 48h default
        logger.info(f"RedisStateManager initialized with TTL={self.ttl}s")
    
    def _key(self, job_id: str, stage: str) -> str:
        """Generate Redis key."""
        return f"job:{job_id}:{stage}"
    
    def create_job(
        self,
        job_id: str,
        bucket: str,
        file: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new job in Redis.
        
        Args:
            job_id: Unique job identifier
            bucket: MinIO bucket name
            file: File path in bucket
            **kwargs: Additional metadata
            
        Returns:
            Job metadata dictionary
        """
        metadata = {
            "job_id": job_id,
            "bucket": bucket,
            "file": file,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress": {"current": 0, "total": 0, "percentage": 0.0},
            "stats": {},
            **kwargs
        }
        
        key = self._key(job_id, "metadata")
        self.redis_client.setex(
            key,
            self.ttl,
            json.dumps(metadata)
        )
        
        logger.info(f"Created job {job_id} for {bucket}/{file}")
        return metadata
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job metadata.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job metadata or None if not found
        """
        key = self._key(job_id, "metadata")
        data = self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Update job metadata.
        
        Args:
            job_id: Job identifier
            status: New status
            progress: Progress update
            stats: Statistics update
            error: Error message if any
            **kwargs: Additional fields to update
            
        Returns:
            Updated metadata
        """
        metadata = self.get_job(job_id)
        if not metadata:
            raise ValueError(f"Job {job_id} not found")
        
        # Update fields
        if status:
            metadata["status"] = status
        if progress:
            metadata["progress"].update(progress)
            # Calculate percentage
            if metadata["progress"]["total"] > 0:
                metadata["progress"]["percentage"] = (
                    metadata["progress"]["current"] / metadata["progress"]["total"] * 100
                )
        if stats:
            metadata["stats"].update(stats)
        if error:
            metadata["error"] = error
            metadata["status"] = "error"
        
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata.update(kwargs)
        
        # Save
        key = self._key(job_id, "metadata")
        self.redis_client.setex(
            key,
            self.ttl,
            json.dumps(metadata)
        )
        
        logger.debug(f"Updated job {job_id}: status={status}")
        return metadata
    
    def save_chunks(self, job_id: str, chunks: List[Dict[str, Any]]):
        """Save chunks to Redis."""
        key = self._key(job_id, "chunks")
        self.redis_client.setex(
            key,
            self.ttl,
            json.dumps(chunks)
        )
        logger.info(f"Saved {len(chunks)} chunks for job {job_id}")
    
    def get_chunks(self, job_id: str) -> List[Dict[str, Any]]:
        """Get chunks from Redis."""
        key = self._key(job_id, "chunks")
        data = self.redis_client.get(key)
        return json.loads(data) if data else []
    
    def save_entities(self, job_id: str, entities: List[Dict[str, Any]]):
        """Save entities to Redis."""
        key = self._key(job_id, "entities")
        self.redis_client.setex(
            key,
            self.ttl,
            json.dumps(entities)
        )
        logger.info(f"Saved {len(entities)} entities for job {job_id}")
    
    def get_entities(self, job_id: str) -> List[Dict[str, Any]]:
        """Get entities from Redis."""
        key = self._key(job_id, "entities")
        data = self.redis_client.get(key)
        return json.loads(data) if data else []
    
    def save_relationships(self, job_id: str, relationships: List[Dict[str, Any]]):
        """Save relationships to Redis."""
        key = self._key(job_id, "relationships")
        self.redis_client.setex(
            key,
            self.ttl,
            json.dumps(relationships)
        )
        logger.info(f"Saved {len(relationships)} relationships for job {job_id}")
    
    def get_relationships(self, job_id: str) -> List[Dict[str, Any]]:
        """Get relationships from Redis."""
        key = self._key(job_id, "relationships")
        data = self.redis_client.get(key)
        return json.loads(data) if data else []
    
    def list_jobs(self, pattern: str = "job:*:metadata") -> List[Dict[str, Any]]:
        """
        List all active jobs.
        
        Args:
            pattern: Redis key pattern
            
        Returns:
            List of job metadata
        """
        keys = self.redis_client.keys(pattern)
        jobs = []
        
        for key in keys:
            data = self.redis_client.get(key)
            if data:
                jobs.append(json.loads(data))
        
        return jobs
    
    def delete_job(self, job_id: str) -> bool:
        """
        Delete a job and all its data.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if deleted
        """
        keys = self.redis_client.keys(f"job:{job_id}:*")
        if keys:
            self.redis_client.delete(*keys)
            logger.info(f"Deleted job {job_id} ({len(keys)} keys)")
            return True
        return False


# Global instance
redis_state = RedisStateManager()

