"""Blueprints pequenos do portal principal.

Esta fase começa a migração para uma aplicação única sem mexer, ainda, nas
rotas internas grandes dos módulos legados. O objetivo é deixar o portal
centralizado e o registro dos programas em um só lugar para que cada módulo
possa virar Blueprint aos poucos.
"""

from flask import Blueprint, jsonify, render_template

portal_bp = Blueprint(
    "portal",
    __name__,
    template_folder="portal_templates",
    static_folder="portal_static",
)

PROGRAMS = [
    {
        "slug": "prompt",
        "name": "Prompt Profissional",
        "prefix": "/prompt",
        "status": "blueprint_nativo",
    },
    {
        "slug": "financeiro",
        "name": "Gestão Financeira",
        "prefix": "/financeiro",
        "status": "blueprint_nativo",
    },
    {
        "slug": "curso-ingles",
        "name": "Portal de Cursos + Chat Agente",
        "prefix": "/curso-ingles",
        "status": "compatibilidade_wsgi",
    },
    {
        "slug": "editor-admin",
        "name": "Editor Admin",
        "prefix": "/editor-admin",
        "status": "blueprint_nativo",
    },
]


@portal_bp.route("/")
@portal_bp.route("/central")
@portal_bp.route("/programas")
def index():
    return render_template("index.html", programs=PROGRAMS)


@portal_bp.route("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "fase": "4E.8",
            "arquitetura": "portal com editor admin, prompt e financeiro em blueprints + ponte WSGI apenas para curso",
            "programas": PROGRAMS,
        }
    )


@portal_bp.route("/system/programs")
def system_programs():
    """Lista única de programas para o front-end/menu consumir."""
    return jsonify({"programs": PROGRAMS})
