# 🚀 LangGraph Chat API

FastAPI server com endpoints OpenAI-compatible usando workflows LangGraph para RAG completo.

## 🎯 Diferença entre os serviços:

```
RAG API (porta 8000)
├─ Endpoints gerais (chunk, embed, ingest, graph)
├─ AIjudante simples (retorna "banana")
├─ Operações granulares e específicas
└─ Ideal para: operações diretas de RAG

LangGraph Chat API (porta 8001)  ← NOVO!
├─ Chat OpenAI-compatible
├─ Usa workflows completos do LangGraph
├─ RAG híbrido automático (vector + graph + rerank)
├─ Resposta contextualizada
└─ Ideal para: chat conversacional com RAG completo
```

## 🚀 Como iniciar:

### Opção 1: Modo Local
```bash
# Terminal 1: Ollama
OLLAMA_HOST=0.0.0.0 ollama serve

# Terminal 2: RAG API (opcional, se precisar dos endpoints gerais)
./start-local.sh

# Terminal 3: LangGraph Chat API
./start-langgraph-api.sh
# ou explicitamente:
./start-langgraph-api.sh local
```

### Opção 2: Modo VPS
```bash
# Aponta para serviços na VPS
./start-langgraph-api.sh vps
```

## 📊 URLs de Acesso:

| Serviço | URL | Descrição |
|---------|-----|-----------|
| LangGraph API | http://localhost:8001 | API principal |
| API Docs | http://localhost:8001/docs | Swagger interativo |
| Health Check | http://localhost:8001/health | Status |
| Models | http://localhost:8001/v1/models | Lista de modelos |

## 🧪 Testar a API:

### 1. Health Check
```bash
curl http://localhost:8001/health
```

### 2. Listar Modelos
```bash
curl http://localhost:8001/v1/models
```

### 3. Chat (OpenAI-compatible)
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "langgraph-rag-v1",
    "messages": [
      {"role": "user", "content": "What is LangGraph?"}
    ],
    "top_k_vector": 10,
    "top_k_graph": 5,
    "rerank_top_k": 5
  }'
```

### 4. Chat com histórico
```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "langgraph-rag-v1",
    "messages": [
      {"role": "user", "content": "What is LangGraph?"},
      {"role": "assistant", "content": "LangGraph is..."},
      {"role": "user", "content": "How does it work?"}
    ]
  }'
```

## 🎨 Integração com Open WebUI:

### Configuração Automática
O Open WebUI já está configurado para detectar ambos endpoints:
- http://host.docker.internal:8000/v1 (RAG API - AIjudante)
- http://host.docker.internal:8001/v1 (LangGraph Chat API)

### Como usar:

1. **Abra Open WebUI**: http://localhost:3000

2. **Vá em Settings → Connections**

3. **Você verá 2 modelos disponíveis**:
   - `aijudante-v1` (porta 8000) - Retorna "banana"
   - `langgraph-rag-v1` (porta 8001) - RAG completo

4. **Selecione `langgraph-rag-v1`** para usar RAG real

5. **Comece a conversar!**

## 🔍 Como funciona internamente:

```
User Message
     ↓
LangGraph Chat API (porta 8001)
     ↓
retrieval_graph.py
     ↓
┌─────────────────────────────────────┐
│  1. Generate Query Embedding        │
│     (Ollama bge-m3)                 │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  2. Parallel Search                 │
│     ├─ Qdrant (chunks)             │
│     ├─ Qdrant (entities)           │
│     ├─ Qdrant (relationships)      │
│     └─ Neo4j (graph)               │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  3. Merge & Rerank (RRF)           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  4. Format Context                  │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  5. Build Response                  │
│     (with sources)                  │
└──────────────┬──────────────────────┘
               ↓
        Response to User
```

## 🎯 Parâmetros do Chat:

```json
{
  "model": "langgraph-rag-v1",
  "messages": [...],
  "top_k_vector": 10,     // Quantos resultados vector buscar
  "top_k_graph": 5,       // Quantos resultados graph buscar
  "rerank_top_k": 5       // Quantos resultados finais retornar
}
```

## 📦 Estrutura de Resposta:

```json
{
  "id": "chatcmpl-langgraph",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "langgraph-rag-v1",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Based on 5 sources I found:\n\n[Context with sources]..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 50,
    "total_tokens": 60
  }
}
```

## 🛑 Parar os serviços:

```bash
# Parar LangGraph API
pkill -f "uvicorn api.main:app"

# Ou usar Ctrl+C no terminal onde está rodando

# Parar tudo (RAG API + Docker)
./stop-local.sh
```

## 🔧 Troubleshooting:

### Porta 8001 em uso
```bash
# Ver o que está usando
lsof -i :8001

# Matar processo
kill -9 $(lsof -t -i :8001)
```

### Erro ao importar graphs
```bash
cd langgraph
source venv/bin/activate
pip install -e .
```

### Erro de conexão com serviços
Verifique se os serviços estão rodando:
```bash
# Neo4j
curl http://localhost:7474

# Qdrant
curl http://localhost:6333

# Ollama
curl http://localhost:11434/api/tags
```

## 🎨 Exemplo de Uso Completo:

```bash
# 1. Ingerir documento (via RAG API)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "langraph-intro",
    "content": "LangGraph is a library for building stateful, multi-actor applications with LLMs.",
    "is_markdown": false
  }'

# 2. Conversar sobre o documento (via LangGraph Chat API)
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "langgraph-rag-v1",
    "messages": [
      {"role": "user", "content": "What is LangGraph?"}
    ]
  }'

# Resposta incluirá contexto recuperado do documento ingerido!
```

## 🚀 Próximos Passos:

1. ✅ Ingira alguns documentos via `/ingest`
2. ✅ Configure Open WebUI para usar `langgraph-rag-v1`
3. ✅ Comece a fazer perguntas sobre os documentos
4. ✅ Experimente ajustar `top_k_vector` e `top_k_graph`

## 💡 Dicas:

- Use `top_k_vector=20` para buscas mais abrangentes
- Use `rerank_top_k=3` para respostas mais concisas
- Ingira documentos markdown para melhor estrutura
- Monitore logs para ver o processo de retrieval

---

**Agora você tem um sistema RAG completo com chat conversacional!** 🎉

