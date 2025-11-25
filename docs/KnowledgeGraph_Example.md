# Knowledge Graph Architecture - Bedrock AgentCore + LangGraph

## Visão Geral

Este documento detalha a estrutura do Knowledge Graph usado no sistema RAG, baseado na arquitetura de agentes com Bedrock AgentCore, LangGraph e MCP (Model Context Protocol).

## Entidades do Domínio

### 1. Arquitetura de Agentes

| Entidade | Descrição | Tipo spaCy |
|----------|-----------|------------|
| **Agent** | Sistema de IA completo que orquestra o fluxo | ORG |
| **Graph** | Estrutura LangGraph que define o workflow | PRODUCT |
| **Node** | Etapa de execução ou decisão no fluxo | PRODUCT |
| **State** | Dados mutáveis compartilhados entre nós | CONCEPT |
| **Transition** | Regras que ligam nós e definem caminhos | CONCEPT |
| **LLM** | Modelo de linguagem (Claude, etc.) | PRODUCT |
| **Tool** | Interface de ação (função Python) | PRODUCT |
| **Memory** | Serviço persistente STM/LTM | PRODUCT |
| **User** | Ator que interage com o agente | PERSON |

### 2. Protocolo e Integração

| Entidade | Descrição | Tipo spaCy |
|----------|-----------|------------|
| **MCP** | Model Context Protocol | PRODUCT |
| **Gateway** | Serviço que executa lógica de negócio | PRODUCT |
| **BusinessSystem** | Sistema terceiro (CRM, ERP, DB) | ORG |
| **BedrockAgentCore** | Runtime serverless AWS | PRODUCT |

### 3. Infraestrutura RAG

| Entidade | Descrição | Tipo spaCy |
|----------|-----------|------------|
| **AWS** | Amazon Web Services | ORG |
| **Bedrock** | Serviço AWS para modelos de IA | PRODUCT |
| **Lambda** | Função serverless AWS | PRODUCT |
| **S3** | Armazenamento de objetos AWS | PRODUCT |
| **Claude** | Modelo LLM da Anthropic | PRODUCT |
| **Haiku** | Versão rápida do Claude | PRODUCT |
| **Sonnet** | Versão balanceada do Claude | PRODUCT |
| **Opus** | Versão mais capaz do Claude | PRODUCT |

### 4. Stack RAG

| Entidade | Descrição | Tipo spaCy |
|----------|-----------|------------|
| **LangChain** | Framework para aplicações LLM | PRODUCT |
| **LangGraph** | Extensão para workflows com estado | PRODUCT |
| **Qdrant** | Vector database | PRODUCT |
| **Neo4j** | Graph database | PRODUCT |
| **MinIO** | Object storage S3-compatible | PRODUCT |
| **Ollama** | Runtime local para modelos | PRODUCT |
| **Kestra** | Orquestrador de workflows | PRODUCT |

### 5. Componentes RAG

| Entidade | Descrição | Tipo spaCy |
|----------|-----------|------------|
| **RAG** | Retrieval Augmented Generation | CONCEPT |
| **Embedding** | Representação vetorial de texto | CONCEPT |
| **Vector** | Vetor numérico para similaridade | CONCEPT |
| **Chunk** | Fragmento de documento | CONCEPT |
| **Document** | Documento completo | CONCEPT |

## Relacionamentos

### 1. Orquestração do Agente

```cypher
// The Agent is implemented by a Graph
(Agent)-[:implemented_by]->(Graph)

// The Graph contains Nodes
(Graph)-[:contains]->(Node)

// The Node operates on State
(Node)-[:operates_on]->(State)
(Node)-[:updates]->(State)

// The Node uses LLM for reasoning
(Node)-[:uses_for_reasoning]->(LLM)

// Transitions connect Nodes
(Node)-[:connects]->(Transition)-[:connects]->(Node)
```

### 2. Integração de Ferramentas

```cypher
// The Node invokes Tools
(Node)-[:invokes]->(Tool)

// The Tool uses MCP protocol
(Tool)-[:uses_protocol]->(MCP)

// MCP routes to Gateway
(MCP)-[:routes_to]->(Gateway)

// Gateway accesses Business System
(Gateway)-[:accesses]->(BusinessSystem)
```

