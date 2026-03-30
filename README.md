<p align="center">
  <img src="./archon-ui-main/public/archon-main-graphic.png" alt="Archon Main Graphic" width="853" height="422">
</p>

<p align="center">
   <a href="https://trendshift.io/repositories/13964" target="_blank"><img src="https://trendshift.io/api/badge/repositories/13964" alt="coleam00%2FArchon | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</p>

<p align="center">
  <em>Power up your AI coding assistants with your own custom knowledge base and task management as an MCP server</em>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#upgrading">Upgrading</a> •
  <a href="#whats-included">What's Included</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#troubleshooting">Troubleshooting</a>
</p>

---

## 🎯 What is Archon?

> Archon is currently in beta! Expect things to not work 100%, and please feel free to share any feedback and contribute with fixes/new features! Thank you to everyone for all the excitement we have for Archon already, as well as the bug reports, PRs, and discussions. It's a lot for our small team to get through but we're committed to addressing everything and making Archon into the best tool it possibly can be!

Archon is the **command center** for AI coding assistants. For you, it's a sleek interface to manage knowledge, context, and tasks for your projects. For the AI coding assistant(s), it's a **Model Context Protocol (MCP) server** to collaborate on and leverage the same knowledge, context, and tasks. Connect Claude Code, Kiro, Cursor, Windsurf, etc. to give your AI agents access to:

- **Your documentation** (local files: Markdown, PDFs, Word docs, and more)
- **Smart search capabilities** with advanced RAG strategies
- **Task management** integrated with your knowledge base
- **Real-time updates** as you add new content and collaborate with your coding assistant on tasks
- **Much more** coming soon to build Archon into an integrated environment for all context engineering

This new vision for Archon replaces the old one (the agenteer). Archon used to be the AI agent that builds other agents, and now you can use Archon to do that and more.

> It doesn't matter what you're building or if it's a new/existing codebase - Archon's knowledge and task management capabilities will improve the output of **any** AI driven coding.

## 🔗 Important Links

