#!/usr/bin/env python3
"""
Testa o regex de parsing da resposta do LLM.
"""

import re
import json

# Resposta REAL do Ollama (limpa, sem os caracteres de controle)
ollama_response = """[
{"text": "Amazon Bedrock", "type": "AWS_SERVICE", "description": "GenAI service"}
]"""

print("="*80)
print("📝 RESPOSTA DO OLLAMA")
print("="*80)
print(ollama_response)
print("="*80)

# Testar regex (o mesmo do código)
json_match = re.search(r'\[.*?\]', ollama_response, re.DOTALL)

if json_match:
    json_str = json_match.group(0)
    print(f"\n✅ JSON Match encontrado:")
    print(json_str)
    print(f"\nTamanho: {len(json_str)} caracteres")
    
    try:
        entities = json.loads(json_str)
        print(f"\n✅ JSON válido! Parsed {len(entities)} entities:")
        for e in entities:
            print(f"   - {e}")
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON inválido: {e}")
else:
    print("\n❌ Nenhum JSON match encontrado")

print("\n" + "="*80)
print("Testando regex GREEDY (.* ao invés de .*?)")
print("="*80)

json_match_greedy = re.search(r'\[.*\]', ollama_response, re.DOTALL)
if json_match_greedy:
    json_str = json_match_greedy.group(0)
    print(f"✅ JSON Match GREEDY encontrado:")
    print(json_str)
    print(f"\nTamanho: {len(json_str)} caracteres")
    
    try:
        entities = json.loads(json_str)
        print(f"\n✅ JSON válido! Parsed {len(entities)} entities:")
        for e in entities:
            print(f"   - {e}")
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON inválido: {e}")
else:
    print("\n❌ Nenhum JSON match encontrado")

