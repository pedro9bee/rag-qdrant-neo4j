#!/usr/bin/env python3
"""
Mostra o prompt EXATO que está sendo usado no processamento real.
"""

import redis
import json
import sys

# Conectar Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Pegar chunks do job
chunks_data = r.get("job:751f87e1-ecf9-48a0-a468-bff7162fd0ea:chunks")

if not chunks_data:
    print("❌ Nenhum chunk encontrado no Redis")
    sys.exit(1)

chunks = json.loads(chunks_data)
print(f"✅ Encontrados {len(chunks)} chunks no Redis\n")

# Pegar o primeiro chunk
chunk = chunks[0]
chunk_text = chunk["text"]
chunk_index = chunk["index"]

print("="*80)
print(f"📦 CHUNK {chunk_index}")
print("="*80)
print(f"Tamanho: {len(chunk_text)} caracteres")
print(f"Preview: {chunk_text[:200]}...")
print("="*80)

# Montar o prompt EXATAMENTE como no código
prompt = f"""
### SYSTEM INSTRUCTION
You are an expert AI Engineer and Data Scientist. 
Your task is to extract technical entities from the course content about Generative AI and Amazon Bedrock.
Return ONLY a valid JSON array.

### RULES
1. Output MUST be a raw JSON list.
2. Do NOT use markdown code blocks.
3. If no entities are found, return [].
4. Be precise with technical terminology.

### SCHEMA & DEFINITIONS
- text: The exact entity name.
- type: Choose EXACTLY one from the list below:
  * AWS_SERVICE: Amazon cloud services (e.g., "Amazon Bedrock", "SageMaker", "AWS Lambda").
  * AI_MODEL: Foundation models and LLMs (e.g., "Claude 3", "Amazon Titan", "Llama 2").
  * TOOL_LIB: Development tools, libraries, frameworks (e.g., "LangChain", "Python", "FAISS").
  * CONCEPT: Theoretical AI concepts and architectures (e.g., "RAG", "Agents", "Fine-tuning").
  * PERSON: Key instructors or authors (e.g., "Shikhar Kwatra").
  * ORG: Companies or organizations (e.g., "Anthropic", "AWS", "Packt").
- description: Brief context (max 5 words).

### EXAMPLES
Input: "In this module, Shikhar demonstrates how to use LangChain with Anthropic Claude v2 on Amazon Bedrock to build a RAG agent."
Output: [
  {{"text": "Shikhar", "type": "PERSON", "description": "Instructor"}},
  {{"text": "LangChain", "type": "TOOL_LIB", "description": "Orchestration framework"}},
  {{"text": "Anthropic Claude v2", "type": "AI_MODEL", "description": "Foundation model"}},
  {{"text": "Amazon Bedrock", "type": "AWS_SERVICE", "description": "GenAI service"}},
  {{"text": "RAG", "type": "CONCEPT", "description": "Retrieval-Augmented Generation"}}
]

### INPUT TEXT
{chunk_text[:1000]}

### OUTPUT
"""

print("\n" + "="*80)
print("📝 PROMPT EXATO QUE SERÁ ENVIADO AO LLM")
print("="*80)
print(prompt)
print("="*80)

print(f"\n📊 ESTATÍSTICAS DO PROMPT:")
print(f"   Tamanho total: {len(prompt)} caracteres")
print(f"   Tamanho do texto de entrada: {len(chunk_text[:1000])} caracteres")
print(f"   Chunk original: {len(chunk_text)} caracteres (limitado a 1000)")

# Salvar em arquivo para análise
with open("/tmp/real_prompt.txt", "w") as f:
    f.write(prompt)

print(f"\n✅ Prompt salvo em: /tmp/real_prompt.txt")
print("\n💡 Para testar este prompt:")
print("   1. Copie o conteúdo de /tmp/real_prompt.txt")
print("   2. Cole no Ollama: ollama run mistral:latest")
print("   3. Ou use: cat /tmp/real_prompt.txt | ollama run mistral:latest")

