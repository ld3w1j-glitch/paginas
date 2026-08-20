from flask import Blueprint, jsonify

system_bp = Blueprint("system", __name__)


@system_bp.get("/health")
def health():
    # Contrato mantido para Railway e testes existentes.
    return jsonify({"ok": True, "service": "portal-de-cursos"})
