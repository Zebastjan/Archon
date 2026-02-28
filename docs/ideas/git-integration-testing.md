
---

# Git Integration & Chunking: Testing Strategy

This document describes how we want to test Archon’s Git integration and repo‑chunking pipeline so we can have real confidence that “scan this repo and index it” actually does what we think it does.

The goal is not to re‑test Git itself; we assume `git` works. We want to test **how Archon behaves when pointed at real and synthetic Git repositories.**

---

## 1. Scope: what we are testing

We care about the **end‑to‑end path**:

1. Given a Git repository (local path or URL),
2. Archon initializes (or associates) an Archon Project for that repo,
3. Archon scans the repo, selects files, and runs the chunking pipeline,
4. Chunks and metadata are stored (Supabase / DB layer),
5. RAG / search tools can answer simple questions about the repo using those chunks.

We want tests that exercise this path under:

- Normal repos (small, simple project).
- Repos with “weird” histories / encodings / tags.
- Different branch layouts.

We explicitly **do not** try to validate Git’s own behavior (that’s Git’s job). We only validate:

- We don’t crash or hang on real‑world repo shapes.
- We record and expose the information we promise (files, commits, chunks).
- RAG over repo chunks returns sensible results on a small, known test repo.

---

## 2. Types of test repositories

We will use three categories of repos:

### 2.1 Synthetic “toy” repos (we define these)

Small, purpose‑built repos created in tests or stored under `testdata/`. Each focuses on one aspect:

- `toy-basic`
  - Single branch, few files (e.g. `src/`, `tests/`, `README`).
  - Tests basic scanning and chunking.
- `toy-branches`
  - `main` + `develop` + one or two `feat/*` branches.
  - Simple merge history.
  - Tests branch discovery, default branch logic, and any branch‑based behavior.
- `toy-binary-and-ignore`
  - Includes large/binary files, `node_modules/`‑style dirs, and a `.gitignore`.
  - Tests file selection logic (what we skip, what we index).

These can be created in test setup (using `git init` + a few commits) or checked in as fixtures.

### 2.2 Real‑world “special case” repos

Use community test repos that intentionally include tricky Git cases:

- `book/git-test-repository` 
  - A Git repository “full of special cases, for testing purposes”: unusual refs, tags, encodings, etc.[1]
  - We **do not** need to understand every case inside it; we only need to ensure: 
    - Archon doesn’t error out while scanning it.
    - We index some reasonable set of files and chunks.
    - RAG can at least answer a basic structural question (e.g. “how many branches?”).

We can vendor this repo as a submodule, a clone into `testdata/`, or as a downloadable fixture used in tests.

### 2.3 Optional: additional topology repos

If needed later, we can add other tiny repos that emphasize:

- Topologically interesting histories (lots of merges).
- Large numbers of small files vs few large files.
- Shallow clones / partial checkouts.

These are lower priority; we start with synthetic + `git-test-repository`.

---

## 3. Test structure and responsibilities

We want **end‑to‑end integration tests** that:

- Run in CI,
- Are deterministic,
- And assert at Archon’s boundaries (API / DB), not inside Git internals.

### 3.1 High‑level test for the “happy path”

This is the most important test; everything else is incremental.

**Scenario: “index a small repo and answer a code question.”**

- Given: a small synthetic repo (`toy-basic`) with a known function, e.g. `src/math.py` containing `add(a, b)`.
- Steps: 
  1. Create or select an Archon Project for this repo (via API or helper).
  2. Invoke Archon’s Git integration to scan the repo and run chunking.
  3. Check the DB/API: 
     - Confirm at least N chunks exist tagged with this project/repo.
     - Confirm we have entries pointing back to `src/math.py`.
  4. Call the RAG/search API or MCP tool: 
     - Query: “What does the function `add` in `src/math.py` do?”
  5. Assert: 
     - The answer mentions the correct file and function name.
     - The answer roughly matches the actual behavior (“adds two numbers”).

This test proves that “Git → chunking → storage → RAG” works in the simplest non‑trivial case.

### 3.2 Behavioral tests on synthetic repos

For each synthetic repo type:

- `toy-basic`
  - Assert: 
    - File count seen by Archon matches expectations (e.g. excludes `.git`, `ignored` dirs).
    - Chunks exist for all source files we care about.
    - No errors are logged.
- `toy-branches`
  - Assert: 
    - Archon detects the expected branches (`main`, `develop`, `feat/*`).
    - Any branch‑specific logic (if we have it) behaves as documented, e.g. default branch = `main` or `develop`.
    - Chunk counts are reasonable on the default branch.
- `toy-binary-and-ignore`
  - Assert: 
    - Binary or ignored directories are not chunked.
    - No chunk records are created for paths that should be excluded.
    - We don’t crash on large files, we just skip them.

These can be standard integration tests (pytest, etc.) that call Archon’s public APIs or internal service functions.

### 3.3 Robustness tests with `git-test-repository`

Using `book/git-test-repository`:[1]

- Setup: 
  - Make this repo available under `testdata/git-test-repo` (clone, submodule, or fixture).
- Tests: 
  - Run the Git integration + chunking on this repo.
  - Assert: 
    - No unhandled exceptions / fatal errors.
    - We index at least some non‑zero number of files and chunks.
    - RAG can answer a basic question that only depends on “Git shape,” e.g.  
      “How many branches are in this repository?” or  
      “Name at least one tag in this repository.”

We are not validating *every* edge case in `git-test-repository`; we just ensure Archon doesn’t fall over and can produce some coherent metadata.

---

## 4. How to implement (for Claude / Minimax)

When implementing this test suite, please:

1. **Use existing Archon entry points wherever possible**
   - Prefer going through the same API/service calls that the app uses, not internal helpers.
   - This ensures we exercise real behavior, not a test‑only code path.
2. **Create or reuse fixtures under a clear path**
   - e.g. `python/tests/git_fixtures/` for synthetic repos.
   - Add a README in that directory explaining what each fixture repo is for.
3. **Keep tests small and focused**
   - Each test should focus on one responsibility (basic indexing, branch detection, ignore logic, robustness on weird repo).
   - Avoid huge “do everything” tests that are hard to debug.
4. **Add logging checks where helpful**
   - Ensure we log key milestones: 
     - Starting scan of repo `X`.
     - Number of files discovered, skipped, and chunked.
     - Number of chunks written.
   - This will make debugging failures much easier.
5. **Wire tests into CI**
   - Make sure the new tests are: 
     - Fast enough to run in CI.
     - Not dependent on network (use local clones/fixtures).
   - If a fixture repo is large, consider using a stripped‑down version or a shallow clone.

---

## 5. Success criteria

We’ll consider the Git integration “basically trustworthy” when:

- The happy‑path test passes reliably.
- The synthetic repo tests cover: 
  - Basic indexing,
  - Branch handling,
  - Ignore/binary behavior.
- The robustness test with `git-test-repository` runs without errors and returns coherent metadata.

After that, we can expand test coverage (e.g. larger repos, more complex branch models), but the above is the minimum bar for “we think it works the way it’s supposed to.”

---

You can drop this into the repo and point Claude/Minimax at it with a prompt like: “Implement the test suite described in this document, in the style of our existing tests.”

Citations:
[1] GitHub - book/git-test-repository: A Git repository full of special cases, for testing purposes https://github.com/book/git-test-repository