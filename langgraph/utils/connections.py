"""
Connection helpers for RAG stack services.

This module provides typed connection factories for OpenAI, QDrant, Neo4J, and MinIO
when running inside Kestra containers.

Usage:
    from utils.connections import get_openai_embeddings, get_openai_llm
    from utils.connections import get_qdrant_client, get_neo4j_driver, get_minio_client
    
    embeddings = get_openai_embeddings()
    llm = get_openai_llm()
    qdrant = get_qdrant_client()
    neo4j = get_neo4j_driver()
    minio = get_minio_client()
"""

import os
from typing import Optional
from contextlib import contextmanager

try:
    from langchain_ollama import OllamaEmbeddings, ChatOllama
except ImportError:
    OllamaEmbeddings = None
    ChatOllama = None

try:
    from qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    GraphDatabase = None
    Driver = None

try:
    import boto3
except ImportError:
    boto3 = None


def get_openai_embeddings(
    model: Optional[str] = None,
    base_url: Optional[str] = None
) -> "OllamaEmbeddings":
    """
    Create Ollama embeddings client.
    
    Args:
        model: Embedding model name (defaults to bge-m3:latest)
        base_url: Ollama base URL (defaults to host.docker.internal:11434)
        
    Returns:
        Configured OllamaEmbeddings instance
        
    Raises:
        ImportError: If langchain-ollama is not installed
    """
    if OllamaEmbeddings is None:
        raise ImportError(
            "langchain-ollama not installed. Run: pip install langchain-ollama"
        )
    
    model = model or os.getenv("EMBEDDING_MODEL", "bge-m3:latest")
    base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    
    return OllamaEmbeddings(
        model=model,
        base_url=base_url
    )


def get_openai_llm(
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.3
) -> "ChatOllama":
    """
    Create Ollama LLM client for instruction/chat tasks.
    
    Args:
        model: LLM model name (defaults to bartowski/phi-3.5-mini-instruct-q5_k_m:latest)
        base_url: Ollama base URL (defaults to host.docker.internal:11434)
        temperature: Sampling temperature (0.0 = deterministic)
        
    Returns:
        Configured ChatOllama instance
        
    Raises:
        ImportError: If langchain-ollama is not installed
    """
    if ChatOllama is None:
        raise ImportError(
            "langchain-ollama not installed. Run: pip install langchain-ollama"
        )
    
    model = model or os.getenv("LLM_MODEL", "bartowski/phi-3.5-mini-instruct-q5_k_m:latest")
    base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature
    )


def get_qdrant_client(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 30
) -> "QdrantClient":
    """
    Create QDrant client with default internal hostname.
    
    Args:
        url: QDrant URL (defaults to internal hostname)
        api_key: Optional API key
        timeout: Request timeout in seconds
        
    Returns:
        Configured QdrantClient instance
        
    Raises:
        ImportError: If qdrant-client is not installed
    """
    if QdrantClient is None:
        raise ImportError("qdrant-client not installed. Run: pip install qdrant-client")
    
    url = url or os.getenv("QDRANT_URL", "http://qdrant:6333")
    api_key = api_key or os.getenv("QDRANT_API_KEY")
    
    return QdrantClient(
        url=url,
        api_key=api_key,
        timeout=timeout
    )


def get_neo4j_driver(
    uri: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    max_connection_lifetime: int = 3600
) -> "Driver":
    """
    Create Neo4J driver with default internal hostname.
    
    Args:
        uri: Neo4J Bolt URI (defaults to internal hostname)
        username: Database username
        password: Database password
        max_connection_lifetime: Connection lifetime in seconds
        
    Returns:
        Configured Neo4J Driver instance
        
    Raises:
        ImportError: If neo4j driver is not installed
    """
    if GraphDatabase is None:
        raise ImportError("neo4j driver not installed. Run: pip install neo4j")
    
    uri = uri or os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    username = username or os.getenv("NEO4J_USER", "neo4j")
    password = password or os.getenv("NEO4J_PASSWORD", "neo4j_password")
    
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        max_connection_lifetime=max_connection_lifetime
    )


@contextmanager
def neo4j_session(driver: "Driver", database: str = "neo4j"):
    """
    Context manager for Neo4J sessions with automatic cleanup.
    
    Args:
        driver: Neo4J driver instance
        database: Database name
        
    Yields:
        Neo4J session
        
    Example:
        driver = get_neo4j_driver()
        with neo4j_session(driver) as session:
            result = session.run("MATCH (n) RETURN count(n)")
            print(result.single())
    """
    session = driver.session(database=database)
    try:
        yield session
    finally:
        session.close()


def get_minio_client(
    endpoint: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    secure: bool = False
):
    """
    Create MinIO (S3) client with default internal hostname.
    
    Args:
        endpoint: MinIO endpoint URL (defaults to internal hostname)
        access_key: Access key ID
        secret_key: Secret access key
        secure: Use HTTPS (default: False for internal network)
        
    Returns:
        Configured boto3 S3 client
        
    Raises:
        ImportError: If boto3 is not installed
    """
    if boto3 is None:
        raise ImportError("boto3 not installed. Run: pip install boto3")
    
    endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "http://minio:9000")  # Internal port is still 9000
    access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin")
    
    # Remove http:// or https:// for boto3
    endpoint_url = endpoint
    if not endpoint.startswith(("http://", "https://")):
        endpoint_url = f"{'https' if secure else 'http'}://{endpoint}"
    
    return boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='us-east-1'  # MinIO doesn't care, but boto3 requires it
    )


def test_connections() -> dict[str, bool]:
    """
    Test connectivity to all RAG services.
    
    Returns:
        Dictionary with service names and their connectivity status
        
    Example:
        status = test_connections()
        print(f"QDrant: {'✓' if status['qdrant'] else '✗'}")
    """
    results = {
        "qdrant": False,
        "neo4j": False,
        "minio": False
    }
    
    # Test QDrant
    try:
        client = get_qdrant_client()
        client.get_collections()
        results["qdrant"] = True
    except Exception as e:
        print(f"QDrant connection failed: {e}")
    
    # Test Neo4J
    try:
        driver = get_neo4j_driver()
        with neo4j_session(driver) as session:
            session.run("RETURN 1")
        driver.close()
        results["neo4j"] = True
    except Exception as e:
        print(f"Neo4J connection failed: {e}")
    
    # Test MinIO
    try:
        client = get_minio_client()
        client.list_buckets()
        results["minio"] = True
    except Exception as e:
        print(f"MinIO connection failed: {e}")
    
    return results


if __name__ == "__main__":
    """Run connectivity tests when executed directly."""
    print("Testing RAG Stack Connectivity...")
    print("-" * 40)
    
    results = test_connections()
    
    for service, status in results.items():
        symbol = "✓" if status else "✗"
        print(f"{symbol} {service.upper()}: {'Connected' if status else 'Failed'}")
    
    print("-" * 40)
    
    all_connected = all(results.values())
    if all_connected:
        print("✓ All services are accessible!")
        exit(0)
    else:
        print("✗ Some services are unreachable")
        exit(1)

