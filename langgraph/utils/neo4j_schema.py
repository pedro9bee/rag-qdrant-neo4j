"""Neo4J schema utilities and Cypher query templates."""

from typing import List, Dict, Any, Optional


# ============================================================================
# Schema Initialization
# ============================================================================

def create_indexes(driver) -> None:
    """
    Create indexes and constraints for RAG schema.
    
    Args:
        driver: Neo4J driver instance
    """
    with driver.session() as session:
        # Document node indexes
        session.run(
            "CREATE CONSTRAINT document_id IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.id IS UNIQUE"
        )
        session.run(
            "CREATE INDEX document_path IF NOT EXISTS "
            "FOR (d:Document) ON (d.path)"
        )
        
        # Chunk node indexes
        session.run(
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.id IS UNIQUE"
        )
        session.run(
            "CREATE INDEX chunk_document IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.document_id)"
        )
        
        # Entity node indexes
        session.run(
            "CREATE CONSTRAINT entity_id IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
        )
        session.run(
            "CREATE INDEX entity_name IF NOT EXISTS "
            "FOR (e:Entity) ON (e.name)"
        )
        session.run(
            "CREATE INDEX entity_type IF NOT EXISTS "
            "FOR (e:Entity) ON (e.type)"
        )


# ============================================================================
# Document Ingestion Queries
# ============================================================================