### 3. Infraestrutura

```cypher
// The Agent executes in Bedrock
(Agent)-[:executes_in]->(BedrockAgentCore)

// The Agent persists data in Memory
(Agent)-[:persists_data_in]->(Memory)

// User interacts with Agent
(User)-[:interacts_with]->(Agent)
```

### 4. Stack RAG

```cypher
// Bedrock oferece Claude
(Bedrock)-[:oferece]->(Claude)

// Claude usa Embeddings
(Claude)-[:usa]->(Embedding)

// LangGraph orquestra RAG
(LangGraph)-[:orquestra]->(RAG)

// RAG consulta Qdrant
(RAG)-[:consulta]->(Qdrant)

// RAG consulta Neo4j
(RAG)-[:consulta]->(Neo4j)

// Document armazena em MinIO
(Document)-[:armazena]->(MinIO)

// Chunk indexa em Qdrant
(Chunk)-[:indexa_em]->(Qdrant)

// Ollama embeddings por bge-m3
(Ollama)-[:embeddings_por]->(bge-m3)
```

## Exemplo Completo de Grafo

```cypher
// 1. Create Nodes (Entities)
CREATE (agent:Agent {name: "RAG Agent", version: "1.0"})
CREATE (graph:Graph {framework: "LangGraph", type: "StateGraph"})
CREATE (node_ingest:Node {name: "Ingest Node", type: "ETL"})
CREATE (node_retrieve:Node {name: "Retrieve Node", type: "Search"})
CREATE (state:State {type: "SharedContext", schema: "TypedDict"})
CREATE (llm:LLM {model: "Claude 3.5 Sonnet", provider: "Bedrock"})
CREATE (tool_embed:Tool {name: "generate_embeddings", type: "Python Function"})
CREATE (tool_search:Tool {name: "vector_search", type: "Python Function"})
CREATE (mcp:MCP {version: "1.0", protocol: "JSON-RPC"})
CREATE (gateway_qdrant:Gateway {name: "Qdrant Gateway", url: "http://qdrant:6333"})
CREATE (gateway_neo4j:Gateway {name: "Neo4j Gateway", url: "bolt://neo4j:7687"})
CREATE (qdrant:BusinessSystem {type: "Vector Database", name: "Qdrant"})
CREATE (neo4j:BusinessSystem {type: "Graph Database", name: "Neo4j"})
CREATE (bedrock:BedrockAgentCore {region: "us-east-1", service: "AgentRuntime"})
CREATE (memory:Memory {type: "DynamoDB", persistence: "LTM"})
CREATE (user:User {role: "End User", interface: "API"});

// 2. Relationships - Orchestration
MATCH (ag:Agent {name: "RAG Agent"}), (gr:Graph {framework: "LangGraph"})
CREATE (ag)-[:implemented_by]->(gr);

MATCH (gr:Graph {framework: "LangGraph"}), (ni:Node {name: "Ingest Node"})
CREATE (gr)-[:contains]->(ni);

MATCH (gr:Graph {framework: "LangGraph"}), (nr:Node {name: "Retrieve Node"})
CREATE (gr)-[:contains]->(nr);

MATCH (ni:Node {name: "Ingest Node"}), (es:State {type: "SharedContext"})
CREATE (ni)-[:operates_on]->(es), (ni)-[:updates]->(es);

MATCH (nr:Node {name: "Retrieve Node"}), (llm:LLM {model: "Claude 3.5 Sonnet"})
CREATE (nr)-[:uses_for_reasoning]->(llm);

// 3. Relationships - Tools
MATCH (ni:Node {name: "Ingest Node"}), (te:Tool {name: "generate_embeddings"})
CREATE (ni)-[:invokes]->(te);

MATCH (nr:Node {name: "Retrieve Node"}), (ts:Tool {name: "vector_search"})
CREATE (nr)-[:invokes]->(ts);

MATCH (te:Tool {name: "generate_embeddings"}), (m:MCP {version: "1.0"})
CREATE (te)-[:uses_protocol]->(m);

MATCH (m:MCP {version: "1.0"}), (gq:Gateway {name: "Qdrant Gateway"})
CREATE (m)-[:routes_to]->(gq);

MATCH (gq:Gateway {name: "Qdrant Gateway"}), (q:BusinessSystem {name: "Qdrant"})
CREATE (gq)-[:accesses]->(q);

MATCH (gn:Gateway {name: "Neo4j Gateway"}), (n:BusinessSystem {name: "Neo4j"})
CREATE (gn)-[:accesses]->(n);

// 4. Relationships - Infrastructure
MATCH (ag:Agent {name: "RAG Agent"}), (br:BedrockAgentCore {region: "us-east-1"})
CREATE (ag)-[:executes_in]->(br);

MATCH (ag:Agent {name: "RAG Agent"}), (mem:Memory {type: "DynamoDB"})
CREATE (ag)-[:persists_data_in]->(mem);

MATCH (u:User {role: "End User"}), (ag:Agent {name: "RAG Agent"})
CREATE (u)-[:interacts_with]->(ag);
```

