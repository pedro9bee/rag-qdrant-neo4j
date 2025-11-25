// ============================================================================
// Neo4j Knowledge Graph Schema Example
// Bedrock AgentCore + LangGraph + MCP Architecture
// ============================================================================

// Clear existing graph (WARNING: Removes all data!)
// MATCH (n) DETACH DELETE n;

// ============================================================================
// 1. Entity Creation (Nodes)
// ============================================================================

// --- Agent Architecture ---
CREATE (agent:Agent {
    name: "RAG Bedrock Agent",
    version: "1.0.0",
    status: "active",
    description: "Complete AI system with RAG and Knowledge Graph"
})

CREATE (graph:Graph {
    framework: "LangGraph",
    type: "StateGraph",
    version: "0.0.40",
    description: "Structure that defines the workflow"
})

CREATE (node_scan:Node {
    name: "scan_minio",
    type: "entry_step",
    function: "Scan documents in MinIO"
})

CREATE (node_chunk:Node {
    name: "chunk_document",
    type: "processing_step",
    function: "Split documents into chunks"
})

CREATE (node_embed:Node {
    name: "generate_embeddings",
    type: "ai_step",
    function: "Generate embeddings with Ollama"
})

CREATE (node_extract:Node {
    name: "extract_entities",
    type: "ai_step",
    function: "Extract and validate entities with spaCy + Phi-3.5"
})

CREATE (node_retrieve:Node {
    name: "hybrid_retrieval",
    type: "search_step",
    function: "Hybrid search (vector + graph)"
})

CREATE (state:State {
    type: "IngestState",
    schema: "TypedDict",
    fields: "documents,chunks,embeddings,entities,relationships"
})

CREATE (transition:Transition {
    type: "conditional_edge",
    condition: "should_continue",
    description: "Determines if more documents need processing"
})

// --- LLM Models ---
CREATE (llm_phi:LLM {
    model: "Phi-3.5-mini",
    provider: "Ollama",
    version: "Q5_K_M",
    type: "instruct",
    function: "Entity validation and relationship extraction"
})

CREATE (llm_claude:LLM {
    model: "Claude 3.5 Sonnet",
    provider: "AWS Bedrock",
    function: "Final user response"
})

CREATE (llm_embed:LLM {
    model: "bge-m3",
    provider: "Ollama",
    dimensions: 1024,
    type: "embedding",
    function: "Multilingual embedding generation"
})

// --- Tools ---
CREATE (tool_spacy:Tool {
    name: "spacy_ner",
    type: "NER",
    model: "en_core_web_sm",
    language: "Python"
})

CREATE (tool_validate:Tool {
    name: "validate_entity",
    type: "LLM Validation",
    model: "Phi-3.5-mini"
})

CREATE (tool_embed:Tool {
    name: "generate_embeddings",
    type: "Embedding",
    model: "bge-m3"
})

CREATE (tool_extract_rel:Tool {
    name: "extract_relationships",
    type: "Relationship Extraction",
    model: "Phi-3.5-mini"
})

CREATE (tool_search:Tool {
    name: "vector_search",
    type: "Vector Search",
    backend: "Qdrant"
})

CREATE (tool_graph_search:Tool {
    name: "graph_search",
    type: "Graph Search",
    backend: "Neo4j"
})

// --- MCP Protocol ---
CREATE (mcp:MCP {
    name: "Model Context Protocol",
    version: "1.0",
    protocol: "JSON-RPC",
    description: "Standardizes communication with backends"
})

// --- Gateways ---
CREATE (gateway_ollama:Gateway {
    name: "Ollama Gateway",
    url: "http://host.docker.internal:11434",
    type: "Local LLM",
    service: "Inference Engine"
})

CREATE (gateway_qdrant:Gateway {
    name: "Qdrant Gateway",
    url: "http://qdrant:6333",
    type: "Vector Database",
    service: "Vector Search"
})

CREATE (gateway_neo4j:Gateway {
    name: "Neo4j Gateway",
    url: "bolt://neo4j:7687",
    type: "Graph Database",
    service: "Knowledge Graph"
})

CREATE (gateway_minio:Gateway {
    name: "MinIO Gateway",
    url: "http://minio:9000",
    type: "Object Storage",
    service: "Document Storage"
})

// --- Business Systems ---
CREATE (sys_qdrant:BusinessSystem {
    name: "Qdrant",
    type: "Vector Database",
    version: "1.16.0",
    dimensions: 1024,
    distance: "cosine"
})

CREATE (sys_neo4j:BusinessSystem {
    name: "Neo4j",
    type: "Graph Database",
    version: "5.26.17",
    edition: "community"
})

CREATE (sys_minio:BusinessSystem {
    name: "MinIO",
    type: "Object Storage",
    compatible: "S3",
    bucket: "rag-documents"
})

CREATE (sys_ollama:BusinessSystem {
    name: "Ollama",
    type: "LLM Runtime",
    host: "Local GPU",
    models: "bge-m3, Phi-3.5-mini"
})

