# LangGraph Agents

This directory contains LangGraph agent definitions.

## What are Agents?

Agents are autonomous entities that can:
- Make decisions based on context
- Use tools to accomplish tasks
- Maintain conversation state
- Reason through complex problems

## Example Agent Structure

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "The conversation messages"]
    next_action: str

def create_rag_agent():
    """Create a RAG agent with QDrant and Neo4J integration."""
    
    workflow = StateGraph(AgentState)
    
    # Define nodes
    workflow.add_node("query_vector_db", query_vector_db_node)
    workflow.add_node("query_knowledge_graph", query_graph_node)
    workflow.add_node("synthesize", synthesize_response_node)
    
    # Define edges
    workflow.set_entry_point("query_vector_db")
    workflow.add_edge("query_vector_db", "query_knowledge_graph")
    workflow.add_edge("query_knowledge_graph", "synthesize")
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()
```

## Best Practices

1. **Type your state**: Use TypedDict for agent state
2. **Modular nodes**: Keep each node focused on one task
3. **Error handling**: Gracefully handle tool failures
4. **Logging**: Track agent decisions for debugging
5. **Testing**: Unit test individual nodes before integration

## Integration with Kestra

Run agents in Kestra flows:

```yaml
tasks:
  - id: run_agent
    type: io.kestra.plugin.scripts.python.Script
    docker:
      image: python:3.11-slim
    beforeCommands:
      - pip install langgraph langchain qdrant-client neo4j
    script: |
      import sys
      sys.path.append('/app/langgraph')
      
      from agents.rag_agent import create_rag_agent
      
      agent = create_rag_agent()
      result = agent.invoke({"messages": [("user", "Your query here")]})
      print(result)
```

## Resources

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangGraph Examples](https://github.com/langchain-ai/langgraph/tree/main/examples)

