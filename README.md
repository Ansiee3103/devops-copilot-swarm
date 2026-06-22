# 🚀 DevOps Copilot Swarm

> Risk-Aware Deployment & Self-Healing Control Plane

## Overview
DevOps Copilot Swarm is a multi-agent AI system that makes
microservice deployments both risk-aware and self-healing.

## Architecture
- **Orchestrator Agent** — Plans deployments
- **Builder Agent**      — Generates configs
- **Blast Radius Agent** — Predicts risk
- **AutoHealer Agent**   — Fixes failures

## Quick Start

### Prerequisites
- Python 3.10+
- Docker Desktop
- Minikube
- Groq API Key

### Installation
\`\`\`bash
git clone https://github.com/your/devops-copilot-swarm
cd devops-copilot-swarm
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python run.py
\`\`\`

### Access
- Dashboard : http://localhost:8000/dashboard/index.html
- API Docs  : http://localhost:8000/docs
- Health    : http://localhost:8000/health

### Default Credentials
- Username: admin
- Password: admin123

## API Reference
See /docs for full interactive API documentation

## Tech Stack
- FastAPI, SQLAlchemy, SQLite
- Groq LLM (llama-3.3-70b-versatile)
- Kubernetes, Docker
- GitHub API