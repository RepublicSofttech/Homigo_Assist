"""OpenAI-compatible chat-completions client (works with Groq, Google Gemini's OpenAI endpoint,
OpenRouter, a local Ollama, or OpenAI itself). Free tiers: set LLM_PROVIDER=groq or gemini + LLM_API_KEY.

Model names change over time — the defaults below are only a starting point; set LLM_MODEL to a
current tool-calling model from your provider's console.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

log = logging.getLogger(__name__)

PRESETS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.0-flash"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": ""},
    "openai_compat": {"base_url": "", "model": ""},
}


class LLMUnavailable(Exception):
    pass


def enabled():
    p = settings.LLM_PROVIDER
    return p in PRESETS and bool(settings.LLM_API_KEY) and bool(_cfg()["base_url"]) and bool(_cfg()["model"])


def _cfg():
    preset = PRESETS.get(settings.LLM_PROVIDER, {})
    return {"base_url": (settings.LLM_BASE_URL or preset.get("base_url", "")).rstrip("/"), "model": settings.LLM_MODEL or preset.get("model", "")}


def _budget_ok():
    key = f"llm_calls:{timezone.localdate().isoformat()}"
    n = cache.get(key, 0)
    if n >= settings.LLM_DAILY_CALL_LIMIT:
        return False
    cache.set(key, n + 1, 60 * 60 * 26)
    return True


def chat(messages, tools=None, temperature=0.3, max_tokens=700):
    """Returns the assistant message dict: {"content": str|None, "tool_calls": [...]}. Raises LLMUnavailable."""
    if not enabled():
        raise LLMUnavailable("LLM not configured")
    if not _budget_ok():
        raise LLMUnavailable("Daily LLM budget reached")
    cfg = _cfg()
    body = {"model": cfg["model"], "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    try:
        r = requests.post(f"{cfg['base_url']}/chat/completions", json=body, timeout=settings.LLM_TIMEOUT,
                          headers={"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise LLMUnavailable(f"LLM request failed: {e}") from e
    if r.status_code >= 400:
        log.warning("LLM error %s: %s", r.status_code, r.text[:300])
        raise LLMUnavailable(f"LLM HTTP {r.status_code}")
    try:
        return r.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as e:
        raise LLMUnavailable("Bad LLM response") from e