- **[GitHub Discussions](https://github.com/coleam00/Archon/discussions)** - Join the conversation and share ideas about Archon
- **[Contributing Guide](CONTRIBUTING.md)** - How to get involved and contribute to Archon
- **[Introduction Video](https://youtu.be/8pRc_s2VQIo)** - Getting started guide and vision for Archon
- **[Archon Kanban Board](https://github.com/users/coleam00/projects/1)** - Where maintainers are managing issues/features
- **[Dynamous AI Mastery](https://dynamous.ai)** - The birthplace of Archon - come join a vibrant community of other early AI adopters all helping each other transform their careers and businesses!

## Quick Start

<p align="center">
  <a href="https://youtu.be/DMXyDpnzNpY">
    <img src="https://img.youtube.com/vi/DMXyDpnzNpY/maxresdefault.jpg" alt="Archon Setup Tutorial" width="640" />
  </a>
  <br/>
  <em>📺 Click to watch the setup tutorial on YouTube</em>
  <br/>
  <a href="./archon-example-workflow">-> Example AI coding workflow in the video <-</a>
</p>

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Node.js 18+](https://nodejs.org/) (for hybrid development mode)
- [Supabase](https://supabase.com/) account (free tier or local Supabase both work)
- [OpenAI API key](https://platform.openai.com/api-keys) (Gemini and Ollama are supported too!)
- (OPTIONAL) [Make](https://www.gnu.org/software/make/) (see [Installing Make](#installing-make) below)

### Setup Instructions

1. **Clone Repository**:
   ```bash
   git clone -b stable https://github.com/coleam00/archon.git
   ```
   ```bash
   cd archon
   ```
   
   **Note:** The `stable` branch is recommended for using Archon. If you want to contribute or try the latest features, use the `main` branch with `git clone https://github.com/coleam00/archon.git`
2. **Environment Configuration**:

   ```bash
   cp .env.example .env
   # Edit .env and add your Supabase credentials:
   # SUPABASE_URL=https://your-project.supabase.co
   # SUPABASE_SERVICE_KEY=your-service-key-here
   ```

   IMPORTANT NOTES:
   - For cloud Supabase: They recently introduced a new type of service role key but use the legacy one (the longer one).
   - For local Supabase: Set `SUPABASE_URL` to http://host.docker.internal:8000 (unless you have an IP address set up). To get `SUPABASE_SERVICE_KEY` run `supabase status -o env`.

3. **Database Setup**: Run the database migrations (PostgreSQL)

4. **Start Services** (choose one):

   **Full Docker Mode (Recommended for Normal Archon Usage)**

   ```bash
   docker compose up --build -d
   ```

   This starts Archon in single-container mode:
   - **Server**: Core API, MCP tools, and embedded PostgreSQL (Port: 8181)

   Ports are configurable in your .env as well!

5. **Configure API Keys**:
   - Open http://localhost:3737
   - You'll automatically be brought through an onboarding flow to set your API key (OpenAI is default)

## ⚡ Quick Test

Once everything is running:

1. **Test Document Upload**: Go to http://localhost:3737 → Knowledge Base → Upload a document (Markdown, PDF, Word, etc.)
2. **Test Projects**: Projects → Create a new project and add tasks
3. **Integrate with your AI coding assistant**: MCP Dashboard → Copy connection config for your AI coding assistant 

## Installing Make

<details>
<summary><strong>🛠️ Make installation (OPTIONAL - For Dev Workflows)</strong></summary>

### Windows

```bash
# Option 1: Using Chocolatey
choco install make

# Option 2: Using Scoop
scoop install make

# Option 3: Using WSL2
wsl --install
# Then in WSL: sudo apt-get install make
```

### macOS

```bash
# Make comes pre-installed on macOS
# If needed: brew install make
```

### Linux

```bash
# Debian/Ubuntu
sudo apt-get install make

# RHEL/CentOS/Fedora
sudo yum install make
```

</details>

<details>
<summary><strong>🚀 Quick Command Reference for Make</strong></summary>
<br/>

| Command           | Description                                             |
| ----------------- | ------------------------------------------------------- |
| `make dev`        | Start hybrid dev (backend in Docker, frontend local) ⭐ |
| `make dev-docker` | Everything in Docker                                    |
| `make stop`       | Stop all services                                       |
| `make test`       | Run all tests                                           |
| `make lint`       | Run linters                                             |
| `make install`    | Install dependencies                                    |
| `make check`      | Check environment setup                                 |
| `make clean`      | Remove containers and volumes (with confirmation)       |

</details>

## 🔄 Database Reset (Start Fresh if Needed)

If you need to completely reset your database and start fresh:

<details>
<summary>⚠️ <strong>Reset Database - This will delete ALL data for Archon!</strong></summary>

1. **Run Reset Script**: In your Supabase SQL Editor, run the contents of `migration/RESET_DB.sql`

   ⚠️ WARNING: This will delete all Archon specific tables and data! Nothing else will be touched in your DB though.

2. **Rebuild Database**: After reset, run `migration/complete_setup.sql` to create all the tables again.

3. **Restart Services**:

   ```bash
   docker compose --profile full up -d
   ```

4. **Reconfigure**:
   - Select your LLM/embedding provider and set the API key again
   - Re-upload any documents

The reset script safely removes all tables, functions, triggers, and policies with proper dependency handling.

</details>

## 📚 Documentation

### Core Services

| Service                    | Container Name             | Default URL           | Purpose                                    |
| -------------------------- | -------------------------- | --------------------- | ------------------------------------------ |
| **Web Interface**          | archon                     | http://localhost:3737 | Main dashboard and controls                |
| **API Server**             | archon                     | http://localhost:8181 | API, MCP tools, and embedded PostgreSQL    |  

## Upgrading

To upgrade Archon to the latest version:

1. **Pull latest changes**:
   ```bash
   git pull
   ```

2. **Rebuild and restart containers**:
   ```bash
   docker compose up -d --build
   ```
   This starts Archon in single-container mode with embedded PostgreSQL.

3. **Check for database migrations**:
   - Run the SQL migration scripts in your database.

## What's Included

### 🧠 Knowledge Management

- **Local Document Processing**: Upload and process PDFs, Word docs, markdown files, RST, ODT, and text documents with intelligent chunking using Dockling
- **Code Example Extraction**: Automatically identifies and indexes code examples from documentation for enhanced search
- **Vector Search**: Advanced semantic search with contextual embeddings for precise knowledge retrieval
- **Source Management**: Organize knowledge by source, type, and tags for easy filtering

### 🤖 AI Integration

- **Model Context Protocol (MCP)**: Connect any MCP-compatible client (Claude Code, Cursor, even non-AI coding assistants like Claude Desktop)
- **MCP Tools**: Comprehensive yet simple set of tools for RAG queries, task management, and project operations
- **Multi-LLM Support**: Works with OpenAI, Ollama, and Google Gemini models
- **RAG Strategies**: Hybrid search, contextual embeddings, and result reranking for optimal AI responses
- **Real-time Streaming**: Live responses from AI agents with progress tracking

### 📋 Project & Task Management

- **Hierarchical Projects**: Organize work with projects, features, and tasks in a structured workflow
- **AI-Assisted Creation**: Generate project requirements and tasks using integrated AI agents
- **Document Management**: Version-controlled documents with collaborative editing capabilities
- **Progress Tracking**: Real-time updates and status management across all project activities

### 🔄 Real-time Collaboration

- **WebSocket Updates**: Live progress tracking for document processing and AI operations
- **Multi-user Support**: Collaborative knowledge building and project management
- **Background Processing**: Asynchronous operations that don't block the user interface
- **Health Monitoring**: Built-in service health checks and automatic reconnection

## Architecture

### Single-Container Architecture

Archon uses a single-container architecture with embedded PostgreSQL:

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Container                     │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Archon Server (port 8181)          │   │
│  │                                                 │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │   │
│  │  │  FastAPI    │  │  MCP Server │  │  Pydantic│ │   │
│  │  │  (API)      │  │  (stdio)    │  │  Agents │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
│                          │                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              PostgreSQL (embedded)              │   │
│  │              - App data, code entities          │   │
│  │              - Knowledge base, vectors          │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### MCP Access

MCP tools are accessed via **stdio transport** (not network):

```bash
docker exec -i archon python -m src.mcp_server.mcp_server_stdio
```

All IDEs (Windsurf, ClaudeCode, OctoFriend, OpenCode) use this pattern.

### Service Responsibilities

| Component              | Location                       | Purpose                          |
| ---------------------- | ------------------------------ | -------------------------------- |
| **Frontend**           | `archon-ui-main/`              | Web interface and dashboard      |
| **Server**             | `python/src/server/`           | Core APIs, MCP tools, agents     |
| **MCP Server**         | `python/src/mcp_server/`       | MCP protocol (stdio transport)   |
| **Database**           | Embedded in container          | PostgreSQL + pgvector            |

### Communication Patterns

- **HTTP**: API requests to port 8181
- **Socket.IO**: Real-time updates from Server to Frontend
- **MCP Protocol**: AI clients connect via stdio (docker exec)
- **Direct Imports**: All components run in same process

### Key Architectural Benefits

- **Simple Deployment**: Single container to manage
- **Lower Overhead**: No inter-service HTTP calls
- **Easier Debugging**: Single log stream, one stack trace
- **Direct Imports**: Full type safety, no serialization
- **Local-First**: Designed for local development and use

## 🔧 Configuring Custom Ports & Hostname

By default, Archon runs on the following ports:

- **archon (UI + API)**: 8181 (API), 3737 (UI - if enabled)
- **Database**: Embedded in container (no external port)

### Changing Ports

To use custom ports, add these variables to your `.env` file:

```bash
# Service Ports Configuration
ARCHON_SERVER_PORT=8181
```

### Configuring Hostname

By default, Archon uses `localhost` as the hostname. You can configure a custom hostname or IP address by setting the `HOST` variable in your `.env` file:

```bash
# Hostname Configuration
HOST=localhost  # Default

# Examples of custom hostnames:
HOST=192.168.1.100     # Use specific IP address
HOST=archon.local      # Use custom domain
```

This is useful when:
- Running Archon on a different machine and accessing it remotely
- Using a custom domain name for your installation
- Deploying in a network environment where `localhost` isn't accessible

After changing hostname or ports:

1. Restart Docker containers: `docker compose down && docker compose up -d`
2. Access the API at: `http://${HOST}:${ARCHON_SERVER_PORT}`

## 🔧 Development

### Quick Start

```bash
# Install dependencies
make install

# Start development (recommended)
make dev        # Backend in Docker, frontend local with hot reload

# Alternative: Everything in Docker
make dev-docker # All services in Docker

# Stop everything (local FE needs to be stopped manually)
make stop
```

### Development Modes

#### Hybrid Mode (Recommended) - `make dev`

Best for active development with instant frontend updates:

- Backend services run in Docker (isolated, consistent)
- Frontend runs locally with hot module replacement
- Instant UI updates without Docker rebuilds

#### Full Docker Mode - `make dev-docker`

For all services in Docker environment:

- All services run in Docker containers
- Better for integration testing
- Slower frontend updates

### Testing & Code Quality

```bash
# Run tests
make test       # Run all tests
make test-fe    # Run frontend tests
make test-be    # Run backend tests

# Run linters
make lint       # Lint all code
make lint-fe    # Lint frontend code
make lint-be    # Lint backend code

# Check environment
make check      # Verify environment setup

# Clean up
make clean      # Remove containers and volumes (asks for confirmation)
```

### Viewing Logs

```bash
# View logs using Docker Compose directly
docker compose logs -f              # All services
docker compose logs -f archon-server # API server
docker compose logs -f archon-mcp    # MCP server
docker compose logs -f archon-ui     # Frontend
```

**Note**: The backend services are configured with `--reload` flag in their uvicorn commands and have source code mounted as volumes for automatic hot reloading when you make changes.

## Troubleshooting

### Common Issues and Solutions

#### Port Conflicts

If you see "Port already in use" errors:

```bash
# Check what's using a port (e.g., 3737)
lsof -i :3737

# Stop all containers and local services
make stop

# Change the port in .env
```

#### Docker Permission Issues (Linux)

If you encounter permission errors with Docker:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in, or run
newgrp docker
```

#### Windows-Specific Issues

- **Make not found**: Install Make via Chocolatey, Scoop, or WSL2 (see [Installing Make](#installing-make))
- **Line ending issues**: Configure Git to use LF endings:
  ```bash
  git config --global core.autocrlf false
  ```

#### Frontend Can't Connect to Backend

- Check backend is running: `curl http://localhost:8181/health`
- Verify port configuration in `.env`
- For custom ports, ensure both `ARCHON_SERVER_PORT` and `VITE_ARCHON_SERVER_PORT` are set

#### Docker Compose Hangs

If `docker compose` commands hang:

```bash
# Reset Docker Compose
docker compose down --remove-orphans
docker system prune -f

# Restart Docker Desktop (if applicable)
```

#### Hot Reload Not Working

- **Frontend**: Ensure you're running in hybrid mode (`make dev`) for best HMR experience
- **Backend**: Check that volumes are mounted correctly in `docker-compose.yml`
- **File permissions**: On some systems, mounted volumes may have permission issues

## 📈 Progress

<p align="center">
  <a href="https://star-history.com/#coleam00/Archon&Date">
    <img src="https://api.star-history.com/svg?repos=coleam00/Archon&type=Date" width="500" alt="Star History Chart">
  </a>
</p>

## 📄 License

Archon Community License (ACL) v1.2 - see [LICENSE](LICENSE) file for details.

**TL;DR**: Archon is free, open, and hackable. Run it, fork it, share it - just don't sell it as-a-service without permission.
# Test
# Test commit for git hook verification
