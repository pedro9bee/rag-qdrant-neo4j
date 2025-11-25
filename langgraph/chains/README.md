# LangChain Chains

This directory contains LangChain chain definitions for structured LLM workflows.

## What are Chains?

Chains are sequential or conditional workflows that:
- Process inputs through multiple steps
- Transform data between steps
- Call LLMs with structured prompts
- Return formatted outputs

## Example Chain Structure

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

def create_retrieval_chain():
    """Create a retrieval-augmented generation chain."""
    
    # Define prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Use this context: {context}"),
        ("user", "{question}")
    ])
    
    # Create chain
    llm = ChatOpenAI(model="gpt-4")
    chain = prompt | llm | StrOutputParser()
    
    return chain

# Usage
chain = create_retrieval_chain()
result = chain.invoke({
    "context": "Retrieved documents from QDrant...",
    "question": "What is the main topic?"
})
```

## Common Chain Types

### 1. Retrieval Chain
Combines vector search with LLM generation:

```python
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Qdrant

vectorstore = Qdrant(...)
retriever = vectorstore.as_retriever()

chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    return_source_documents=True
)
```

### 2. Sequential Chain
Execute steps in order:

```python
from langchain.chains import SequentialChain

chain = SequentialChain(
    chains=[extract_entities, summarize, generate_response],
    input_variables=["text"],
    output_variables=["response"]
)
```

### 3. Router Chain
Conditional branching:

```python
from langchain.chains.router import MultiPromptChain

chain = MultiPromptChain(
    router_chain=router,
    destination_chains={
        "technical": technical_chain,
        "general": general_chain
    }
)
```

## Integration with RAG Stack

```python
from utils.connections import get_qdrant_client, get_neo4j_driver

def create_hybrid_rag_chain():
    """Combine QDrant (vector) + Neo4J (graph) for enhanced RAG."""
    
    qdrant = get_qdrant_client()
    neo4j = get_neo4j_driver()
    
    # Vector retrieval
    def retrieve_vectors(query: str):
        # Query QDrant
        return vector_results
    
    # Graph retrieval
    def retrieve_graph(entities: list):
        # Query Neo4J
        return graph_results
    
    # Combine and generate
    # Your chain logic here
```

## Best Practices

1. **LCEL Syntax**: Use LangChain Expression Language (`|` operator)
2. **Streaming**: Enable streaming for better UX
3. **Error Handling**: Use fallbacks for LLM failures
4. **Caching**: Cache LLM responses when appropriate
5. **Monitoring**: Log chain execution for debugging

## Running in Kestra

```yaml
tasks:
  - id: run_chain
    type: io.kestra.plugin.scripts.python.Script
    docker:
      image: python:3.11-slim
    beforeCommands:
      - pip install langchain langchain-openai
    env:
      OPENAI_API_KEY: "{{ secret('OPENAI_API_KEY') }}"
    script: |
      import sys
      sys.path.append('/app/langgraph')
      
      from chains.retrieval_chain import create_retrieval_chain
      
      chain = create_retrieval_chain()
      result = chain.invoke({"question": "Your question"})
      print(result)
```

## Resources

- [LangChain Chains Guide](https://python.langchain.com/docs/modules/chains/)
- [LCEL Documentation](https://python.langchain.com/docs/expression_language/)

