import asyncio
import json
import logging
import re
import torch
from typing import List, Dict, Any

# GLiNER para Entidades (Rápido e Preciso)
from gliner import GLiNER

# LangChain para Ollama (Relacionamentos)
from langchain_openai import ChatOpenAI
from app.config import settings

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalGraphEngine:
    def __init__(self):
        # 1. GLiNER (Entidades) - Roda na GPU do Mac (MPS) ou CPU
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info(f"🚀 Loading GLiNER on {device}...")
        self.ner_model = GLiNER.from_pretrained("urchade/gliner_large-v2.1").to(device)
        
        # 2. Ollama (Relacionamentos) - Roda local
        logger.info("🧠 Connecting to Local Ollama...")
        self.llm_rels = ChatOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q5_K_M",
            temperature=0.0,    # Zero criatividade para não errar JSON
            max_retries=1,
            timeout=60.0
        )

        # Labels para o GLiNER
        self.entity_labels = [
            "AWS_SERVICE", "GENAI_MODEL", "AI_CONCEPT", 
            "TOOL_LIB", "ARCH_PATTERN", "SECURITY", 
            "PROMPTING", "ORG", "PERSON"
        ]

    def _safe_json_parse(self, text: str) -> List[Dict]:
        """Tenta extrair JSON de qualquer jeito. Se falhar, retorna lista vazia."""
        text = text.strip()
        
        # Remove Markdown
        if "```" in text:
            try:
                text = re.split(r"```(?:json)?", text)[1].split("```")[0].strip()
            except: pass

        # Busca lista [...]
        start = text.find('[')
        end = text.rfind(']')
        
        if start != -1 and end != -1:
            text = text[start:end+1]
        
        try:
            data = json.loads(text)
            if isinstance(data, list): return data
            if isinstance(data, dict) and "relationships" in data: 
                return data["relationships"]
            return []
        except:
            return [] # Retorna vazio em caso de erro (ZERA o chunk)

    # ========================================================================
    # 1. EXTRAÇÃO DE ENTIDADES (GLiNER)
    # ========================================================================
    
    async def extract_entities_batch_parallel(self, chunks: List[Dict]) -> List[Dict]:
        """
        Interface compatível com o pipeline. Usa GLiNER.
        """
        all_entities = []
        total = len(chunks)
        logger.info(f"🔍 Starting Entity Extraction (GLiNER) on {total} chunks...")
        
        for i, chunk in enumerate(chunks):
            try:
                # GLiNER é síncrono, rodamos em thread para não bloquear
                predictions = await asyncio.to_thread(
                    self.ner_model.predict_entities, 
                    chunk["text"], 
                    self.entity_labels, 
                    threshold=0.3
                )
                
                for p in predictions:
                    all_entities.append({
                        "text": p["text"],
                        "type": p["label"],
                        "description": "Entity extracted from context",
                        "score": float(p["score"]),
                        "chunk_index": chunk["index"]
                    })
                
                if i % 50 == 0:
                    logger.info(f"✅ Entities Progress: {i}/{total}")
                    
            except Exception as e:
                logger.error(f"❌ Entity Error chunk {chunk['index']}: {e}")
                continue # Pula chunk com erro
                
        return all_entities

    # ========================================================================
    # 2. EXTRAÇÃO DE RELACIONAMENTOS (OLLAMA) - O QUE FALTAVA
    # ========================================================================

    async def extract_relationships_batch_parallel(self, chunks: List[Dict], entities: List[Dict]) -> List[Dict]:
        """
        Extrai relacionamentos em pequenos lotes para não afogar o Mac.
        Se um chunk falhar, ele zera e continua.
        """
        all_relationships = []
        total = len(chunks)
        
        # Batch pequeno para rodar local (Mac M3)
        batch_size = 5 
        
        # Indexar entidades para acesso rápido
        ents_by_chunk = {}
        for e in entities:
            cid = e.get("chunk_index")
            if cid is not None:
                if cid not in ents_by_chunk: ents_by_chunk[cid] = []
                ents_by_chunk[cid].append(e)

        logger.info(f"🔗 Starting Relationship Extraction on Local Ollama ({total} chunks)")

        for i in range(0, total, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            tasks = []
            
            for chunk in batch_chunks:
                c_idx = chunk['index']
                c_ents = ents_by_chunk.get(c_idx, [])
                
                # Só chama LLM se tiver pelo menos 2 entidades para conectar
                if len(c_ents) >= 2:
                    tasks.append(self._process_single_relationship_chunk(chunk, c_ents))
            
            if not tasks:
                continue

            # Executa o lote
            results = await asyncio.gather(*tasks)
            
            # Agrega resultados válidos
            for res in results:
                if res:
                    all_relationships.extend(res)
            
            logger.info(f"✅ Rel Batch {i//batch_size + 1} Done. Total Rels: {len(all_relationships)}")

        return all_relationships

    async def _process_single_relationship_chunk(self, chunk: Dict, entities: List[Dict]) -> List[Dict]:
        """Processa um único chunk. Se der erro, retorna []."""
        try:
            entity_list = ", ".join([f"{e['text']} ({e['type']})" for e in entities[:30]])
            
            prompt = f"""Identify relationships between these entities based on the text.
TEXT: {chunk['text'][:2000]}
ENTITIES: {entity_list}
Format: JSON list of objects with 'source', 'target', 'relation'.
"""
            # Invoca Ollama
            res = await self.llm_rels.ainvoke(prompt)
            
            # Parse Seguro
            rels = self._safe_json_parse(res.content)
            
            valid_rels = []
            for r in rels:
                if isinstance(r, dict) and r.get("source") and r.get("target"):
                    r["chunk_index"] = chunk["index"]
                    valid_rels.append(r)
            
            return valid_rels

        except Exception as e:
            # Loga o erro mas não para o processo. Retorna vazio.
            logger.error(f"❌ Rel Error Chunk {chunk['index']}: {e}")
            return []

# Instância Global (para ser importada pelas rotas)
entity_processor = LocalGraphEngine()