def create_document_node(
    session,
    document_id: str,
    path: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create document node in Neo4J.
    
    Args:
        session: Neo4J session
        document_id: Unique document ID
        path: File path in MinIO
        content: Full document content
        metadata: Additional metadata
        
    Returns:
        Created node properties
    """
    metadata = metadata or {}
    
    query = """
    CREATE (d:Document {
        id: $document_id,
        path: $path,
        content: $content,
        created_at: datetime(),
        metadata: $metadata
    })
    RETURN d
    """
    
    result = session.run(
        query,
        document_id=document_id,
        path=path,
        content=content,
        metadata=metadata
    )
    
    return result.single()["d"]


def create_chunk_node(
    session,
    chunk_id: str,
    document_id: str,
    chunk_index: int,
    text: str,
    start_char: int,
    end_char: int,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create chunk node and link to document.
    
    Args:
        session: Neo4J session
        chunk_id: Unique chunk ID
        document_id: Parent document ID
        chunk_index: Index of chunk in document
        text: Chunk text content
        start_char: Start character position
        end_char: End character position
        metadata: Additional metadata
        
    Returns:
        Created node properties
    """
    metadata = metadata or {}
    
    query = """
    MATCH (d:Document {id: $document_id})
    CREATE (c:Chunk {
        id: $chunk_id,
        document_id: $document_id,
        chunk_index: $chunk_index,
        text: $text,
        start_char: $start_char,
        end_char: $end_char,
        created_at: datetime(),
        metadata: $metadata
    })
    CREATE (d)-[:HAS_CHUNK {index: $chunk_index}]->(c)
    RETURN c
    """
    
    result = session.run(
        query,
        chunk_id=chunk_id,
        document_id=document_id,
        chunk_index=chunk_index,
        text=text,
        start_char=start_char,
        end_char=end_char,
        metadata=metadata
    )
    
    return result.single()["c"]


def create_entity_node(
    session,
    entity_id: str,
    name: str,
    entity_type: str,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create or merge entity node.
    
    Args:
        session: Neo4J session
        entity_id: Unique entity ID
        name: Entity name
        entity_type: Entity type (e.g., Person, Organization, Location)
        description: Entity description
        metadata: Additional metadata
        
    Returns:
        Created/merged node properties
    """
    metadata = metadata or {}
    
    query = """
    MERGE (e:Entity {id: $entity_id})
    ON CREATE SET
        e.name = $name,
        e.type = $entity_type,
        e.description = $description,
        e.created_at = datetime(),
        e.metadata = $metadata
    ON MATCH SET
        e.updated_at = datetime()
    RETURN e
    """
    
    result = session.run(
        query,
        entity_id=entity_id,
        name=name,
        entity_type=entity_type,
        description=description,
        metadata=metadata
    )
    
    return result.single()["e"]


def link_entity_to_chunk(
    session,
    entity_id: str,
    chunk_id: str,
    relationship_type: str = "MENTIONED_IN",
    properties: Optional[Dict[str, Any]] = None
) -> None:
    """
    Create relationship between entity and chunk.
    
    Args:
        session: Neo4J session
        entity_id: Entity node ID
        chunk_id: Chunk node ID
        relationship_type: Type of relationship
        properties: Relationship properties
    """
    properties = properties or {}
    
    query = f"""
    MATCH (e:Entity {{id: $entity_id}})
    MATCH (c:Chunk {{id: $chunk_id}})
    MERGE (e)-[r:{relationship_type}]->(c)
    SET r += $properties
    RETURN r
    """
    
    session.run(
        query,
        entity_id=entity_id,
        chunk_id=chunk_id,
        properties=properties
    )


def create_entity_relationship(
    session,
    source_entity_id: str,
    target_entity_id: str,
    relationship_type: str,
    properties: Optional[Dict[str, Any]] = None
) -> None:
    """
    Create relationship between two entities.
    
    Args:
        session: Neo4J session
        source_entity_id: Source entity ID
        target_entity_id: Target entity ID
        relationship_type: Type of relationship
        properties: Relationship properties
    """
    properties = properties or {}
    
    query = f"""
    MATCH (source:Entity {{id: $source_entity_id}})
    MATCH (target:Entity {{id: $target_entity_id}})
    MERGE (source)-[r:{relationship_type}]->(target)
    SET r += $properties
    RETURN r
    """
    
    session.run(
        query,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        properties=properties
    )


# ============================================================================
# Retrieval Queries
# ============================================================================

def get_chunks_by_document_id(session, document_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a document.
    
    Args:
        session: Neo4J session
        document_id: Document ID
        
    Returns:
        List of chunk nodes
    """
    query = """
    MATCH (d:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
    RETURN c
    ORDER BY c.chunk_index
    """
    
    result = session.run(query, document_id=document_id)
    return [record["c"] for record in result]


def get_entities_by_chunk_id(session, chunk_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all entities mentioned in a chunk.
    
    Args:
        session: Neo4J session
        chunk_id: Chunk ID
        
    Returns:
        List of entity nodes
    """
    query = """
    MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk {id: $chunk_id})
    RETURN e
    """
    
    result = session.run(query, chunk_id=chunk_id)
    return [record["e"] for record in result]


def get_related_chunks_by_entity(
    session,
    entity_name: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find chunks that mention a specific entity.
    
    Args:
        session: Neo4J session
        entity_name: Entity name to search
        limit: Maximum number of chunks to return
        
    Returns:
        List of chunk nodes with entity relationships
    """
    query = """
    MATCH (e:Entity {name: $entity_name})-[:MENTIONED_IN]->(c:Chunk)
    RETURN c, e
    LIMIT $limit
    """
    
    result = session.run(query, entity_name=entity_name, limit=limit)
    return [{"chunk": record["c"], "entity": record["e"]} for record in result]


def get_entity_graph(
    session,
    entity_name: str,
    depth: int = 2
) -> Dict[str, Any]:
    """
    Get entity and its relationships up to specified depth.
    
    Args:
        session: Neo4J session
        entity_name: Starting entity name
        depth: Relationship depth to traverse
        
    Returns:
        Graph with entities and relationships
    """
    query = f"""
    MATCH path = (e:Entity {{name: $entity_name}})-[*1..{depth}]-(related:Entity)
    RETURN e, relationships(path) as rels, related
    LIMIT 100
    """
    
    result = session.run(query, entity_name=entity_name)
    
    entities = set()
    relationships = []
    
    for record in result:
        entities.add(dict(record["e"]))
        entities.add(dict(record["related"]))
        
        for rel in record["rels"]:
            relationships.append({
                "type": rel.type,
                "properties": dict(rel)
            })
    
    return {
        "entities": list(entities),
        "relationships": relationships
    }

