<div align="center">

# 🤖 DevOps Copilot Swarm

**Risk-Aware Deployment & Self-Healing Control Plane**

[![Tests](https://github.com/ansiee3103/devops-copilot-swarm/actions/workflows/deploy.yml/badge.svg)](https://github.com/ansiee3103/devops-copilot-swarm/actions)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![AWS](https://img.shields.io/badge/deployed-AWS-orange.svg)](https://aws.amazon.com)

*A production-grade multi-agent AI system that makes microservice deployments
intelligent, risk-aware, and autonomous.*

[Live Demo](http://localhost:8080/dashboard/index.html) •
[API Docs](http://localhost:8080/docs) •
[Report Bug](https://github.com/ansiee3103/devops-copilot-swarm/issues)

</div>

---

## ✨ What It Does

DevOps Copilot Swarm deploys your microservices **intelligently**:

1. **Analyzes** your GitHub repo and plans the deployment
2. **Generates** production Dockerfiles, K8s manifests, and CI/CD pipelines
3. **Predicts** blast radius and blocks risky deployments automatically
4. **Heals** failures autonomously without human intervention
5. **Learns** from every deployment to get smarter over time

## 🏗️ Architecture

                ┌─────────────────────┐
                │   Dashboard (HTTPS) │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   FastAPI Backend   │
                │  JWT + RBAC + Redis │
                └──┬──────────────┬───┘
                   │              │
          ┌────────▼──┐    ┌──────▼────────┐
          │PostgreSQL │    │  AI Agent Pool |
          │  (RDS)    │    │  ┌───────────┐ |
          └───────────┘    │  │Orchestrat.│ |
                           │  │Builder    │ │
                           │  │BlastRadius│ │
                           │  │AutoHealer │ │
                           │  └───────────┘ │
                           └────────────────┘

## 🤖 AI Agents

| Agent                | Role                            |  Output                     |
|--------------------- |--------------------------------- |---------------------------- |
| 🧠 **Orchestrator** | Analyzes repo, plans deployment  | Deployment plan            |
| 🏗️ **Builder**      | Generates production configs     | Dockerfile, K8s, CI/CD     |
| 🔍 **Blast Radius** | Predicts risk & impact           | Risk score 0-10            |
| 🔧 **AutoHealer**   | Detects & fixes failures         | Healing report             |

## ⚡ Performance

Load Test Results (10 concurrent users, 5 minutes):

✅ Total Requests:  5,210

✅ Error Rate:      0.00%

✅ Avg Response:    147ms

✅ P95 Response:    599ms

✅ Throughput:      17+ req/sec

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker Desktop
- At least one LLM API key (Groq is free)

### Setup

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/devops-copilot-swarm
cd devops-copilot-swarm

# Install
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your GROQ_API_KEY to .env (free at console.groq.com)

# Start databases
docker run -d --name devops-postgres \
  -e POSTGRES_USER=devops \
  -e POSTGRES_PASSWORD=devops123 \
  -e POSTGRES_DB=devops_swarm \
  -p 5432:5432 postgres:15-alpine

docker run -d --name devops-redis \
  -p 6379:6379 redis:7-alpine

# Run
python run.py
```

Open: http://localhost:8080/dashboard/index.html

Login: `admin` / `admin123`

### Docker Compose (Recommended)

```bash
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

## 🌐 Deploy to AWS (Free Tier)

See [AWS Deployment Guide](docs/AWS_DEPLOYMENT.md)

## 🧪 Testing

```bash
# Unit tests
pytest tests/ -v

# Performance tests
pytest tests/load/performance_test.py -v -s

# Load tests (requires k6)
k6 run tests/load/k6_test.js
```

## 📡 API Reference

| Method | Endpoint                            | Description        |
|--------|-------------------------------------|--------------------|
| POST   | `/auth/login`                       | Authenticate       |
| POST   | `/api/v1/deploy`                    | Trigger deployment |
| GET    | `/api/v1/status/{id}`               | Real-time status   |
| GET    | `/api/v1/history`                   | Deployment history |
| GET    | `/api/v1/stats`                     | Analytics          |
| GET    | `/api/v1/aiops/anomaly/{service}`   | Anomaly detection  |
| POST   | `/api/v1/aiops/confidence`          | Confidence score   |
| GET    | `/api/v1/aiops/predict/window`      | Best deploy time   |
| POST   | `/api/v1/cluster/chat`              | NL cluster queries |

Full docs: https:yourip.nip.io/docs

## 🔌 Integrations

- ✅ **Slack** — Deployment alerts
- ✅ **Email** — Gmail SMTP
- ✅ **PagerDuty** — On-call routing
- ✅ **Microsoft Teams** — Enterprise notifications
- ✅ **GitHub** — Source analysis
- ✅ **Kubernetes** — Multi-cluster support

## 🛠️ Tech Stack

| Layer         | Technology                                             |
|---------------|--------------------------------------------------------|
| Backend       | FastAPI, Python 3.12                                   |
| Database      | PostgreSQL, Redis                                      |
| AI/ML         | Groq, Mistral, Cohere, scikit-learn                    |
| Cloud         | AWS EC2, RDS, ECR, CloudWatch                          |
| DevOps        | Docker, GitHub Actions                                 |
| Security      | JWT, bcrypt, RBAC                                      |
| Testing       | pytest, k6                                             |

## 📄 License

MIT License — see [LICENSE](LICENSE)

## 🙏 Acknowledgments

- [Google Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) — Demo microservices
- [FastAPI](https://fastapi.tiangolo.com) — Web framework
- [Groq](https://groq.com) — LLM inference
- [Anthropic Claude](https://anthropic.com) — AI assistance during development
- [Antigravity IDE](https://antigravity.com) — AI assistance during development

