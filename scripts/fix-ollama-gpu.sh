#!/bin/bash
# Fix Ollama to use GPU on Arch Linux

echo "═══════════════════════════════════════════════════════════════════"
echo "  Ollama GPU Setup"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check GPU
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found - NVIDIA drivers not installed?"
    exit 1
fi

echo "GPU detected:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo ""

# Check if Ollama has CUDA support
if ls /usr/lib/ollama/libcudart* 2>/dev/null | grep -q .; then
    echo "✓ Ollama appears to have CUDA libraries"
else
    echo "⚠️  Ollama appears to be CPU-only"
    echo ""
    echo "To fix this on Arch Linux, you have options:"
    echo ""
    echo "Option 1: Install ollama-cuda from AUR (RECOMMENDED)"
    echo "  yay -S ollama-cuda"
    echo "  sudo systemctl restart ollama"
    echo ""
    echo "Option 2: Use official Ollama installer with CUDA"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo "  # Then edit /etc/systemd/system/ollama.service to add CUDA"
    echo ""
    echo "Option 3: Use Docker with GPU support"
    echo "  docker run -d --gpus=all -p 11434:11434 ollama/ollama"
    echo ""
fi

echo "Current Ollama version:"
ollama --version
echo ""

# Check which runner is being used
if ps aux | grep -q "ollama.*runner"; then
    echo "Ollama is running. Checking if using GPU..."
    if nvidia-smi | grep -q "ollama"; then
        echo "✓ Ollama IS using GPU"
    else
        echo "⚠️  Ollama is NOT using GPU (CPU only)"
        echo ""
        echo "Embedding speed: ~2-3 entities/second (CPU)"
        echo "With GPU: ~20-30 entities/second expected"
        echo ""
        echo "Recommendation: Install ollama-cuda"
        echo "  yay -S ollama-cuda"
        echo "  sudo systemctl restart ollama"
    fi
else
    echo "Ollama is not currently running"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
