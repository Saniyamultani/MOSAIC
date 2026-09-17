# MOSAIC

**A proactive personal intelligence system.**

ChatGPT answers questions about information you give it. MOSAIC builds a model of
your world, watches the outside world, and tries to discover when the two collide.

```
Capture → Understand → Connect → Monitor → Discover → Verify → Alert
```

You hand it a receipt, a warranty, a bill or a sentence. It extracts the details,
asks you to confirm once, and builds a **Life Graph** of what you own. From then on
it polls approved external sources, and when something out there touches something
in your graph it runs an eight-agent verification pipeline before deciding whether
to interrupt you — and every alert can show you exactly why it fired.

---

## Run it

**Requirements:** Python 3.10+ and Node 18+. Nothing else. No Docker, no database
server, no API key.

```bash
# macOS / Linux
./start.sh

# Windows
start.bat
```

Then open **http://localhost:3000** (API docs at http://localhost:8000/docs).

The first run creates a virtualenv, installs dependencies, seeds the demo data and
starts both servers. `./start.sh --fresh` wipes the database and re-seeds.

<details>
<summary>Manual start, if you prefer</summary>

```bash
# terminal 1 — backend
cd backend
python -m venv .venv && source .venv\Scripts\activate   # Windows: 
pip install -r requirements.txt
python -m app.seed --reset        # loads the demo and runs one monitoring cycle
uvicorn app.main:app --reload --port 8000

# terminal 2 — frontend
cd frontend
npm install
npm run dev
```
</details>

### Turning on Gemini

MOSAIC ships with a deterministic rule-based extractor so it works with no API key.
To use the real model, get a free key at <https://aistudio.google.com/apikey> and:

```bash
cd backend
cp .env.example .env
# set GOOGLE_API_KEY=...
```

Nothing else changes — the LLM sits behind an interface, and if a Gemini call fails
the pipeline falls back to the offline path instead of going down.

---


## What the demo shows

`python -m app.seed --reset` reproduces the full walkthrough:

| Day | What happens |
|-----|--------------|
| 1 | A phone receipt and its extended warranty go in. The Entity Agent recognises that "Galaxy S26 Ultra" in the warranty is the phone from the receipt and merges them into one node. |
| 2 | A television receipt goes in. MOSAIC notices the TV and the phone share a credit card and raises a 🔵 **new connection**. |
| 3 | A subscription and a broadband bill go in. |
| 7 | Approved sources publish. The pipeline decides what deserves an alert. |

The seed output on day 7:

```
🚨 alerted     Samsung expands the Galaxy S26 display service programme in India
🚨 alerted     September security patch released for the Galaxy S26 series
🛑 refuted     Recall: Sony BRAVIA XR-55A80K power boards may overheat
·  no_match    CVE-2026-31887: authentication bypass in TP-Link Archer AX55 firmware
🚨 alerted     Netflix revises Premium plan pricing in India from October 2026
·  no_match    Foldable shipments grew 14% last quarter, analysts say
```

The refused one is the point. The user owns an **XR-65**A80K; the recall covers the
**XR-55**A80K. The Skeptic Agent kills the match before it ever becomes a
notification:

> *Skeptic Agent — Refuted the match: the notice affects XR-55A80K; your unit is XR-65A80K.*

---

## Architecture

### The eight agents

| # | Agent | What it does |
|---|-------|--------------|
| 1 | **Ingestion** | Parses PDFs, images, emails, `.ics`, URLs and free text into structured fields |
| 2 | **Entity** | Decides whether new input refers to a node already in the graph ("Samsung S26" = "Galaxy S26" = "SM-S926B") before writing |
| 3 | **Research** | Polls approved sources in trust order: official > government > manufacturer > retailer > press > web |
| 4 | **RAG** | Retrieves evidence from the private store (your documents) and the external store (the outside world) |
| 5 | **Relationship** | Scores whether an external item touches a node, combining lexical lookup, vector search and graph traversal |
| 6 | **Skeptic** | Tries to *disprove* the match — model, region, purchase window, ownership evidence, source trust |
| 7 | **Relevance** | Match strength × importance × urgency × source trust → a confidence score and a severity tier |
| 8 | **Alert** | Writes the notification, carrying its reasoning chain and evidence with it |

### Orchestration (LangGraph)

Two state machines in `backend/app/pipeline/graph.py`:

