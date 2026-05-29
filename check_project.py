"""Verificador rápido do portal antes de rodar localmente ou subir para Railway.

Uso:
    python check_project.py

O script não depende de Flask instalado. Ele faz checagens estáticas para pegar
os erros mais comuns depois da migração para Blueprints:
- variáveis obrigatórias ausentes em produção;
- arquivos/pastas essenciais;
- banco SQLite, pycache e pyc no pacote;
- endpoints usados em url_for() que não existem nos Blueprints já migrados;
- arquivos estáticos chamados pelos templates e inexistentes no projeto;
- estrutura de deploy Railway/Procfile.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent

BLUEPRINT_ENDPOINTS = {
    "portal": {
        "portal.index",
        "portal.health",
        "portal.system_programs",
        "static",
    },
    "editor_admin": {
        "editor_admin.static",
        "editor_admin.index",
        "editor_admin.servicos",
        "editor_admin.projetos",
        "editor_admin.estrutura",
        "editor_admin.detalhe",
        "editor_admin.login",
        "editor_admin.logout",
    },
    "prompt": {
        "prompt.static",
        "prompt.index",
        "prompt.login",
        "prompt.logout",
        "prompt.admin_panel",
        "prompt.save_project",
        "prompt.delete_project",
        "prompt.save_template",
        "prompt.delete_template",
        "prompt.clear_history",
        "prompt.delete_history",
        "prompt.export_history",
        "prompt.export_package",
        "prompt.export_backup",
        "prompt.save_api_settings",
        "prompt.api_gemini_models",
        "prompt.api_test_gemini",
        "prompt.api_analyze_error",
        "prompt.api_gemini",
        "prompt.api_chat_start",
        "prompt.api_chat_send",
        "prompt.api_chat_get",
        "prompt.export_chat",
        "prompt.api_generated_file",
        "prompt.export_generated_file",
        "prompt.export_chat_apply",
        "prompt.chat_executor",
        "prompt.agent_chat",
        "prompt.agent_chat_start",
        "prompt.agent_chat_message",
        "prompt.agent_chat_download",
        "prompt.agent_chat_status",
        "prompt.agent_chat_ollama_models",
        "prompt.agent_chat_select_ollama",
    },
    "financeiro": {
        "financeiro.static",
        "financeiro.index",
        "financeiro.admin_ai",
        "financeiro.ai_analyze",
        "financeiro.dashboard",
        "financeiro.accounts",
        "financeiro.edit_account",
        "financeiro.delete_account",
        "financeiro.transactions",
        "financeiro.import_receipt_transaction",
        "financeiro.import_picpay_transaction",
        "financeiro.edit_transaction",
        "financeiro.delete_transaction",
        "financeiro.uploaded_file",
        "financeiro.reports",
        "financeiro_auth.register",
        "financeiro_auth.login",
        "financeiro_auth.logout",
    },
}

LEGACY_COURSE_ENDPOINT_PREFIXES = {
    # O curso ainda roda pela ponte WSGI. Estes endpoints ficam isolados dentro
    # da sub-aplicação e não precisam do prefixo curso_ingles.* nesta fase.
    "home",
    "login",
    "logout",
    "dashboard",
    "agent_chat_page",
    "agent_chat_download",
    "portal_mcp_chat",
    "admin_panel",
    "admin_ollama_models",
    "admin_ollama_use_model",
    "principios",
    "admissao",
    "hierarquia",
    "regimento",
    "documentos",
    "portugues_home",
    "portugues_search",
    "portugues_practice",
    "portugues_final_exam",
    "portugues_lesson_detail",
    "module_detail",
    "take_exam",
    "ingles_home",
    "ingles_search",
    "ingles_practice",
    "ingles_phrasebook",
    "ingles_vocabulary",
    "ingles_study_plan",
    "ingles_final_exam",
    "ingles_module_detail",
    "static",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str = ""

    @property
    def symbol(self) -> str:
        return "OK" if self.ok else "ERRO"


def is_production_env() -> bool:
    env = (os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV") or "").lower()
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID") or env in {"prod", "production"})




def looks_like_placeholder_database_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.strip().lower()
    placeholders = ("porta", "usuario", "senha", "host", "banco", "postgresql://...", "postgres://...")
    return any(token in lowered for token in placeholders)


def check_database_url_placeholders() -> CheckResult:
    problems = []
    for name in ["DATABASE_URL", "CURSO_INGLES_DATABASE_URL"]:
        value = os.getenv(name)
        if looks_like_placeholder_database_url(value):
            problems.append(f"{name} está com valor de exemplo: {value}")
    env_files = [ROOT / ".env"]
    for env_file in env_files:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean = line.strip()
            if not clean or clean.startswith("#") or "=" not in clean:
                continue
            name, value = clean.split("=", 1)
            if name.strip() in {"DATABASE_URL", "CURSO_INGLES_DATABASE_URL"} and looks_like_placeholder_database_url(value):
                problems.append(f".env: {name.strip()} está com valor de exemplo")
    return CheckResult("DATABASE_URL sem placeholder", not problems, "; ".join(problems))

def iter_files(patterns: Iterable[str]) -> Iterable[Path]:
    for pattern in patterns:
        yield from ROOT.rglob(pattern)


def check_required_files() -> CheckResult:
    required = [
        "portal.py",
        "portal_blueprints.py",
        "legacy_wsgi_bridge.py",
        "security_config.py",
        "extensions.py",
        "ai_service.py",
        "storage_service.py",
        "requirements.txt",
        "Procfile",
        "railway.json",
        ".gitignore",
        ".env.example",
    ]
    missing = [item for item in required if not (ROOT / item).exists()]
    return CheckResult("Arquivos essenciais", not missing, ", ".join(missing))


def check_prod_env() -> CheckResult:
    if not is_production_env():
        return CheckResult("Variáveis de produção", True, "ambiente local: avisos não bloqueiam")
    missing = [name for name in ["SECRET_KEY", "ADMIN_USER", "ADMIN_PASSWORD", "DATABASE_URL"] if not os.getenv(name)]
    return CheckResult("Variáveis de produção", not missing, ", ".join(missing))


def check_no_forbidden_artifacts() -> CheckResult:
    forbidden = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.suffix == ".db":
            # Banco de teste criado pelo usuário pode existir localmente depois; no ZIP final não deve existir.
            forbidden.append(rel)
    return CheckResult("Sem .db/.pyc/__pycache__ versionados", not forbidden, "; ".join(forbidden[:20]))


def collect_url_for_strings() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    regex = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
    for path in list(iter_files(["*.py", "*.html"])):
        if ".venv" in path.parts or "venv" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in regex.finditer(text):
            found.append((path.relative_to(ROOT).as_posix(), match.group(1)))
    return found


def check_url_for_endpoints() -> CheckResult:
    known = set().union(*BLUEPRINT_ENDPOINTS.values()) | LEGACY_COURSE_ENDPOINT_PREFIXES
    ignored_prefixes = (".",)  # endpoints relativos de Flask, se aparecerem
    problems = []
    for rel, endpoint in collect_url_for_strings():
        if endpoint.startswith(ignored_prefixes):
            continue
        if endpoint not in known:
            # Dinâmicos/legados podem aparecer futuramente; aqui queremos sinalizar suspeitos.
            problems.append(f"{rel}: {endpoint}")
    return CheckResult("url_for() com endpoints conhecidos", not problems, "; ".join(problems[:30]))


def extract_static_refs() -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]\s*,\s*filename\s*=\s*['\"]([^'\"]+)['\"]")
    for path in ROOT.rglob("*.html"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for endpoint, filename in pattern.findall(text):
            refs.append((path.relative_to(ROOT).as_posix(), endpoint, filename))
    return refs


def static_base_for(endpoint: str, template_path: str) -> Path | None:
    if endpoint == "static":
        if template_path.startswith("curso_ingles_app/"):
            return ROOT / "curso_ingles_app" / "static"
        return ROOT / "portal_static"
    if endpoint == "editor_admin.static":
        return ROOT / "editor_admin_app" / "static"
    if endpoint == "prompt.static":
        return ROOT / "prompt_app" / "static"
    if endpoint == "financeiro.static":
        return ROOT / "financeiro_app" / "static"
    return None


def check_static_files() -> CheckResult:
    missing = []
    for template_path, endpoint, filename in extract_static_refs():
        base = static_base_for(endpoint, template_path)
        if base is None:
            continue
        if not (base / filename).exists():
            missing.append(f"{template_path}: {endpoint} -> {filename}")
    return CheckResult("Arquivos estáticos referenciados", not missing, "; ".join(missing[:30]))


def check_ambiguous_sqlalchemy_relationships() -> CheckResult:
    """Detecta relationship("Classe") ambíguo quando há classes repetidas no mesmo db.

    Depois da unificação do db, nomes como User ou AppSetting existem em mais de
    um módulo. Em relationships, use o caminho completo do módulo, por exemplo
    "financeiro_app.models.AppSetting".
    """
    class_locations: dict[str, list[str]] = {}
    for path in ROOT.rglob("*.py"):
        if "venv" in path.parts or ".venv" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_locations.setdefault(node.name, []).append(rel)

    duplicated = {name for name, locations in class_locations.items() if len(locations) > 1}
    problems: list[str] = []
    pattern = re.compile(r"relationship\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")
    for path in ROOT.rglob("*.py"):
        if "venv" in path.parts or ".venv" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            target = match.group(1)
            if target in duplicated:
                problems.append(f"{rel}: relationship(\"{target}\") é ambíguo; use caminho completo do módulo")
    return CheckResult("Relationships SQLAlchemy sem ambiguidade", not problems, "; ".join(problems[:20]))



def check_namespaced_templates() -> CheckResult:
    """Evita colisão de templates entre Blueprints.

    Em Blueprints migrados, render_template("index.html") pode carregar o
    index.html do portal central. Use sempre um namespace, como
    prompt/index.html, financeiro/dashboard.html ou editor_admin/index.html.
    """
    modules = {
        "prompt_app": "prompt/",
        "financeiro_app": "financeiro/",
        "editor_admin_app": "editor_admin/",
    }
    problems = []
    for module_dir, expected_prefix in modules.items():
        for path in (ROOT / module_dir).rglob("*.py"):
            if "venv" in path.parts or ".venv" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Name) and func.id == "render_template"):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
                    continue
                template_name = node.args[0].value
                if not template_name.startswith(expected_prefix):
                    problems.append(f"{rel}:{node.lineno} render_template(\"{template_name}\") deveria começar com \"{expected_prefix}\"")
    return CheckResult("Templates namespaced por Blueprint", not problems, "; ".join(problems[:30]))

def check_procfile() -> CheckResult:
    procfile = ROOT / "Procfile"
    if not procfile.exists():
        return CheckResult("Procfile", False, "ausente")
    text = procfile.read_text(encoding="utf-8", errors="ignore")
    ok = "portal:application" in text or "portal:create_application" in text
    return CheckResult("Procfile aponta para o portal", ok, text.strip())


def check_python_syntax() -> CheckResult:
    bad = []
    for path in ROOT.rglob("*.py"):
        if "venv" in path.parts or ".venv" in path.parts:
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as exc:
            bad.append(f"{path.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
    return CheckResult("Sintaxe Python", not bad, "; ".join(bad[:20]))


def main() -> int:
    checks = [
        check_required_files(),
        check_prod_env(),
        check_database_url_placeholders(),
        check_no_forbidden_artifacts(),
        check_python_syntax(),
        check_url_for_endpoints(),
        check_static_files(),
        check_namespaced_templates(),
        check_ambiguous_sqlalchemy_relationships(),
        check_procfile(),
    ]
    print("\nCHECK DO PROJETO - Fase 4E\n" + "=" * 34)
    failed = False
    for result in checks:
        print(f"[{result.symbol}] {result.name}")
        if result.details:
            print(f"     {result.details}")
        failed = failed or not result.ok
    print("=" * 34)
    if failed:
        print("Resultado: existe algo para corrigir antes de subir.")
        return 1
    print("Resultado: check estático passou. Agora rode o app e teste as telas principais.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
