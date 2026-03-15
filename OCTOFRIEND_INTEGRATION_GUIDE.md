# OctoFriend Integration Guide

## Overview

This guide explains how to integrate the Cephalosage Orchestrator and MCP Server into your OctoFriend setup for intelligent code auditing.

## Quick Start

### 1. Clone and Setup

```bash
# Clone Archon repository
git clone https://github.com/archon/archon.git
cd archon

# Setup Python environment
cd python
uv sync --all-extras
```

### 2. Configure Database

```bash
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Run migrations
PGPASSWORD=archon_local_dev psql -h localhost -p 5434 -U archon -d archon -f migration/complete_setup.sql
PGPASSWORD=archon_local_dev psql -h localhost -p 5434 -U archon -d archon -f migration/015_add_metrics_and_audit_tables.sql
PGPASSWORD=archon_local_dev psql -h localhost -p 5434 -U archon -d archon -f migration/016_expand_audit_rules_and_methodology.sql
```

### 3. Install Ollama and Pull Model

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull recommended model
ollama pull llama3.2

# Or pull Liquid 8B (recommended for production)
ollama pull lfm2-8b-a1b
```

### 4. Start Services

```bash
# Terminal 1: Start Ollama
