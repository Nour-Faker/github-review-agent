# GitHub Review Agent 🤖

> Agent IA de Revue de Code Automatique pour les Pull Requests GitHub
> Développé par **Nour Faker** — Stage Été 2026 — Smartovate LTD

[![CI](https://github.com/Nour-Faker/github-review-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Nour-Faker/github-review-agent/actions)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat&logo=python)](https://python.org)
[![Azure](https://img.shields.io/badge/Azure-App%20Service-0078D4?style=flat&logo=microsoft-azure)](https://azure.microsoft.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker)](https://docker.com)

**Live:** http://github-review-agent-nour.azurewebsites.net

---

## What it does

- Listens for GitHub webhook events (PR opened, synchronized)
- Extracts diff hunks from the PR
- Sends each hunk to Azure OpenAI GPT-5-mini for analysis
- Posts inline comments with severity labels: 🔴 Critical · 🟠 Warning · 💡 Info
- Responds to `@ai-reviewer` mentions with contextual answers
- Tracks all reviews in PostgreSQL with critical/warning counters
- Exposes a React dashboard with real-time metrics

---

## Architecture

GitHub Webhook → FastAPI → DiffExtractor → LLMAnalyzer (Azure OpenAI)
↓
GitHubCommenter ← AnalysisResult (severity + category)
↓
PostgreSQL (reviews table)
↓
React Dashboard (/api/metrics, /api/reviews)


---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.10 |
| Database | PostgreSQL + psycopg2 |
| LLM | Azure OpenAI GPT-5-mini |
| Auth | JWT (python-jose) |
| Security | HMAC-SHA256 webhook verification |
| Frontend | React, Recharts, Axios |
| Deployment | Docker, Azure App Service (Sweden Central) |
| CI | GitHub Actions (pytest, 37 tests) |

---

## Features

| Feature | Ticket | Description |
|---|---|---|
| Webhook receiver | NF-3 | FastAPI + HMAC-SHA256 verification |
| Diff extraction | NF-5 | Parse hunks via GitHub API |
| LLM analysis | NF-6 | Azure OpenAI GPT-5-mini, structured JSON output |
| Inline comments | NF-8 | Severity-tagged PR comments |
| @ai-reviewer | NF-9 | Mention handler with diff context |
| Rate limiting | NF-13 | Exponential backoff retry |
| Bot loop prevention | NF-15 | Bot sender detection |
| Structured output | NF-38 | ReviewComment dataclass with severity/category/confidence |
| Split counters | NF-39 | critical_count + warning_count in DB |
| CI pipeline | NF-42 | GitHub Actions, 37 tests |
| Severity emoji | NF-43 | 🔴/🟠/💡 prefix on every comment |

---

## Local setup

```bash
git clone https://github.com/Nour-Faker/github-review-agent
cd github-review-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

---

## Environment variables

| Variable | Description |
|---|---|
| `WEBHOOK_SECRET` | GitHub webhook secret |
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name (e.g. gpt-5-mini) |
| `DATABASE_URL` | PostgreSQL connection string |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) |
| `JWT_SECRET` | Secret for JWT signing |
| `LLM_PROVIDER` | `azure` or `openai` |

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/webhook` | GitHub webhook receiver |
| GET | `/health` | Health check + dependency status |
| GET | `/api/metrics` | Total PRs, bugs, critical/warning counts |
| GET | `/api/reviews` | Review history from DB |
| GET | `/api/repos` | List GitHub repos |
| POST | `/api/trigger/{owner}/{repo}/{pr}` | Manually trigger a review |
| POST | `/api/summarize/{owner}/{repo}/{pr}` | AI summary of a PR |

---

## Tests

```bash
python -m pytest tests/ -v
# 37 tests — DiffExtractor, webhook, process, integration
```

---

## Deployment

```bash
docker build -t github-review-agent .
az webapp deploy --resource-group nour --name github-review-agent-nour
```

---

## Sprints

| Sprint | Période | Tickets |
|---|---|---|
| Sprint 1 | 1–14 Juil 2026 | NF-2, NF-3 — Webhook receiver |
| Sprint 2 | 15–28 Juil 2026 | NF-5, NF-6, NF-13 — Diff + LLM |
| Sprint 3 | 29 Juil–11 Août 2026 | NF-8, NF-9, NF-14, NF-15 — Commenter |
| Sprint 4 | 12–25 Août 2026 | NF-11, NF-38 à NF-45 — Deploy + quality |

---

## Author

**Nour Faker** — 1ère année Génie Informatique, ENICarthage
Stage Été 2026 — Smartovate LTD
Supervisor: M. Abdelkhalek Bakkari, CEO & Founder
GitHub: [@Nour-Faker](https://github.com/Nour-Faker)