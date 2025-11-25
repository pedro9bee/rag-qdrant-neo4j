# Kestra Flow Examples

This directory contains example Kestra flows demonstrating integration with the RAG stack.

## Quick Start

1. Start the stack:
   ```bash
   make up
   ```

2. Access Kestra UI: http://localhost:8080

3. Create a new flow and paste the contents of `kestra-flow-example.yml`

4. Execute the flow with a test query

## Available Examples

### `kestra-flow-example.yml`

A complete RAG pipeline example that demonstrates:
- Connecting to QDrant (vector database)
- Connecting to Neo4J (knowledge graph)
- Querying both data sources
- Combining results for context-aware responses

**Usage**:
1. Copy the YAML content
2. In Kestra UI, go to "Flows" > "Create"
3. Paste the YAML
4. Save and execute
5. Provide a query input (e.g., "What is machine learning?")

## Creating Your Own Flows

### Basic Structure

```yaml
id: my-flow
namespace: company.team

inputs:
  - id: my_input
    type: STRING

tasks:
  - id: my_task
    type: io.kestra.plugin.scripts.python.Script
    docker:
      image: python:3.11-slim
    beforeCommands:
      - pip install <your-dependencies>
    script: |
      # Your Python code here
      print("Hello from Kestra!")
```

### Best Practices

1. **Use beforeCommands for dependencies**:
   ```yaml
   beforeCommands:
     - pip install --no-cache-dir langchain qdrant-client neo4j
   ```

2. **Access secrets securely**:
   ```yaml
   env:
     OPENAI_API_KEY: "{{ secret('OPENAI_API_KEY') }}"
   ```

3. **Use internal hostnames**:
   ```python
   qdrant = QdrantClient(url="http://qdrant:6333")
   neo4j = GraphDatabase.driver("bolt://neo4j:7687")
   ```

4. **Handle errors gracefully**:
   ```python
   try:
       # Your code
   except Exception as e:
       print(f"Error: {e}")
       raise  # Kestra will mark task as failed
   ```

5. **Output useful information**:
   ```yaml
   outputs:
     - id: result
       type: STRING
       value: "{{ outputs.my_task.vars.result }}"
   ```

## Advanced Patterns

### Parallel Execution

```yaml
tasks:
  - id: parallel_group
    type: io.kestra.core.tasks.flows.Parallel
    tasks:
      - id: query_qdrant
        type: io.kestra.plugin.scripts.python.Script
        # ...
      
      - id: query_neo4j
        type: io.kestra.plugin.scripts.python.Script
        # ...
```

### Conditional Execution

```yaml
tasks:
  - id: check_condition
    type: io.kestra.plugin.scripts.python.Script
    script: |
      print("::output::condition::true")
  
  - id: conditional_task
    type: io.kestra.plugin.scripts.python.Script
    runIf: "{{ outputs.check_condition.vars.condition == 'true' }}"
```

### Error Handling

```yaml
tasks:
  - id: risky_task
    type: io.kestra.plugin.scripts.python.Script
    script: |
      # Might fail
    retry:
      maxAttempt: 3
      behavior: RETRY
```

## Resources

- [Kestra Documentation](https://kestra.io/docs)
- [LangChain Python Docs](https://python.langchain.com/docs)
- [QDrant API Reference](https://qdrant.tech/documentation/quick-start/)
- [Neo4J Python Driver](https://neo4j.com/docs/python-manual/current/)