// --- Runtime ---
CREATE (bedrock:BedrockAgentCore {
    service: "AWS Bedrock AgentCore",
    region: "us-east-1",
    type: "Serverless Runtime",
    features: "Agent Runtime, Memory, Knowledge Bases"
})

CREATE (kestra:BedrockAgentCore {
    service: "Kestra",
    type: "Orchestrator",
    url: "http://kestra:8080",
    description: "On-premise workflow orchestrator"
})

// --- Memory ---
CREATE (memory:Memory {
    type: "Neo4j Persistent",
    persistence: "LTM",
    structure: "Knowledge Graph",
    description: "Persistent knowledge graph"
})

CREATE (memory_vector:Memory {
    type: "Qdrant Vectors",
    persistence: "STM/LTM",
    structure: "Vector Index",
    description: "Vector index for semantic search"
})

// --- User ---
CREATE (user:User {
    role: "End User",
    interface: "REST API",
    access: "Query & Response"
})

CREATE (developer:User {
    role: "Developer",
    interface: "Kestra UI",
    access: "Workflow Management"
})

// ============================================================================
// 2. Relationships - Agent Orchestration
// ============================================================================

// The Agent is implemented by a Graph
MATCH (ag:Agent {name: "RAG Bedrock Agent"}), (gr:Graph {framework: "LangGraph"})
CREATE (ag)-[:implemented_by {version: "1.0"}]->(gr);

// The Graph contains Nodes
MATCH (gr:Graph {framework: "LangGraph"}), (n:Node)
CREATE (gr)-[:contains]->(n);

// Nodes operate on and update State
MATCH (n:Node), (st:State {type: "IngestState"})
CREATE (n)-[:operates_on]->(st), (n)-[:updates]->(st);

// Nodes use LLM for different functions
MATCH (ne:Node {name: "generate_embeddings"}), (le:LLM {model: "bge-m3"})
CREATE (ne)-[:uses_for_reasoning {function: "embedding"}]->(le);

MATCH (nx:Node {name: "extract_entities"}), (lp:LLM {model: "Phi-3.5-mini"})
CREATE (nx)-[:uses_for_reasoning {function: "entity_validation"}]->(lp);

MATCH (nr:Node {name: "hybrid_retrieval"}), (lc:LLM {model: "Claude 3.5 Sonnet"})
CREATE (nr)-[:uses_for_reasoning {function: "final_response"}]->(lc);

// Transitions connect Nodes (sequential flow)
MATCH (n1:Node {name: "scan_minio"}), (n2:Node {name: "chunk_document"}), (t:Transition)
CREATE (n1)-[:connects {order: 1}]->(t)-[:connects {order: 2}]->(n2);

MATCH (n2:Node {name: "chunk_document"}), (n3:Node {name: "generate_embeddings"}), (t:Transition)
CREATE (n2)-[:connects {order: 2}]->(t)-[:connects {order: 3}]->(n3);

MATCH (n3:Node {name: "generate_embeddings"}), (n4:Node {name: "extract_entities"}), (t:Transition)
CREATE (n3)-[:connects {order: 3}]->(t)-[:connects {order: 4}]->(n4);

// ============================================================================
// 3. Relationships - Tool Integration
// ============================================================================

// Nodes invoke Tools
MATCH (nx:Node {name: "extract_entities"}), (ts:Tool {name: "spacy_ner"})
CREATE (nx)-[:invokes {order: 1}]->(ts);

MATCH (nx:Node {name: "extract_entities"}), (tv:Tool {name: "validate_entity"})
CREATE (nx)-[:invokes {order: 2}]->(tv);

MATCH (ne:Node {name: "generate_embeddings"}), (te:Tool {name: "generate_embeddings"})
CREATE (ne)-[:invokes]->(te);

MATCH (nr:Node {name: "hybrid_retrieval"}), (tsv:Tool {name: "vector_search"})
CREATE (nr)-[:invokes]->(tsv);

MATCH (nr:Node {name: "hybrid_retrieval"}), (tsg:Tool {name: "graph_search"})
CREATE (nr)-[:invokes]->(tsg);

// Tools use MCP protocol
MATCH (f:Tool), (m:MCP {version: "1.0"})
WHERE f.type IN ["Vector Search", "Graph Search"]
CREATE (f)-[:uses_protocol]->(m);

// MCP routes to Gateways
MATCH (m:MCP {version: "1.0"}), (go:Gateway {name: "Ollama Gateway"})
CREATE (m)-[:routes_to {service: "LLM"}]->(go);

MATCH (m:MCP {version: "1.0"}), (gq:Gateway {name: "Qdrant Gateway"})
CREATE (m)-[:routes_to {service: "Vector"}]->(gq);

MATCH (m:MCP {version: "1.0"}), (gn:Gateway {name: "Neo4j Gateway"})
CREATE (m)-[:routes_to {service: "Graph"}]->(gn);

