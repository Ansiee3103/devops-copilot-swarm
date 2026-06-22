import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="d:/devops-copilot-swarm/.env")

def test_groq():
    print("Testing Groq...")
    key = os.getenv("GROQ_API_KEY")
    print(f"Key preview: {key[:8]}...{key[-8:] if key else ''}")
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json"
            },
            json = {
                "model":      "llama-3.3-70b-versatile",
                "messages":   [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            },
            timeout = 10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Groq failed: {e}")

def test_opencode():
    print("\nTesting OpenCode...")
    key = os.getenv("OPENCODE_API_KEY")
    print(f"Key preview: {key[:8]}...{key[-8:] if key else ''}")
    try:
        response = requests.post(
            "https://opencode.ai/zen/v1/chat/completions",
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json"
            },
            json = {
                "model":      os.getenv("OPENCODE_MODEL", "deepseek-v4-flash-free"),
                "messages":   [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            },
            timeout = 10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"OpenCode failed: {e}")

def test_mistral():
    print("\nTesting Mistral...")
    key = os.getenv("MISTRAL_API_KEY")
    print(f"Key preview: {key[:8]}...{key[-8:] if key else ''}")
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json"
            },
            json = {
                "model":      "mistral-small-latest",
                "messages":   [{"role": "user", "content": "Hello"}],
                "max_tokens": 10
            },
            timeout = 10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Mistral failed: {e}")

def test_cohere():
    print("\nTesting Cohere...")
    key = os.getenv("COHERE_API_KEY")
    print(f"Key preview: {key[:8]}...{key[-8:] if key else ''}")
    try:
        response = requests.post(
            "https://api.cohere.com/v2/chat",
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json"
            },
            json = {
                "model":    "command-r",
                "messages": [{"role": "user", "content": "Hello"}]
            },
            timeout = 10
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Cohere failed: {e}")

if __name__ == "__main__":
    test_groq()
    test_opencode()
    test_mistral()
    test_cohere()
