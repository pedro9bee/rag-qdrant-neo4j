#!/usr/bin/env python3
"""
Script de teste rápido para extração de entidades.
Testa diferentes modelos até encontrar um que funcione.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.entity_processor import EntityProcessor
from app.config import settings


async def test_extraction():
    """Testa extração com um chunk de exemplo."""
    
    # Chunk de teste
    test_chunk = {
        "index": 0,
        "text": """# Generative AI with Amazon Bedrock

Build, scale, and secure generative AI applications using Amazon Bedrock

Shikhar Kwatra, a senior AI/ML solutions architect at Amazon Web Services, 
holds the distinction of being the world's Youngest Master Inventor with 
over 500 patents in AI/ML and IoT domains.

Published by Packt Publishing Ltd."""
    }
    
    print(f"\n{'='*80}")
    print(f"🧪 TESTE DE EXTRAÇÃO DE ENTIDADES")
    print(f"{'='*80}")
    print(f"Modelo: {settings.ENTITY_EXTRACTION_MODEL}")
    print(f"Backend: {settings.LLM_BACKEND}")
    print(f"{'='*80}\n")
    
    # Criar processor
    processor = EntityProcessor()
    
    # Testar extração
    print("🚀 Iniciando extração...\n")
    entities = await processor.extract_entities_from_chunk(test_chunk)
    
    print(f"\n{'='*80}")
    print(f"📊 RESULTADO")
    print(f"{'='*80}")
    print(f"Total de entidades extraídas: {len(entities)}")
    
    if entities:
        print(f"\n✅ SUCESSO! Entidades encontradas:\n")
        for i, entity in enumerate(entities, 1):
            print(f"{i}. {entity['text']} ({entity['type']})")
            print(f"   → {entity['description']}")
            print()
        return True
    else:
        print(f"\n❌ FALHA: Nenhuma entidade extraída")
        print(f"\nTente outro modelo em env.local:")
        print(f"  - mistral:latest")
        print(f"  - llama3.2:3b")
        print(f"  - hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M")
        print(f"  - hf.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF:Q5_K_M")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_extraction())
    sys.exit(0 if success else 1)

