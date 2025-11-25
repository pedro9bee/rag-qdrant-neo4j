#!/usr/bin/env python3
"""Teste simples de extração com Ollama direto."""

import asyncio
import json
import re
from langchain_ollama import ChatOllama

async def test():
    """Testa extração direta."""
    
    text = """Shikhar Kwatra is a senior AI/ML solutions architect at Amazon Web Services. 
He works with Amazon Bedrock and has over 500 patents in AI/ML domains. 
The book was published by Packt Publishing Ltd."""
    
    # Prompt ultra-simples
    prompt = f"""Extract entities from text. Return JSON array only:

TEXT: {text}

Format: [{{"text":"name","type":"PERSON|ORG|TECH","description":"desc"}}]

JSON:"""
    
    print("="*80)
    print("PROMPT:")
    print("="*80)
    print(prompt)
    print("="*80)
    
    # Testar com mistral:latest
    model = ChatOllama(
        base_url="http://localhost:11434",
        model="mistral:latest",
        temperature=0.3
    )
    
    print("\n🚀 Calling Ollama (mistral:latest)...\n")
    response = model.invoke(prompt)
    answer = response.content.strip()
    
    print("="*80)
    print("RESPOSTA:")
    print("="*80)
    print(answer)
    print("="*80)
    
    # Parse JSON
    json_match = re.search(r'\[.*?\]', answer, re.DOTALL)
    if json_match:
        entities = json.loads(json_match.group(0))
        print(f"\n✅ {len(entities)} entidades extraídas:")
        for e in entities:
            print(f"  - {e.get('text')} ({e.get('type')}): {e.get('description', 'N/A')}")
        return True
    else:
        print("\n❌ Nenhum JSON encontrado")
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)

