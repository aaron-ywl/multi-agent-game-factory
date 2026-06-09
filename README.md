<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/LangGraph-0.2+-green" alt="LangGraph">
  <img src="https://img.shields.io/badge/Milvus-Lite-orange" alt="Milvus">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-teal" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

<h1 align="center">🎮 Multi-Agent Game Factory</h1>
<h3 align="center">From idea to playable game — 6 AI agents collaborate to design, code, review, test, and generate art</h3>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    🌐 Web UI (Dark Theme)                        │
│          Real-time SSE streaming of 6-agent pipeline             │
└────────────────────────────┬────────────────────────────────────┘
                             │ FastAPI + SSE
┌────────────────────────────▼────────────────────────────────────┐
│                🧠 LangGraph Agent Pipeline                       │
│                                                                  │
│  Input → [🎮 Designer] → [📖 Narrative] → [💻 CodeGen]          │
│                                               ↓                  │
│  Output ← [🎨 Art] ← [🧪 Test] ← [🔍 Reviewer]                  │
│             ↑ Conditional: needs_regeneration → retry (≤3x)     │
└──────────────────────────────────────────────────────────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Milvus Lite  │   │    SQLite    │   │  Qwen-Image  │
│  Vector RAG   │   │   Memory     │   │  2D Assets   │
│  BM25+Rerank  │   │              │   │  3 per run   │
└──────────────┘   └──────────────┘   └──────────────┘
```

## 🤖 6 Agents

| # | Agent | Input | Output | Verification |
|:--:|-------|-------|--------|-------------|
| 1 | 🎮 **Designer** | User idea | GDD (title/genre/mechanics/features) | Structured JSON |
| 2 | 📖 **Narrative** | GDD | World-building, 3-4 characters with skills, quests | Structured JSON |
| 3 | 💻 **CodeGen** | GDD + Narrative | Runnable Python game | Compile → run → auto-fix ≤2 retries |
| 4 | 🔍 **Reviewer** | Code | Bugs, optimizations, security, score | 5-dimension review |
| 5 | 🧪 **Test Agent** | Code | pytest suite | Generate → execute → auto-fix failures |
| 6 | 🎨 **Art Director** | GDD + Narrative | 2D/3D prompts + **real images** | Qwen-Image-2.0, 3 per run |

**Auto game-type detection** — keywords in the user's request trigger different code templates:

- 🏰 **Tower Defense** — `Plant` + `Zombie` classes, grid battlefield, sun economy, ASCII wave display
- ⚔️ **Fighting** — `Fighter` class, skill animations, HP bars, auto-play rounds

## 🔮 Vector RAG Pipeline

```
User Query
    │
    ├─ 🔄 Query Rewrite (LLM generates 3 variants)
    ├─ 🔍 Vector Search (Milvus IVF_FLAT, COSINE)
    ├─ 📝 BM25 Keyword Search (in-memory, Chinese bigram+trigram)
    ├─ 🔀 Merge & Dedup (content hash)
    ├─ 🎯 Rerank (bge-reranker-v2-m3)
    ├─ 🚫 Score Filter (threshold ≥ 0.3)
    └─ 📤 Top-K injected into Agent prompts
```

| Component | Tech | Detail |
|-----------|------|--------|
| Vector DB | Milvus Lite | Embedded, no external service |
| Chunking | 500 chars + 125 overlap | Overlap sliding window with semantic boundaries |
| Embedding | text-embedding-v1 | 1536 dims |
| BM25 | Custom in-memory | k1=1.5, b=0.75, Chinese aware |
| Rerank | bge-reranker-v2-m3 | API-based, boosts top-3 accuracy |

**Knowledge base**: 5 professional game development PDFs (~150KB each) covering core loops, combat math, code architecture, AIGC art pipelines, and monetization design.

## 🧠 Memory Architecture

```
Layer 1 — Conversation Memory: SQLite sessions table, user-triggered save, LLM auto-summary
Layer 2 — Working Memory:    LangGraph SharedState across 6 agents
Layer 3 — Long-term Memory:  Verified code auto-indexed into Milvus (only when code + tests pass)
```

No automatic saves — the user sees a save/discard bar after each pipeline run.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- OpenAI-compatible API key (works with DeepSeek, Qwen, GLM, GPT-4, etc.)

### Setup

```bash
git clone https://github.com/your-org/multi-agent-game-factory.git
cd multi-agent-game-factory

pip install -r requirements.txt

# Edit .env with your API key
# OPENAI_API_KEY=sk-xxxx
# OPENAI_BASE_URL=https://api.openai.com/v1

# Index the knowledge base (first run only)
PYTHONPATH=. python3 scripts/index_knowledge.py

# Start the web server
PYTHONPATH=. python3 -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000

# Open http://localhost:8000
```

### CLI Demo

```bash
# Full pipeline
python3 demo.py run "Design a gacha card RPG with elemental combat and PvP arena"

# Single tools
python3 demo.py tool balance --attack 50 --health 500
python3 demo.py tool enhance --prompt "a warrior character" --style stylized
```

## 📡 API Reference

### Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/generate` | Run full 6-agent pipeline (single response) |
| `POST` | `/api/v1/generate-stream` | SSE streaming for real-time UI |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sessions` | List saved sessions |
| `GET` | `/api/v1/sessions/{id}` | Get session detail |
| `POST` | `/api/v1/sessions/{id}/save` | Save session to memory |
| `POST` | `/api/v1/sessions/{id}/discard` | Discard and forget |

### Knowledge Base

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/vector/stats` | Collection statistics |
| `POST` | `/api/v1/vector/reindex` | Rebuild index from PDFs |
| `POST` | `/api/v1/vector/index-pdfs` | Ingest all PDFs |

