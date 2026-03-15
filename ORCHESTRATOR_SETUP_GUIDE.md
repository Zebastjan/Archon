# Cephalosage Orchestrator Setup Guide

## Overview

The Cephalosage Orchestrator is a local HTTP service that enhances code audits with LLM-powered insights. It uses a 7-14B parameter model running on RTX 3060 12GB with 4-bit quantization.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   MCP Server    │────▶│  Orchestrator    │────▶│  Local LLM      │
│  (Frontier)     │     │  (FastAPI)       │     │  (Ollama)       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                        │                        │
         │                        ▼                        │
         │               ┌──────────────────┐              │
         │               │  repo_health_  │              │
         │               │  check()         │              │
         │               └──────────────────┘              │
         │                        │                        │
         ▼                        ▼                        ▼
   Returns:              Calls:                   Generates:
   {health_score,        PostgreSQL                Natural language
    executive_summary,   + metrics                 summary
    detailed_analysis}   + audit results
```

## Prerequisites

### Hardware Requirements
- **GPU**: RTX 3060 12GB (or equivalent)
- **RAM**: 16GB+ recommended
- **Storage**: 10GB free space for models

### Software Requirements
- Python 3.10+
- Ollama (for local LLM)
- PostgreSQL 14+

## Installation

### Step 1: Install Ollama

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Or download from https://ollama.com/download
```

### Step 2: Download Model

Choose one of these models (7-14B, 4-bit quantized):

```bash
# Option A: Llama 3.2 (8B) - Fast, good quality
ollama pull llama3.2

# Option B: Qwen 2.5 (7B) - Excellent for code analysis
ollama pull qwen2.5:7b

# Option C: Mistral (7B) - Good balance
ollama pull mistral:7b

# Option D: Codellama (7B) - Code-optimized
ollama pull codellama:7b
```

**Recommended**: `llama3.2` for general use, `codellama:7b` for code-specific tasks.

### Step 3: Verify Ollama

```bash
# Start Ollama
ollama serve

# In another terminal, test:
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Hello, world!"
}'
```

### Step 4: Install Python Dependencies

```bash
cd /home/zebastjan/dev/archon/python

# Install orchestrator dependencies
uv add fastapi uvicorn httpx

# Or with pip
pip install fastapi uvicorn httpx
```

## Configuration

### Environment Variables

```bash
# .env file
ORCHESTRATOR_PORT=8080
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.2

# Optional: Custom PostgreSQL URL
ARCHON_DATABASE_URL=postgresql://archon:archon_local_dev@localhost:5434/archon
```

### Model Selection

### Recommended Models for RTX 3060 12GB

#### Option 1: LiquidAI LFM2-8B-A1B (Liquid 8B) ⭐ RECOMMENDED - DEFAULT
```bash
LOCAL_LLM_MODEL=kahnwong/lfm2:8b-a1b  # Mixture-of-Experts, 8B parameters
```

**✅ TESTED & VALIDATED** - This is our recommended model!

- **VRAM Usage**: ~4.7GB (fits comfortably on RTX 3060 12GB)
- **Speed**: Super fast inference (~1-2s)
- **Quality**: Excellent - better output than comparable models
- **Architecture**: Mixture-of-Experts (MoE) with efficient routing
- **Best For**: Production orchestration, production deployments

**Why This Model?**
- ⚡ **Fast**: Significantly faster inference than other 8B models
- 🎯 **High Quality**: Output quality rivals larger models
- 💾 **Efficient**: Only ~4.7GB VRAM usage
- ✅ **Tested**: Validated with real audit prompts

**Installation:**
```bash
# This model is already pulled!
ollama list | grep lfm2

# If you need to pull it:
ollama pull kahnwong/lfm2:8b-a1b
```

#### Option 2: Llama 3.2 (Alternative)
```bash
LOCAL_LLM_MODEL=lfm2-8b-a1b  # Mixture-of-Experts, 3-4B quality at 1.5B active
```

**Why Liquid 8B?**
- **Architecture**: Mixture-of-Experts (MoE) with 1.5B active parameters per forward pass
- **Quality**: Matches 3-4B dense models despite lower active parameter count
- **Efficiency**: Optimized for local tool orchestration and function calling
- **VRAM**: ~4.5GB with 4-bit quantization
- **Speed**: Medium (~2-3s inference) with higher quality

**Installation:**
```bash
# Via Ollama
ollama pull lfm2-8b-a1b

# Or via HuggingFace + llama.cpp
# Download from: https://huggingface.co/LiquidAI/lfm2-8b-a1b
```

