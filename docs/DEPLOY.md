# Deployment Guide - RAG Stack on Contabo VPS

This guide covers deploying the complete RAG stack (MinIO, Qdrant, Neo4j, Kestra, Ollama, Redis) to a Contabo VPS.

## Prerequisites

- Contabo VPS with at least **8GB RAM** and **4 vCPUs**
- Docker and Docker Compose installed
- SSH access to the VPS
- Domain/IP: `62.171.130.110` (replace with your actual IP)

## Quick Deploy

### 1. Clone Repository on VPS

```bash
ssh root@62.171.130.110

cd /opt
git clone <your-repo-url> contabo
cd contabo
```

### 2. Copy Files from Local to VPS

From your local machine:

```bash
# Copy entire project to VPS
scp -r /Users/pedrofernandes/repositories/contabo root@62.171.130.110:/opt/

# Or copy specific files if already cloned
scp docker-compose.yml root@62.171.130.110:/opt/contabo/
scp -r ollama/ root@62.171.130.110:/opt/contabo/
scp -r langgraph/ root@62.171.130.110:/opt/contabo/
```

### 3. Make Scripts Executable

```bash
ssh root@62.171.130.110
cd /opt/contabo
chmod +x ollama/init-models.sh
```

### 4. Start the Stack

```bash
# Start all services
docker-compose up -d

# Monitor logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 5. Wait for Ollama Models to Initialize

```bash
# Watch Ollama initialization (first time only, takes 5-10 minutes)
docker logs -f ollama-init

# Verify models are loaded
docker exec ollama ollama list
```

Expected output:
```
NAME                                              ID              SIZE      MODIFIED
bartowski/phi-3.5-mini-instruct-q5_k_m:latest    abc123def456    2.3 GB    2 minutes ago
bge-m3:latest                                     xyz789uvw123    1.8 GB    3 minutes ago
```

## Service Access

Once deployed, services are available at:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Kestra** | http://62.171.130.110:8080 | None (basic-auth disabled) |
| **MinIO Console** | http://62.171.130.110:9003 | minioadmin / minioadmin |
| **MinIO API** | http://62.171.130.110:9002 | minioadmin / minioadmin |
| **Neo4j Browser** | http://62.171.130.110:7474 | neo4j / neo4j_password |
| **Qdrant Dashboard** | http://62.171.130.110:6333/dashboard | None |
| **MinerU Gateway** | http://62.171.130.110:8000 | None |
| **Ollama API** | http://62.171.130.110:11434 | None |
| **Redis** | 62.171.130.110:6379 | None |

## Workflow Setup

### 1. Upload Workflows to Kestra

1. Access Kestra: http://62.171.130.110:8080
2. Go to **Flows** → **Create**
3. Upload workflows:
   - `langgraph/flows/ingest_rag.yml` (Document ingestion)
   - `langgraph/flows/retrieval_rag.yml` (Hybrid retrieval)

### 2. Upload Documents to MinIO

```bash
# Using MinIO Console (Web UI)
# 1. Go to http://62.171.130.110:9003
# 2. Login with minioadmin / minioadmin
# 3. Create bucket "markdown" (or use existing)
# 4. Upload your .md files

# Or using mc (MinIO Client)
mc alias set contabo http://62.171.130.110:9002 minioadmin minioadmin
mc cp your-document.md contabo/markdown/
```

### 3. Run Ingestion Workflow

In Kestra UI:
1. Navigate to `ai.rag.ingest_rag` flow
2. Click **Execute**
3. Set inputs:
   ```yaml
   minio_bucket: markdown
   minio_path: ""
   ```
4. Monitor execution

### 4. Query RAG System

In Kestra UI:
1. Navigate to `ai.rag.retrieval_rag` flow
2. Click **Execute**
3. Set inputs:
   ```yaml
   user_query: "What is AWS Bedrock?"
   top_k_vector: 10
   top_k_graph: 5
   rerank_top_k: 5
   ```

## Configuration

### Environment Variables

All configuration is in `docker-compose.yml` under the `kestra` service environment section:

```yaml
environment:
  # MinIO
  MINIO_ENDPOINT: "http://minio:9000"
  MINIO_ACCESS_KEY: "minioadmin"
  MINIO_SECRET_KEY: "minioadmin"
  
  # Qdrant
  QDRANT_URL: "http://qdrant:6333"
  QDRANT_COLLECTION_NAME: "rag_embeddings"
  
  # Neo4j
  NEO4J_URI: "bolt://neo4j:7687"
  NEO4J_USER: "neo4j"
  NEO4J_PASSWORD: "neo4j_password"
  
  # Ollama
  OLLAMA_URL: "http://ollama:11434"
  EMBEDDING_MODEL: "bge-m3:latest"
  LLM_MODEL: "bartowski/phi-3.5-mini-instruct-q5_k_m:latest"
  
  # Knowledge Graph
  ENTITIES_LIST: "Agent,Graph,AWS,Bedrock,..."
  RELATIONSHIPS_LIST: "uses,contains,implements,..."
