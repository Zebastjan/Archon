# Code Intelligence System Recovery Plan

## Current State
- **Entities**: 888,536 extracted ✅
- **Relationships**: 855k+ built ✅
- **Embeddings**: 4,509 (0.5%) ❌ CRITICAL
- **Ollama**: Running with bge-large ✅
- **Last Sync**: March 18 (3+ days stale)

## Immediate Actions Required

### 1. Complete Embedding Generation (START NOW)
```bash
cd /home/zebastjan/dev/archon
screen -S embeddings -dm bash -c '. python/.venv/bin/activate && python scripts/generate_embeddings.py --batch-size 50'
```
**ETA**: 2-4 hours running in background

### 2. Install Git Hooks
```bash
for repo in ~/dev/{archon,syllablaze,octofriend,Omnibus}; do
  cd $repo && ~/dev/archon/scripts/setup_git_hooks.sh
done
```

### 3. Fix Nim Support for Omnibus
```bash
cd ~/dev/archon
. python/.venv/bin/activate
python -c "from src.server.services.code_entity_extraction_service import CodeEntityExtractionService; import asyncio; asyncio.run(CodeEntityExtractionService().extract_and_store_entities('15f7ea16-d016-492b-8193-dbbd55f33281', '/home/zebastjan/dev/Omnibus'))"
```

## Verification
Run `python scripts/code_health_check.py` to verify all checks pass.
