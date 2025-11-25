#!/usr/bin/env python3
"""
Standalone runner for LangGraph RAG workflows.

This script allows running the ingestion and retrieval graphs
without Kestra orchestration.

Usage:
    # Ingest documents from MinIO
    python run_standalone.py ingest --bucket documents --path docs/

    # Query the RAG system
    python run_standalone.py query "What is LangGraph?"

    # Run retrieval with custom parameters
    python run_standalone.py query "Explain RAG" --top-k-vector 20 --top-k-graph 10
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from graphs.ingest_graph import build_ingest_graph
from graphs.retrieval_graph import build_retrieval_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_ingestion(bucket: str, path: str):
    """
    Run document ingestion workflow.
    
    Args:
        bucket: MinIO bucket name
        path: Path prefix in bucket
    """
    logger.info(f"Starting ingestion: bucket={bucket}, path={path}")
    
    # Build graph
    graph = build_ingest_graph()
    
    # Run ingestion
    result = graph.invoke({
        "minio_bucket": bucket,
        "minio_path": path,
        "documents": [],
        "processed_count": 0
    })
    
    # Print results
    if result.get("error"):
        logger.error(f"Ingestion failed: {result['error']}")
        return False
    
    logger.info(f"Ingestion completed successfully")
    logger.info(f"Documents processed: {result.get('processed_count', 0)}/{len(result.get('documents', []))}")
    
    return True


def run_query(
    query: str,
    top_k_vector: int = 10,
    top_k_graph: int = 5,
    rerank_top_k: int = 5
):
    """
    Run RAG query workflow.
    
    Args:
        query: User query
        top_k_vector: Number of vector results
        top_k_graph: Number of graph results
        rerank_top_k: Number of final results after reranking
    """
    logger.info(f"Running query: {query}")
    
    # Build graph
    graph = build_retrieval_graph()
    
    # Run query
    result = graph.invoke({
        "user_query": query,
        "top_k_vector": top_k_vector,
        "top_k_graph": top_k_graph,
        "rerank_top_k": rerank_top_k
    })
    
    # Print results
    if result.get("error"):
        logger.error(f"Query failed: {result['error']}")
        return False
    
    print("\n" + "=" * 80)
    print("RAG QUERY RESULTS")
    print("=" * 80)
    print(f"\nQuery: {query}\n")
    print(f"Context:\n{result.get('context', 'No context found')}\n")
    
    metadata = result.get('metadata', {})
    print(f"Sources: {metadata.get('num_sources', 0)} "
          f"(Vector: {metadata.get('vector_count', 0)}, "
          f"Graph: {metadata.get('graph_count', 0)})")
    print("=" * 80 + "\n")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Standalone runner for LangGraph RAG workflows"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents from MinIO")
    ingest_parser.add_argument(
        "--bucket",
        default="documents",
        help="MinIO bucket name (default: documents)"
    )
    ingest_parser.add_argument(
        "--path",
        default="",
        help="Path prefix in bucket (default: '')"
    )
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Query the RAG system")
    query_parser.add_argument("query", help="Query string")
    query_parser.add_argument(
        "--top-k-vector",
        type=int,
        default=10,
        help="Number of vector results (default: 10)"
    )
    query_parser.add_argument(
        "--top-k-graph",
        type=int,
        default=5,
        help="Number of graph results (default: 5)"
    )
    query_parser.add_argument(
        "--rerank-top-k",
        type=int,
        default=5,
        help="Number of final results after reranking (default: 5)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Run command
    if args.command == "ingest":
        success = run_ingestion(args.bucket, args.path)
    elif args.command == "query":
        success = run_query(
            args.query,
            top_k_vector=args.top_k_vector,
            top_k_graph=args.top_k_graph,
            rerank_top_k=args.rerank_top_k
        )
    else:
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

