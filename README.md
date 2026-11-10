# PlacidWay Knowledge Bot

A chatbot that answers patient questions using **only** the content of seven PlacidWay pages about ITC Immunity
Therapy Center (Tijuana, Mexico) and an alternative-medicine price comparison. Every answer cites the page it came
from. When the pages don't hold the answer, the bot says so and offers a free quote instead of guessing.

**Live:** https://placid.43-133-156-126.sslip.io

## How it works

```
question + recent chat history (kept in the browser)
  │
  ├─ 1. Router (Claude Haiku 5.5, structured output)
  │     rewrites the question as a standalone English search query (follow-ups, Spanish/Arabic…),
  │     detects intent: info · price · comparison · medical_advice · booking · quote_request · greeting · out_of_scope
  │     booking / quote / greeting / out-of-scope → short reply (+ lead form). No retrieval, no facts.
  │
  ├─ 2. Hybrid retrieval (Qdrant, local mode)
  │     dense: BAAI/bge-small-en-v1.5 · sparse: BM25 · fused with Reciprocal Rank Fusion · top 6 chunks
  │
  ├─ 3. Answer (Claude Opus 5.5, structured output)
  │     {answerable, answer, cited_ids, medical_topic}: answers only from the chunks, in the user's language
  │
  └─ 4. Guards
        · cited chunk ids must be ones we actually retrieved; source links come from chunk metadata
        · code: every money amount and every number with a unit (%, weeks, days, months, years, sessions…)
          in the answer must appear in the cited chunks or in the user's own message ("it is not $50" is fine).
          Works across English, Spanish and Arabic, including digits written as words ("three weeks")
        · claim check (Claude Haiku): flags non-numeric claims the cited chunks don't support
          (accreditations, inclusions, therapy names, medical claims)
        · any failure → one retry with the reason, then "I don't know" + quote form; logged as a content gap
        · a short medical disclaimer is added once per conversation when the answer touches treatment
```

Why two layers: numbers are where a wrong answer hurts most, so they are checked in code, which an LLM can't talk its way
past. The claim check covers everything else. It is a second model, so it can miss things. If it is unavailable the
request continues (fail open), because numbers and citations are already verified by then. Turn it off with
`CLAIM_CHECK=false`.

### Ingestion

1. **Crawl** (`app/ingest/crawler.py`): fetches exactly the seven configured URLs, never follows links. It checks
   `robots.txt` first and sends a descriptive User-Agent. It waits `max(3s, robots Crawl-delay)` between requests:
   PlacidWay's robots.txt asks for 3s, which is slower than one request per second.
2. **Parse** (`app/ingest/parser.py`): keeps only each page type's content containers and removes navigation, footer,
   sidebar, forms, popups, reviews/testimonials and the site-wide promo cards. Those cards carry *other* clinics'
   prices, and leaving them in would make the bot quote the wrong numbers. Tables become one line per row
   (`Out-Patient Program | 3 Weeks | $18,995`) so a price is never separated from its label. The video page keeps
   ITC's own videos (title + PlacidWay video link), grouped by category.
3. **Chunk** (`app/ingest/chunker.py`): one chunk per heading section, split on line boundaries above 1,500 chars,
   with ids like `P2-C3`. The page title and heading are added to the embedded text. That gives 117 chunks.
4. **Index** (`app/services/index.py`): builds into a temp directory and swaps it in, so a failed refresh never breaks
   the live index.

No layout model (Docling etc.) or GPU is needed. The source is clean server-rendered HTML whose headings and tables
already give the structure, and embeddings run on CPU in seconds.

### Refreshing content

```bash
python -m app.ingest                     # re-crawl and rebuild (skips the rebuild if nothing changed)
curl -X POST https://<host>/api/v1/admin/refresh -H "Authorization: Bearer $API_KEY"
```

The change check hashes the *parsed* text per page, so tokens and timestamps that change on every page load don't
trigger rebuilds.

## Tools and models

