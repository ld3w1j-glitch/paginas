"""Utilitários compartilhados dos cursos internos.

Este módulo concentra pequenas rotinas que eram duplicadas entre as trilhas de
Português e Inglês. A ideia é reduzir o arquivo principal sem mudar rotas nem
templates nesta fase.
"""
from __future__ import annotations


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_text(item) for item in value)
    return str(value)


def trim_snippet(value: str, limit: int = 280) -> str:
    snippet = (value or "").strip()
    if len(snippet) > limit:
        return snippet[: limit - 3].rstrip() + "..."
    return snippet


def search_blocks(query: str, blocks: list[str], limit: int = 3) -> list[str]:
    q = (query or "").strip().lower()
    if not q:
        return []
    matches = []
    for block in blocks or []:
        text = _text(block)
        if q in text.lower():
            matches.append(trim_snippet(text))
        if len(matches) >= limit:
            break
    return matches


def search_collection(
    query: str,
    items: list[dict],
    *,
    text_fields: list[str],
    result_key: str,
    fallback_field: str = "summary",
    nested_list_field: str | None = None,
    nested_text_fields: list[str] | None = None,
    nested_limit: int = 4,
) -> list[dict]:
    """Busca genérica para trilhas de estudo.

    Retorna uma lista no mesmo formato usado pelos templates atuais:
    {result_key: item, "matches": [...]}.
    """
    q = (query or "").strip().lower()
    if not q:
        return []

    results: list[dict] = []
    for item in items or []:
        haystack = " ".join(_text(item.get(field, "")) for field in text_fields).lower()
        snippets: list[str] = []

        if nested_list_field and nested_text_fields:
            for nested in item.get(nested_list_field, []) or []:
                nested_text = " ".join(_text(nested.get(field, "")) for field in nested_text_fields)
                if q in nested_text.lower():
                    title = _text(nested.get("title", "")).strip()
                    focus = _text(nested.get("focus", "")).strip()
                    label = f"{title}: {focus}" if title and focus else nested_text
                    snippets.append(trim_snippet(label))
                if len(snippets) >= nested_limit:
                    break

        block_matches = search_blocks(query, item.get("blocks", []), limit=3)
        snippets.extend(block_matches)

        if q in haystack or snippets:
            fallback = _text(item.get(fallback_field, ""))
            results.append({result_key: item, "matches": snippets or [fallback]})

    return results
