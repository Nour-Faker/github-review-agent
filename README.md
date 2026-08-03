# GitHub Review Agent 🤖

> AI-powered automated code review agent for GitHub Pull Requests  
> Built by **Nour Faker** — Summer Internship 2026 — Smartovate LTD

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green)
![Azure](https://img.shields.io/badge/Azure-OpenAI-0078D4?logo=microsoft-azure)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 📸 Dashboard Preview

| Dashboard | Reviews | Analytics | Settings |
|-----------|---------|-----------|----------|
| KPI cards, activity chart, PR list | Review history with bug detection | Token usage, weekly overview | Agent config, service status |

> Live dashboard built with React + Recharts, connected to FastAPI backend deployed on Azure.

---

## 📋 What It Does

GitHub Review Agent is a production AI agent that automatically reviews Pull Requests and posts intelligent code review comments powered by GPT-5-mini via Azure OpenAI.

When a developer opens or updates a PR, or mentions `@ai-reviewer` in a comment, the agent:

1. Receives the GitHub event via secured webhook (HMAC-SHA256)
2. Validates the request authenticity
3. Extracts the code diff from the PR
4. Sends the diff to GPT-5-mini for analysis
5. Posts a structured review comment directly on the PR with detected bugs, security issues, and suggestions

---

## 🏗️ Architecture

```
GitHub PR Event
      │
      ▼
POST /webhook (FastAPI)
      │
      ├── security.py        → HMAC-SHA256 signature verification
      ├── rate_limiter.py    → Token quota + retry logic
      ├── diff_extractor.py  → Parse and extract code changes
      ├── llm_analyzer.py    → GPT-5-mini via Azure OpenAI
      └── commenter.py       → Post review comment on GitHub PR
```

### Component Diagram

```
github-review-agent/
├── app/
│   ├── main.py            # FastAPI entry point — routes + CORS
│   ├── config.py          # AppSettings — environment variables
│   ├── security.py        # HMAC-SHA256 webhook verification
│   ├── webhook.py         # WebhookHandler — event orchestration
│   ├── diff_extractor.py  # NF-5 — Diff extraction and parsing
│   ├── rate_limiter.py    # NF-13 — Rate limiting + LLM retry
│   ├── llm_analyzer.py    # NF-6 — LLM code analysis
│   └── commenter.py       # NF-8 — GitHub comment publisher
├── .env                   # Secrets (never committed)
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- GitHub account with a configured GitHub App
- Azure OpenAI access (GPT-5-mini deployment)

### 1. Clone the repository

```bash
git clone https://github.com/Nour-Faker/github-review-agent.git
cd github-review-agent
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file at the root:

```env
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=your_webhook_secret
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
```

> ⚠️ Never commit `.env` to Git. It is already excluded via `.gitignore`.

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Verify it's running

```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "1.0", "model": "gpt-5-mini"}
```

---

## 🐳 Docker

```bash
# Build
docker build -t github-review-agent .

# Run
docker run -p 8000:8000 --env-file .env github-review-agent
```

---

## ☁️ Deployment (Azure)

This project is deployed on **Azure Web Apps** using the Azure CLI:

```bash
az webapp up \
  --name github-review-agent-nour \
  --resource-group nour \
  --location swedencentral \
  --runtime PYTHON:3.11
```

Set environment variables in Azure:

```bash
az webapp config appsettings set \
  --name github-review-agent-nour \
  --resource-group nour \
  --settings GITHUB_TOKEN=... AZURE_OPENAI_KEY=...
```

**Production URL:**  
`https://github-review-agent-nour.azurewebsites.net`

---

## 📡 API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/webhook` | Receives GitHub webhook events |
| `GET` | `/health` | Server health check |
| `GET` | `/api/repos` | List all GitHub repositories |
| `GET` | `/api/repos/{owner}/{repo}/pulls` | List PRs for a repository |
| `GET` | `/api/metrics` | Review statistics (total, analysed, bugs) |
| `GET` | `/api/reviews` | Review history |
| `GET` | `/docs` | Interactive API documentation (Swagger UI) |

---

## 🔒 Security

### HMAC-SHA256 Webhook Verification

Every incoming webhook request is verified before processing:

- GitHub signs each request with `X-Hub-Signature-256`
- The server recomputes the signature using the shared secret
- `hmac.compare_digest()` prevents timing attacks
- Returns HTTP 401 if the signature is invalid

```python
# security.py
def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Bot Loop Prevention (NF-15)

The agent detects its own comments to prevent infinite reply loops:

```python
# webhook.py
if comment_author == "smartovate-review-agent[bot]":
    return  # Ignore own comments
```

### Secrets Management

- All credentials stored in `.env` (excluded from Git)
- Production secrets stored in Azure App Settings
- No hardcoded keys anywhere in the codebase

---

## 🧠 How the LLM Analysis Works

```python
# llm_analyzer.py
def analyze(self, diff: str) -> str:
    prompt = f"""
    You are a senior software engineer reviewing a Pull Request.
    Analyze this code diff and identify:
    - Security vulnerabilities
    - Bugs and logic errors
    - Performance issues
    - Code quality improvements
    
    Code diff:
    {diff}
    """
    response = self.client.chat.completions.create(
        model=self.deployment,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=500
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        return "Analysis complete — no critical issues detected in this diff."
    return content
```

---

## 📊 Features

| Feature | Status | Description |
|---------|--------|-------------|
| Webhook receiver | ✅ | Receives `pull_request` and `issue_comment` events |
| HMAC-SHA256 security | ✅ | Verifies every incoming request |
| Diff extraction | ✅ | Parses GitHub unified diffs |
| LLM code analysis | ✅ | GPT-5-mini via Azure OpenAI |
| PR comment posting | ✅ | Posts review directly on the PR |
| `@ai-reviewer` mention | ✅ | Trigger analysis by mentioning the bot |
| Bot loop prevention | ✅ | Ignores its own comments |
| Rate limiting | ✅ | Token quota + exponential retry |
| React dashboard | ✅ | Live monitoring of reviews and metrics |
| Azure deployment | ✅ | Deployed on Azure Web Apps |
| Docker support | ✅ | Containerized for portability |

---

## 🗂️ Sprint History

### ✅ Sprint 1 — Backend Foundation (1–14 Jul 2026)

| Ticket | Description | Status |
|--------|-------------|--------|
| NF-2 | GitHub App setup and webhook configuration | ✅ Done |
| NF-3 | FastAPI server with health endpoint | ✅ Done |

### ✅ Sprint 2 — Core Agent Logic (15–28 Jul 2026)

| Ticket | Description | Status |
|--------|-------------|--------|
| NF-5 | Code diff extraction and parsing | ✅ Done |
| NF-6 | LLM integration via Azure OpenAI | ✅ Done |
| NF-13 | Token limit handling + LLM retry logic | ✅ Done |

### ✅ Sprint 3 — Production & Dashboard (29 Jul–3 Aug 2026)

| Ticket | Description | Status |
|--------|-------------|--------|
| NF-8 | GitHub PR comment publisher | ✅ Done |
| NF-9 | `@ai-reviewer` mention handler | ✅ Done |
| NF-11 | Dockerfile for containerization | ✅ Done |
| NF-14 | Fix invalid line comment placement | ✅ Done |
| NF-15 | Bot infinite reply loop prevention | ✅ Done |

---

## 🛠️ Tech Stack

| Technology | Version | Role |
|------------|---------|------|
| Python | 3.11 | Core language |
| FastAPI | 0.111+ | REST API + webhook server |
| Uvicorn | 0.29+ | ASGI server |
| Azure OpenAI GPT-5-mini | — | Code analysis LLM |
| GitHub API v3 | — | Fetch diffs + post comments |
| httpx | — | Async HTTP client |
| python-dotenv | 1.0+ | Environment variable management |
| React | 18+ | Monitoring dashboard |
| Recharts | — | Analytics charts |
| Azure Web Apps | — | Cloud deployment |
| Docker | — | Containerization |

---

## 🧪 Testing the Agent

### Option 1 — Trigger via PR

1. Open a Pull Request in any monitored repository
2. The agent automatically analyses the diff and posts a review comment

### Option 2 — Mention the bot

In any PR comment, write:

```
@ai-reviewer what are the security issues in this code?
```

The agent will respond with an AI-generated review.

### Option 3 — Dashboard

Open the React dashboard, select a repository, and click **Run Agent** on any PR.

---

## 📁 Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | ✅ | GitHub Personal Access Token |
| `GITHUB_WEBHOOK_SECRET` | ✅ | Secret for HMAC-SHA256 verification |
| `AZURE_OPENAI_ENDPOINT` | ✅ | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_KEY` | ✅ | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ | Model deployment name (e.g. `gpt-5-mini`) |

---

## 👩‍💻 Author

**Nour Faker**  
1st Year Computer Engineering Student — ENICarthage  
Summer Internship 2026 — Smartovate LTD  
GitHub: [@Nour-Faker](https://github.com/Nour-Faker)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*GitHub Review Agent · Smartovate LTD · Nour Faker · 2026*