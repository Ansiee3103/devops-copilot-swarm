# 🚀 DevOps Copilot Swarm

> Risk-Aware Deployment & Self-Healing Control Plane

A production-grade multi-agent AI system that makes microservice deployments
intelligent, risk-aware, and autonomous.

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20RDS%20%7C%20ECR-orange)
![License](https://img.shields.io/badge/license-MIT-blue)

## ✨ Features

- 🧠 **Orchestrator Agent** — Plans deployments using GitHub context
- 🏗️ **Builder Agent** — Generates production Dockerfiles, K8s manifests, CI/CD
- 🔍 **Blast Radius Agent** — Predicts risk score and blocks dangerous deploys
- 🔧 **AutoHealer Agent** — Detects and fixes failures autonomously
- 🤖 **Multi-LLM Routing** — Groq → OpenCode → Mistral → Cohere failover
- 📊 **ML Risk Model** — Learns from deployment history
- 💰 **Cost Intelligence** — Estimates cloud costs per deployment
- 🔒 **Compliance Engine** — SOC2, ISO27001, HIPAA checks
- 🔌 **Plugin System** — Extensible with Slack, PagerDuty, Datadog

## 🏗️ Architecture

┌─────────────────────────────────────┐

│        Dashboard (HTTPS)            │

└──────────────┬──────────────────────┘

│

┌──────────────▼──────────────────────┐

│    FastAPI Backend (EC2 t3.small)   │

│    JWT Auth + RBAC + Rate Limiting  │

└──────┬───────────────┬──────────────┘

│               │

┌──────▼──────┐  ┌─────▼────────────┐

│  PostgreSQL  │  │  AI Agent Pool   │

│  (RDS)      │  │  Groq/Mistral/   │

└─────────────┘  │  Cohere/OpenCode │

                 └──────────────────┘

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker
- AWS CLI configured
- API keys: Groq, Mistral, Cohere

### Local Development

```bash
# Clone repo
git clone https://github.com/ansiee3103/devops-copilot-swarm
cd devops-copilot-swarm

# Setup
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Start services
docker start devops-postgres devops-redis

# Run
python run.py
```

Open: `http://localhost:8080/dashboard/index.html`

### Production (AWS)

```bash
# Deploy to AWS
./aws/deploy.sh

# Or push to main branch for auto-deploy via GitHub Actions
git push origin main
```

## 🌐 Live Demo

Dashboard: `https://<EC2_PUBLIC_IP>.nip.io/dashboard/index.html`

API Docs:  `https://<EC2_PUBLIC_IP>.nip.io/docs`

Health:    `https://<EC2_PUBLIC_IP>.nip.io/health`

Login:     `admin` / `admin123`

## 📊 API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login |
| POST | `/api/v1/deploy` | Trigger deployment |
| GET | `/api/v1/status/{id}` | Deployment status |
| GET | `/api/v1/history` | Deployment history |
| GET | `/api/v1/stats` | Analytics |
| GET | `/api/v1/cluster/health` | K8s health |
| POST | `/api/v1/cluster/chat` | NL cluster queries |
| GET | `/api/v1/ml/predict` | Risk prediction |
| GET | `/api/v1/cost/estimate` | Cost estimate |
| POST | `/api/v1/compliance/check` | Compliance audit |

## 🧪 Testing

```bash
pytest tests/ -v
```

## 🏢 SaaS Plans

| Plan | Price | Deployments |
|------|-------|-------------|
| Free | $0/mo | 10/month    |
| Pro | $29/mo | 100/month   |
| Enterprise | $99/mo | Unlimited |

## 🛠️ Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Celery
- **Database:** PostgreSQL (RDS), Redis
- **AI:** Groq, Mistral, Cohere, OpenCode
- **Cloud:** AWS EC2, RDS, ECR
- **ML:** scikit-learn, Gradient Boosting
- **Monitoring:** CloudWatch, Prometheus
- **CI/CD:** GitHub Actions

## 📄 License

MIT License — see [LICENSE](LICENSE)