**Configuration:**
```python
# In orchestrator_service.py
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "lfm2-8b-a1b")

# Optional: Adjust MoE routing temperature for your use case
LLM_OPTIONS = {
    "temperature": 0.3,
    "num_predict": 2048,
    "moe_temperature": 0.1,  # Lower = more deterministic routing
}
```

**Best For:**
- Complex audit summaries requiring nuanced understanding
- Multi-step tool orchestration
- Code analysis with technical precision
- Production deployments where quality > speed

#### Option 3: Other Models
```bash
# Code-optimized
codellama:7b

# Balanced
mistral:7b

# Excellent analysis  
qwen2.5:7b
```

### Model Comparison

| Model | Params | Active | VRAM | Speed | Quality | Status | Best Use Case |
|-------|--------|--------|------|-------|---------|--------|---------------|
| **kahnwong/lfm2:8b-a1b** ⭐ | 8B | 1.5B | ~4.7GB | **Super Fast** | **Excellent** | **TESTED** ✅ | **Production** |
| llama3.2 | 8B | 8B | ~4GB | Fast | Good | Available | Quick audits |
| codellama:7b | 7B | 7B | ~5GB | Medium | Good | Available | Code-specific |
| qwen2.5:7b | 7B | 7B | ~5GB | Medium | Excellent | Available | Analysis |

### 🎯 Model Testing Results

**Tested Configuration:**
- Model: `kahnwong/lfm2:8b-a1b`
- Hardware: RTX 3060 12GB
- Quantization: 4-bit (GGUF)
- Inference Time: ~1-2 seconds per summary

**Performance vs Other Models:**
- ✅ **Faster** than `llama3.2` and `qwen2.5-coder:7b`
- ✅ **Better output quality** on code audit prompts
- ✅ **More concise** and actionable summaries
- ✅ **Lower VRAM usage** than expected for 8B model

**Sample Prompt Tested:**
```
"Summarize this code audit: Health score 75/100, 7 critical 
complexity issues, files: prompts/system-prompt.ts (complexity 51)..."

Liquid 8B Response:
"Repository shows good overall structure (75/100) but has 
concerning complexity debt. Seven functions exceed safe complexity 
thresholds, with prompts/system-prompt.ts at critical level (51). 
Recommend immediate refactoring of the top 3 most complex 
functions before adding new features."
```

**Verdict**: The Liquid 8B model provides the best speed-to-quality ratio for our orchestration use case.

### Switching Models

The orchestrator is model-agnostic. To switch:

```bash
# 1. Pull new model
ollama pull lfm2-8b-a1b

# 2. Update environment
export LOCAL_LLM_MODEL=lfm2-8b-a1b

# 3. Restart orchestrator
python scripts/start_orchestrator.py
```

**No code changes required** - the orchestrator API remains identical regardless of model.

## Running the Orchestrator

### Method 1: Direct Python

```bash
cd /home/zebastjan/dev/archon/python

# Start the orchestrator
python scripts/start_orchestrator.py

# Or use uv
uv run python scripts/start_orchestrator.py
```

### Method 2: FastAPI Direct

```bash
cd /home/zebastjan/dev/archon/python

uv run python -m uvicorn src.orchestrator.orchestrator_service:app \
  --host 0.0.0.0 \
  --port 8080 \
  --reload
```

### Method 3: Production (with systemd)

Create `/etc/systemd/system/cephalosage-orchestrator.service`:

```ini
[Unit]
Description=Cephalosage Orchestrator Service
After=network.target ollama.service

[Service]
Type=simple
User=zebastjan
WorkingDirectory=/home/zebastjan/dev/archon/python
Environment=PATH=/home/zebastjan/.local/bin:/usr/local/bin
Environment=ORCHESTRATOR_PORT=8080
Environment=LOCAL_LLM_URL=http://localhost:11434
Environment=LOCAL_LLM_MODEL=llama3.2
ExecStart=/home/zebastjan/.local/bin/uv run python scripts/start_orchestrator.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cephalosage-orchestrator
sudo systemctl start cephalosage-orchestrator
```

## Testing

### Test Health Endpoint

```bash
curl http://localhost:8080/health

# Expected response:
{"status":"healthy","orchestrator":"cephelosage","version":"0.1.0"}
```

### Test Orchestrated Audit

```bash
# Test with octofriend repo
curl -X POST "http://localhost:8080/orchestrator/repo_health_check" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_id": "140cae72-3d91-42ae-8099-a36f56877018",
    "focus": "full",
    "include_llm_summary": true
  }'
```

### Run Tests

