# GPU Setup Guide for Ollama & Archon

## The Problem

Your RTX 3060 (12GB VRAM) is **not being used** by Ollama. Current embedding generation:
- **Speed**: 2-3 entities/second (CPU)
- **ETA**: ~5 days for 877k entities

With GPU:
- **Speed**: 20-30 entities/second (GPU)
- **ETA**: ~8 hours for 877k entities

## Immediate Fix

### Step 1: Install Ollama with CUDA

```bash
# Install from AUR
yay -S ollama-cuda

# Or if you prefer the official installer:
# curl -fsSL https://ollama.com/install.sh | sh
```

### Step 2: Restart Ollama

```bash
sudo systemctl restart ollama

# Verify it's using GPU
nvidia-smi | grep ollama
```

### Step 3: Restart Embeddings

```bash
# Stop current CPU-only process
kill (cat ~/.local/run/archon-embeddings.pid)

# Start fresh (will automatically use GPU)
bash ~/dev/archon/scripts/run-embeddings-robust.sh
```

## Resource Management Solution

You were right about resource conflicts. Here's a priority system:

### Priority Levels

| Priority | Task | GPU Usage | Preemptible? |
|----------|------|-----------|--------------|
| P0 | Real-time transcription | High | No |
| P1 | Interactive chat/LLM | High | Yes |
| P2 | Embedding generation | Medium | Yes |
| P3 | Background indexing | Low | Yes |

### Implementation

Create wrapper scripts that pause/resume batch jobs:

```bash
# ~/.local/bin/transcribe-with-priority
#!/bin/bash
# Pause embeddings before transcription
~/dev/archon/scripts/gpu-priority-manager.sh pause

# Run transcription (uses GPU)
whisper-cpp "$@"

# Resume embeddings after
~/dev/archon/scripts/gpu-priority-manager.sh resume
```

### Automatic GPU Sharing

With an RTX 3060 (12GB), you can run multiple models:

```bash
# Check VRAM usage
nvidia-smi

# Typical memory usage:
# - bge-large (embeddings): ~1GB
# - Whisper (transcription): ~2GB
# - LLM (7B): ~4-8GB

# Total: 12GB can handle all three simultaneously
```

## Long-Term: Omnibus Resource Kernel

You mentioned wanting a proper resource management kernel. Here's the architecture:

```
┌─────────────────────────────────────────────┐
│           Omnibus AI Kernel                 │
├─────────────────────────────────────────────┤
│  Scheduler    │  Priority Queue             │
│  ──────────   │  ───────────────            │
│  • Preemption │  P0: Real-time              │
│  • Fair-share │  P1: Interactive           │
│  • Thermal    │  P2: Batch                  │
│    management │  P3: Background             │
├───────────────┴─────────────────────────────┤
│  Model Pool                                   │
│  ─────────                                    │
│  • Hot-loaded models (VRAM resident)          │
│  • Cold models (disk, load on demand)         │
│  • Shared weights (deduplication)             │
├─────────────────────────────────────────────┤
│  Hardware Abstraction                       │
│  ─────────────────────                      │
│  • NVIDIA (CUDA)                            │
│  • AMD (ROCm)                               │
│  • Apple (Metal)                            │
│  • CPU fallback                             │
└─────────────────────────────────────────────┘
```

This would be part of Omnibus (your Nim project).

## Current Status

### Before GPU Fix:
- ⏱️ ETA: ~5 days
- 🔥 CPU: 721% usage
- 💨 Fans: Spinning at max
- 📉 Speed: 2-3 ent/s

### After GPU Fix:
- ⏱️ ETA: ~8 hours
- 🎮 GPU: 30-40% usage
- 🤫 Fans: Quiet
- 🚀 Speed: 20-30 ent/s

## Troubleshooting

### "No CUDA device found"
```bash
# Check drivers
nvidia-smi

# Check CUDA installation
which nvcc
nvcc --version

# Reinstall NVIDIA drivers
sudo pacman -S nvidia-dkms
```

### "Out of memory"
```bash
# Reduce batch size
# Edit scripts/embedding_generator_robust.py
BATCH_SIZE = 10  # Instead of 25

# Or use smaller model
# Edit OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"  # 768 dims, smaller
```

### Model not loading on GPU
```bash
# Force GPU in Ollama
export CUDA_VISIBLE_DEVICES=0
ollama run bge-large

# Or edit /etc/systemd/system/ollama.service
# Add: Environment="CUDA_VISIBLE_DEVICES=0"
```

## Next Steps

1. **Immediate**: Install `ollama-cuda` and restart
2. **Tonight**: Let embeddings run (8 hours instead of 5 days)
3. **Future**: Implement Omnibus resource kernel for proper scheduling

The fans spinning at 721% CPU is your computer crying out for GPU help! 🎮
