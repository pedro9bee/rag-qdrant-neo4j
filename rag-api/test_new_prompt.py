#!/usr/bin/env python3
"""
Teste rápido do novo prompt de extração de entidades.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_ollama import ChatOllama

async def test():
    """Testa o novo prompt."""
    
    chunk_text = """# Generative AI with Amazon Bedrock

Build, scale, and secure generative AI applications using Amazon Bedrock.

Shikhar Kwatra, a senior AI/ML solutions architect at Amazon Web Services, 
holds the distinction of being the world's Youngest Master Inventor with 
over 500 patents in AI/ML and IoT domains.

This course covers LangChain integration with Claude 3 on Amazon Bedrock, 
building RAG agents, and using FAISS for vector search. You'll learn how 
to implement fine-tuning with Amazon SageMaker and deploy models using AWS Lambda.

Published by Packt Publishing Ltd."""
    
    # Novo prompt
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
    
    print("="*80)
    print("🔍 TESTANDO NOVO PROMPT")
    print("="*80)
    print(f"\nTexto de entrada ({len(chunk_text)} chars):")
    print("-"*80)
    print(chunk_text[:300] + "...")
    print("-"*80)
    
    # Call Ollama
    model = ChatOllama(
        base_url="http://localhost:11434",
        model="mistral:latest",
        temperature=0.3
    )
    
    print("\n🚀 Calling mistral:latest...")
    response = model.invoke(prompt)
    answer = response.content.strip()
    
    print("\n" + "="*80)
    print("💬 RESPOSTA DO LLM:")
    print("="*80)
    print(answer)
    print("="*80)
    
    # Parse JSON
    import json
    import re
    
    json_match = re.search(r'\[.*?\]', answer, re.DOTALL)
    if json_match:
        try:
            entities = json.loads(json_match.group(0))
            print(f"\n✅ Extraídas {len(entities)} entidades:")
            print("-"*80)
            for i, e in enumerate(entities, 1):
                print(f"{i}. {e.get('text', 'N/A')} ({e.get('type', 'N/A')})")
                print(f"   → {e.get('description', 'N/A')}")
            print("-"*80)
            return True
        except json.JSONDecodeError as e:
            print(f"\n❌ Erro ao parsear JSON: {e}")
            return False
    else:
        print("\n❌ Nenhum JSON array encontrado na resposta")
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)

