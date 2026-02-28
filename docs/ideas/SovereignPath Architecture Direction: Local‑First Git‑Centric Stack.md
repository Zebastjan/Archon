## SovereignPath Architecture Direction: Local‑First Git‑Centric Stack

### High‑level stance

SovereignPath/Archon is **local‑first and Git‑centric by design**. Cloud services (Neon, Supabase, managed vector DBs, etc.) are optional adapters—not foundational dependencies.

Core goals:

- Digital sovereignty: everything fundamental runs locally or on infra the user controls.  
- Git as the primary source of truth for projects and history.  
- A small, robust local DB as a queryable mirror of that history and the knowledge graph.  
- IPFS as the “infrastructure substrate” for large, shared artifacts (not a cloud DB).

***

## 1. Core data stack

### 1.1 Default database: Postgres in the Archon container

- Ship **PostgreSQL** as the default DB, running *inside* the Archon Docker container.  
- Use Postgres for:  
  - Project/agent metadata.  
  - Git‑aware project state (commits, branches, project states).  
  - Knowledge base metadata and vector indices.  
- Rely on **pgvector** (or equivalent) for vector search.

Rationale:

- Strong concurrency and robustness, even for a “single user with many agents.”  
- Direct compatibility with Neon/Supabase if users choose to connect to them.  
- Mature ecosystem for migrations, admin, and tooling.

SQLite is *not* the primary target:

- It’s viable for niche, single‑user setups, but concurrency, vector extensions, and compatibility constraints make it a weaker default.  
- We can support it later behind the same abstraction, but we shouldn’t optimize the architecture around it.

### 1.2 Optional backends via `db_connector`

Introduce a thin `db_connector` abstraction that:

- Standardizes operations like:  
  - Open connection  
  - Run migrations  
  - Vector search  
  - Basic CRUD for core Archon entities  
- Supports Postgres as the primary implementation.  
- Optionally adds adapters for:  
  - Neon (serverless Postgres)  
  - Supabase (Postgres + additional platform features)  
  - Weaviate or other vector stores (for users who insist on external vector infra)

These are **opt‑in**, never required for local use.

***

## 2. Git‑aware metadata model

### 2.1 Git as the canonical project timeline

Git remains the **source of truth** for:

- Code  
- Prompts  
- Agent graph definitions  
- Migrations and DB config  
- Project‑level configs

Archon does **not** try to version entire DB files with Git. Instead, it **models Git inside the DB**.

### 2.2 Git metadata inside Postgres

Add a Git‑aware schema along these lines:

- `repos`  
  - Local path, unique ID, etc.

- `git_commits`  
  - `id` (PK)  
  - `repo_id`  
  - `sha`  
  - `branch_name`  
  - `author`, `message`, `timestamp`

- `project_states`  
  - `id`  
  - `repo_id`  
  - `git_commit_id` (FK)  
  - Serialized/projected metadata for that commit (active tools, KB wiring, DB settings, etc.)

- `agent_runs`  
  - `id`  
  - `repo_id`  
  - `git_commit_id` (FK)  
  - `branch_name`  
  - Purpose, outcome, artifacts, etc.

- `kb_datasets` / `kb_dataset_versions`  
  - Dataset identity and versions.  
  - Links to Git commits for project‑owned docs.  
  - Links to IPFS CIDs / external URIs for large corpora.

Behavior:

- Archon watches Git events (branch checkout, commit) and records/update entries in these tables.  
- Agents can query “what was the state of this project at commit X on branch Y?” via the DB.  
- The DB becomes a **queryable history mirror** keyed to Git, not an independent timeline.

### 2.3 No DB time travel; DB is append‑only history

- We **don’t** roll the DB forward/back like Git.  
- Instead, we append new rows tied to new commits/branches.  
- Rollbacks and branch switches happen in Git; Archon uses Git’s SHA/branch to select the relevant rows in Postgres.

This avoids snapshot complexity and keeps the DB simple and robust.

***

## 3. Knowledge base architecture

### 3.1 Metadata in DB, content in files/IPFS

Design the KB around three layers:

1. **Metadata and indices (in Postgres):**  
   - Which datasets exist.  
   - Which version is in use.  
   - Chunk IDs, embeddings, pointers to content (paths, URLs, IPFS CIDs).  

2. **Core project content (in Git):**  
   - Project code and documentation.  
   - Small, text‑based knowledge assets.  

3. **External/heavy content (in filesystem/IPFS):**  
   - Web‑collected resources.  
   - Large PDFs, codebases, logs, artifacts.

The DB indexes content; it does **not** store large blobs.

### 3.2 IPFS as the “infrastructure” layer

For large or shared assets:

- Store content in **IPFS** (local node + optional pinning service).  
- Store IPFS CIDs and metadata in Postgres.  
- Optionally use existing **Git↔IPFS integration** (e.g., git‑remote‑ipfs) so repos or artifacts can be backed by IPFS if desired.

Benefits:

- Durable, content‑addressed storage.  
- Users can choose their own pinning provider or run their own node.  
- No dependency on proprietary cloud blob storage.

***

## 4. Rollbacks, branching, and experiments

### 4.1 How branching works in this model

- Git branches control **code and config**.  
- The DB keeps a history of **project states and agent runs per commit/branch**.  
- When you check out a branch or older commit:  
  - Git gives you the right code/config.  
  - Archon looks up the corresponding `project_state` and KB wiring.  
  - Agents operate with context consistent with that point in history.

We **don’t** need Neon‑style database branching for this; it’s all modeled logically in Postgres keyed to Git.

### 4.2 Rollbacks and experiments

- Small‑scale safety: use DB transactions and migration “down” scripts.  
- Project‑scale “oops, wrong direction”:  
  - Use Git to roll back code/config.  
  - Use the DB’s Git‑keyed history to restore/project the associated metadata and KB view.  
  - For data‑heavy experiments, optionally use separate DBs (e.g., `archon_main`, `archon_experiment1`) managed by Archon tooling, but this is an implementation detail—not the core conceptual model.

***

## 5. Positioning vs SaaS‑first tools

Most current tools:

- Default to SaaS (Supabase, Neon, cloud vector DBs).  
- Treat self‑hosting as an afterthought.

SovereignPath/Archon:

- Defaults to **local Postgres + Git + IPFS**.  
- Emphasizes **digital sovereignty** and **offline‑capable workflows**.  
- Treats cloud DBs and managed services as **optional integrations**, not requirements.  
- Gives agents a rich, queryable history of the project anchored in Git, which many SaaS‑centric tools simply don’t provide.

This makes Archon attractive to:

- Privacy‑sensitive teams and enterprises.  
- Power users and home‑lab users who want control over their stack.  
- Developers who value Git‑native workflows and local‑first architectures.

***

## 6. Next implementation steps

1. **Lock in Postgres as the default DB** inside the Archon Docker image.  
2. **Design and implement the Git‑aware schema** (repos, commits, branches, project_states, agent_runs, KB tables).  
3. Build a `db_connector` abstraction with a Postgres implementation first.  
4. Add a small Git integration layer that:  
   - Detects commits/branch switches.  
   - Writes/reads `project_states` tied to `git_commits`.  
5. Integrate IPFS:  
   - Define how CIDs are stored in KB tables.  
   - Support local node + configurable pinning provider.  
6. Later: add optional adapters for Neon/Supabase/Weaviate behind `db_connector`.

***

You can drop this into the roadmap as the **“Sovereign Data & Git‑Aware Architecture”** section and iterate details (schema diagrams, milestones) from there.
