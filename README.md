# Zomato Top 5

AI-powered restaurant recommendation service using the [Zomato Hugging Face dataset](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) and an LLM for ranking and explanations.

## Documentation

| Doc | Description |
|-----|-------------|
| [`docs/context.md`](docs/context.md) | Product context |
| [`docs/architecture.md`](docs/architecture.md) | System architecture |
| [`docs/implementation-plan.md`](docs/implementation-plan.md) | Phase-wise plan |
| [`docs/data-schema.md`](docs/data-schema.md) | HF dataset column mapping |
| [`docs/edge-cases.md`](docs/edge-cases.md) | Edge cases & handling |

## Requirements

- Python 3.11+
- Internet access (first run downloads ~574 MB dataset from Hugging Face)

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

## Phase 1: Data ingestion

Load and preview normalized restaurants:

```bash
python -m app.main ingest --limit 3
```

Or from Python:

```bash
python -c "from app.ingestion.loader import load_restaurants; print(load_restaurants()[:3])"
```

## Phase 2: Filter candidates

Filter by location, budget, cuisine, and minimum rating (uses in-memory store):

```bash
python -m app.main filter --location Bangalore --budget medium --cuisine Italian --min-rating 4.0
```

Python API:

```python
from app.ingestion.loader import load_restaurants
from app.filtering import filter_candidates
from app.models import UserPreferences, BudgetPreference

load_restaurants()  # or load_restaurants(raw_df=...) in tests
prefs = UserPreferences(
    location="Bangalore",
    budget=BudgetPreference.MEDIUM,
    cuisine="Italian",
    min_rating=4.0,
)
batch = filter_candidates(prefs)
print(len(batch.candidates), [r.name for r in batch.candidates[:3]])
```

## Phase 4: Full pipeline (orchestrator)

Single entry point `recommend()` wires ingestion → filter → LLM → response:

```bash
# Default CLI (no subcommand) — mock LLM without GROQ_API_KEY
python -m app.main --location Bangalore --budget medium --cuisine Italian --min-rating 4.0

# Table output
python -m app.main --location Bangalore --budget medium --cuisine Italian --min-rating 4.0 --format table

# Subcommand still works
python -m app.main recommend --location Bangalore --budget medium --cuisine Italian --min-rating 4.0
```

Real Groq rankings — set `GROQ_API_KEY` in `.env`.

Python API:

```python
from app.models import UserPreferences, BudgetPreference
from app.orchestrator import recommend

response = recommend(
    UserPreferences(
        location="Bangalore",
        budget=BudgetPreference.MEDIUM,
        cuisine="Italian",
        min_rating=4.0,
    )
)
if response.status == "success":
    print(response.recommendations[0].explanation)
```

## Phase 5: Streamlit UI

Interactive form for all preference fields and scannable result cards:

```bash
cd "d:\Zomato-Top 5"
.\.venv\Scripts\streamlit.exe run app/presentation/ui.py
```

The app opens in your browser. Enter location, budget, cuisine, minimum rating, and optional extras (e.g. family-friendly), then click **Get my top picks**. Results show rank, name, cuisine, rating, cost, and AI explanation. Without `GROQ_API_KEY`, the mock LLM is used automatically.

## Run tests

Tests use local fixtures and do **not** require downloading the full dataset:

```bash
pytest
```

Optional integration test against Hugging Face (slow, requires network):

```bash
pytest -m integration
```

## Project layout

```text
app/
  ingestion/     # loader, normalize, in-memory store
  filtering/     # filter_service → CandidateBatch
  llm/           # prompt_builder, Groq client, parser, engine
  orchestrator.py  # recommend() pipeline (Phase 4)
  presentation/  # Streamlit UI (Phase 5)
  models.py      # Restaurant, UserPreferences, etc.
  main.py        # CLI entry
prompts/
  v1_rank_and_explain.txt
config/
  settings.py    # Environment configuration
tests/
  fixtures/      # Sample rows for unit tests
docs/
```

## Environment variables

See [`.env.example`](.env.example). Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `HF_DATASET_ID` | ManikaSaini/zomato-restaurant-recommendation | Dataset source |
| `HF_LOAD_RETRIES` | 3 | Retry count on HF failure |
| `DEFAULT_TOP_N` | 5 | Recommendations count (later phases) |
| `FALLBACK_RELAXATION` | true | Relax cuisine or budget when no strict matches |
| `MAX_CANDIDATES` | 30 | Max restaurants sent to LLM |
| `LLM_PROVIDER` | groq | `groq` or `mock` |
| `LLM_MODEL` | llama-3.3-70b-versatile | Groq model id |
| `GROQ_API_KEY` | — | Required for real Groq calls |

## Implementation status

- [x] Phase 0 — Project foundation
- [x] Phase 1 — Data ingestion
- [x] Phase 2 — Filter service
- [x] Phase 3 — LLM recommendation engine (Groq + mock fallback)
- [x] Phase 4 — Application orchestrator
- [x] Phase 5 — Streamlit UI
- [ ] Phase 6 — Hardening & deploy
