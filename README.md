# Governed Context Layer on Google Cloud (`governed-context-layer-gcp`)

Companion codebase for **"Vibe Coding, Meet Reality: Building a Governed Context Layer with Cloud SQL for PostgreSQL, Google Cloud Knowledge Catalog, and MCP Toolbox for Databases"** (inspired by Rod Johnson's article *[Vibe Coding, Meet Reality](https://medium.com/@springrod/vibe-coding-meet-reality-0fb1e4e04053)*).

This repository demonstrates how to build a **3-Layer Governed Semantic, Security & Operational Context Architecture** on Google Cloud so developers and domain experts can rapidly generate "Single Pane of Glass" dashboards and AI agents without leaking customer PII or hallucinating business metrics.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph L3["Layer 3: Rapid 'Single Pane of Glass' Apps & Agents (Vibe-Coded Safely)"]
        UI["Morning Franchise Pulse Dashboard\n(FastAPI + HTMX / Antigravity)"]
        AST["AST Boundary + Agent Registry Verifier\n(Blocks direct DB imports & rogue Shadow IT MCPs)"]
    end

    subgraph L2["Layer 2: The Governed Semantic & Operational Context Layer (Built by Engineers)"]
        MA["Google Cloud Model Armor + Cloud DLP\n(Blocks Prompt Jailbreaks & Scrubs Free-Text PII)"]
        IAP["Cloud IAP + Cloud Armor\n(OIDC Row-Level Identity + 429 Rate Limiting)"]
        KC["Google Cloud Knowledge Catalog + BigQuery Graph\n(Context Set + Business Glossary + Property Graph)"]
        MCP["MCP Toolbox for Databases (tools.yaml)\n(Parameterized Queries + SQL PII Masking + Audit Logs)"]
    end

    subgraph L1["Layer 1: Core Enterprise Database"]
        PG[("Cloud SQL for PostgreSQL\n(stores, customers, orders, suppliers, bean_inventory)")]
    end

    UI -->|"1. Screened by"| MA
    MA -->|"2. Verified OIDC & Rate Limit"| IAP
    IAP -->|"3. Calls ONLY named MCP tools"| MCP
    KC -.->|"Defines official metrics, joins & GQL graph"| MCP
    KC -.->|"Guides coding agent"| UI
    MCP -->|"4. Executes locked $1/$2 SQL"| PG
    AST -->|"Verifies before startup"| UI
```

---

## Repository Layout

| File | Purpose |
| :--- | :--- |
| [`sql/01_schema_and_seed.sql`](./sql/01_schema_and_seed.sql) | Cloud SQL for PostgreSQL schema & seed data for *Roast & Co.* (`stores`, `customers`, `orders`, `suppliers`, `bean_inventory`, `restock_requests`). |
| [`knowledge_catalog_setup.py`](./knowledge_catalog_setup.py) | Builds the **Google Cloud Knowledge Catalog** Context Set (`type="context-set"`), Business Glossary & Table Entries (`upsert_entry`), `schema-join` links (`upsert_entry_link`), `lookup_context` YAML simulation, and **BigQuery Property Graph (`CREATE PROPERTY GRAPH` & ISO GQL)** DDL. |
| [`tools.yaml`](./tools.yaml) | Declarative **MCP Toolbox for Databases** configuration (`cloud-sql-postgres` + `google-oidc` `authServices`) exposing 5 governed, parameterized, PII-masked tools. |
| [`context_layer_gateway.py`](./context_layer_gateway.py) | Runnable Python gateway comparing Naive Direct-to-DB SQL against the Governed Context Layer, plus **Model Armor + Cloud DLP** (`ModelArmorGuard`), **OIDC row-level auth**, **Agent Registry verification**, **Multi-Hop Supply Chain traversal**, and **Cloud Armor rate limiting** (`EdgeRateLimiter`). |
| [`roast_context_mcp_server.py`](./roast_context_mcp_server.py) | Local MCP server for **Google Antigravity Manager** exposing the Knowledge Catalog lookup, Model Armor prompt screening, and governed database tools for natural-language queries. |
| [`antigravity_mcp_config.json`](./antigravity_mcp_config.json) | Sample MCP configuration for Google Antigravity Manager (`~/.gemini/antigravity/mcp_config.json`). |
| [`single_pane_app.py`](./single_pane_app.py) | FastAPI **Single Pane of Glass** dashboard (`Morning Franchise Pulse`) with zero database drivers/SQL + `verify_no_direct_db_access()` AST static boundary verifier. |
| [`test_context_layer_blog.py`](./test_context_layer_blog.py) | Automated 11-test verification suite covering naive vs. governed queries and all 5 real-world production gaps. |

---

## Quickstart (Run Locally in 30 Seconds)

Prerequisites: **Python 3.12+** and **[`uv`](https://docs.astral.sh/uv/)**.

```bash
# 1. Install dependencies
uv sync

# 2. Run the side-by-side Naive Direct-to-DB vs. Governed Context Layer comparison
uv run python context_layer_gateway.py

# 3. Inspect the Google Cloud Knowledge Catalog `lookup_context` YAML summary
uv run python knowledge_catalog_setup.py

# 4. Run the full 11-test verification suite
uv run python test_context_layer_blog.py

# 5. Launch the Single Pane of Glass web dashboard on http://127.0.0.1:8011
uv run python single_pane_app.py
```
