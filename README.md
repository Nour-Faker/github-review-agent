# 🤖 GitHub Review Agent

> **Agent IA de Revue de Code Automatique pour les Pull Requests GitHub**  
> Développé par **Nour Faker** — Stage Été 2026 — Smartovate LTD

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)](https://python.org)
[![Azure](https://img.shields.io/badge/Azure-Container%20Apps-0078D4?style=flat&logo=microsoft-azure)](https://azure.microsoft.com)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat&logo=docker)](https://docker.com)
[![GPT-5-mini](https://img.shields.io/badge/LLM-GPT--5--mini-412991?style=flat&logo=openai)](https://openai.com)

---

## 📋 Description

GitHub Review Agent est un agent IA déployé en production sur **Azure Container Apps** qui analyse automatiquement les Pull Requests GitHub et publie des commentaires de revue de code générés par **GPT-5-mini (Azure OpenAI)**.

Quand un développeur ouvre ou met à jour une PR, l'agent :

1. 📥 Reçoit l'événement via **webhook GitHub** (HTTPS sécurisé)
2. 🔐 Vérifie l'authenticité de la requête (**HMAC-SHA256**)
3. 📊 Extrait les modifications de code (**diff par fichier**)
4. 🧠 Envoie le code à **GPT-5-mini** pour analyse
5. 💬 Publie un **commentaire de revue** directement sur la PR

---

## 🚀 Demo en production

**URL de l'agent :**
```
https://github-review-agent.wonderfultree-b6fdb6ec.eastus.azurecontainerapps.io
```

**Health check :**
```
GET /health → {"status": "ok"}
```

**API Docs (Swagger) :**
```
GET /docs
```

---

## 🏗️ Architecture

```
GitHub PR Event
      ↓
GitHub Webhook (HTTPS)
      ↓
FastAPI Server (Azure Container Apps)
      ↓
┌─────────────────────────────────────┐
│  1. verify_signature() — HMAC-SHA256 │
│  2. is_bot_sender() — NF-15          │
│  3. check_quota() — NF-12            │
│  4. fetch_diff() — GitHub API        │
│  5. is_oversized() — NF-13           │
│  6. parse_hunks() — DiffExtractor    │
│  7. analyze_hunk() — LLMAnalyzer     │
│  8. post_review() — GitHubCommenter  │
└─────────────────────────────────────┘
      ↓
GitHub PR Comment (GPT-5-mini Analysis)
```

---

## 📁 Structure du projet

```
github-review-agent/
├── app/
│   ├── __init__.py
│   ├── main.py            # Point d'entrée FastAPI
│   ├── config.py          # AppSettings — variables d'environnement
│   ├── security.py        # Vérification HMAC-SHA256
│   ├── webhook.py         # WebhookHandler — orchestration principale
│   ├── diff_extractor.py  # NF-5 — Extraction et parsing des diffs
│   ├── rate_limiter.py    # NF-12/13 — Rate limiting + retry LLM
│   ├── llm_analyzer.py    # NF-6 — Analyse code via Azure OpenAI
│   └── commenter.py       # NF-8 — Publication commentaires GitHub
├── Dockerfile             # NF-11 — Conteneurisation
├── .dockerignore
├── .gitignore
├── requirements.txt
├── test_agent.py          # Tests du pipeline complet
└── README.md
```

---

## ⚡ Fonctionnalités

| Feature | Ticket | Description |
|---------|--------|-------------|
| GitHub App | NF-2 | App configurée avec webhooks et permissions PR |
| FastAPI Server | NF-3 | Endpoint `/webhook` + vérification HMAC-SHA256 |
| Extraction Diffs | NF-5 | Récupération et parsing du diff via GitHub API |
| Analyse LLM | NF-6 | Analyse bugs/sécurité/mauvaises pratiques via GPT-5-mini |
| Publication | NF-8 | Commentaires de revue automatiques sur la PR |
| @ai-reviewer | NF-9 | Réponse aux mentions dans les commentaires |
| Rate limiting | NF-12 | Limite de requêtes par sender (100/heure) |
| Token limit | NF-13 | Retry avec backoff exponentiel si rate limit LLM |
| Ligne invalide | NF-14 | CommentValidator avant chaque post |
| Anti-boucle | NF-15 | Détection et ignore des événements bot |
| Déploiement | NF-11 | Docker + Azure Container Registry + Container Apps |

---

## 🛠️ Installation locale

### Prérequis
- Python 3.11+
- Docker Desktop
- Compte GitHub avec GitHub App configurée
- Accès Azure OpenAI

### 1. Cloner le repo
```bash
git clone https://github.com/Nour-Faker/github-review-agent.git
cd github-review-agent
```

### 2. Environnement virtuel
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 3. Dépendances
```bash
pip install -r requirements.txt
```

### 4. Variables d'environnement
Créer `.env` à la racine :
```env
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
```

### 5. Lancer le serveur
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Tester le pipeline
```bash
python test_agent.py
```

---

## 🐳 Déploiement Azure

### Build et push Docker
```bash
docker build -t github-review-agent .
az acr login --name nourfakeracr
docker tag github-review-agent nourfakeracr.azurecr.io/github-review-agent:latest
docker push nourfakeracr.azurecr.io/github-review-agent:latest
```

### Deploy sur Azure Container Apps
```bash
az containerapp update \
  --name github-review-agent \
  --resource-group Nour \
  --image nourfakeracr.azurecr.io/github-review-agent:latest
```

---

## 🔒 Sécurité

### HMAC-SHA256
Chaque webhook GitHub est vérifié cryptographiquement :
- GitHub envoie `X-Hub-Signature-256`
- Le serveur recalcule avec le secret partagé
- `hmac.compare_digest()` protège contre les timing attacks
- Requête rejetée HTTP 401 si signature invalide

### Secrets
- Toutes les clés stockées dans Azure Container Apps Secrets
- Jamais de secrets dans le code source
- `.env` exclu de Git via `.gitignore`

---

## 📊 Cas d'utilisation

### PR normale
```
Développeur ouvre PR → Agent analyse → Commentaire détaillé posté
```

### PR trop grande (> 1000 lignes)
```
Développeur ouvre PR → Agent détecte taille → Message d'avertissement
"⚠️ Cette PR dépasse 1000 lignes — analyse impossible. Merci de découper."
```

### Mention @ai-reviewer
```
Développeur commente "@ai-reviewer explique ce code"
→ Agent répond automatiquement avec analyse GPT-5-mini
```

---

## 🗂️ Sprints

| Sprint | Période | Tickets | Statut |
|--------|---------|---------|--------|
| Sprint 1 (S1-S2) | 1–14 Juil 2026 | NF-2, NF-3 | ✅ Terminé |
| Sprint 2 (S3-S4) | 15–28 Juil 2026 | NF-5, NF-6, NF-13 | ✅ Terminé |
| Sprint 3 (S5-S6) | 29 Juil–11 Août 2026 | NF-8, NF-9, NF-14, NF-15 | ✅ Terminé |
| Sprint 4 (S7-S8) | 12–25 Août 2026 | NF-11, NF-12 | ✅ Terminé |

---

## 🛠️ Stack technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11 | Langage principal |
| FastAPI | 0.111+ | Serveur webhook REST |
| Uvicorn | 0.29+ | Serveur ASGI production |
| Azure OpenAI GPT-5-mini | 2025-08-07 | Analyse du code |
| Azure Container Apps | — | Hébergement production |
| Azure Container Registry | Basic | Stockage images Docker |
| Docker | — | Conteneurisation |
| GitHub App | — | Webhooks + permissions PR |
| GitHub API v3 | — | Fetch diff + post commentaires |
| httpx | 0.28+ | Requêtes HTTP async |
| python-dotenv | 1.0+ | Variables d'environnement |

---

## 👩‍💻 Auteur

**Nour Faker**  
Étudiante 1ère année — Génie Informatique  
ENICarthage | Stage Été 2026 — Smartovate LTD  
GitHub : [@Nour-Faker](https://github.com/Nour-Faker)

---

*© 2026 Smartovate LTD — Agent IA de Revue de Code — Tous droits réservés*
HEREDOC
echo "Done"
