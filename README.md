# GitHub Review Agent 🤖

AI-powered code review agent that automatically analyzes GitHub Pull Requests using Azure OpenAI and posts inline comments with severity-tagged feedback.

**Live:** http://github-review-agent-nour.azurewebsites.net

---

## What it does

- Listens for GitHub webhook events (PR opened, synchronized)
- Extracts diff hunks from the PR
- Sends each hunk to Azure OpenAI GPT-5-mini for analysis
- Posts inline comments on the PR with severity labels: 🔴 Critical · 🟠 Warning · 💡 Info
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

## Local setup

```bash
git clone https://github.com/Nour-Faker/github-review-agent
cd github-review-agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # fill in your values
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

![CI](https://github.com/Nour-Faker/github-review-agent/actions/workflows/ci.yml/badge.svg)

---

## Project

Built during a summer internship at **Smartovate Ltd** (July–August 2026).
Supervisor: M. Abdelkhalek Bakkari, CEO & Founder.
Student: Nour Faker, ENICarthage — Computer Engineering Year 1.