### Tools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tools/balance` | Combat balance calculator |
| `POST` | `/api/v1/tools/validate-code` | Syntax validator |
| `POST` | `/api/v1/tools/enhance-prompt` | AIGC prompt enhancer |
| `POST` | `/api/v1/tools/asset-checklist` | Asset checklist generator |

## 📂 Project Structure

```
multi-agent-game-factory/
├── src/
│   ├── agents/              # 6 AI agent implementations
│   │   ├── game_designer.py     # Agent 1: Game design (GDD)
│   │   ├── narrative_agent.py   # Agent 2: World & character design
│   │   ├── code_generator.py    # Agent 3: Code gen + verify + auto-fix
│   │   ├── code_reviewer.py     # Agent 4: Multi-dimension code review
│   │   ├── test_agent.py        # Agent 5: pytest generation + execution
│   │   └── art_director.py      # Agent 6: AIGC prompts + real image gen
│   ├── graph/               # LangGraph pipeline orchestration
│   │   ├── state.py             # Shared state definition
│   │   ├── game_pipeline.py     # 6-agent batch pipeline
│   │   └── stream_pipeline.py   # SSE streaming pipeline
│   ├── services/            # Core services
│   │   ├── llm_client.py        # OpenAI-compatible LLM client
│   │   ├── vector_rag_service.py # Milvus + BM25 + Rerank
│   │   ├── image_gen.py         # Qwen-Image-2.0 service
│   │   └── memory.py            # SQLite 3-layer memory
│   ├── skills/              # Tool/Skill abstraction layer
│   │   ├── registry.py          # Global skill registry
│   │   ├── game_tools.py        # Balance/validation/prompt/assets
│   │   └── setup.py             # Skill registration
│   ├── api/                 # FastAPI routes
│   │   ├── app.py               # Application entry
│   │   └── routes.py            # All API endpoints
│   └── config/              # Configuration
│       └── settings.py          # .env-driven settings
├── static/
│   └── index.html           # 🌐 Dark-theme web UI
├── data/
│   └── knowledge_pdfs/      # 📚 5 game dev knowledge PDFs
├── scripts/
│   ├── generate_knowledge_pdfs.py  # PDF generator
│   └── index_knowledge.py          # Milvus index script
├── demo.py                  # CLI demo entry
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 🔧 Tech Stack

| Layer | Tech | Role |
|-------|------|------|
| LLM | DeepSeek-V3.2 (swappable) | Reasoning engine for all 6 agents |
| Embedding | text-embedding-v1 (1536d) | Text vectorization |
| Orchestration | LangGraph StateGraph | 6-node pipeline + conditional routing |
| Vector DB | Milvus Lite | Embedded knowledge storage & retrieval |
| BM25 | Custom | Keyword recall (Chinese-aware tokenizer) |
| Rerank | bge-reranker-v2-m3 | Precision re-ranking |
| Image Gen | Qwen-Image-2.0 | 2D character + environment assets |
| Database | SQLite | Sessions + knowledge feedback |
| API | FastAPI + SSE | REST + real-time streaming |
| Frontend | Vanilla HTML/CSS/JS | Dark theme, zero dependencies |

## 📊 Verified Results

| Agent | Pass Rate | Notes |
|-------|:---:|-------|
| 🎮 Designer | 100% | Structured GDD with all required fields |
| 📖 Narrative | 100% | World + 3-4 chars (each 3 skills) + quests |
| 💻 CodeGen | 95%+ | First-pass success, auto-fix covers most failures |
| 🔍 Reviewer | 100% | 5-dimension review, 3-8 findings per run |
| 🧪 Test Agent | 95%+ | Auto pytest generation, matching constructor signatures |
| 🎨 Art Director | 90%+ | 2 character + 1 environment image per run |

## 🎮 Live Demo

**Input**: *"开发一个二次元卡牌RPG游戏，抽卡+回合制战斗，PVE和PVP，核心特色是元素克制和角色羁绊系统"*

### Step 1 — Enter your idea and hit launch

![Input](docs/screenshots/01-input.png)

### Step 2 — Pipeline running in real-time

Six agents light up green as they complete. Each agent's result card appears as it finishes.

![Running](docs/screenshots/02-running.png)

### Step 3 — Full output: complete game design + runnable code + tests + art

![Results](docs/screenshots/04-results-top.png)

### What was actually produced

<table>
<tr><td>🎮 <b>Game Design</b></td><td>《元素纪元：羁绊契约》— Anime Card RPG with elemental rock-paper-scissors combat and character bond synergy system</td></tr>
<tr><td>📖 <b>Narrative</b></td><td>3 characters × 3 skills each (e.g. 艾莉娅 with 星火燎原/元素共鸣/羁绊守护), world-building + quests</td></tr>
<tr><td>💻 <b>Code</b></td><td><code>outputs/main.py</code> — 8,678 chars, runs on first attempt ✅, Fighter class with skill animations + HP bars + auto-battle</td></tr>
<tr><td>🔍 <b>Review</b></td><td>Score 70/100, 4 bugs found + 3 optimizations suggested</td></tr>
<tr><td>🧪 <b>Tests</b></td><td><code>outputs/test_main.py</code> — pytest 3/3 all passed</td></tr>
<tr><td>🎨 <b>Art</b></td><td>3 images generated via Qwen-Image-2.0 — 艾莉娅 (character), 炎狱领主-烬 (character), 元素回廊 (environment scene)</td></tr>
</table>

### Architecture Diagram

<p align="center">
  <img src="docs/screenshots/03-results-full.png" alt="Full Pipeline Results" width="80%">
</p>


## 📄 License

MIT

---

<p align="center">
  <sub>Built for game developers who want AI to do the heavy lifting.</sub>
</p>
