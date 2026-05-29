import requests
from flask import current_app


def get_market_snapshot():
    """Busca dados de mercado. Se a API não estiver configurada ou falhar, retorna fallback."""
    api_url = current_app.config.get("MARKET_API_URL")
    if api_url:
        try:
            response = requests.get(api_url, timeout=8)
            response.raise_for_status()
            data = response.json()
            return {
                "source": "API configurada",
                "items": data.get("items", data if isinstance(data, list) else []),
            }
        except Exception as exc:
            return {
                "source": "Fallback: API falhou",
                "error": str(exc),
                "items": fallback_items(),
            }
    return {"source": "Dados demonstrativos", "items": fallback_items()}


def fallback_items():
    return [
        {"name": "USD/BRL", "value": "configurar API", "change": "—"},
        {"name": "EUR/BRL", "value": "configurar API", "change": "—"},
        {"name": "IBOV", "value": "configurar API", "change": "—"},
    ]
