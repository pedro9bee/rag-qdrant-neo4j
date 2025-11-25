"""
Graph service for Neo4j operations.
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase, Driver
from contextlib import contextmanager
from app.config import settings

logger = logging.getLogger(__name__)


class GraphService:
    """Service for Neo4j graph operations."""
    
    def __init__(self):
        """Initialize the graph service."""
        self.driver: Optional[Driver] = None
        logger.info("GraphService initialized")
    
    def connect(self):
        """Connect to Neo4j."""
        if not self.driver:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            logger.info(f"Connected to Neo4j: {settings.NEO4J_URI}")
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None
            logger.info("Neo4j connection closed")
    
    @contextmanager
    def session(self, database: str = "neo4j"):
        """Context manager for Neo4j sessions."""
        if not self.driver:
            self.connect()
        
        session = self.driver.session(database=database)
        try:
            yield session
        finally:
            session.close()
    
    async def create_indexes(self):
        """Create necessary indexes in Neo4j."""
        with self.session() as session:
            # Create indexes for faster lookups
            indexes = [
                "CREATE INDEX document_id_idx IF NOT EXISTS FOR (d:Document) ON (d.id)",
                "CREATE INDEX chunk_id_idx IF NOT EXISTS FOR (c:Chunk) ON (c.id)",
                "CREATE INDEX entity_id_idx IF NOT EXISTS FOR (e:Entity) ON (e.id)",
                "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            ]
            
            for index_query in indexes:
                try:
                    session.run(index_query)
                    logger.debug(f"Created index: {index_query[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation warning: {e}")
    
    async def create_document_node(
        self,
        document_id: str,
        path: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Create a document node."""
        with self.session() as session:
            query = """
            MERGE (d:Document {id: $document_id})
            SET d.path = $path,
                d.content = $content,
                d.metadata = $metadata,
                d.updated_at = timestamp()
            RETURN d
            """
            session.run(
                query,
                document_id=document_id,
                path=path,
                content=content,
                metadata=metadata or {}
            )
            logger.debug(f"Created document node: {document_id}")
    
    async def create_chunk_node(
        self,
        chunk_id: str,
        document_id: str,
        chunk_index: int,
        text: str,
        start_char: int,
        end_char: int,
        metadata: Dict[str, Any] = None
    ):
        """Create a chunk node and link to document."""
        with self.session() as session:
            query = """
            MATCH (d:Document {id: $document_id})
            MERGE (c:Chunk {id: $chunk_id})
            SET c.chunk_index = $chunk_index,
                c.text = $text,
                c.start_char = $start_char,
                c.end_char = $end_char,
                c.metadata = $metadata,
                c.updated_at = timestamp()
            MERGE (d)-[:HAS_CHUNK]->(c)
            RETURN c
            """
            session.run(
                query,
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=chunk_index,
                text=text,
                start_char=start_char,
                end_char=end_char,
                metadata=metadata or {}
            )
            logger.debug(f"Created chunk node: {chunk_id}")
    
    async def create_entity_node(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        description: str = None
    ):
        """Create an entity node with entity_type as Label.
        
        Creates nodes like (:Entity:AI_CONCEPT {name: "temperature"})
        """
        with self.session() as session:
            # Sanitize entity_type for use as Label
            label = entity_type.upper().replace(' ', '_').replace('-', '_')
            
            # Use APOC to add dynamic label
            query = f"""
            MERGE (e:Entity {{id: $entity_id}})
            SET e.name = $name,
                e.type = $entity_type,
                e.description = $description,
                e.updated_at = timestamp()
            WITH e
            CALL apoc.create.addLabels(e, [$label]) YIELD node
            RETURN node
            """
            session.run(
                query,
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                description=description,
                label=label
            )
            logger.debug(f"Created entity node: {name} (:{label})")
    
    async def link_entity_to_chunk(self, entity_id: str, chunk_id: str):
        """Link an entity to a chunk."""
        with self.session() as session:
            query = """
            MATCH (e:Entity {id: $entity_id})
            MATCH (c:Chunk {id: $chunk_id})
            MERGE (e)-[:MENTIONED_IN]->(c)
            """
            session.run(query, entity_id=entity_id, chunk_id=chunk_id)
            logger.debug(f"Linked entity {entity_id} to chunk {chunk_id}")
    
    async def create_entity_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: str
    ):
        """Create a relationship between two entities by ID."""
        with self.session() as session:
            # Use dynamic relationship type
            query = f"""
            MATCH (e1:Entity {{id: $source_entity_id}})
            MATCH (e2:Entity {{id: $target_entity_id}})
            MERGE (e1)-[r:{relationship_type.upper().replace(' ', '_')}]->(e2)
            RETURN r
            """
            session.run(
                query,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id
            )
            logger.debug(f"Created relationship: {source_entity_id} -[{relationship_type}]-> {target_entity_id}")
    
    def create_entity(self, name: str, entity_type: str):
        """Create an entity node by name with entity_type as Label (sync).
        
        Creates nodes like (:Entity:AI_CONCEPT {name: "temperature"})
        """
        with self.session() as session:
            # Generate deterministic ID from name
            entity_id = hashlib.md5(name.encode()).hexdigest()
            # Sanitize entity_type for use as Label
            label = entity_type.upper().replace(' ', '_').replace('-', '_')
            
            # Use APOC to add dynamic label
            query = f"""
            MERGE (e:Entity {{name: $name}})
            ON CREATE SET e.id = $entity_id, e.type = $entity_type, e.created_at = timestamp()
            ON MATCH SET e.type = $entity_type, e.updated_at = timestamp()
            WITH e
            CALL apoc.create.addLabels(e, [$label]) YIELD node
            RETURN node
            """
            session.run(
                query,
                name=name,
                entity_id=entity_id,
                entity_type=entity_type,
                label=label
            )
            logger.debug(f"Created/updated entity: {name} (:{label})")
    
    def create_relationship(
        self,
        source: str,
        relation: str,
        target: str,
        chunk_index: int = -1
    ):
        """Create a relationship between two entities by name (sync).
        
        Uses MERGE to avoid duplicates on re-execution.
        Creates entities if they don't exist.
        
        Args:
            source: Source entity name
            relation: Relationship type (e.g., PART_OF, DEPLOYS)
            target: Target entity name
            chunk_index: Source chunk index
        """
        with self.session() as session:
            # Sanitize relation for Cypher (uppercase, replace spaces with underscores)
            rel_type = relation.upper().replace(' ', '_').replace('-', '_')
            
            # MERGE ensures no duplicates - creates entities if needed
            query = f"""
            MERGE (a:Entity {{name: $source}})
            MERGE (b:Entity {{name: $target}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.chunk_index = $chunk_index,
                r.updated_at = timestamp()
            RETURN r
            """
            session.run(
                query,
                source=source,
                target=target,
                chunk_index=chunk_index
            )
            logger.debug(f"Created relationship: {source} -[{rel_type}]-> {target}")
    
    async def search_entities(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for entities by name."""
        with self.session() as session:
            cypher_query = """
            MATCH (e:Entity)
            WHERE e.name CONTAINS $query
            RETURN e.id as id, e.name as name, e.type as type, e.description as description
            LIMIT $limit
            """
            result = session.run(cypher_query, query=query, limit=limit)
            return [dict(record) for record in result]
    
    async def get_entity_graph(self, entity_name: str, depth: int = 2) -> Dict[str, Any]:
        """Get the subgraph around an entity."""
        with self.session() as session:
            query = """
            MATCH path = (e:Entity {name: $entity_name})-[*1..$depth]-(related)
            RETURN path
            LIMIT 100
            """
            result = session.run(query, entity_name=entity_name, depth=depth)
            
            nodes = []
            relationships = []
            
            for record in result:
                path = record["path"]
                for node in path.nodes:
                    nodes.append({
                        "id": node.element_id,
                        "labels": list(node.labels),
                        "properties": dict(node)
                    })
                for rel in path.relationships:
                    relationships.append({
                        "id": rel.element_id,
                        "type": rel.type,
                        "start": rel.start_node.element_id,
                        "end": rel.end_node.element_id,
                        "properties": dict(rel)
                    })
            
            return {
                "nodes": nodes,
                "relationships": relationships
            }


# Global service instance
graph_service = GraphService()