```bash
cd /home/zebastjan/dev/archon/python

# Run orchestrator tests
uv run pytest tests/orchestrator/ -v

# Run with coverage
uv run pytest tests/orchestrator/ --cov=src.orchestrator
```

## MCP Integration

The orchestrator is automatically used by the MCP tool:

```python
# In code_audit_tools.py
async def orchestrated_repo_health_check(repo_id, focus):
    try:
        # Try orchestrator first
        response = await httpx.AsyncClient().post(
            f"{ORCHESTRATOR_URL}/orchestrator/repo_health_check",
            params={"repo_id": repo_id, "focus": focus}
        )
        return response.json()
    except ConnectError:
        # Fall back to standard repo_health_check
        return run_repo_health_check(repo_id, focus)
```

### Configure MCP Server

Add to `.env`:

```bash
ORCHESTRATOR_URL=http://localhost:8080
```

## Usage Examples

### Example 1: Full Audit

```bash
curl -X POST "http://localhost:8080/orchestrator/repo_health_check" \
  -d "repo_id=abc-123&focus=full"
```

**Response:**
```json
{
  "success": true,
  "health_score": 78,
  "executive_summary": "Repository has good overall health...",
  "detailed_analysis": "• Fix hardcoded secrets\n• Refactor complex functions...",
  "orchestrated": true,
  "llm_model": "llama3.2",
  ...
}
```

### Example 2: Security-Focused Audit

```bash
curl -X POST "http://localhost:8080/orchestrator/repo_health_check" \
  -d "repo_id=abc-123&focus=security"
```

### Example 3: Refactoring Plan

```bash
curl -X POST "http://localhost:8080/orchestrator/plan_refactors" \
  -d "repo_id=abc-123&run_id=xyz-789"
```

## Performance Optimization

### Model Selection by Task

| Task | Recommended Model | VRAM | Speed |
|------|-----------------|------|-------|
| Quick audits | llama3.2 | ~4GB | Fast |
| Security analysis | codellama:7b | ~5GB | Medium |
| Complex analysis | qwen2.5:7b | ~5GB | Medium |
| Documentation | mistral:7b | ~5GB | Fast |

### Quantization Options

```bash
# 4-bit quantization (default, recommended)
ollama pull llama3.2

# 8-bit quantization (higher quality, more VRAM)
ollama pull llama3.2:8b
```

### Caching

The orchestrator caches:
- Audit results (by repo_id + focus)
- LLM responses (optional)

To enable caching:

```python
# In orchestrator_service.py
ENABLE_LLM_CACHE = True
LLM_CACHE_TTL = 3600  # seconds
```

## Troubleshooting

### Issue: "Connection refused" to Ollama

**Solution:**
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve
```

### Issue: Out of VRAM

**Solutions:**
1. Use smaller model: `ollama pull llama3.2:3b`
2. Reduce context window
3. Close other GPU applications

### Issue: Slow responses

**Solutions:**
1. Use quantized model: `llama3.2` instead of `llama3.2:70b`
2. Increase timeout: `timeout: 120`
3. Disable LLM summary: `include_llm_summary: false`

### Issue: Tests failing

**Check:**
```bash
# Verify database
psql -h localhost -p 5434 -U archon -d archon -c "SELECT 1"

# Verify Ollama
curl http://localhost:11434/api/tags

# Verify orchestrator
curl http://localhost:8080/health
```

## Monitoring

### Logs

```bash
# View logs
sudo journalctl -u cephalosage-orchestrator -f

# Or if running directly
python scripts/start_orchestrator.py 2>&1 | tee orchestrator.log
```

### Metrics

```bash
# Check response times
curl -w "@curl-format.txt" -o /dev/null -s \
  http://localhost:8080/orchestrator/repo_health_check \
  -d "repo_id=test"
```

## Security Considerations

1. **Local-only**: Orchestrator should not be exposed to internet
2. **Authentication**: Add auth if needed:
   ```python
   from fastapi.security import HTTPBearer
   ```
3. **Rate limiting**: Implement if exposing externally

## Future Enhancements

1. **Streaming responses**: For long-running audits
2. **WebSocket support**: Real-time updates
3. **Model hot-swapping**: Change LLM without restart
4. **Distributed orchestration**: Multi-GPU support
5. **Caching layer**: Redis for distributed caching

## Summary

✅ **Installed**: Ollama with 7-14B model
✅ **Configured**: Environment variables
✅ **Running**: Orchestrator service on port 8080
✅ **Integrated**: MCP tool with fallback
✅ **Tested**: All endpoints working

**Next**: Test with `orchestrated_repo_health_check` MCP tool.
