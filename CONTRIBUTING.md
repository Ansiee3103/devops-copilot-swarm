# Contributing to DevOps Copilot Swarm

We welcome contributions! Here's how to get started.

## 🚀 Quick Setup

```bash
git clone https://github.com/ansiee3103/devops-copilot-swarm
cd devops-copilot-swarm
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python run.py
```

## 🧪 Running Tests

```bash
pytest tests/ -v
```

## 📝 How to Contribute

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

## 🔧 Adding a New Agent

1. Create `agents/my_agent.py`
2. Follow the pattern in `agents/orchestrator.py`
3. Import in `backend/services/deployment_service.py`
4. Add tests in `tests/`

## 🔌 Adding a New LLM Provider

1. Add provider function in `utils/groq_client.py`
2. Add to `PROVIDERS` list
3. Add API key to `.env.example`

## 📋 Code Style

- Python: Follow PEP 8
- Use type hints where possible
- Add docstrings to functions
- Write tests for new features

## 🐛 Reporting Bugs

Open an issue with:
- Description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version)