```

### Security Hardening (Production)

⚠️ **IMPORTANT**: Change default credentials before production deployment:

```yaml
# MinIO
MINIO_ROOT_USER: your-secure-user
MINIO_ROOT_PASSWORD: your-secure-password-min-8-chars

# Neo4j
NEO4J_AUTH: neo4j/your-secure-neo4j-password

# Kestra (enable auth)
kestra:
  server:
    basic-auth:
      enabled: true
      username: admin@kestra.io
      password: your-secure-kestra-password
```

### Firewall Setup (Optional but Recommended)

```bash
# Allow only specific ports
ufw allow 22/tcp    # SSH
ufw allow 8080/tcp  # Kestra
ufw allow 9003/tcp  # MinIO Console
ufw enable

# Or allow specific IPs only
ufw allow from YOUR_IP_ADDRESS to any port 8080
```

## Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f ollama
docker-compose logs -f kestra
docker-compose logs -f mineru-processor
```

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart ollama
docker-compose restart kestra
```

### Update Stack

```bash
cd /opt/contabo

# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose pull
docker-compose up -d
```

### Backup Data

```bash
# Backup all volumes
docker run --rm -v kestra_data:/data -v $(pwd):/backup alpine tar czf /backup/kestra_data.tar.gz /data
docker run --rm -v minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_data.tar.gz /data
docker run --rm -v neo4j_data:/data -v $(pwd):/backup alpine tar czf /backup/neo4j_data.tar.gz /data
docker run --rm -v qdrant_storage:/data -v $(pwd):/backup alpine tar czf /backup/qdrant_storage.tar.gz /data
docker run --rm -v ollama_data:/data -v $(pwd):/backup alpine tar czf /backup/ollama_data.tar.gz /data
```

### Clean Up

```bash
# Stop and remove all containers
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove unused images
docker image prune -a
```

## Troubleshooting

### Ollama Models Not Loading

```bash
# Check if Ollama is running
docker exec ollama ollama list

# Manually trigger initialization
docker-compose restart ollama-init
docker logs -f ollama-init

# Check available disk space (models need ~5GB)
df -h
```

### Kestra Workflow Fails

```bash
# Check Kestra logs
docker logs kestra

# Verify environment variables are set
docker exec kestra env | grep OLLAMA_URL

# Test Ollama connectivity from Kestra
docker exec kestra curl http://ollama:11434/api/tags
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Reduce concurrent conversions in MinerU
# Edit docker-compose.yml:
MAX_CONCURRENT_CONVERSIONS: 1

# Or add swap space
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Cannot Access Services Externally

```bash
# Check if ports are bound to 0.0.0.0
netstat -tulpn | grep LISTEN

# Restart with updated docker-compose.yml
docker-compose down
docker-compose up -d

# Check firewall
ufw status
```

## Performance Tuning

### For VPS with Limited Resources (4GB RAM)

```yaml
# Use lighter Ollama model (Q4 instead of Q5)
LLM_MODEL: "bartowski/phi-3.5-mini-instruct-q4_k_m:latest"

# Reduce chunk size
CHUNK_SIZE: "500"

# Reduce concurrent processing
MAX_CONCURRENT_CONVERSIONS: 1
```

### For VPS with More Resources (16GB+ RAM)

```yaml
# Use higher quality model
LLM_MODEL: "bartowski/phi-3.5-mini-instruct-q6_k:latest"

# Increase chunk size for better context
CHUNK_SIZE: "2000"

# Increase concurrent processing
MAX_CONCURRENT_CONVERSIONS: 5
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review documentation: `docs/` directory
- Check Ollama README: `ollama/README.md`

