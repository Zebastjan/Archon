# ADR: Adopt Tavily for Web Crawling in Archon Ingestion

**Status:** Proposed  
**Date:** 2026-02-27  
**Owner:** Archon Ingestion / Server  

## 1. Context

Archon needs a **working web crawler** to unblock several downstream goals (knowledge base ingestion, RAG over arbitrary docs, workflow automation that depends on “go read this site and learn it,” etc.).  

We currently have a “crawl it yourself” implementation that:

- Struggles with modern websites that are heavily JavaScript- and CSS-driven.  
- Requires non-trivial effort to maintain (e.g., headless browsers, timeouts, anti-bot measures, brittle HTML parsing).  
- Produces noisy output with a lot of boilerplate and low signal-to-noise, which then has to be cleaned up before it is useful for RAG.

In practice, **building and maintaining a world-class crawler plus extractor is a deep, specialized problem**. Doing it ourselves competes with our core mission (Archon as an AI agent framework and knowledge backbone), and we’ve seen enough pain to believe it will remain a time sink.

We therefore want to adopt a **hosted web crawling and extraction service** that:

- Handles modern web complexity (scripts, dynamic content).  
- Returns relatively clean, LLM-ready text.  
- Provides simple, predictable knobs: URL, depth/limits, and a bounded cost model.

This ADR explains why we are choosing Tavily for that role, and outlines a high-level staging plan.

## 2. Decision

We will:

1. **Adopt Tavily as the primary web crawling and extraction provider** for Archon’s ingestion pipeline.  
2. **Keep the existing “roll-your-own” crawler as a fallback / advanced option**, but stop investing significant effort into making it robust for arbitrary sites.  
3. **Design our ingestion around a provider abstraction**, so Tavily is the default implementation but not hard-coded; we can add or swap providers later.  
4. Implement a **Stage 1 integration** with a very simple UX: “start from URL + depth,” with conservative internal limits to prevent runaway crawls.

## 3. Rationale: Why Tavily vs. building our own

### 3.1. Web crawling is hard and brittle

Modern websites:

- Serve large amounts of JavaScript and CSS that are irrelevant to the content we care about.  
- Often require JS execution to render the actual content.  
- Use dynamic routing, infinite scroll, anti-bot protections, and complex markup.

A robust crawler must handle:

- Headless browser orchestration, timeouts, and retries.  
- De-duplication and canonicalization of URLs.  
- Heuristics to find main content vs. navigation, boilerplate, ads, etc.  
- Ongoing adaptation as the web evolves.

We have already seen that trying to maintain this ourselves is **time-consuming, fragile, and distracting** from Archon’s core value. Making it “world-class” would realistically be its own product line.

### 3.2. Why a hosted service at all

Using a hosted service:

- Offloads the complexity of **HTML parsing, JS execution, and content extraction**.  
- Gives us predictable, credits-based pricing and operational guarantees.  
- Lets us focus on **what we do with the content** (chunking, embeddings, workflows, UI) rather than **how to reliably fetch it**.

We could try to patch our existing crawler, but that moves us only slightly up the quality curve while keeping us on the hook for ongoing maintenance.

### 3.3. Why Tavily specifically

We choose Tavily as the first-class provider because:

- It is explicitly designed as a “web access layer for AI agents,” with APIs oriented around **search, map, extract, and crawl**, rather than generic, low-level scraping.  
- It focuses on returning **clean, LLM-friendly text** and supports specifying depth and limits, which map naturally to our ingestion mental model (“URL + depth”).  
- It offers clear controls for:
  - Crawl depth / breadth.  
  - Total page limits.  
  - Extraction modes (e.g., basic vs more advanced), so we can start simple and optimize later.  
- It has a modern SDK and ecosystem integrations, which lowers implementation and maintenance cost on our side.

Architecturally, Tavily aligns well with the way we want to think about ingestion:

- **Stage 1:** “Just crawl this URL up to a certain depth and give me text.”  
- **Stage 2+:** Preflight mapping, cost estimation, and more selective extraction.

## 4. Rationale: Why keep our own crawler at all (but de-prioritize it)

We will retain the existing “crawl-it-yourself” path as:

- A **fallback** when Tavily is unavailable or misconfigured.  
- An **escape hatch** for power users who explicitly want full control (e.g., highly customized scraping logic on their own infrastructure).

However, we will:

- Stop treating our own crawler as the default or as a target for major improvements.  
- Avoid tying new features to its quirks.  
- Document it as a “best-effort / advanced” option, not the primary supported path.

This keeps an option open without splitting our focus.

## 5. Scope of this ADR vs. implementation details

This ADR is about the **why**:

- Why we are introducing Tavily.  
- Why we are not doubling down on our in-house crawler.  
- Why we accept a hosted service dependency here.

Implementation details (exact schemas, function names, etc.) are considered **out of scope** for this ADR and should live in:

- A short implementation spec attached to the relevant issue/PR.  
- Module-level documentation or comments near the new provider code.

That said, we fix the **shape** of the initial behavior here to provide enough clarity for implementation.

### 5.1. Stage 1: Basic ingestion with safety caps

Stage 1 behavior:

- User (or agent) provides:
  - `url` (starting URL)  
  - `depth` (intentional link depth; likely 1–3)

- The ingestion system:
  - Maps `depth` to Tavily crawl parameters, with conservative internal caps (e.g., maximum depth, breadth, and total pages).  
  - Calls Tavily to crawl and extract basic text content from the site.  
  - Feeds the resulting pages into the existing chunk → embed → store pipeline.  
  - Stores metadata about:
    - The provider (`tavily`)  
    - The effective parameters used  
    - How many pages were crawled (and, when available, usage stats)

Stage 1 explicitly **does not** include:

- Map-based preflight to estimate size/cost.  
- Automatic quality assessment of the crawled content.  
- Advanced extraction modes or rich semantic metadata from Tavily.

Those are reserved for later stages.

### 5.2. Future stages (vision only)

Non-binding, but to capture the direction:

- **Stage 2 – Preflight Map and cost estimation:**  
  - Before a crawl, run a lightweight “map” to understand how big the target is and approximate cost.  
  - Use this to warn the user (or an agent) when they are about to trigger a very large or expensive crawl.

- **Stage 3 – Smarter selection and quality:**  
  - Use Map plus sampling to identify “good” vs “low-value” sections (e.g., docs vs marketing noise) before full ingestion.  
  - Apply filters or heuristics to keep the KB clean.

- **Stage 4 – Multiple providers / hybrid modes:**  
  - Introduce additional providers as needed, behind the same abstraction.  
  - Allow switching providers per workspace or per crawl job.

These stages will be described in future ADRs/specs.

## 6. Consequences

**Positive:**

- We unblock a **reliable, production-grade crawling path** without sinking effort into crawling infrastructure.  
- We get closer to “URL → ingested KB content” as a first-class capability.  
- We contain the in-house crawler’s complexity by relegating it to fallback status.  
- Our architecture remains flexible via a provider abstraction, so we are not locked in forever.

**Negative / Risks:**

- We take on a dependency on an external service for a critical capability.  
- Tavily’s pricing and limits become part of our cost model and need monitoring.  
- Some advanced or niche use cases might still require the in-house crawler or future providers.