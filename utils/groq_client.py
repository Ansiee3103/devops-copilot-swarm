import os
import time
import hashlib
import requests
from dotenv import load_dotenv
from backend.core.logger import get_logger

load_dotenv()
logger = get_logger("llm_router")

PROVIDERS = [
    {"name": "Groq",    "enabled": bool(os.getenv("GROQ_API_KEY")),    "key": os.getenv("GROQ_API_KEY", "")},
    {"name": "OpenCode","enabled": bool(os.getenv("OPENCODE_API_KEY")),"key": os.getenv("OPENCODE_API_KEY", "")},
    {"name": "Mistral", "enabled": bool(os.getenv("MISTRAL_API_KEY")), "key": os.getenv("MISTRAL_API_KEY", "")},
    {"name": "Cohere",  "enabled": bool(os.getenv("COHERE_API_KEY")),  "key": os.getenv("COHERE_API_KEY", "")},
]

provider_failures  = {p["name"]: 0 for p in PROVIDERS}
provider_last_fail = {p["name"]: 0 for p in PROVIDERS}
COOLDOWN_SECONDS   = 60

# ── Groq ──────────────────────────────────────────────────
def ask_groq(prompt: str, system: str = "") -> str:
    """Groq API — fixed for latest version"""
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers = {
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type":  "application/json"
        },
        json = {
            "model":      "llama-3.3-70b-versatile",
            "messages":   _build_messages(prompt, system),
            "max_tokens": 1500
        },
        timeout = 60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# ── Mistral ───────────────────────────────────────────────
def ask_mistral(prompt: str, system: str = "") -> str:
    """Mistral API — updated for new SDK"""
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers = {
            "Authorization": f"Bearer {os.getenv('MISTRAL_API_KEY')}",
            "Content-Type":  "application/json"
        },
        json = {
            "model":      "mistral-small-latest",
            "messages":   _build_messages(prompt, system),
            "max_tokens": 1500
        },
        timeout = 60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# ── OpenCode ──────────────────────────────────────────────
def ask_opencode(prompt: str, system: str = "") -> str:
    """OpenCode Zen API — OpenAI-compatible"""
    response = requests.post(
        "https://opencode.ai/zen/v1/chat/completions",
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENCODE_API_KEY')}",
            "Content-Type":  "application/json"
        },
        json = {
            "model":      os.getenv("OPENCODE_MODEL", "deepseek-v4-flash-free"),
            "messages":   _build_messages(prompt, system),
            "max_tokens": 1500
        },
        timeout = 60
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# ── Cohere ────────────────────────────────────────────────
def ask_cohere(prompt: str, system: str = "") -> str:
    """Cohere API — updated model name"""
    response = requests.post(
        "https://api.cohere.com/v2/chat",
        headers = {
            "Authorization": f"Bearer {os.getenv('COHERE_API_KEY')}",
            "Content-Type":  "application/json"
        },
        json = {
            "model":    "command-r",        # ✅ Updated model
            "messages": _build_messages(prompt, system)
        },
        timeout = 60
    )
    response.raise_for_status()
    return response.json()["message"]["content"][0]["text"]

# ── Helper ────────────────────────────────────────────────
def _build_messages(prompt: str, system: str = "") -> list:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages

PROVIDER_FUNCTIONS = {
    "Groq":    ask_groq,
    "OpenCode":ask_opencode,
    "Mistral": ask_mistral,
    "Cohere":  ask_cohere,
}

# ── Availability ──────────────────────────────────────────
def is_provider_available(name: str) -> bool:
    if provider_failures[name] >= 3:
        if time.time() - provider_last_fail[name] < COOLDOWN_SECONDS:
            return False
        provider_failures[name] = 0
    return True

# ── Main Router ───────────────────────────────────────────
def ask_llm(prompt: str, system: str = "", max_tokens: int = 1500, retries: int = 3) -> str:
    available = [
        p for p in PROVIDERS
        if p["enabled"] and is_provider_available(p["name"])
    ]

    if not available:
        for name in provider_failures:
            provider_failures[name] = 0
        available = [p for p in PROVIDERS if p["enabled"]]

    if not available:
        raise Exception("No LLM providers configured! Add API keys to .env")

    last_error = None

    for provider in available:
        name = provider["name"]
        func = PROVIDER_FUNCTIONS[name]

        for attempt in range(1, retries + 1):
            try:
                logger.info(f"🤖 LLM via {name} (attempt {attempt}/{retries})")
                result = func(prompt, system)
                provider_failures[name] = 0
                logger.info(f"✅ {name} OK ({len(result)} chars)")
                return result

            except Exception as e:
                last_error = e
                error_str  = str(e).lower()
                logger.warning(f"⚠️ {name} failed: {e}")

                if any(x in error_str for x in ["rate limit", "429", "quota", "exceeded", "too many"]):
                    logger.warning(f"🚫 {name} rate limited — switching")
                    provider_failures[name]  = 3
                    provider_last_fail[name] = time.time()
                    break

                if attempt < retries:
                    wait = 2 ** attempt
                    time.sleep(wait)
                else:
                    provider_failures[name] += 1
                    provider_last_fail[name] = time.time()

    raise Exception(f"All LLM providers failed. Last: {last_error}")

# ── Status ────────────────────────────────────────────────
def get_llm_status() -> dict:
    return {
        p["name"]: {
            "enabled":    p["enabled"],
            "available":  is_provider_available(p["name"]),
            "failures":   provider_failures[p["name"]],
            "configured": bool(p["key"])
        }
        for p in PROVIDERS
    }

# ── LLM Cache Key ───────────────────────────────────────────
def _get_cache_key(prompt: str, system: str) -> str:
    content = f"{system}||{prompt}"
    return f"llm:{hashlib.md5(content.encode()).hexdigest()}"

# ── Cached LLM Call ────────────────────────────────────────
def ask_llm_cached(prompt: str, system: str = "",
                   ttl: int = 3600, **kwargs) -> str:
    """LLM call with Redis caching — avoids duplicate API calls"""
    key = _get_cache_key(prompt, system)

    try:
        from backend.cache import cache_get, cache_set
        cached = cache_get(key)
        if cached:
            logger.info("✅ LLM cache HIT — skipping API call")
            return cached.get("response", "")
    except Exception:
        pass

    result = ask_llm(prompt, system, **kwargs)

    try:
        from backend.cache import cache_set
        cache_set(key, {"response": result}, ttl=ttl)
        logger.debug("💾 LLM response cached")
    except Exception:
        pass

    return result