| Part | Choice | Why |
|---|---|---|
| API | FastAPI + Uvicorn | small, typed, async-ready |
| LLM (answer) | Claude Opus 5.5 | accuracy and following "only from context" rules matter most here |
| LLM (router) | Claude Haiku 5.5 | fast, cheap rewrite/classify step |
| Provider switch | `LLM_PROVIDER=anthropic\|openai` | `openai` also covers OpenRouter, Ollama and vLLM via `OPENAI_BASE_URL` |
| Embeddings | fastembed `bge-small-en-v1.5` + BM25 | local, free, no GPU. BM25 catches exact terms such as "adenocarcinoma" |
| Vector store | Qdrant local mode | hybrid search + RRF built in, no extra server for 117 chunks |
| Storage | SQLite | unanswered questions and leads |
| UI | one static HTML file | no build step. Chat history stays in the browser, so the server is stateless |

LLM providers sit behind one small interface (`app/adapters/protocols.py`). Each adapter returns a validated
pydantic object, so the rest of the code doesn't care which provider answered. The Anthropic adapter uses the
official SDK with structured outputs, prompt caching and server-side refusal fallback.

## Project layout

```
app/
  adapters/     LLM port + Anthropic / OpenAI-compatible adapters
  api/v1/       chat, leads, admin (refresh, unanswered, leads), health
  core/         settings, logging, API-key auth
  ingest/       crawler → parser → chunker  (python -m app.ingest)
  prompts/      router + answer prompts
  schemas/      request/response and LLM output models
  services/     index, chat pipeline, guards, store
static/         chat UI
evals/          question set + runner → TEST_RESULTS.md
tests/          parser, guards and pipeline tests (offline, fake LLM)
```

## Run locally

```bash
uv venv -p 3.11 .venv && source .venv/bin/activate
uv pip install -r requirements-dev.txt
cp .env.example .env            # set ANTHROPIC_API_KEY (and API_KEYS for admin endpoints)
python -m app.ingest            # crawl the 7 pages (~25s at 3s per page) and build the index
python runner.py --reload       # http://localhost:8000
```

Using OpenAI or OpenRouter instead of Claude only takes env changes:

```bash
LLM_PROVIDER=openai OPENAI_API_KEY=... ANSWER_MODEL=gpt-4.1 ROUTER_MODEL=gpt-4.1-mini python runner.py
```

## Tests and evals

```bash
pytest                          # offline: parser, promo-price stripping, guards, pipeline with a fake LLM
python evals/run_eval.py --url http://localhost:8000   # 18 questions against a running bot → TEST_RESULTS.md
```

The eval checks are rules, not an LLM judge: required amounts present, forbidden amounts absent, the expected source
page cited, intent, and lead form. See `evals/questions.yaml`.

## API

| Method | Path | |
|---|---|---|
| POST | `/api/v1/chat` | `{message, history[], channel}` → `{answer, sources[], answered, intent, show_lead_form}` |
| POST | `/api/v1/leads` | `{name, email, question}` |
| POST | `/api/v1/admin/refresh` | re-crawl + rebuild (Bearer API key) |
| GET | `/api/v1/admin/unanswered` | questions the bot couldn't answer (Bearer API key) |
| GET | `/api/v1/admin/leads` | captured leads (Bearer API key) |
| GET | `/api/v1/health` | status and chunk count |

## Deployment

Docker Compose on a small VPS: the app plus Caddy for automatic HTTPS. CI/CD runs on GitHub Actions:

- `ci.yml`: tests on every pull request.
- `release.yml`, on every push to `main`: tests run, then the commit deploys over SSH (`git checkout <sha>` →
  `docker compose up -d --build` → Caddy reload → health check). In parallel,
  [release-please](https://github.com/googleapis/release-please) updates its release PR from conventional commits,
  merges it automatically and tags the version. During the container swap Caddy holds requests, so users see a
  slower reply instead of an error.

Secrets are never in the repo: the server keeps its own `.env`, and Actions only needs `SSH_HOST`, `SSH_USER` and
`SSH_KEY`.
