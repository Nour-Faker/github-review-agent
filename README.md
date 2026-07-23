# GitHub Review Agent 🤖

> Agent IA de revue de code automatique pour les Pull Requests GitHub  
> Développé par **Nour Faker** — Stage Été 2026 — Smartovate LTD

---

## 📋 Description

GitHub Review Agent est un agent IA qui analyse automatiquement les Pull Requests GitHub et publie des commentaires de revue de code générés par GPT-4o (Azure OpenAI).

Quand un développeur ouvre ou met à jour une PR, l'agent :
1. Reçoit l'événement via webhook GitHub
2. Vérifie l'authenticité de la requête (HMAC-SHA256)
3. Extrait les modifications de code (diff)
4. Envoie le code à GPT-4o pour analyse
5. Publie un commentaire de revue directement sur la PR

---

## 🏗️ Architecture

```
GitHub PR → Webhook → FastAPI Server → DiffExtractor → LLMAnalyzer → GitHub Comment
```

### Diagramme des composants

```
WebhookHandler
├── security.py       → Vérification HMAC-SHA256
├── rate_limiter.py   → Quota par sender + retry LLM
├── diff_extractor.py → Extraction et parsing du diff
├── llm_analyzer.py   → Analyse GPT-4o via Azure OpenAI
└── commenter.py      → Publication commentaires PR (Sprint 3)
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
│   ├── webhook.py         # WebhookHandler — orchestration
│   ├── diff_extractor.py  # NF-5 — Extraction des diffs
│   ├── rate_limiter.py    # NF-13 — Rate limiting + retry
│   ├── llm_analyzer.py    # NF-6 — Analyse LLM
│   └── commenter.py       # NF-8 — Publication commentaires (Sprint 3)
├── .env                   # Variables sensibles (non versionné)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Installation

### Prérequis
- Python 3.11+
- Compte GitHub avec GitHub App configurée
- Accès Azure OpenAI (Smartovate LTD)

### 1. Cloner le repo
```bash
git clone https://github.com/Nour-Faker/github-review-agent.git
cd github-review-agent
```

### 2. Créer l'environnement virtuel
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement
Créer un fichier `.env` à la racine :
```env
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...
AZURE_OPENAI_ENDPOINT=https://agent-ia-visualisation.openai.azure.com/
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### 5. Lancer le serveur
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Vérifier le serveur
```
GET http://localhost:8000/health
→ {"status": "ok"}
```

---

## 📡 Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/webhook` | Reçoit les événements GitHub |
| `GET` | `/health` | Vérification du statut du serveur |

---

## 🔒 Sécurité

### Vérification HMAC-SHA256
Chaque requête webhook est vérifiée avec une signature HMAC-SHA256 :
- GitHub envoie le header `X-Hub-Signature-256`
- Le serveur recalcule la signature avec le secret partagé
- `hmac.compare_digest()` protège contre les timing attacks
- Requête rejetée avec HTTP 401 si la signature est invalide

### Variables sensibles
- Toutes les clés sont stockées dans `.env`
- Le fichier `.env` est exclu de Git via `.gitignore`
- Jamais de clé dans le code source

---

## 🗂️ Sprints

### ✅ Sprint 1 (S1-S2) — 1–14 Juil 2026
| Ticket | Description | Statut |
|--------|-------------|--------|
| NF-2 | Création de la GitHub App | ✅ Terminé |
| NF-3 | Mise en place du serveur backend | ✅ Terminé |

### ✅ Sprint 2 (S3-S4) — 15–28 Juil 2026
| Ticket | Description | Statut |
|--------|-------------|--------|
| NF-5 | Extraction des modifications de code (Diffs) | ✅ Terminé |
| NF-6 | Analyse du code par le LLM | ✅ Terminé |
| NF-13 | Dépassement de la limite de tokens du LLM | ✅ Terminé |

### 🔄 Sprint 3 (S5-S6) — 29 Juil–11 Août 2026
| Ticket | Description | Statut |
|--------|-------------|--------|
| NF-8 | Publication des commentaires sur la PR | 🔄 En cours |
| NF-9 | Gestion des commandes textuelles | 🔄 En cours |
| NF-14 | Commentaires GitHub placés sur des lignes invalides | 🔄 En cours |
| NF-15 | Boucle infinie de réponses aux commentaires | 🔄 En cours |

---

## 🛠️ Stack technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11 | Langage principal |
| FastAPI | 0.111+ | Serveur webhook |
| Uvicorn | 0.29+ | Serveur ASGI |
| Azure OpenAI GPT-4o | — | Analyse du code |
| GitHub API | v3 | Fetch diff + post commentaires |
| httpx | — | Requêtes HTTP async |
| python-dotenv | 1.0+ | Variables d'environnement |

---

## 📊 Diagrammes UML

Les diagrammes UML complets sont disponibles dans le rapport technique :
- Cas d'utilisation
- Classes / Composants
- Objets
- Séquence
- Collaboration
- États-Transitions
- Activités

---

## 👩‍💻 Auteur

**Nour Faker**  
Étudiante 1ère année — Génie Informatique  
ENICarthage | Stage Été 2026 — Smartovate LTD  
GitHub : [@Nour-Faker](https://github.com/Nour-Faker)

---

*Smartovate LTD — Agent IA de Revue de Code — 2026*