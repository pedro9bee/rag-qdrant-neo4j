# LangChain Custom Tools

This directory contains custom tool definitions for LangChain agents.

## What are Tools?

Tools are functions that agents can call to:
- Query external systems (QDrant, Neo4J, APIs)
- Perform computations
- Retrieve information
- Execute actions

## Example Tool Structure

```python
from typing import Optional
from langchain.tools import BaseTool
from pydantic import Field

class QdrantSearchTool(BaseTool):
    name: str = "qdrant_search"
    description: str = "Search for similar documents in the vector database"
    
    collection_name: str = Field(default="documents")
    
    def _run(self, query: str, k: int = 5) -> list[str]:
        """Execute the tool."""
        from utils.connections import get_qdrant_client
        
        client = get_qdrant_client()
        # Perform search
        results = client.search(
            collection_name=self.collection_name,
            query_vector=encode(query),
            limit=k
        )
        return [r.payload["text"] for r in results]
    
    async def _arun(self, query: str, k: int = 5) -> list[str]:
        """Async version."""
        return self._run(query, k)
```

## RAG Stack Tools

### 1. QDrant Vector Search

```python
from langchain.tools import tool

@tool
def search_vectors(query: str, collection: str = "documents") -> str:
    """Search for similar documents in QDrant vector database."""
    from utils.connections import get_qdrant_client
    
    client = get_qdrant_client()
    # Implementation
    return results
```

### 2. Neo4J Graph Query

```python
@tool
def query_knowledge_graph(entity: str) -> str:
    """Query Neo4J knowledge graph for entity relationships."""
    from utils.connections import get_neo4j_driver, neo4j_session
    
    driver = get_neo4j_driver()
    with neo4j_session(driver) as session:
        result = session.run(
            "MATCH (e:Entity {name: $name})-[r]->(related) RETURN related",
            name=entity
        )
        return list(result)
```

### 3. MinIO Document Retrieval

```python
@tool
def get_document_from_storage(document_id: str, bucket: str = "documents") -> str:
    """Retrieve document from MinIO object storage."""
    from utils.connections import get_minio_client
    
    client = get_minio_client()
    obj = client.get_object(bucket, document_id)
    return obj.read().decode('utf-8')
```

## Tool Best Practices

1. **Clear Descriptions**: Agent uses description to decide when to call
2. **Type Hints**: Full typing for inputs and outputs
3. **Error Handling**: Return error messages, don't raise exceptions
4. **Sync + Async**: Implement both `_run` and `_arun` when possible
5. **Connection Reuse**: Use connection helpers from `utils/`

## Using Tools with Agents

```python
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI

from tools.qdrant_tool import QdrantSearchTool
from tools.neo4j_tool import Neo4jQueryTool

# Initialize tools
tools = [
    QdrantSearchTool(),
    Neo4jQueryTool()
]

# Create agent
llm = ChatOpenAI(model="gpt-4")
agent = create_openai_functions_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools)

# Execute
result = agent_executor.invoke({"input": "Find similar documents about AI"})
```

## Tool Categories

### Information Retrieval
- Vector search (QDrant)
- Graph queries (Neo4J)
- Document fetching (MinIO)

### Data Processing
- Text extraction
- Entity recognition
- Summarization

### External APIs
- Web search
- API calls
- Database queries

## Running in Kestra

```yaml
tasks:
  - id: agent_with_tools
    type: io.kestra.plugin.scripts.python.Script
    docker:
      image: python:3.11-slim
    beforeCommands:
      - pip install langchain langchain-openai qdrant-client neo4j
    env:
      OPENAI_API_KEY: "{{ secret('OPENAI_API_KEY') }}"
    script: |
      import sys
      sys.path.append('/app/langgraph')
      
      from tools.qdrant_tool import search_vectors
      from tools.neo4j_tool import query_knowledge_graph
      
      # Use tools in your agent
      result = search_vectors("machine learning")
      print(result)
```

## Resources

- [LangChain Tools Documentation](https://python.langchain.com/docs/modules/agents/tools/)
- [Custom Tools Guide](https://python.langchain.com/docs/modules/agents/tools/custom_tools)