// Gateways access Business Systems
MATCH (go:Gateway {name: "Ollama Gateway"}), (so:BusinessSystem {name: "Ollama"})
CREATE (go)-[:accesses {protocol: "HTTP/REST"}]->(so);

MATCH (gq:Gateway {name: "Qdrant Gateway"}), (sq:BusinessSystem {name: "Qdrant"})
CREATE (gq)-[:accesses {protocol: "HTTP/REST"}]->(sq);

MATCH (gn:Gateway {name: "Neo4j Gateway"}), (sn:BusinessSystem {name: "Neo4j"})
CREATE (gn)-[:accesses {protocol: "Bolt"}]->(sn);

MATCH (gm:Gateway {name: "MinIO Gateway"}), (sm:BusinessSystem {name: "MinIO"})
CREATE (gm)-[:accesses {protocol: "S3 Compatible"}]->(sm);

// ============================================================================
// 4. Relationships - Infrastructure and Context
// ============================================================================

// The Agent executes in different runtimes
MATCH (ag:Agent {name: "RAG Bedrock Agent"}), (k:BedrockAgentCore {service: "Kestra"})
CREATE (ag)-[:executes_in {environment: "On-Premise"}]->(k);

// The Agent persists data in different memories
MATCH (ag:Agent {name: "RAG Bedrock Agent"}), (mn:Memory {type: "Neo4j Persistent"})
CREATE (ag)-[:persists_data_in {type: "Knowledge Graph"}]->(mn);

MATCH (ag:Agent {name: "RAG Bedrock Agent"}), (mv:Memory {type: "Qdrant Vectors"})
CREATE (ag)-[:persists_data_in {type: "Vector Index"}]->(mv);

// Users interact with the Agent
MATCH (u:User {role: "End User"}), (ag:Agent {name: "RAG Bedrock Agent"})
CREATE (u)-[:interacts_with {via: "API"}]->(ag);

MATCH (d:User {role: "Developer"}), (k:BedrockAgentCore {service: "Kestra"})
CREATE (d)-[:interacts_with {via: "UI"}]->(k);

// ============================================================================
// 5. Relationships - RAG Stack Specific
// ============================================================================

// Stack components
MATCH (sys_ollama:BusinessSystem {name: "Ollama"}), (llm_embed:LLM {model: "bge-m3"})
CREATE (sys_ollama)-[:offers {type: "embedding"}]->(llm_embed);

MATCH (sys_ollama:BusinessSystem {name: "Ollama"}), (llm_phi:LLM {model: "Phi-3.5-mini"})
CREATE (sys_ollama)-[:offers {type: "instruct"}]->(llm_phi);

MATCH (sys_qdrant:BusinessSystem {name: "Qdrant"}), (memory_vector:Memory {type: "Qdrant Vectors"})
CREATE (sys_qdrant)-[:stores]->(memory_vector);

MATCH (sys_neo4j:BusinessSystem {name: "Neo4j"}), (memory:Memory {type: "Neo4j Persistent"})
CREATE (sys_neo4j)-[:stores]->(memory);

// ============================================================================
// 6. Create Indexes for Performance
// ============================================================================

// Indexes already created by default schema, but we can add more
CREATE INDEX agent_name IF NOT EXISTS FOR (a:Agent) ON (a.name);
CREATE INDEX node_name IF NOT EXISTS FOR (n:Node) ON (n.name);
CREATE INDEX tool_name IF NOT EXISTS FOR (f:Tool) ON (f.name);
CREATE INDEX llm_model IF NOT EXISTS FOR (l:LLM) ON (l.model);
CREATE INDEX system_name IF NOT EXISTS FOR (s:BusinessSystem) ON (s.name);

// ============================================================================
// 7. Useful Example Queries
// ============================================================================

// === Visualize entire agent flow ===
// MATCH path = (u:User)-[:interacts_with]->(a:Agent)
//               -[:implemented_by]->(g:Graph)
//               -[:contains]->(n:Node)
// RETURN path;

// === Find all components a Node uses ===
// MATCH path = (n:Node {name: "extract_entities"})-[*1..3]-(component)
// RETURN path;

// === Trace flow from tool to final system ===
// MATCH path = (f:Tool {name: "vector_search"})
//               -[:uses_protocol]->(m:MCP)
//               -[:routes_to]->(g:Gateway)
//               -[:accesses]->(s:BusinessSystem)
// RETURN path;

// === List all LLMs and their providers ===
// MATCH (llm:LLM)
// OPTIONAL MATCH (sys:BusinessSystem)-[:offers]->(llm)
// RETURN llm.model, llm.provider, sys.name, llm.function;

// === Find all integration points (Gateways) ===
// MATCH (g:Gateway)-[:accesses]->(s:BusinessSystem)
// RETURN g.name, g.url, s.name, s.type;

// === Dependency analysis: What depends on Ollama? ===
// MATCH path = (component)-[*1..4]-(sys:BusinessSystem {name: "Ollama"})
// RETURN DISTINCT labels(component)[0] as component_type, 
//        component.name as name,
//        length(path) as distance;