```
ingestion   capture ──▶ ⏸ human confirm ──▶ commit (resolve → write → index)

monitor     relate ──▶ retrieve ──▶ challenge ──▶ score ──▶ notify
               │                       │            │
               ▼                       ▼            ▼
          no match                  refuted    below threshold
```

The pause in the ingestion graph is a real LangGraph `interrupt_before` — the
✓ Confirm button in the UI is what resumes it. The three exits in the monitor graph
are conditional edges: a suppressed alert is recorded with its reason, not silently
dropped.

### Storage — zero infrastructure by default, swappable

| Layer | Default | Opt-in |
|-------|---------|--------|
| Relational | SQLite | PostgreSQL (`DATABASE_URL=postgresql+psycopg://…`) |
| Life Graph | nodes/edges in the relational DB, BFS traversal in Python | Neo4j with Cypher traversal (`GRAPH_BACKEND=neo4j`) |
| Vectors | cosine over a `BLOB` column | Qdrant (`VECTOR_BACKEND=qdrant`) |
| Embeddings | signed feature hashing, instant, no download | sentence-transformers (`EMBEDDING_BACKEND=sentence-transformers`) |
| LLM | deterministic rule-based | Google Gemini (`GOOGLE_API_KEY`) |
| Scheduling | APScheduler in-process | swap `monitor_job` onto Celery + Redis |

Every one of these sits behind an interface, so the "portfolio architecture"
version and the "clone and run" version are the same codebase. `docker-compose.yml`
brings up Postgres + Neo4j + Qdrant when you want to demonstrate the full stack.

### Layout

```
backend/
  app/
    agents/          the eight agents, one file each
    pipeline/        LangGraph state machines
    graphstore/      Life Graph (relational default, Neo4j optional)
    rag/             embeddings + the private/external vector stores
    llm/             provider interface, Gemini, deterministic offline
    ingest/          file parsers + fields → graph structuring
    api/             FastAPI routers
    models.py        SQLAlchemy schema
    seed.py          the demo walkthrough
  data/
    external_feed.json   approved sources + their items (the offline feed)
  tests/            end-to-end pipeline tests
frontend/
  app/              dashboard · life graph · radar · add
  components/       alert card, evidence drawer, graph node
```

---

## The screens

- **Dashboard** — greeting, three stat cards (🚨 Important, 🔗 Connections, 📅 Upcoming), and a feed of recent discoveries.
- **Life Graph** — an explorable node graph. Click any node for its details, connections, source documents and alerts.
- **Radar** — a curated feed, not a notification dump. Four tiers: 🔴 Important, 🟡 Worth knowing, 🔵 New connection, 🟢 Informational.
- **Add** — type it, upload it, or paste a URL; review the extracted fields; ✓ Confirm.
- **MOSAIC Assistant** — ask questions about confirmed items, documents, and alerts from
  the floating assistant available on every screen.

### "Why am I seeing this?"

Every alert opens its whole chain — the external update, the source and its trust
tier, the matched model, your item, the graph hops around it — then the verification
checklist, the confidence bar, the evidence from both knowledge stores, and the
step-by-step trace of what each agent did. Nothing about an alert is a black box.

---

## Tests

```bash
cd backend && pytest
```

Six end-to-end tests cover extraction, graph writes, alias merging, alerting,
skeptical suppression of a model mismatch, and correctly ignoring irrelevant news.

---

## Adding your own external sources

`backend/data/external_feed.json` holds the approved sources and their items. Add an
entry there for a reproducible offline demo, or set `ENABLE_NETWORK_RESEARCH=true`
and add a source row with `kind: "rss"` and a real feed URL to poll live. The
`POST /api/external/publish` endpoint injects a single item on demand — handy for
demonstrating the pipeline live.

---

## Notes and limits

- Single-user by design. `api/deps.py::current_user` is the one place real auth would slot in; everything downstream is already scoped by `user_id`.
- The offline extractor is regex and heuristics. It handles the common Indian-retail receipt shapes well and degrades on unusual formats — that is what the Gemini path is for.
- PDF reading and image OCR are included in `requirements.txt`. Image OCR also needs the
  Tesseract binary installed on Windows and available on `PATH`; if OCR cannot run,
  MOSAIC reports the specific parser issue in the extraction trace.
- Free tiers (Gemini, NewsAPI) are development resources, not production capacity.