## Pipeline de Extração

O pipeline RAG implementado extrai automaticamente estas entidades e relacionamentos dos documentos:

### 1. Detecção de Entidades (spaCy NER)

```python
# spaCy detecta entidades iniciais
doc = nlp(chunk_text)
for ent in doc.ents:
    # ORG: AWS, Bedrock, Neo4j, etc.
    # PRODUCT: LangGraph, Claude, Qdrant, etc.
    # PERSON: USUARIO, etc.
    pass
```

### 2. Validação com Phi-3.5

```python
# LLM valida cada entidade contra ENTITIES_LIST
validation_prompt = f"""
Does the following text contain the entity "{entity}" 
in a relevant, central, meaningful way?
Answer with ONLY "YES" or "NO".
"""
# Apenas entidades validadas são persistidas
```

### 3. Extração de Relacionamentos

```python
# LLM extrai relacionamentos estruturados
extraction_prompt = f"""
Extract relationships between entities from the allowed list.
Allowed entities: {ENTITIES_LIST}
Text: {chunk}

Return ONLY valid JSON array of triples.
Predicates must be snake_case, infinitive form.

Example:
[
  {{"subject": "Agent", "predicate": "implemented_by", "object": "Graph"}},
  {{"subject": "Node", "predicate": "uses_for_reasoning", "object": "LLM"}}
]
"""
```

## Queries Úteis

### Encontrar todos os componentes de um Agente

```cypher
MATCH path = (a:Agent)-[*1..3]-(component)
WHERE a.name = "RAG Agent"
RETURN path;
```

### Rastrear fluxo de dados

```cypher
MATCH path = (u:User)-[:interacts_with]->(a:Agent)
              -[:implemented_by]->(g:Graph)
              -[:contains]->(n:Node)
              -[:invokes]->(f:Tool)
RETURN path;
```

### Verificar stack tecnológico

```cypher
MATCH (system:BusinessSystem)
OPTIONAL MATCH (gateway:Gateway)-[:accesses]->(system)
OPTIONAL MATCH (mcp:MCP)-[:routes_to]->(gateway)
RETURN system.name, gateway.name, count(mcp) as num_protocols;
```

## Benefícios desta Arquitetura de Grafo

1. **Rastreabilidade Completa**: Cada decisão do agente pode ser rastreada através do grafo
2. **Descoberta de Dependências**: Identificar facilmente quais sistemas dependem de quais
3. **Análise de Impacto**: Avaliar impacto de mudanças antes de implementar
4. **Otimização de Caminhos**: Encontrar rotas mais eficientes entre componentes
5. **Documentação Viva**: O grafo representa a arquitetura real extraída dos documentos

## Próximos Passos

1. **Enriquecer Entidades**: Adicionar propriedades específicas do domínio
2. **Tipos de Relacionamento**: Criar subtipos mais específicos
3. **Validação de Esquema**: Garantir consistência do grafo
4. **Métricas de Qualidade**: Avaliar completude e precisão das extrações
5. **Visualização**: Criar dashboards interativos no Neo4j Browser

