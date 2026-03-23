#!/bin/bash
# Configure Ollama to be accessible from Docker containers
# This binds Ollama to localhost (127.0.0.1) and the Docker bridge (172.17.0.1)
# so it's accessible from the host AND from Docker containers, but NOT from the network

echo "Configuring Ollama for Docker access..."

# Create systemd override directory
sudo mkdir -p /etc/systemd/system/ollama.service.d/

# Create override file
cat << 'EOF' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
[Service]
# Bind to localhost AND Docker bridge IP
# 127.0.0.1:11434 for local access
# 172.17.0.1:11434 for Docker container access
Environment="OLLAMA_HOST=127.0.0.1:11434,172.17.0.1:11434"
EOF

# Reload systemd
sudo systemctl daemon-reload

# Restart Ollama
sudo systemctl restart ollama

echo "✓ Ollama configured to accept connections from:"
echo "  - localhost:11434 (host local)"
echo "  - 172.17.0.1:11434 (Docker containers)"
echo ""
echo "Testing connection from Docker container..."

# Test from container
docker exec archon curl -s http://172.17.0.1:11434/api/tags 2>&1 | head -5

if [ $? -eq 0 ]; then
    echo "✓ Success! Docker container can reach Ollama"
else
    echo "✗ Failed to connect from container"
    echo "Make sure Ollama is running: systemctl status ollama"
fi