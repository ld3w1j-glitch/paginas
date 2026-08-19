"""Integrações de IA usadas exclusivamente pelo Portal de Cursos."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
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
    return "ollama" if (provider or "").strip().lower() in {"ollama", "local"} else "gemini"


def build_config(
    *,
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    ollama_base_url: str | None = None,
) -> AIConfig:
    provider_name = normalize_provider(provider or os.getenv("AI_PROVIDER", "gemini"))
    default_model = os.getenv("OLLAMA_MODEL", "llama3.1") if provider_name == "ollama" else DEFAULT_GEMINI_MODEL
    return AIConfig(
        provider=provider_name,
        api_key=(api_key or os.getenv("GOOGLE_API_KEY", "")).strip(),
        model=(model or default_model).strip(),
        ollama_base_url=(ollama_base_url or DEFAULT_OLLAMA_URL).rstrip("/"),
    )


def call_ai(
    action: str,
    text: str,
    *,
    config: AIConfig | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
    ollama_base_url: str | None = None,
) -> str:
    cfg = config or build_config(
        provider=provider,
        api_key=api_key,
        model=model_name,
        ollama_base_url=ollama_base_url,
    )
    if cfg.provider == "ollama":
        return _call_ollama(action, text, cfg)
    return _call_gemini(action, text, cfg)


def _call_gemini(action: str, text: str, cfg: AIConfig) -> str:
    if not cfg.api_key:
        return "Configure a chave do Google Gemini no painel Admin ou nas variáveis de ambiente."

    instructions = {
        "chat": "Responda em português do Brasil de forma clara, lógica e útil.",
        "melhorar": "Melhore este texto mantendo clareza e concisão.",
        "reduzir": "Reduza este texto mantendo o essencial.",
        "arquitetura": "Transforme o pedido em uma especificação técnica organizada.",
        "erro": "Analise o erro e gere um plano de correção.",
    }.get(action, "Responda ao pedido com clareza.")

    prompt = f"{instructions}\n\n{text or ''}"
    safe_model = urllib.parse.quote(cfg.model, safe="")
    safe_key = urllib.parse.quote(cfg.api_key, safe="")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={safe_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "topP": 0.9, "maxOutputTokens": 4096},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
        candidates = result.get("candidates", [])
        if not candidates:
            return "Gemini respondeu sem conteúdo. Verifique o modelo configurado."
        parts = candidates[0].get("content", {}).get("parts", [])
        answer = "\n".join(part.get("text", "") for part in parts).strip()
        return answer or "Gemini respondeu sem texto."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return _format_gemini_http_error(exc.code, detail, cfg.model)
    except Exception as exc:
        return f"Erro ao chamar Gemini: {exc}"


def _format_gemini_http_error(status_code: int, detail: str, model_name: str) -> str:
    lower = (detail or "").lower()
    try:
        parsed = json.loads(detail) if detail else {}
        message = parsed.get("error", {}).get("message", "")
    except Exception:
        message = detail or ""

    if status_code == 429 or "resource_exhausted" in lower or "quota" in lower:
        return "A cota da API Gemini foi esgotada ou está indisponível. Aguarde ou verifique a cota da chave."
    if status_code == 400 and ("api key" in lower or "key" in lower):
        return "A chave Google parece inválida ou mal formatada. Salve a chave novamente no painel Admin."
    if status_code == 404 or "not found" in lower:
        return f"O modelo Gemini configurado não foi encontrado: {model_name}."
    if status_code in {401, 403}:
        return "A chamada foi recusada pelo Google. Verifique se a API Key está ativa e autorizada."
    return f"Erro HTTP ao chamar Gemini: {status_code}. Detalhe: {(message or detail)[:700]}"


def _call_ollama(action: str, text: str, cfg: AIConfig) -> str:
    prompt = text or ""
    if action and action != "chat":
        prompt = f"Ação solicitada: {action}\n\n{prompt}"
    payload = json.dumps({"model": cfg.model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        f"{cfg.ollama_base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        return (data.get("response") or "").strip() or "Ollama respondeu sem texto."
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"Modelo Ollama não encontrado: {cfg.model}.") from exc
        raise RuntimeError(f"Erro HTTP ao chamar Ollama: {exc.code}.") from exc
    except Exception as exc:
        raise RuntimeError(f"Não consegui conectar ao Ollama em {cfg.ollama_base_url}: {exc}") from exc


def list_ai_models(
    *,
    provider: str = "gemini",
    api_key: str | None = None,
    ollama_base_url: str | None = None,
) -> dict[str, Any]:
    if normalize_provider(provider) == "ollama":
        base = (ollama_base_url or DEFAULT_OLLAMA_URL).rstrip("/")
        with urllib.request.urlopen(f"{base}/api/tags", timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    key = (api_key or os.getenv("GOOGLE_API_KEY", "")).strip()
    if not key:
        return {"ok": False, "error": "Configure a Google API Key antes de buscar modelos.", "models": []}
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key, safe='')}"
    request = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = []
        for item in payload.get("models", []):
            methods = item.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            name = (item.get("name") or "").removeprefix("models/")
            if name:
                models.append({"name": name, "display_name": item.get("displayName") or name})
        models.sort(key=lambda item: item["name"])
        return {"ok": True, "models": models, "count": len(models)}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": _format_gemini_http_error(exc.code, detail, "ListModels"), "models": []}
    except Exception as exc:
        return {"ok": False, "error": f"Falha ao buscar modelos: {exc}", "models": []}
