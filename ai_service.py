"""Serviço central de IA do portal.

Todos os módulos devem usar este arquivo em vez de importar diretamente outro app
(ex.: curso -> prompt_app). Isso reduz acoplamento e deixa a troca de provedor em
um único ponto.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


@dataclass(frozen=True)
class AIConfig:
    provider: str = "gemini"
    api_key: str = ""
    model: str = DEFAULT_GEMINI_MODEL
    ollama_base_url: str = DEFAULT_OLLAMA_URL


def normalize_provider(provider: str | None) -> str:
    provider = (provider or "gemini").strip().lower()
    if provider in {"ollama", "local"}:
        return "ollama"
    return "gemini"


def build_config(*, provider: str | None = None, api_key: str | None = None, model: str | None = None, ollama_base_url: str | None = None) -> AIConfig:
    provider_name = normalize_provider(provider or os.getenv("AI_PROVIDER", "gemini"))
    if provider_name == "ollama":
        default_model = os.getenv("OLLAMA_MODEL", "llama3.1")
    else:
        default_model = DEFAULT_GEMINI_MODEL
    return AIConfig(
        provider=provider_name,
        api_key=(api_key or os.getenv("GOOGLE_API_KEY", "")).strip(),
        model=(model or default_model).strip(),
        ollama_base_url=(ollama_base_url or DEFAULT_OLLAMA_URL).rstrip("/"),
    )


def call_ai(action: str, text: str, *, config: AIConfig | None = None, api_key: str | None = None, model_name: str | None = None, provider: str | None = None, ollama_base_url: str | None = None) -> str:
    """Chama o provedor configurado.

    Mantém compatibilidade com chamadas antigas que passavam api_key/model_name,
    mas centraliza o ponto de entrada para todos os programas do portal.
    """
    cfg = config or build_config(provider=provider, api_key=api_key, model=model_name, ollama_base_url=ollama_base_url)
    if cfg.provider == "ollama":
        return _call_ollama(action, text, cfg)
    return _call_gemini(action, text, cfg)


def _call_gemini(action: str, text: str, cfg: AIConfig) -> str:
    # Import tardio para evitar acoplamento de inicialização entre apps.
    from prompt_app.prompt_engine import call_gemini
    return call_gemini(action or "chat", text or "", api_key=cfg.api_key, model_name=cfg.model)


def _call_ollama(action: str, text: str, cfg: AIConfig) -> str:
    import json
    import urllib.error
    import urllib.request

    prompt = text or ""
    if action and action != "chat":
        prompt = f"Ação solicitada: {action}\n\n{prompt}"
    payload = json.dumps({"model": cfg.model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg.ollama_base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
            return (data.get("response") or "").strip() or "Ollama respondeu sem texto."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        if exc.code == 404:
            raise RuntimeError(f"Modelo Ollama não encontrado: {cfg.model}. Escaneie os modelos instalados e selecione um existente.") from exc
        raise RuntimeError(f"Erro HTTP ao chamar Ollama: {exc.code}. Detalhe: {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Não consegui conectar ao Ollama em {cfg.ollama_base_url}. Detalhe: {exc}") from exc


def list_ai_models(*, provider: str = "gemini", api_key: str | None = None, ollama_base_url: str | None = None) -> dict[str, Any]:
    provider_name = normalize_provider(provider)
    if provider_name == "ollama":
        import json
        import urllib.request
        base = (ollama_base_url or DEFAULT_OLLAMA_URL).rstrip("/")
        with urllib.request.urlopen(f"{base}/api/tags", timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    from prompt_app.prompt_engine import list_gemini_models
    return list_gemini_models(api_key=api_key)
