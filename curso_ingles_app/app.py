import json
import os
import re
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import date, datetime, timedelta
from functools import lru_cache, wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from ai_service import call_ai
from extensions import db
from security_config import get_admin_password, get_admin_user, get_database_url, get_secret_key
from storage_service import workspace_dir

from .course_utils import search_collection
from .data import DEFAULT_MODULES, DOCS_DATA, ROLES_DATA, SITE_DATA
from .english_local_runtime import (
    ai_status as english_ai_status,
)
from .english_local_runtime import (
    discover_voice,
    pronunciation_score,
    transcribe_wav,
)
from .english_local_runtime import (
    start_ai as start_english_ai,
)
from .english_local_runtime import (
    stop_ai as stop_english_ai,
)
from .english_tutor import SCENARIOS as ENGLISH_SCENARIOS
from .english_tutor import normalize_exercise_answer, tutor_response

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "legiao.db")
DEFAULT_ADMIN_EMAIL = get_admin_user()
DEFAULT_ADMIN_PASSWORD = get_admin_password()
PORTUGUES_CONTENT_DIR = os.path.join(BASE_DIR, "content", "portugues")
PORTUGUES_COURSE_PATH = os.path.join(PORTUGUES_CONTENT_DIR, "curso_portugues.json")
PORTUGUES_ACTIVITY_PATH = os.path.join(PORTUGUES_CONTENT_DIR, "activity_bank.json")
INGLES_CONTENT_DIR = os.path.join(BASE_DIR, "content", "ingles")
INGLES_COURSE_PATH = os.path.join(INGLES_CONTENT_DIR, "english_course.json")
INGLES_ACTIVITY_PATH = os.path.join(INGLES_CONTENT_DIR, "activity_bank.json")
AGENT_WORKSPACE_DIR = str(workspace_dir("curso_ingles_agent"))
PROJECT_ROOT = Path(BASE_DIR).parent
ENGLISH_AI_DIR = Path(os.getenv("ENGLISH_AI_DIR", PROJECT_ROOT / "ia_local"))
ENGLISH_VOICE_DIR = Path(os.getenv("ENGLISH_VOICE_DIR", PROJECT_ROOT / "voz_local"))


AGENT_TEAM = [
    {
        "id": "coordenador",
        "name": "Coordenador de Agentes",
        "mission": "entender o pedido, escolher o próximo agente e manter a conversa organizada por etapas",
        "triggers": ["plano", "organizar", "etapa", "conversa", "geral", "começar", "decidir"],
    },
    {
        "id": "contexto",
        "name": "Analista de Contexto",
        "mission": "ler histórico, tela atual, permissões e objetivo antes de qualquer execução",
        "triggers": ["contexto", "histórico", "permissão", "cargo", "usuário", "admin", "login", "acesso"],
    },
    {
        "id": "leanctx",
        "name": "LeanCTX - Contexto Enxuto",
        "mission": "reduzir contexto, eliminar repetição, montar um resumo operacional e passar somente o necessário para o próximo agente",
        "triggers": ["leanctx", "lean ctx", "contexto enxuto", "economizar token", "economia de token", "resumir contexto", "tokens", "memória", "memoria", "continuidade"],
    },
    {
        "id": "ux_ui",
        "name": "Designer UX/UI",
        "mission": "melhorar usabilidade, responsividade, fluxo visual e clareza da interface",
        "triggers": ["visual", "responsivo", "interface", "tela", "design", "botão", "layout", "mobile", "pc", "css"],
    },
    {
        "id": "frontend",
        "name": "Frontend",
        "mission": "alterar HTML, CSS e JavaScript da tela com foco em interação e estado do chat",
        "triggers": ["html", "css", "javascript", "js", "template", "formulário", "modal", "clique", "menu"],
    },
    {
        "id": "backend",
        "name": "Backend Flask",
        "mission": "alterar rotas, banco, autenticação, APIs, Ollama, Gemini e regras do servidor",
        "triggers": ["flask", "python", "rota", "api", "banco", "sqlite", "modelo", "ollama", "gemini", "mcp", "salvar", "excluir"],
    },
    {
        "id": "seguranca",
        "name": "Segurança e Permissões",
        "mission": "validar riscos, proteger chaves de API, usuários, cargos e dados sensíveis",
        "triggers": ["senha", "key", "chave", "segurança", "permissão", "admin", "token", "credencial"],
    },
    {
        "id": "arquivos",
        "name": "Gerador de Arquivos/ZIP",
        "mission": "definir arquivos necessários, gerar blocos [[FILE:...]] e preparar pacote final",
        "triggers": ["zip", "arquivo", "baixar", "entregar", "gerar projeto", "download", "criar arquivos"],
    },
    {
        "id": "testador",
        "name": "Testador",
        "mission": "revisar funcionamento, apontar riscos de erro e sugerir teste antes de liberar",
        "triggers": ["erro", "bug", "teste", "quebrado", "não funciona", "falha", "404", "500", "validar"],
    },
]


def _select_agent_chain(question: str, context: dict | None = None, stage: str = "plan", allow_files: bool = False) -> list[dict]:
    """Escolhe uma cadeia curta de agentes com base na conversa para economizar tokens."""
    context = context or {}
    text_parts = [question or "", context.get("page_context") or "", context.get("selected_text") or ""]
    for item in (context.get("history") or [])[-6:]:
        text_parts.append(item.get("content") or "")
    text = "\n".join(text_parts).lower()

    selected_ids = ["coordenador"]
    scored = []
    for agent in AGENT_TEAM:
        if agent["id"] == "coordenador":
            continue
        score = sum(1 for trigger in agent["triggers"] if trigger.lower() in text)
        if score:
            scored.append((score, agent["id"]))

    priority = ["contexto", "leanctx", "seguranca", "backend", "frontend", "ux_ui", "arquivos", "testador"]
    scored.sort(key=lambda item: (-item[0], priority.index(item[1]) if item[1] in priority else 99))
    for _, agent_id in scored:
        if agent_id not in selected_ids and len(selected_ids) < 4:
            selected_ids.append(agent_id)

    long_context = len(text) > 2200 or len(context.get("history") or []) >= 4
    if long_context and "leanctx" not in selected_ids:
        selected_ids.insert(1, "leanctx")
    if (allow_files or stage == "execute" or any(word in text for word in ["zip", "arquivo", "baixar", "download"])) and "arquivos" not in selected_ids:
        selected_ids.append("arquivos")
    if stage in {"execute", "rethink"} and "testador" not in selected_ids:
        selected_ids.append("testador")
    if len(selected_ids) == 1:
        selected_ids.append("contexto")
    selected_ids = selected_ids[:5]
    lookup = {agent["id"]: agent for agent in AGENT_TEAM}
    return [lookup[agent_id] for agent_id in selected_ids if agent_id in lookup]


def _agent_chain_summary(chain: list[dict]) -> str:
    return " → ".join(agent["name"] for agent in chain)


def _build_multi_agent_block(chain: list[dict]) -> str:
    lines = [
        "EQUIPE MULTIAGENTE ATIVA:",
        "Você não é um agente único. Você coordena uma equipe e deve decidir quando passar a tarefa para o próximo agente.",
        "Use somente os agentes necessários para economizar contexto e tokens.",
        "Sempre aplique LeanCTX antes de passar de um agente para outro: compacte o contexto, remova repetição e mantenha apenas decisões, arquivos, riscos e próximo passo.",
        "Cadeia selecionada para esta mensagem:",
    ]
    for index, agent in enumerate(chain, start=1):
        lines.append(f"{index}. {agent['name']} — {agent['mission']}")
    lines.extend([
        "",
        "Formato obrigatório da resposta:",
        "- Comece com 'Roteamento multiagente:' e mostre a sequência de agentes usada.",
        "- Para cada agente acionado, escreva um bloco curto: 'Agente: nome' e 'Decisão: ...'.",
        "- Inclua um bloco 'LeanCTX:' com: Objetivo, Contexto essencial, Arquivos prováveis, Riscos e Próximo agente.",
        "- Se perceber que outro especialista precisa continuar, registre 'Chamando próximo agente: nome' antes do bloco seguinte.",
        "- Não exponha pensamento interno bruto; mostre apenas decisões resumidas e verificáveis.",
        "- No final diga qual agente deve continuar se o usuário responder ou aprovar.",
    ])
    return "\n".join(lines)


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = get_secret_key()
app.config["SQLALCHEMY_DATABASE_URI"] = get_database_url(f"sqlite:///{DB_PATH}", env_name="CURSO_INGLES_DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


class Role(db.Model):
    __tablename__ = "curso_role"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    level = db.Column(db.Integer, unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)


class User(db.Model):
    __tablename__ = "curso_user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("curso_role.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    role = db.relationship("Role")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)




class PortalSetting(db.Model):
    __tablename__ = "curso_portal_setting"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AgentConversation(db.Model):
    __tablename__ = "curso_agent_conversation"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    title = db.Column(db.String(180), default="Nova conversa", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("curso_ingles_app.app.User")
    messages = db.relationship("AgentMessage", backref="conversation", cascade="all, delete-orphan", lazy=True, order_by="AgentMessage.id.asc()")


class AgentMessage(db.Model):
    __tablename__ = "curso_agent_message"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("curso_agent_conversation.id"), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False)
    content = db.Column(db.Text, default="", nullable=False)
    stage = db.Column(db.String(40), default="message", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def get_portal_setting(key: str, default: str = "") -> str:
    setting = PortalSetting.query.filter_by(key=key).first()
    if setting and setting.value is not None:
        return setting.value
    return default


def set_portal_setting(key: str, value: str) -> None:
    setting = PortalSetting.query.filter_by(key=key).first()
    if not setting:
        setting = PortalSetting(key=key, value=value or "")
        db.session.add(setting)
    else:
        setting.value = value or ""
    db.session.commit()


def get_portal_ai_config() -> dict:
    return {
        "provider": get_portal_setting("ai_provider", os.getenv("AI_PROVIDER", "gemini")),
        "api_key": get_portal_setting("mcp_google_api_key", os.getenv("GOOGLE_API_KEY", "")),
        "model": get_portal_setting("mcp_gemini_model", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
        "ollama_base_url": get_portal_setting("ollama_base_url", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")),
        "ollama_model": get_portal_setting("ollama_model", os.getenv("OLLAMA_MODEL", "llama3.1")),
    }

def _normalize_ollama_base_url(base_url: str | None) -> str:
    return (base_url or "http://localhost:11434").strip().rstrip("/") or "http://localhost:11434"


def _list_ollama_models(base_url: str | None = None) -> list[dict]:
    """Lista os modelos instalados no Ollama acessível pelo servidor Flask."""
    clean_base = _normalize_ollama_base_url(base_url)
    req = urllib.request.Request(clean_base + "/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
    models = []
    for item in data.get("models", []) or []:
        name = item.get("name") or item.get("model") or ""
        if not name:
            continue
        details = item.get("details") or {}
        size_bytes = item.get("size") or 0
        try:
            size_gb = round(float(size_bytes) / (1024 ** 3), 2) if size_bytes else None
        except Exception:
            size_gb = None
        models.append({
            "name": name,
            "model": name,
            "family": details.get("family") or details.get("format") or "",
            "parameter_size": details.get("parameter_size") or "",
            "quantization_level": details.get("quantization_level") or "",
            "size_gb": size_gb,
            "modified_at": item.get("modified_at") or "",
        })
    return sorted(models, key=lambda m: m["name"].lower())


def _ollama_connection_hint(base_url: str | None = None) -> str:
    return (
        "Abra o Ollama no computador onde este Flask está rodando e confira a URL "
        f"{_normalize_ollama_base_url(base_url)}. Se o portal estiver no Railway, localhost é o servidor da Railway, "
        "não o seu PC; nesse caso use um Ollama exposto em rede/servidor ou rode o portal localmente."
    )

class StudyModule(db.Model):
    __tablename__ = "curso_study_module"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    min_role_level = db.Column(db.Integer, nullable=False)
    target_role_level = db.Column(db.Integer, nullable=False)
    passing_score = db.Column(db.Integer, default=70, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    questions = db.relationship(
        "Question",
        backref="module",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Question.id.asc()",
    )


class Question(db.Model):
    __tablename__ = "curso_question"
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("curso_study_module.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, default="", nullable=False)


class ModuleAttempt(db.Model):
    __tablename__ = "curso_module_attempt"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey("curso_study_module.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("curso_ingles_app.app.User")
    module = db.relationship("StudyModule")


class EnglishTutorPreference(db.Model):
    __tablename__ = "curso_english_tutor_preference"
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), primary_key=True)
    level = db.Column(db.String(10), default="A1", nullable=False)
    objective = db.Column(db.String(300), default="Conversação e compreensão geral", nullable=False)
    tutor_engine = db.Column(db.String(40), default="integrated", nullable=False)
    scenario_key = db.Column(db.String(80), default="free", nullable=False)
    local_ai_url = db.Column(db.String(500), default="http://127.0.0.1:8080/v1/chat/completions", nullable=False)
    local_ai_model = db.Column(db.String(160), default="local-model", nullable=False)
    local_ai_model_file = db.Column(db.String(500), default="", nullable=False)
    voice_model_file = db.Column(db.String(500), default="", nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EnglishTutorMessage(db.Model):
    __tablename__ = "curso_english_tutor_message"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, default="", nullable=False)
    corrected_text = db.Column(db.Text, default="", nullable=False)
    explanations_json = db.Column(db.Text, default="[]", nullable=False)
    engine = db.Column(db.String(160), default="Professor integrado offline", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EnglishTutorMistake(db.Model):
    __tablename__ = "curso_english_tutor_mistake"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    rule_key = db.Column(db.String(80), nullable=False)
    source_text = db.Column(db.Text, default="", nullable=False)
    corrected_text = db.Column(db.Text, default="", nullable=False)
    explanation = db.Column(db.Text, default="", nullable=False)
    times_seen = db.Column(db.Integer, default=1, nullable=False)
    times_correct = db.Column(db.Integer, default=0, nullable=False)
    next_review = db.Column(db.Date, default=date.today, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "rule_key", name="uq_english_mistake_user_rule"),)


class EnglishTutorExercise(db.Model):
    __tablename__ = "curso_english_tutor_exercise"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    mistake_rule_key = db.Column(db.String(80), default="", nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    options_json = db.Column(db.Text, default="[]", nullable=False)
    answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, default="", nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    correct = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EnglishPronunciationAttempt(db.Model):
    __tablename__ = "curso_english_pronunciation_attempt"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    target_text = db.Column(db.Text, nullable=False)
    transcript = db.Column(db.Text, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    missing_json = db.Column(db.Text, default="[]", nullable=False)
    extra_json = db.Column(db.Text, default="[]", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EnglishTranslationMemory(db.Model):
    __tablename__ = "curso_english_translation_memory"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    source_text = db.Column(db.Text, nullable=False)
    normalized_source = db.Column(db.Text, nullable=False)
    translation = db.Column(db.Text, nullable=False)
    uses = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "normalized_source", name="uq_english_translation_user_source"),)


class EnglishCourseProgress(db.Model):
    __tablename__ = "curso_english_course_progress"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    item_type = db.Column(db.String(40), nullable=False)
    item_key = db.Column(db.String(220), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "item_type", "item_key", name="uq_english_progress_user_item"),)


class EnglishStudyEvent(db.Model):
    __tablename__ = "curso_english_study_event"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("curso_user.id"), nullable=False, index=True)
    study_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)
    item_key = db.Column(db.String(220), nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "event_type", "item_key", name="uq_english_event_user_item"),)


@app.context_processor
def inject_globals():
    current_user = get_current_user()
    roles = Role.query.order_by(Role.level.asc()).all()
    return {
        "site": SITE_DATA,
        "current_user": current_user,
        "all_roles": roles,
    }


@app.before_request
def load_user_into_context():
    g.user = get_current_user()


@app.template_filter("datetime_br")
def datetime_br(value):
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y %H:%M")


@app.template_filter("nl2br")
def nl2br(value):
    return (value or "").replace("\n", "<br>")


@app.template_filter("slugify")
def slugify_filter(value):
    return slugify(value or "")



def slugify(value: str) -> str:
    cleaned = (
        value.lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
    )
    parts = [piece for piece in cleaned.replace("/", " ").replace("-", " ").split() if piece]
    return "-".join(parts)



def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)



def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not g.user:
            flash("Faça login para acessar a área interna.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapper



def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not g.user or not g.user.is_admin:
            flash("Apenas o administrador pode acessar esta área.", "danger")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapper



def seed_roles() -> None:
    for role_data in ROLES_DATA:
        role = Role.query.filter_by(level=role_data["level"]).first()
        if not role:
            role = Role(**role_data)
            db.session.add(role)
        else:
            role.name = role_data["name"]
            role.description = role_data["description"]
    db.session.commit()



def seed_admin() -> None:
    admin_role = Role.query.filter_by(level=6).first() or Role.query.filter_by(level=1).first()
    admin_user = User.query.filter_by(email=DEFAULT_ADMIN_EMAIL).first()
    if not admin_user:
        admin_user = User(
            name="Washington",
            email=DEFAULT_ADMIN_EMAIL,
            is_admin=True,
            role_id=admin_role.id,
        )
        admin_user.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(admin_user)
        db.session.commit()
    elif not admin_user.is_admin:
        admin_user.is_admin = True
        admin_user.role_id = admin_role.id
        db.session.commit()
    elif admin_user.role_id != admin_role.id:
        admin_user.role_id = admin_role.id
        db.session.commit()



def seed_modules() -> None:
    if StudyModule.query.count() > 0:
        return

    for index, module_data in enumerate(DEFAULT_MODULES, start=1):
        module = StudyModule(
            title=module_data["title"],
            slug=slugify(module_data["title"]),
            summary=module_data["summary"],
            content=module_data["content"],
            min_role_level=module_data["min_role_level"],
            target_role_level=module_data["target_role_level"],
            passing_score=module_data["passing_score"],
            is_published=True,
            sort_order=index,
        )
        db.session.add(module)
        db.session.flush()

        for question_data in module_data["questions"]:
            question = Question(module_id=module.id, **question_data)
            db.session.add(question)

    db.session.commit()



@lru_cache(maxsize=1)
def load_portuguese_course_data():
    with open(PORTUGUES_COURSE_PATH, "r", encoding="utf-8") as file:
        course_payload = json.load(file)
    with open(PORTUGUES_ACTIVITY_PATH, "r", encoding="utf-8") as file:
        activity_payload = json.load(file)
    return course_payload, activity_payload


def derive_lesson_assets(lesson: dict) -> dict:
    bullet_points = [block[2:].strip() for block in lesson.get("blocks", []) if isinstance(block, str) and block.startswith("○ ")]
    quick_points = bullet_points[:4]
    if not quick_points:
        quick_points = [lesson.get("summary", "").strip(), lesson.get("preview", "").replace("○ ", "").strip()]
        quick_points = [item for item in quick_points if item][:3]

    checklist = []
    headings = lesson.get("headings", []) or []
    if headings:
        checklist.extend([f"Revisar: {heading['title']}" for heading in headings[:3]])
    while len(checklist) < 3:
        generic_items = [
            "Ler a lição com calma",
            "Anotar a regra principal",
            "Fazer o treino da própria lição",
        ]
        checklist.extend(generic_items[: max(0, 3 - len(checklist))])

    lesson["assets"] = {
        "quick_points": quick_points,
        "checklist": checklist[:4],
    }
    return lesson


def build_portuguese_overview():
    course_payload, activity_payload = load_portuguese_course_data()
    lessons = sorted(course_payload.get("lessons", []), key=lambda item: item.get("order", 0))
    normalized_lessons = [derive_lesson_assets(dict(lesson)) for lesson in lessons]
    quizzes = activity_payload.get("quizzes", [])
    flashcards = activity_payload.get("flashcards", [])

    overview = {
        "course_title": "Português Brasil · Área interna",
        "source_pdf": "Curso interno importado do pacote PortuguesBrasilDesktop",
        "source_pages": max((lesson.get("page_end", 0) for lesson in normalized_lessons), default=0),
        "highlights": [
            "Lições organizadas em sequência dentro da área interna da Legião.",
            "Marcação de progresso, notas locais, checklist e revisão por lição.",
            "Modo prática com quiz, flashcards e filtro por assunto.",
            "Prova final para consolidar o estudo de português.",
        ],
    }
    site_meta = {
        "total_lessons": len(normalized_lessons),
        "total_quizzes": len(quizzes),
        "final_exam_size": len(quizzes),
    }
    featured = normalized_lessons[:4]
    lesson_map = {lesson["slug"]: lesson for lesson in normalized_lessons}
    return {
        "overview": overview,
        "lessons": normalized_lessons,
        "lesson_map": lesson_map,
        "featured": featured,
        "quizzes": quizzes,
        "flashcards": flashcards,
        "site_meta": site_meta,
    }


PORTUGUESE_STAGE_RULES = [
    {
        "start": 0,
        "end": 3,
        "min_role_level": 1,
        "title": "Núcleo I · Base de entrada",
        "summary": "Introdução, leitura do material e primeiras classes gramaticais.",
    },
    {
        "start": 4,
        "end": 7,
        "min_role_level": 2,
        "title": "Núcleo II · Expansão morfológica",
        "summary": "Pronome, verbo, advérbio e aprofundamento do vocabulário funcional.",
    },
    {
        "start": 8,
        "end": 10,
        "min_role_level": 3,
        "title": "Núcleo III · Conexão e uso",
        "summary": "Preposição, conjunção e interjeição para organizar melhor a expressão.",
    },
    {
        "start": 11,
        "end": 13,
        "min_role_level": 4,
        "title": "Núcleo IV · Precisão normativa",
        "summary": "Porquês, senão/se não e sintaxe para elevar o padrão de escrita.",
    },
    {
        "start": 14,
        "end": 16,
        "min_role_level": 5,
        "title": "Núcleo V · Consolidação avançada",
        "summary": "Exercícios de análise, estruturas complexas e estudo das orações.",
    },
]
PORTUGUESE_PRACTICE_MIN_ROLE = 2
PORTUGUESE_FINAL_EXAM_MIN_ROLE = 3


def get_role_name(level: int) -> str:
    role = next((item for item in ROLES_DATA if item["level"] == level), None)
    return role["name"] if role else f"Nível {level}"



def can_access_role_level(user: User | None, min_level: int) -> bool:
    if not user:
        return False
    return user.is_admin or user.role.level >= min_level



def stage_rule_for_order(order: int) -> dict:
    for rule in PORTUGUESE_STAGE_RULES:
        if rule["start"] <= order <= rule["end"]:
            return rule
    return PORTUGUESE_STAGE_RULES[-1]



def enrich_portuguese_course_for_user(course_data: dict, user: User | None) -> dict:
    enriched = dict(course_data)
    lessons = []
    lesson_map = {}
    phase_groups = []

    for rule in PORTUGUESE_STAGE_RULES:
        phase_groups.append(
            {
                **rule,
                "required_role_name": get_role_name(rule["min_role_level"]),
                "is_unlocked": can_access_role_level(user, rule["min_role_level"]),
                "lessons": [],
            }
        )

    for lesson in course_data["lessons"]:
        item = dict(lesson)
        rule = stage_rule_for_order(item.get("order", 0))
        item["min_role_level"] = rule["min_role_level"]
        item["required_role_name"] = get_role_name(rule["min_role_level"])
        item["stage_title"] = rule["title"]
        item["stage_summary"] = rule["summary"]
        item["is_locked"] = not can_access_role_level(user, item["min_role_level"])
        lessons.append(item)
        lesson_map[item["slug"]] = item
        for group in phase_groups:
            if group["start"] <= item.get("order", 0) <= group["end"]:
                group["lessons"].append(item)
                break

    accessible_lesson_slugs = {lesson["slug"] for lesson in lessons if not lesson["is_locked"]}
    accessible_quizzes = [item for item in course_data["quizzes"] if item.get("lesson_slug") in accessible_lesson_slugs]
    accessible_flashcards = [item for item in course_data["flashcards"] if item.get("lesson_slug") in accessible_lesson_slugs]
    featured = [lesson for lesson in lessons if not lesson["is_locked"]][:4] or lessons[:4]
    next_unlock = next((group for group in phase_groups if not group["is_unlocked"]), None)

    site_meta = dict(course_data["site_meta"])
    site_meta.update(
        {
            "accessible_lessons": len(accessible_lesson_slugs),
            "locked_lessons": len(lessons) - len(accessible_lesson_slugs),
            "accessible_quizzes": len(accessible_quizzes),
            "practice_min_role_name": get_role_name(PORTUGUESE_PRACTICE_MIN_ROLE),
            "final_exam_min_role_name": get_role_name(PORTUGUESE_FINAL_EXAM_MIN_ROLE),
        }
    )

    enriched.update(
        {
            "lessons": lessons,
            "lesson_map": lesson_map,
            "featured": featured,
            "quizzes": accessible_quizzes,
            "flashcards": accessible_flashcards,
            "site_meta": site_meta,
            "phase_groups": phase_groups,
            "next_unlock": next_unlock,
            "course_access": {
                "practice_min_role_level": PORTUGUESE_PRACTICE_MIN_ROLE,
                "practice_min_role_name": get_role_name(PORTUGUESE_PRACTICE_MIN_ROLE),
                "final_exam_min_role_level": PORTUGUESE_FINAL_EXAM_MIN_ROLE,
                "final_exam_min_role_name": get_role_name(PORTUGUESE_FINAL_EXAM_MIN_ROLE),
            },
        }
    )
    return enriched



def ensure_portuguese_access(min_level: int, area_label: str):
    if can_access_role_level(g.user, min_level):
        return None
    flash(
        f"Seu cargo atual ainda não libera {area_label}. Necessário: {get_role_name(min_level)} ou superior.",
        "warning",
    )
    return redirect(url_for("portugues_home"))


def search_portuguese_lessons(query: str, lessons: list[dict]) -> list[dict]:
    return search_collection(
        query,
        lessons,
        text_fields=["title", "label", "summary"],
        result_key="lesson",
        fallback_field="summary",
    )



@lru_cache(maxsize=1)
def load_english_course_data():
    with open(INGLES_COURSE_PATH, "r", encoding="utf-8") as file:
        course_payload = json.load(file)
    with open(INGLES_ACTIVITY_PATH, "r", encoding="utf-8") as file:
        activity_payload = json.load(file)
    return course_payload, activity_payload


ENGLISH_STAGE_RULES = [
    {
        "start": 1,
        "end": 2,
        "min_role_level": 1,
        "title": "Núcleo I · Base funcional",
        "summary": "Entrada no inglês com sobrevivência básica, apresentação e estruturas curtas.",
    },
    {
        "start": 3,
        "end": 4,
        "min_role_level": 2,
        "title": "Núcleo II · Construção diária",
        "summary": "Rotina, tempo, cidade e expansão do uso cotidiano com mais segurança.",
    },
    {
        "start": 5,
        "end": 6,
        "min_role_level": 3,
        "title": "Núcleo III · Comunicação aplicada",
        "summary": "Interação em situações práticas, perguntas, respostas e vocabulário funcional.",
    },
    {
        "start": 7,
        "end": 8,
        "min_role_level": 4,
        "title": "Núcleo IV · Consolidação de uso",
        "summary": "Mais fluidez para descrever ações, contexto, rotina ampliada e compreensão oral.",
    },
    {
        "start": 9,
        "end": 9,
        "min_role_level": 5,
        "title": "Núcleo V · Segurança de expressão",
        "summary": "Módulos mais densos para sustentar conversa com menos travamento.",
    },
    {
        "start": 10,
        "end": 10,
        "min_role_level": 6,
        "title": "Núcleo VI · Fechamento completo",
        "summary": "Topo da trilha interna do inglês com acesso integral e revisão final.",
    },
]
ENGLISH_PRACTICE_MIN_ROLE = 2
ENGLISH_FINAL_EXAM_MIN_ROLE = 3


def english_stage_rule_for_number(number: int) -> dict:
    for rule in ENGLISH_STAGE_RULES:
        if rule["start"] <= number <= rule["end"]:
            return rule
    return ENGLISH_STAGE_RULES[-1]


def build_english_module_assets(module: dict) -> dict:
    lesson_titles = [lesson.get("title", "") for lesson in module.get("lessons", [])]
    return {
        "lesson_count": len(lesson_titles),
        "lesson_preview": lesson_titles[:4],
        "chipline": " • ".join(module.get("skills", [])[:5]),
        "quick_words": module.get("vocabulary", [])[:10],
    }


def build_english_overview():
    course_payload, activity_payload = load_english_course_data()
    modules = sorted(course_payload.get("modules", []), key=lambda item: item.get("number", 0))
    normalized_modules = []
    for index, module in enumerate(modules):
        item = dict(module)
        item["assets"] = build_english_module_assets(item)
        item["prev_slug"] = modules[index - 1]["slug"] if index > 0 else None
        item["next_slug"] = modules[index + 1]["slug"] if index < len(modules) - 1 else None
        normalized_modules.append(item)

    module_by_slug = {module["slug"]: module for module in normalized_modules}
    quizzes = activity_payload.get("quizzes", [])
    flashcards = activity_payload.get("flashcards", [])
    final_exam = activity_payload.get("final_exam", [])
    phrasebook = course_payload.get("phrasebook", [])
    vocabulary_banks = course_payload.get("vocabulary_banks", [])
    study_plan = course_payload.get("study_plan", [])

    overview = dict(course_payload.get("overview", {}))
    overview.setdefault("site_name", "English Track Pro · Área interna")
    overview.setdefault("hero_title", "Curso interno de inglês")
    overview.setdefault("hero_subtitle", "Trilha estruturada para membros logados.")

    site_meta = {
        "total_modules": len(normalized_modules),
        "total_lessons": sum(len(module.get("lessons", [])) for module in normalized_modules),
        "total_quizzes": len(quizzes),
        "total_flashcards": len(flashcards),
        "final_exam_size": len(final_exam),
    }

    return {
        "overview": overview,
        "modules": normalized_modules,
        "module_map": module_by_slug,
        "quizzes": quizzes,
        "flashcards": flashcards,
        "final_exam": final_exam,
        "phrasebook": phrasebook,
        "vocabulary_banks": vocabulary_banks,
        "study_plan": study_plan,
        "featured": normalized_modules[:6],
        "site_meta": site_meta,
    }


def enrich_english_course_for_user(course_data: dict, user: User | None) -> dict:
    enriched = dict(course_data)
    modules = []
    module_map = {}
    phase_groups = []

    for rule in ENGLISH_STAGE_RULES:
        phase_groups.append(
            {
                **rule,
                "required_role_name": get_role_name(rule["min_role_level"]),
                "is_unlocked": can_access_role_level(user, rule["min_role_level"]),
                "modules": [],
            }
        )

    for module in course_data["modules"]:
        item = dict(module)
        rule = english_stage_rule_for_number(item.get("number", 0))
        item["min_role_level"] = rule["min_role_level"]
        item["required_role_name"] = get_role_name(rule["min_role_level"])
        item["stage_title"] = rule["title"]
        item["stage_summary"] = rule["summary"]
        item["is_locked"] = not can_access_role_level(user, item["min_role_level"])
        modules.append(item)
        module_map[item["slug"]] = item
        for group in phase_groups:
            if group["start"] <= item.get("number", 0) <= group["end"]:
                group["modules"].append(item)
                break

    accessible_module_slugs = {module["slug"] for module in modules if not module["is_locked"]}
    accessible_quizzes = [item for item in course_data["quizzes"] if item.get("module_slug") in accessible_module_slugs]
    accessible_flashcards = [item for item in course_data["flashcards"] if item.get("module_slug") in accessible_module_slugs]
    accessible_banks = [item for item in course_data["vocabulary_banks"] if item.get("module_slug") in accessible_module_slugs]
    featured = [module for module in modules if not module["is_locked"]][:6] or modules[:6]
    next_unlock = next((group for group in phase_groups if not group["is_unlocked"]), None)

    site_meta = dict(course_data["site_meta"])
    site_meta.update(
        {
            "accessible_modules": len(accessible_module_slugs),
            "locked_modules": len(modules) - len(accessible_module_slugs),
            "accessible_quizzes": len(accessible_quizzes),
            "accessible_flashcards": len(accessible_flashcards),
        }
    )

    enriched.update(
        {
            "modules": modules,
            "module_map": module_map,
            "featured": featured,
            "quizzes": accessible_quizzes,
            "flashcards": accessible_flashcards,
            "vocabulary_banks": accessible_banks,
            "phrasebook": course_data["phrasebook"],
            "study_plan": course_data["study_plan"],
            "site_meta": site_meta,
            "phase_groups": phase_groups,
            "next_unlock": next_unlock,
            "course_access": {
                "practice_min_role_level": ENGLISH_PRACTICE_MIN_ROLE,
                "practice_min_role_name": get_role_name(ENGLISH_PRACTICE_MIN_ROLE),
                "final_exam_min_role_level": ENGLISH_FINAL_EXAM_MIN_ROLE,
                "final_exam_min_role_name": get_role_name(ENGLISH_FINAL_EXAM_MIN_ROLE),
            },
        }
    )
    return enriched


def ensure_english_access(min_level: int, area_label: str):
    if can_access_role_level(g.user, min_level):
        return None
    flash(
        f"Seu cargo atual ainda não libera {area_label}. Necessário: {get_role_name(min_level)} ou superior.",
        "warning",
    )
    return redirect(url_for("ingles_home"))


def search_english_modules(query: str, modules: list[dict]) -> list[dict]:
    return search_collection(
        query,
        modules,
        text_fields=["title", "summary", "skills", "vocabulary"],
        result_key="module",
        fallback_field="summary",
        nested_list_field="lessons",
        nested_text_fields=["title", "focus", "examples", "patterns"],
        nested_limit=4,
    )


def _english_preference(user_id: int) -> EnglishTutorPreference:
    preference = db.session.get(EnglishTutorPreference, user_id)
    if preference is None:
        preference = EnglishTutorPreference(user_id=user_id)
        db.session.add(preference)
        db.session.commit()
    return preference


def _english_preference_settings(preference: EnglishTutorPreference) -> dict[str, str]:
    return {
        "tutor_engine": preference.tutor_engine,
        "tutor_scenario": preference.scenario_key,
        "local_ai_url": preference.local_ai_url,
        "local_ai_model": preference.local_ai_model,
        "local_ai_model_file": preference.local_ai_model_file,
        "voice_model_file": preference.voice_model_file,
    }


def _english_record_event(user_id: int, event_type: str, item_key: str, xp: int) -> int:
    event = EnglishStudyEvent.query.filter_by(
        user_id=user_id,
        event_type=event_type[:50],
        item_key=item_key[:220],
    ).first()
    if event is not None:
        return 0
    db.session.add(
        EnglishStudyEvent(
            user_id=user_id,
            study_date=date.today(),
            event_type=event_type[:50],
            item_key=item_key[:220],
            xp=max(0, int(xp)),
        )
    )
    return max(0, int(xp))


def _english_streak(user_id: int) -> int:
    values = {
        row[0]
        for row in db.session.query(EnglishStudyEvent.study_date)
        .filter_by(user_id=user_id)
        .distinct()
        .all()
        if row[0]
    }
    if not values:
        return 0
    cursor = date.today()
    if cursor not in values:
        cursor -= timedelta(days=1)
        if cursor not in values:
            return 0
    streak = 0
    while cursor in values:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _english_learning_metrics(user_id: int) -> dict:
    xp = db.session.query(db.func.coalesce(db.func.sum(EnglishStudyEvent.xp), 0)).filter_by(user_id=user_id).scalar() or 0
    completed_modules = EnglishCourseProgress.query.filter_by(user_id=user_id, item_type="module", completed=True).count()
    completed_lessons = EnglishCourseProgress.query.filter_by(user_id=user_id, item_type="lesson", completed=True).count()
    completed_exercises = EnglishTutorExercise.query.filter_by(user_id=user_id, completed=True).count()
    correct_exercises = EnglishTutorExercise.query.filter_by(user_id=user_id, completed=True, correct=True).count()
    return {
        "xp": int(xp),
        "streak": _english_streak(user_id),
        "completed_modules": completed_modules,
        "completed_lessons": completed_lessons,
        "completed_exercises": completed_exercises,
        "accuracy": round(correct_exercises / completed_exercises * 100) if completed_exercises else 0,
    }


def _english_tutor_stats(user_id: int) -> dict:
    return {
        "conversations": EnglishTutorMessage.query.filter_by(user_id=user_id, role="assistant").count(),
        "mistakes": EnglishTutorMistake.query.filter_by(user_id=user_id).count(),
        "mastered": EnglishTutorMistake.query.filter(
            EnglishTutorMistake.user_id == user_id,
            EnglishTutorMistake.times_correct >= 3,
        ).count(),
        "exercises": EnglishTutorExercise.query.filter_by(user_id=user_id, completed=True, correct=True).count(),
    }


def _english_student_context(user_id: int) -> dict:
    mistakes = (
        EnglishTutorMistake.query.filter_by(user_id=user_id)
        .order_by(
            (EnglishTutorMistake.times_seen - EnglishTutorMistake.times_correct).desc(),
            EnglishTutorMistake.updated_at.desc(),
        )
        .limit(8)
        .all()
    )
    progress = _english_learning_metrics(user_id)
    return {
        "frequent_difficulties": [
            {
                "rule": item.rule_key,
                "explanation": item.explanation,
                "seen": item.times_seen,
                "correct": item.times_correct,
            }
            for item in mistakes
        ],
        "completed_lessons": progress["completed_lessons"],
        "completed_modules": progress["completed_modules"],
        "exercise_accuracy_percent": progress["accuracy"],
        "study_streak": progress["streak"],
    }


def _serialize_english_exercise(exercise: EnglishTutorExercise | None) -> dict | None:
    if exercise is None:
        return None
    try:
        options = json.loads(exercise.options_json or "[]")
    except json.JSONDecodeError:
        options = []
    return {
        "id": exercise.id,
        "rule_key": exercise.mistake_rule_key,
        "prompt": exercise.prompt,
        "options": options if isinstance(options, list) else [],
        "answer": exercise.answer,
        "explanation": exercise.explanation,
        "attempts": exercise.attempts,
    }


def _store_english_tutor_result(user_id: int, source: str, result: dict) -> dict | None:
    corrected = str(result.get("corrected_text", "")).strip()[:4000]
    corrections = []
    for item in result.get("corrections", [])[:20] if isinstance(result.get("corrections"), list) else []:
        if not isinstance(item, dict):
            continue
        rule_key = re.sub(r"[^a-z0-9_-]+", "-", str(item.get("rule_key", "general")).lower()).strip("-")[:80]
        explanation = str(item.get("explanation", "")).strip()[:1000]
        if rule_key and explanation:
            corrections.append({"rule_key": rule_key, "explanation": explanation})

    db.session.add(EnglishTutorMessage(user_id=user_id, role="user", content=source[:4000], engine=""))
    assistant = EnglishTutorMessage(
        user_id=user_id,
        role="assistant",
        content=str(result.get("reply", ""))[:8000],
        corrected_text=corrected,
        explanations_json=json.dumps(corrections, ensure_ascii=False),
        engine=str(result.get("engine", "Professor integrado offline"))[:160],
    )
    db.session.add(assistant)
    db.session.flush()

    for correction in corrections:
        if correction["rule_key"] == "capitalization":
            continue
        mistake = EnglishTutorMistake.query.filter_by(user_id=user_id, rule_key=correction["rule_key"]).first()
        if mistake is None:
            mistake = EnglishTutorMistake(
                user_id=user_id,
                rule_key=correction["rule_key"],
                source_text=source[:4000],
                corrected_text=corrected,
                explanation=correction["explanation"],
                next_review=date.today(),
            )
            db.session.add(mistake)
        else:
            mistake.source_text = source[:4000]
            mistake.corrected_text = corrected
            mistake.explanation = correction["explanation"]
            mistake.times_seen += 1
            mistake.next_review = date.today()

    stored_exercise = None
    raw_exercise = result.get("exercise")
    if isinstance(raw_exercise, dict):
        prompt = str(raw_exercise.get("prompt", "")).strip()[:1000]
        answer = str(raw_exercise.get("answer", "")).strip()[:1000]
        options = [str(item).strip()[:1000] for item in raw_exercise.get("options", []) if str(item).strip()][:6]
        options = list(dict.fromkeys(options))
        if answer and answer not in options:
            options.append(answer)
        if prompt and answer and len(options) >= 2:
            stored = EnglishTutorExercise(
                user_id=user_id,
                mistake_rule_key=re.sub(
                    r"[^a-z0-9_-]+", "-", str(raw_exercise.get("rule_key", "general")).lower()
                ).strip("-")[:80],
                prompt=prompt,
                options_json=json.dumps(options, ensure_ascii=False),
                answer=answer,
                explanation=str(raw_exercise.get("explanation", ""))[:1000],
            )
            db.session.add(stored)
            db.session.flush()
            stored_exercise = _serialize_english_exercise(stored)

    _english_record_event(user_id, "tutor_message", f"message:{assistant.id}", 3)
    db.session.commit()
    return stored_exercise


def _normalize_english_memory_source(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _english_sentence_units(value: str) -> list[str]:
    return [
        match.group(0).strip()
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", value)
        if match.group(0).strip()
    ]


def _store_english_translation_pair(user_id: int, source: str, translation: str) -> None:
    normalized = _normalize_english_memory_source(source)
    memory = EnglishTranslationMemory.query.filter_by(user_id=user_id, normalized_source=normalized).first()
    if memory is None:
        db.session.add(
            EnglishTranslationMemory(
                user_id=user_id,
                source_text=source,
                normalized_source=normalized,
                translation=translation,
            )
        )
    else:
        memory.source_text = source
        memory.translation = translation
        memory.uses += 1


def _english_memory_segments(user_id: int, source: str) -> list[dict]:
    units = _english_sentence_units(source)[:80]
    if not units:
        return []
    normalized = [_normalize_english_memory_source(item) for item in units]
    rows = EnglishTranslationMemory.query.filter(
        EnglishTranslationMemory.user_id == user_id,
        EnglishTranslationMemory.normalized_source.in_(normalized),
    ).all()
    lookup = {row.normalized_source: row.translation for row in rows}
    return [
        {"source": item, "translation": lookup[_normalize_english_memory_source(item)]}
        for item in units
        if _normalize_english_memory_source(item) in lookup
    ]


def init_database() -> None:
    with app.app_context():
        db.create_all()
        seed_roles()
        seed_admin()
        seed_modules()



def can_access_module(user: User, module: StudyModule) -> bool:
    if user.is_admin:
        return True
    return user.role.level >= module.min_role_level



def latest_attempt_for(user_id: int, module_id: int):
    return (
        ModuleAttempt.query.filter_by(user_id=user_id, module_id=module_id)
        .order_by(ModuleAttempt.created_at.desc())
        .first()
    )



def maybe_promote_user(user: User, module: StudyModule) -> str | None:
    if module.target_role_level <= user.role.level:
        return None

    target_role = Role.query.filter_by(level=module.target_role_level).first()
    if not target_role:
        return None

    user.role_id = target_role.id
    db.session.commit()
    return target_role.name





def _local_mcp_answer(question: str, context: dict) -> str:
    page_title = context.get("page_title") or "página atual"
    path = context.get("path") or "rota atual"
    selected_text = (context.get("selected_text") or "").strip()

    lines = [
        f"**Análise contextual da interface: {page_title}**",
        "",
        "Estou usando o contexto da página aberta para orientar a resposta. Como a chave da IA não está configurada no ambiente, esta resposta usa o modo MCP local.",
        "",
        f"**Pergunta:** {question}",
        f"**Rota:** `{path}`",
    ]
    if selected_text:
        preview = selected_text[:600] + ("..." if len(selected_text) > 600 else "")
        lines.extend(["", "**Trecho selecionado/visível:**", preview])

    lines.extend([
        "",
        "**Direção lógica:**",
        "1. Identifique exatamente em qual bloco da tela você está mexendo.",
        "2. Confirme se a ação afeta apenas conteúdo visual, dados do usuário ou permissão de acesso.",
        "3. Se for alteração visual, ajuste primeiro o template e depois o CSS correspondente.",
        "4. Se for regra de acesso, confirme login, cargo e rota protegida antes de alterar a interface.",
        "5. Depois da alteração, reinicie o Flask e use Ctrl + F5 para limpar cache.",
    ])
    return "\n".join(lines)


def _build_mcp_prompt(question: str, context: dict) -> str:
    user_name = getattr(g.user, "name", "visitante") if getattr(g, "user", None) else "visitante"
    role_name = getattr(getattr(g.user, "role", None), "name", "sem cargo") if getattr(g, "user", None) else "visitante"
    visible_text = (context.get("visible_text") or "")[:4500]
    selected_text = (context.get("selected_text") or "")[:1500]
    return f"""
Você é um MCP contextual do portal. Responda em português do Brasil, com raciocínio lógico, direto e útil.
Seu papel é ajudar o usuário a entender ou decidir algo dentro da interface atual do portal, sem inventar dados.

Contexto do usuário:
- Nome: {user_name}
- Cargo/acesso: {role_name}

Contexto da interface:
- Título da página: {context.get('page_title') or 'não identificado'}
- Rota atual: {context.get('path') or 'não identificada'}
- URL: {context.get('url') or 'não informada'}
- Texto selecionado: {selected_text or 'nenhum'}
- Texto visível resumido da página: {visible_text or 'não enviado'}

Pergunta do usuário:
{question}

Regras da resposta:
- Explique primeiro a conclusão prática.
- Use o contexto da tela atual.
- Se faltar informação, diga exatamente o que falta.
- Não exponha senhas, chaves de API nem credenciais.
- Quando orientar mudança no sistema, cite quais arquivos provavelmente precisam ser alterados.
- Mantenha a resposta objetiva e aplicável.
""".strip()





def _safe_agent_path(raw_path: str) -> str:
    """Normaliza caminho criado pelo agente sem permitir sair do workspace."""
    cleaned = (raw_path or "").strip().replace("\\", "/")
    cleaned = cleaned.strip("/ ")
    cleaned = re.sub(r"[^A-Za-z0-9_./\- ]+", "_", cleaned)
    parts = []
    for part in cleaned.split("/"):
        part = part.strip()
        if not part or part in {".", ".."}:
            continue
        parts.append(part[:80])
    if not parts:
        return "resposta_do_agente.md"
    path = "/".join(parts)
    if "." not in os.path.basename(path):
        path = f"{path}.txt"
    return path[:220]


def _extract_agent_files(text: str) -> list[dict]:
    """Extrai arquivos no formato [[FILE:caminho]]conteúdo[[/FILE]]."""
    files = []
    pattern = re.compile(r"\[\[FILE:(.*?)\]\](.*?)\[\[/FILE\]\]", re.DOTALL | re.IGNORECASE)
    for match in pattern.finditer(text or ""):
        name = _safe_agent_path(match.group(1))
        content = match.group(2).strip("\n")
        if content:
            files.append({"path": name, "content": content})
    return files


def _default_agent_files(question: str, answer: str) -> list[dict]:
    """Fallback local quando a IA não devolve blocos de arquivo."""
    q = (question or "").lower()
    files = [
        {
            "path": "README.md",
            "content": "# Arquivos gerados pelo Chat Agente\n\nPedido do usuário:\n\n> " + (question or "sem pedido") + "\n\nResumo do agente:\n\n" + (answer or "Sem resposta."),
        }
    ]
    if any(word in q for word in ["python", "flask", "site", "html", "css", "javascript", "programa", "app"]):
        files.extend([
            {
                "path": "app.py",
                "content": "from flask import Flask, render_template\n\napp = Flask(__name__)\n\n@app.route('/')\ndef index():\n    return render_template('index.html')\n\nif __name__ == '__main__':\n    app.run(debug=True)\n",
            },
            {
                "path": "templates/index.html",
                "content": "<!doctype html>\n<html lang='pt-br'>\n<head>\n  <meta charset='utf-8'>\n  <meta name='viewport' content='width=device-width, initial-scale=1'>\n  <title>Projeto gerado pelo Chat Agente</title>\n  <link rel='stylesheet' href='/static/css/style.css'>\n</head>\n<body>\n  <main class='card'>\n    <h1>Projeto gerado pelo Chat Agente</h1>\n    <p>Use este ponto de partida e ajuste conforme sua necessidade.</p>\n  </main>\n</body>\n</html>\n",
            },
            {
                "path": "static/css/style.css",
                "content": "body{margin:0;min-height:100vh;background:#07120d;color:#edf7ee;font-family:Arial,sans-serif;display:grid;place-items:center}.card{max-width:760px;padding:32px;border-radius:28px;background:#0c1f16;border:1px solid rgba(240,201,79,.25);box-shadow:0 24px 70px rgba(0,0,0,.35)}h1{margin-top:0}p{color:#b8c9bb}\n",
            },
            {
                "path": "requirements.txt",
                "content": "Flask>=3.0.0\n",
            },
        ])
    return files


def _save_agent_zip(files: list[dict], question: str) -> tuple[str, list[str]]:
    os.makedirs(AGENT_WORKSPACE_DIR, exist_ok=True)
    job_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
    job_dir = os.path.join(AGENT_WORKSPACE_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    written = []
    for item in files[:80]:
        rel_path = _safe_agent_path(item.get("path") or "arquivo.txt")
        content = item.get("content") or ""
        target = os.path.abspath(os.path.join(job_dir, rel_path))
        if not target.startswith(os.path.abspath(job_dir) + os.sep):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        written.append(rel_path)

    if not written:
        target = os.path.join(job_dir, "README.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("# Resposta do Chat Agente\n\n" + (question or "Sem pedido."))
        written.append("README.md")

    zip_path = os.path.join(AGENT_WORKSPACE_DIR, f"{job_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, filenames in os.walk(job_dir):
            for filename in filenames:
                abs_path = os.path.join(root, filename)
                arcname = os.path.relpath(abs_path, job_dir)
                zf.write(abs_path, arcname)
    return job_id, written

def _agent_conversation_for_user(conversation_id=None, title: str | None = None) -> AgentConversation:
    conv = None
    if conversation_id:
        conv = AgentConversation.query.filter_by(id=conversation_id, user_id=g.user.id).first()
    if not conv:
        clean_title = (title or "Nova conversa").strip()[:160] or "Nova conversa"
        conv = AgentConversation(user_id=g.user.id, title=clean_title)
        db.session.add(conv)
        db.session.commit()
    return conv


def _save_agent_message(conversation: AgentConversation, role: str, content: str, stage: str = "message") -> None:
    db.session.add(AgentMessage(conversation_id=conversation.id, role=role, content=content or "", stage=stage or "message"))
    conversation.updated_at = datetime.utcnow()
    if conversation.title == "Nova conversa" and role == "user" and content:
        conversation.title = content.strip().replace("\n", " ")[:90]
    db.session.commit()


def _serialize_agent_conversation(conv: AgentConversation) -> dict:
    return {
        "id": conv.id,
        "title": conv.title,
        "updated_at": conv.updated_at.strftime("%d/%m/%Y %H:%M") if conv.updated_at else "",
        "created_at": conv.created_at.strftime("%d/%m/%Y %H:%M") if conv.created_at else "",
        "messages": [
            {"role": msg.role, "content": msg.content, "stage": msg.stage, "created_at": msg.created_at.strftime("%d/%m/%Y %H:%M")}
            for msg in conv.messages
        ],
    }


def _call_ollama(prompt: str, base_url: str, model: str) -> str:
    clean_base = _normalize_ollama_base_url(base_url)
    clean_model = (model or "").strip()
    if not clean_model:
        raise RuntimeError("Nenhum modelo Ollama foi selecionado. Escaneie os modelos locais no Admin e selecione um modelo instalado.")
    payload = json.dumps({
        "model": clean_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.25}
    }).encode("utf-8")
    req = urllib.request.Request(
        clean_base + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        return (data.get("response") or "").strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:400]
        if exc.code == 404:
            try:
                available = ", ".join(m["name"] for m in _list_ollama_models(clean_base))
            except Exception:
                available = "não consegui listar os modelos instalados"
            raise RuntimeError(f"Modelo Ollama não encontrado: {clean_model}. Modelos disponíveis: {available}. Detalhe: {detail}") from exc
        raise RuntimeError(f"Erro HTTP do Ollama {exc.code}. Detalhe: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Não consegui conectar ao Ollama. " + _ollama_connection_hint(clean_base) + f" Detalhe: {exc.reason}") from exc


def _call_agent_model(prompt: str, ai_config: dict) -> tuple[str, str, str | None]:
    provider = (ai_config.get("provider") or "gemini").strip().lower()
    if provider == "ollama":
        answer = _call_ollama(prompt, ai_config.get("ollama_base_url"), ai_config.get("ollama_model"))
        return answer, "ollama", ai_config.get("ollama_model")
    api_key = (ai_config.get("api_key") or "").strip()
    if api_key:
        model_name = (ai_config.get("model") or "gemini-2.5-flash").strip()
        answer = call_ai("chat", prompt, api_key=api_key, model_name=model_name)
        return answer, "gemini", model_name
    return "", "local", None


def _build_agent_stage_prompt(question: str, context: dict | None = None, stage: str = "plan", chain: list[dict] | None = None) -> str:
    chain = chain or _select_agent_chain(question, context, stage)
    base = _build_agent_prompt(question, context) + "\n\n" + _build_multi_agent_block(chain)
    if stage == "plan":
        return base + """

MODO ETAPA 1 — PLANO ANTES DE EXECUTAR:
Não entregue o resultado final ainda. Mostre apenas um raciocínio resumido e verificável, sem pensamento interno bruto.
Responda com:
1. Entendi o objetivo
2. Contexto que vou usar
3. Etapas que pretendo seguir
4. Riscos/arquivos envolvidos
5. Pergunta final: Posso executar ou deseja que eu repense?
"""
    if stage == "rethink":
        return base + """

MODO REPENSAR:
Revise o plano anterior, encontre pontos fracos e proponha um plano melhor.
Não entregue o resultado final ainda. Mostre um resumo lógico, verificável e peça confirmação para executar.
"""
    return base + """

MODO EXECUÇÃO APROVADA:
Agora entregue o resultado final. Se for pedido com arquivos/ZIP, gere os blocos [[FILE:caminho]] completos.
Antes do resultado, inclua um pequeno resumo das etapas executadas, sem expor pensamento interno bruto.
"""


def _local_agent_answer(question: str, context: dict | None = None) -> str:
    context = context or {}
    user_name = getattr(g.user, "name", "usuário") if getattr(g, "user", None) else "usuário"
    role_name = getattr(getattr(g.user, "role", None), "name", "membro") if getattr(g, "user", None) else "membro"
    page_context = (context.get("page_context") or "").strip()
    selected_text = (context.get("selected_text") or "").strip()

    response = [
        f"**Chat Agente do Portal — {user_name}**",
        "",
        "Estou em modo local porque a IA externa pode não estar configurada ou disponível. Mesmo assim, posso orientar usando a lógica do portal.",
        "",
        f"**Seu acesso atual:** {role_name}",
        f"**Pergunta:** {question}",
        "",
        "**Resposta prática:**",
        "- Verifique primeiro em qual página do portal você está: Início, Área interna, Português, Inglês, Admin ou Documentos.",
        "- Se a dúvida for sobre liberação de conteúdo, confira o cargo mínimo exigido e o cargo atual do usuário.",
        "- Se a dúvida for sobre alteração visual, normalmente os arquivos envolvidos são o template HTML da página e o CSS correspondente.",
        "- Se a dúvida for sobre IA, confirme se a Google API Key foi salva no painel Admin e se o modelo selecionado está disponível.",
        "- Quando a conversa crescer, o agente LeanCTX deve compactar o histórico e passar somente o essencial para o próximo agente.",
    ]
    if page_context:
        preview = page_context[:700] + ("..." if len(page_context) > 700 else "")
        response.extend(["", "**Contexto enviado pela tela:**", preview])
    if selected_text:
        preview = selected_text[:500] + ("..." if len(selected_text) > 500 else "")
        response.extend(["", "**Trecho selecionado:**", preview])
    response.extend([
        "",
        "**Próximo passo recomendado:**",
        "Explique qual resultado você quer alcançar nessa tela e eu posso transformar isso em uma orientação de alteração ou regra de uso.",
    ])
    return "\n".join(response)


def _build_agent_prompt(question: str, context: dict | None = None) -> str:
    context = context or {}
    user_name = getattr(g.user, "name", "usuário") if getattr(g, "user", None) else "usuário"
    role_name = getattr(getattr(g.user, "role", None), "name", "membro") if getattr(g, "user", None) else "membro"
    history = context.get("history") or []
    history_lines = []
    for item in history[-8:]:
        role = (item.get("role") or "").strip()
        content = (item.get("content") or "").strip()[:900]
        if content:
            history_lines.append(f"{role}: {content}")

    page_context = (context.get("page_context") or "")[:5000]
    selected_text = (context.get("selected_text") or "")[:1500]
    return f"""
Você é o Chat Agente do Portal. Responda em português do Brasil, de forma lógica, objetiva e útil.
Você ajuda o usuário dentro do portal, considerando interface, cursos, permissões, admin, páginas, conteúdo e integrações de IA.
Aplique LeanCTX: mantenha contexto enxuto, remova repetição, preserve decisões importantes e passe apenas o necessário para o próximo agente.
Não exponha credenciais, chaves de API ou senhas. Se uma ação envolver segurança, explique o cuidado necessário.

Usuário conectado:
- Nome: {user_name}
- Cargo: {role_name}

Contexto atual da interface:
- Página: {context.get('page_title') or 'não informada'}
- Rota: {context.get('path') or 'não informada'}
- Texto selecionado: {selected_text or 'nenhum'}
- Texto visível/contexto: {page_context or 'não enviado'}

Histórico recente do chat:
{chr(10).join(history_lines) if history_lines else 'sem histórico anterior'}

Pergunta atual:
{question}

Como responder:
1. Comece com a conclusão prática.
2. Use o contexto da página atual quando existir.
3. Se for orientação técnica, indique os arquivos prováveis e a lógica da alteração.
4. Se faltar informação, diga exatamente o que falta.
5. Evite resposta longa demais; seja claro e acionável.
6. Quando o usuário pedir para criar arquivos, gerar projeto, gerar ZIP, criar código ou entregar algo baixável, inclua os arquivos no final usando exatamente este formato:
[[FILE:nome/do/arquivo.ext]]
conteúdo completo do arquivo aqui
[[/FILE]]
Pode criar vários blocos [[FILE:...]]. Não use caminhos absolutos e não use ../.
""".strip()


@app.route("/agent-chat")
@login_required
def agent_chat_page():
    ai_config = get_portal_ai_config()
    provider = (ai_config.get("provider") or "gemini").strip().lower()
    has_key = bool((ai_config.get("api_key") or "").strip())
    has_ollama = bool((ai_config.get("ollama_base_url") or "").strip() and (ai_config.get("ollama_model") or "").strip())
    model_label = ai_config.get("ollama_model") if provider == "ollama" else ai_config.get("model")
    return render_template(
        "agent_chat.html",
        ai_provider=provider,
        ai_model=model_label or "modo local",
        has_ai_key=has_ollama if provider == "ollama" else has_key,
    )


@app.route("/agent-chat/conversations", methods=["GET", "POST", "DELETE"])
@login_required
def agent_chat_conversations():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        conv = _agent_conversation_for_user(title=payload.get("title") or "Nova conversa")
        return jsonify({"ok": True, "conversation": _serialize_agent_conversation(conv)})
    if request.method == "DELETE":
        AgentConversation.query.filter_by(user_id=g.user.id).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True})
    conversations = AgentConversation.query.filter_by(user_id=g.user.id).order_by(AgentConversation.updated_at.desc()).limit(80).all()
    return jsonify({"ok": True, "conversations": [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at.strftime("%d/%m/%Y %H:%M") if c.updated_at else ""}
        for c in conversations
    ]})


@app.route("/agent-chat/conversations/<int:conversation_id>", methods=["GET", "DELETE"])
@login_required
def agent_chat_conversation_detail(conversation_id):
    conv = AgentConversation.query.filter_by(id=conversation_id, user_id=g.user.id).first_or_404()
    if request.method == "DELETE":
        db.session.delete(conv)
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"ok": True, "conversation": _serialize_agent_conversation(conv)})


@app.route("/agent-chat/api", methods=["POST"])
@login_required
def agent_chat_api():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or payload.get("question") or "").strip()
    context = payload.get("context") or {}
    allow_files = bool(payload.get("allow_files"))
    stage = (payload.get("stage") or "plan").strip().lower()
    conversation_id = payload.get("conversation_id")
    if stage not in {"plan", "execute", "rethink"}:
        stage = "plan"
    if not question:
        return jsonify({"ok": False, "answer": "Digite uma pergunta para o Chat Agente."}), 400

    conv = _agent_conversation_for_user(conversation_id, title=question)
    if stage == "plan":
        _save_agent_message(conv, "user", question, "question")
    elif stage == "rethink":
        _save_agent_message(conv, "user", "Repensar antes de executar: " + question, "rethink_request")
    else:
        _save_agent_message(conv, "user", "Execução aprovada: " + question, "execute_request")

    ai_config = get_portal_ai_config()
    mode = "local"
    model_used = None
    agent_chain = _select_agent_chain(question, context, stage, allow_files)
    try:
        prompt = _build_agent_stage_prompt(question, context, stage, agent_chain)
        if allow_files and stage == "execute":
            prompt += "\n\nO usuário permitiu criar arquivos e ZIP. Gere arquivos completos quando fizer sentido usando [[FILE:caminho]]."
        answer, mode, model_used = _call_agent_model(prompt, ai_config)
        if not answer or "erro" in answer.lower()[:100] or "configure" in answer.lower()[:180]:
            answer = _local_agent_answer(question, context)
            if stage == "plan":
                answer = "**Plano resumido antes de executar**\n\n1. Vou analisar o pedido dentro do contexto da página atual.\n2. Vou identificar se envolve interface, permissão, IA, arquivo ou ZIP.\n3. Vou propor o caminho mais seguro antes de alterar/gerar qualquer coisa.\n4. Depois da sua aprovação, libero o resultado final.\n\nPosso executar ou deseja que eu repense?\n\n" + answer
            elif stage == "rethink":
                answer = "**Plano repensado**\n\nRevisei a intenção e vou priorizar segurança, clareza, arquivos necessários e teste de funcionamento antes de liberar o resultado. Confirme para executar.\n\n" + answer
            mode = "local"
            model_used = None
    except Exception as exc:
        answer = _local_agent_answer(question, context)
        answer += f"\n\n**Observação técnica:** não consegui chamar o provedor configurado agora. Detalhe: {str(exc)[:260]}"
        mode = "local"
        model_used = None

    if 'agent_chain' not in locals():
        agent_chain = _select_agent_chain(question, context, stage, allow_files)
    if "Roteamento multiagente:" not in answer:
        answer = "**Roteamento multiagente:** " + _agent_chain_summary(agent_chain) + "\n\n" + answer

    _save_agent_message(conv, "agent", answer, stage)
    response = {
        "ok": True,
        "answer": answer,
        "mode": mode,
        "model": model_used,
        "stage": stage,
        "conversation_id": conv.id,
        "conversation_title": conv.title,
        "agent_chain": [{"id": agent["id"], "name": agent["name"], "mission": agent["mission"]} for agent in agent_chain],
        "next_agent": agent_chain[-1]["name"] if agent_chain else "Coordenador de Agentes",
    }

    if allow_files and stage == "execute":
        files = _extract_agent_files(answer)
        if not files:
            files = _default_agent_files(question, answer)
            response["answer"] += "\n\n**Arquivos:** criei um pacote inicial com base no seu pedido. Para projetos grandes, aprove o plano e peça detalhamento por partes."
        job_id, written = _save_agent_zip(files, question)
        response.update({
            "zip_url": url_for("agent_chat_download", job_id=job_id),
            "files": written,
            "file_count": len(written),
        })
    return jsonify(response)


@app.route("/agent-chat/download/<job_id>")
@login_required
def agent_chat_download(job_id):
    safe_id = re.sub(r"[^A-Za-z0-9_\-]", "", job_id or "")
    zip_path = os.path.abspath(os.path.join(AGENT_WORKSPACE_DIR, f"{safe_id}.zip"))
    base = os.path.abspath(AGENT_WORKSPACE_DIR)
    if not zip_path.startswith(base + os.sep) or not os.path.exists(zip_path):
        return "Arquivo não encontrado.", 404
    return send_file(zip_path, as_attachment=True, download_name=f"chat_agente_{safe_id}.zip")


@app.route("/mcp/portal", methods=["POST"])
def portal_mcp_chat():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    context = payload.get("context") or {}

    if not question:
        return jsonify({"ok": False, "answer": "Digite uma pergunta para o MCP analisar a tela atual."}), 400

    prompt = _build_mcp_prompt(question, context)
    ai_config = get_portal_ai_config()

    try:
        answer, mode, model_name = _call_agent_model(prompt, ai_config)
        if not answer or "configure a chave" in answer.lower() or "google_api_key" in answer.lower():
            answer = _local_mcp_answer(question, context)
            answer += "\n\n**IA externa:** o provedor configurado não retornou resposta útil. Teste a conexão no painel Admin."
            return jsonify({"ok": True, "answer": answer, "mode": "local"})
    except Exception as exc:
        answer = _local_mcp_answer(question, context)
        answer += f"\n\n**Observação técnica:** não consegui chamar a IA externa agora. Detalhe: {str(exc)[:220]}"
        return jsonify({"ok": True, "answer": answer, "mode": "local"})

    return jsonify({"ok": True, "answer": answer, "mode": mode, "model": model_name})


@app.route("/")
def home():
    featured_modules = (
        StudyModule.query.filter_by(is_published=True)
        .order_by(StudyModule.sort_order.asc())
        .limit(3)
        .all()
    )
    return render_template("home.html", featured_modules=featured_modules)


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "portal-de-cursos"})


@app.route("/regimento")
def regimento():
    return render_template("regimento.html")


@app.route("/admissao")
def admissao():
    return render_template("admissao.html")


@app.route("/hierarquia")
def hierarquia():
    return render_template("hierarquia.html")


@app.route("/principios")
def principios():
    return render_template("principios.html")


@app.route("/documentos")
def documentos():
    return render_template("documentos.html", docs=DOCS_DATA)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Login inválido. Verifique seu e-mail e senha.", "danger")
        elif not user.is_active:
            flash("Seu acesso está desativado no momento.", "warning")
        else:
            session["user_id"] = user.id
            flash(f"Bem-vindo, {user.name}.", "success")
            destination = request.args.get("next") or url_for("dashboard")
            return redirect(destination)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da área interna.", "success")
    return redirect(url_for("home"))


@app.route("/area")
@login_required
def dashboard():
    published_modules = (
        StudyModule.query.filter_by(is_published=True)
        .order_by(StudyModule.sort_order.asc(), StudyModule.created_at.asc())
        .all()
    )
    available_modules = [m for m in published_modules if can_access_module(g.user, m)]
    recent_attempts = (
        ModuleAttempt.query.filter_by(user_id=g.user.id)
        .order_by(ModuleAttempt.created_at.desc())
        .limit(6)
        .all()
    )

    attempts_map = {
        module.id: latest_attempt_for(g.user.id, module.id) for module in available_modules
    }
    portuguese_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    english_data = enrich_english_course_for_user(build_english_overview(), g.user)

    return render_template(
        "dashboard.html",
        available_modules=available_modules,
        attempts_map=attempts_map,
        recent_attempts=recent_attempts,
        portuguese_data=portuguese_data,
        english_data=english_data,
    )


@app.route("/modulo/<slug>")
@login_required
def module_detail(slug):
    module = StudyModule.query.filter_by(slug=slug, is_published=True).first_or_404()
    if not can_access_module(g.user, module):
        flash("Seu cargo ainda não permite acessar este conteúdo.", "warning")
        return redirect(url_for("dashboard"))

    latest_attempt = latest_attempt_for(g.user.id, module.id)
    target_role = Role.query.filter_by(level=module.target_role_level).first()
    return render_template(
        "module_detail.html",
        module=module,
        latest_attempt=latest_attempt,
        target_role=target_role,
    )


@app.route("/modulo/<slug>/prova", methods=["GET", "POST"])
@login_required
def take_exam(slug):
    module = StudyModule.query.filter_by(slug=slug, is_published=True).first_or_404()
    if not can_access_module(g.user, module):
        flash("Seu cargo ainda não permite fazer esta prova.", "warning")
        return redirect(url_for("dashboard"))

    questions = module.questions
    if not questions:
        flash("Este módulo ainda não possui questões cadastradas.", "warning")
        return redirect(url_for("module_detail", slug=slug))

    result = None

    if request.method == "POST":
        correct_answers = 0
        feedback = []
        for question in questions:
            selected = request.form.get(f"question_{question.id}", "").upper().strip()
            is_correct = selected == question.correct_option
            if is_correct:
                correct_answers += 1
            feedback.append(
                {
                    "question": question,
                    "selected": selected or "-",
                    "is_correct": is_correct,
                }
            )

        score = round((correct_answers / len(questions)) * 100)
        passed = score >= module.passing_score

        attempt = ModuleAttempt(
            user_id=g.user.id,
            module_id=module.id,
            score=score,
            passed=passed,
        )
        db.session.add(attempt)
        db.session.commit()

        promoted_to = None
        if passed:
            promoted_to = maybe_promote_user(g.user, module)
            if promoted_to:
                flash(
                    f"Prova aprovada com {score}%. Cargo atualizado para {promoted_to}.",
                    "success",
                )
            else:
                flash(f"Prova aprovada com {score}%.", "success")
        else:
            flash(
                f"Você obteve {score}%. Estude mais e tente novamente.",
                "danger",
            )

        result = {
            "score": score,
            "passed": passed,
            "feedback": feedback,
            "promoted_to": promoted_to,
        }

    return render_template("exam.html", module=module, questions=questions, result=result)


@app.route("/admin/ollama/models", methods=["GET"])
@admin_required
def admin_ollama_models():
    base_url = request.args.get("base_url") or get_portal_setting("ollama_base_url", "http://localhost:11434")
    try:
        models = _list_ollama_models(base_url)
        return jsonify({
            "ok": True,
            "base_url": _normalize_ollama_base_url(base_url),
            "models": models,
            "selected_model": get_portal_setting("ollama_model", ""),
            "message": f"{len(models)} modelo(s) encontrado(s)." if models else "Ollama respondeu, mas não retornou modelos instalados.",
        })
    except Exception as exc:
        return jsonify({
            "ok": False,
            "base_url": _normalize_ollama_base_url(base_url),
            "models": [],
            "message": str(exc)[:500],
            "hint": _ollama_connection_hint(base_url),
        }), 200


@app.route("/admin/ollama/use", methods=["POST"])
@admin_required
def admin_ollama_use_model():
    payload = request.get_json(silent=True) or {}
    model = (payload.get("model") or "").strip()
    base_url = _normalize_ollama_base_url(payload.get("base_url") or get_portal_setting("ollama_base_url", "http://localhost:11434"))
    if not model:
        return jsonify({"ok": False, "message": "Selecione um modelo Ollama."}), 400
    set_portal_setting("ai_provider", "ollama")
    set_portal_setting("ollama_base_url", base_url)
    set_portal_setting("ollama_model", model)
    return jsonify({"ok": True, "message": f"Modelo {model} conectado ao Chat Agente e ao MCP.", "model": model, "base_url": base_url})


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_panel():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_mcp_api":
            provider = request.form.get("ai_provider", "gemini").strip() or "gemini"
            api_key = request.form.get("mcp_google_api_key", "").strip()
            model = request.form.get("mcp_gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            ollama_base_url = request.form.get("ollama_base_url", "http://localhost:11434").strip() or "http://localhost:11434"
            ollama_model = request.form.get("ollama_model", "llama3.1").strip() or "llama3.1"
            clear_key = request.form.get("clear_mcp_key") == "on"

            set_portal_setting("ai_provider", provider)
            set_portal_setting("mcp_gemini_model", model)
            set_portal_setting("ollama_base_url", ollama_base_url)
            set_portal_setting("ollama_model", ollama_model)

            if clear_key:
                set_portal_setting("mcp_google_api_key", "")
                flash("Chave Gemini removida. Configurações do provedor foram salvas.", "success")
            else:
                current_key = get_portal_setting("mcp_google_api_key", "")
                if api_key:
                    set_portal_setting("mcp_google_api_key", api_key)
                    flash("Configuração de IA salva com segurança.", "success")
                elif current_key or provider == "ollama":
                    flash("Configuração de IA salva. A chave Gemini existente foi mantida, se houver.", "success")
                else:
                    flash("Configuração salva. Para usar Gemini, cole uma Google API Key; para Ollama, mantenha o Ollama aberto localmente.", "warning")

        elif action == "test_mcp_api":
            provider = request.form.get("ai_provider", get_portal_setting("ai_provider", "gemini")).strip() or "gemini"
            api_key = request.form.get("mcp_google_api_key", "").strip() or get_portal_setting("mcp_google_api_key", "")
            model = request.form.get("mcp_gemini_model", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
            ollama_base_url = request.form.get("ollama_base_url", get_portal_setting("ollama_base_url", "http://localhost:11434")).strip() or "http://localhost:11434"
            ollama_model = request.form.get("ollama_model", get_portal_setting("ollama_model", "llama3.1")).strip() or "llama3.1"
            try:
                if provider == "ollama":
                    test_answer = _call_ollama("Responda apenas: Ollama conectado com sucesso.", ollama_base_url, ollama_model)
                    if test_answer:
                        flash("Conexão Ollama testada com sucesso.", "success")
                    else:
                        flash("Ollama respondeu vazio. Verifique se o modelo está instalado.", "warning")
                else:
                    if not api_key:
                        flash("Cole ou salve uma Google API Key antes de testar Gemini.", "warning")
                    else:
                        test_answer = call_ai("chat", "Responda apenas: MCP conectado com sucesso.", api_key=api_key, model_name=model)
                        if test_answer and "erro" not in test_answer.lower() and "configure" not in test_answer.lower():
                            flash("Conexão MCP/Gemini testada com sucesso.", "success")
                        else:
                            flash("Teste executado, mas o Gemini retornou aviso: " + (test_answer or "sem resposta")[:280], "warning")
            except Exception as exc:
                flash("Não consegui testar a IA agora: " + str(exc)[:260], "danger")

        elif action == "create_user":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            role_level = int(request.form.get("role_level", 1))
            role = Role.query.filter_by(level=role_level).first()

            if not name or not email or not password:
                flash("Preencha nome, e-mail e senha do novo acesso.", "danger")
            elif User.query.filter_by(email=email).first():
                flash("Já existe um usuário com esse e-mail.", "warning")
            else:
                user = User(name=name, email=email, role_id=role.id, is_admin=False)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("Novo login criado com sucesso.", "success")

        elif action == "update_user":
            user_id = int(request.form.get("user_id"))
            user = User.query.get_or_404(user_id)
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "").strip()
            role_level = int(request.form.get("role_level", 1))
            role = Role.query.filter_by(level=role_level).first()
            make_admin = request.form.get("is_admin") == "on"
            is_active = request.form.get("is_active") == "on"

            email_owner = User.query.filter(User.email == email, User.id != user.id).first()

            if not name or not email:
                flash("Preencha nome e login/e-mail do usuário.", "danger")
            elif email_owner:
                flash("Já existe outro usuário usando esse login/e-mail.", "warning")
            elif not role:
                flash("Cargo selecionado não foi encontrado.", "danger")
            elif user.id == g.user.id and not make_admin:
                flash("Você não pode remover seu próprio acesso de administrador.", "warning")
            elif user.id == g.user.id and not is_active:
                flash("Você não pode desativar o próprio usuário logado.", "warning")
            else:
                user.name = name
                user.email = email
                user.role_id = role.id
                user.is_admin = make_admin
                user.is_active = is_active
                if password:
                    user.set_password(password)
                db.session.commit()
                flash("Usuário atualizado com sucesso.", "success")

        elif action == "delete_user":
            user_id = int(request.form.get("user_id"))
            user = User.query.get_or_404(user_id)

            if user.id == g.user.id:
                flash("Você não pode remover o próprio usuário logado.", "warning")
            elif user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
                flash("Não é possível remover o último administrador do sistema.", "warning")
            else:
                ModuleAttempt.query.filter_by(user_id=user.id).delete()
                db.session.delete(user)
                db.session.commit()
                flash("Usuário removido com sucesso.", "success")

        elif action == "update_user_role":
            # Compatibilidade com versões antigas do formulário.
            user_id = int(request.form.get("user_id"))
            role_level = int(request.form.get("role_level"))
            user = User.query.get_or_404(user_id)
            role = Role.query.filter_by(level=role_level).first()
            user.role_id = role.id
            user.is_active = request.form.get("is_active") == "on"
            db.session.commit()
            flash("Cargo e status do membro atualizados.", "success")

        elif action == "create_module":
            title = request.form.get("title", "").strip()
            summary = request.form.get("summary", "").strip()
            content = request.form.get("content", "").strip()
            min_role_level = int(request.form.get("min_role_level", 1))
            target_role_level = int(request.form.get("target_role_level", 1))
            passing_score = int(request.form.get("passing_score", 70))
            slug = slugify(request.form.get("slug", "").strip() or title)

            if not title or not summary or not content:
                flash("Preencha título, resumo e conteúdo do módulo.", "danger")
            elif StudyModule.query.filter_by(slug=slug).first():
                flash("Já existe um módulo com esse slug/título.", "warning")
            else:
                module = StudyModule(
                    title=title,
                    slug=slug,
                    summary=summary,
                    content=content,
                    min_role_level=min_role_level,
                    target_role_level=target_role_level,
                    passing_score=passing_score,
                    is_published=True,
                    sort_order=(StudyModule.query.count() + 1),
                )
                db.session.add(module)
                db.session.commit()
                flash("Novo conteúdo exclusivo criado.", "success")

        elif action == "update_module":
            module_id = int(request.form.get("module_id"))
            module = StudyModule.query.get_or_404(module_id)
            module.min_role_level = int(request.form.get("min_role_level"))
            module.target_role_level = int(request.form.get("target_role_level"))
            module.passing_score = int(request.form.get("passing_score"))
            module.is_published = request.form.get("is_published") == "on"
            db.session.commit()
            flash("Configuração do conteúdo atualizada.", "success")

        elif action == "add_question":
            module_id = int(request.form.get("module_id"))
            prompt = request.form.get("prompt", "").strip()
            option_a = request.form.get("option_a", "").strip()
            option_b = request.form.get("option_b", "").strip()
            option_c = request.form.get("option_c", "").strip()
            option_d = request.form.get("option_d", "").strip()
            correct_option = request.form.get("correct_option", "A").strip().upper()
            explanation = request.form.get("explanation", "").strip()

            if not all([prompt, option_a, option_b, option_c, option_d]):
                flash("Preencha a pergunta e as quatro alternativas.", "danger")
            else:
                question = Question(
                    module_id=module_id,
                    prompt=prompt,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct_option,
                    explanation=explanation,
                )
                db.session.add(question)
                db.session.commit()
                flash("Questão adicionada ao módulo.", "success")

        return redirect(url_for("admin_panel"))

    users = User.query.order_by(User.is_admin.desc(), User.created_at.asc()).all()
    modules = StudyModule.query.order_by(StudyModule.sort_order.asc(), StudyModule.id.asc()).all()
    attempts = ModuleAttempt.query.order_by(ModuleAttempt.created_at.desc()).limit(12).all()
    mcp_config = get_portal_ai_config()
    mcp_has_key = bool((mcp_config.get("api_key") or "").strip())
    return render_template(
        "admin.html",
        users=users,
        modules=modules,
        attempts=attempts,
        mcp_config=mcp_config,
        mcp_has_key=mcp_has_key,
    )


@app.route("/area/portugues")
@login_required
def portugues_home():
    course_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    query = (request.args.get("q") or "").strip()
    lessons = course_data["lessons"]
    if query:
        lowered = query.lower()
        lessons = [
            lesson for lesson in lessons
            if lowered in lesson.get("title", "").lower()
            or lowered in lesson.get("label", "").lower()
            or (not lesson.get("is_locked") and lowered in lesson.get("summary", "").lower())
            or (
                not lesson.get("is_locked")
                and any(lowered in block.lower() for block in lesson.get("blocks", []))
            )
        ]

    return render_template(
        "portugues/index.html",
        overview=course_data["overview"],
        site_overview=course_data["overview"],
        all_lessons=course_data["lessons"],
        lessons=lessons,
        featured=course_data["featured"],
        query=query,
        site_meta=course_data["site_meta"],
        phase_groups=course_data["phase_groups"],
        next_unlock=course_data["next_unlock"],
        course_access=course_data["course_access"],
    )


@app.route("/area/portugues/buscar")
@login_required
def portugues_search():
    course_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    query = (request.args.get("q") or "").strip()
    visible_lessons = [lesson for lesson in course_data["lessons"] if not lesson.get("is_locked")]
    results = search_portuguese_lessons(query, visible_lessons)
    return render_template(
        "portugues/search.html",
        query=query,
        results=results,
        site_overview=course_data["overview"],
        all_lessons=course_data["lessons"],
        site_meta=course_data["site_meta"],
    )


@app.route("/area/portugues/licao/<slug>")
@login_required
def portugues_lesson_detail(slug):
    course_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    lesson = course_data["lesson_map"].get(slug)
    if not lesson:
        return redirect(url_for("portugues_home"))
    if lesson.get("is_locked"):
        flash(
            f"Esta lição ainda não está liberada para seu cargo. Necessário: {lesson['required_role_name']}.",
            "warning",
        )
        return redirect(url_for("portugues_home"))

    lessons = course_data["lessons"]
    index = next((idx for idx, item in enumerate(lessons) if item["slug"] == slug), 0)
    prev_lesson = next((item for item in reversed(lessons[:index]) if not item.get("is_locked")), None)
    next_lesson = next((item for item in lessons[index + 1 :] if not item.get("is_locked")), None)
    related_quiz = [item for item in course_data["quizzes"] if item.get("lesson_slug") == slug]
    related_flashcards = [item for item in course_data["flashcards"] if item.get("lesson_slug") == slug]

    return render_template(
        "portugues/lesson.html",
        lesson=lesson,
        prev_lesson=prev_lesson,
        next_lesson=next_lesson,
        related_quiz=related_quiz,
        related_flashcards=related_flashcards,
        site_overview=course_data["overview"],
        all_lessons=course_data["lessons"],
        site_meta=course_data["site_meta"],
    )


@app.route("/area/portugues/pratica")
@login_required
def portugues_practice():
    access_redirect = ensure_portuguese_access(PORTUGUESE_PRACTICE_MIN_ROLE, "a prática do curso de português")
    if access_redirect:
        return access_redirect

    course_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    return render_template(
        "portugues/practice.html",
        quiz_items=course_data["quizzes"],
        flashcards=course_data["flashcards"],
        site_overview=course_data["overview"],
        all_lessons=course_data["lessons"],
        site_meta=course_data["site_meta"],
        course_access=course_data["course_access"],
    )


@app.route("/area/portugues/prova-final")
@login_required
def portugues_final_exam():
    access_redirect = ensure_portuguese_access(PORTUGUESE_FINAL_EXAM_MIN_ROLE, "a prova final do curso de português")
    if access_redirect:
        return access_redirect

    course_data = enrich_portuguese_course_for_user(build_portuguese_overview(), g.user)
    return render_template(
        "portugues/final_exam.html",
        exam_items=course_data["quizzes"],
        site_overview=course_data["overview"],
        all_lessons=course_data["lessons"],
        site_meta=course_data["site_meta"],
        course_access=course_data["course_access"],
    )



@app.route("/area/ingles")
@login_required
def ingles_home():
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    return render_template(
        "ingles/index.html",
        overview=course_data["overview"],
        featured=course_data["featured"],
        roadmap=course_data["modules"],
        quizzes=course_data["quizzes"][:6],
        phrasebook_preview=course_data["phrasebook"][:4],
        study_plan=course_data["study_plan"],
        vocab_preview=course_data["vocabulary_banks"][:4],
        all_modules=course_data["modules"],
        site_meta=course_data["site_meta"],
        phase_groups=course_data["phase_groups"],
        next_unlock=course_data["next_unlock"],
        course_access=course_data["course_access"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/modulo/<slug>")
@login_required
def ingles_module_detail(slug):
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    module = course_data["module_map"].get(slug)
    if not module:
        return redirect(url_for("ingles_home"))
    if module.get("is_locked"):
        flash(
            f"Este módulo ainda não está liberado para seu cargo. Necessário: {module['required_role_name']}.",
            "warning",
        )
        return redirect(url_for("ingles_home"))

    related_quiz = [item for item in course_data["quizzes"] if item.get("module_slug") == slug][:8]
    related_cards = [item for item in course_data["flashcards"] if item.get("module_slug") == slug][:10]
    prev_module = course_data["module_map"].get(module["prev_slug"]) if module.get("prev_slug") else None
    if prev_module and prev_module.get("is_locked"):
        prev_module = None
    next_module = course_data["module_map"].get(module["next_slug"]) if module.get("next_slug") else None
    if next_module and next_module.get("is_locked"):
        next_module = None

    return render_template(
        "ingles/module.html",
        overview=course_data["overview"],
        module=module,
        related_quiz=related_quiz,
        related_cards=related_cards,
        prev_module=prev_module,
        next_module=next_module,
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/praticar")
@login_required
def ingles_practice():
    access_redirect = ensure_english_access(ENGLISH_PRACTICE_MIN_ROLE, "a prática do curso de inglês")
    if access_redirect:
        return access_redirect

    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    selected = request.args.get("module", "all")
    quizzes = course_data["quizzes"] if selected == "all" else [item for item in course_data["quizzes"] if item.get("module_slug") == selected]
    cards = course_data["flashcards"] if selected == "all" else [item for item in course_data["flashcards"] if item.get("module_slug") == selected]
    return render_template(
        "ingles/practice.html",
        overview=course_data["overview"],
        selected_module=selected,
        quiz_items=quizzes,
        flashcards=cards,
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/frases")
@login_required
def ingles_phrasebook():
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    return render_template(
        "ingles/phrasebook.html",
        overview=course_data["overview"],
        sections=course_data["phrasebook"],
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/vocabulario")
@login_required
def ingles_vocabulary():
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    query = request.args.get("q", "").strip().lower()
    banks = course_data["vocabulary_banks"]
    if query:
        filtered = []
        for bank in banks:
            words = [word for word in bank.get("words", []) if query in word.lower()]
            if query in bank.get("module_title", "").lower() or words:
                filtered.append({**bank, "words": words if words else bank.get("words", [])})
        banks = filtered
    return render_template(
        "ingles/vocabulary.html",
        overview=course_data["overview"],
        banks=banks,
        query=query,
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/plano")
@login_required
def ingles_study_plan():
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    return render_template(
        "ingles/study_plan.html",
        overview=course_data["overview"],
        plan=course_data["study_plan"],
        modules=course_data["modules"],
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/prova-final")
@login_required
def ingles_final_exam():
    access_redirect = ensure_english_access(ENGLISH_FINAL_EXAM_MIN_ROLE, "a prova final do curso de inglês")
    if access_redirect:
        return access_redirect

    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    return render_template(
        "ingles/final_exam.html",
        overview=course_data["overview"],
        exam_items=course_data["final_exam"],
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/buscar")
@login_required
def ingles_search():
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    query = request.args.get("q", "").strip()
    visible_modules = [module for module in course_data["modules"] if not module.get("is_locked")]
    results = search_english_modules(query, visible_modules)
    return render_template(
        "ingles/search.html",
        overview=course_data["overview"],
        query=query,
        results=results,
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
    )


@app.route("/area/ingles/laboratorio")
@login_required
def ingles_lab():
    preference = _english_preference(g.user.id)
    history_rows = (
        EnglishTutorMessage.query.filter_by(user_id=g.user.id)
        .order_by(EnglishTutorMessage.id.desc())
        .limit(40)
        .all()
    )
    history = []
    for row in reversed(history_rows):
        try:
            explanations = json.loads(row.explanations_json or "[]")
        except json.JSONDecodeError:
            explanations = []
        history.append({
            "role": row.role,
            "content": row.content,
            "corrected_text": row.corrected_text,
            "engine": row.engine,
            "explanations": explanations if isinstance(explanations, list) else [],
        })
    pending = (
        EnglishTutorExercise.query.filter_by(user_id=g.user.id, completed=False)
        .order_by(EnglishTutorExercise.id.desc())
        .first()
    )
    attempts = (
        EnglishPronunciationAttempt.query.filter_by(user_id=g.user.id)
        .order_by(EnglishPronunciationAttempt.id.desc())
        .limit(8)
        .all()
    )
    course_data = enrich_english_course_for_user(build_english_overview(), g.user)
    phrases = [
        "Learning a language takes time and practice.",
        "Could you tell me where the station is?",
        "I would like to improve my English pronunciation.",
        "She works during the week and studies at night.",
        "Yesterday I went to the store and bought some food.",
    ]
    return render_template(
        "ingles/lab.html",
        overview=course_data["overview"],
        all_modules=course_data["modules"],
        phrasebook=course_data["phrasebook"],
        preference=preference,
        history=history,
        exercise=_serialize_english_exercise(pending),
        stats=_english_tutor_stats(g.user.id),
        metrics=_english_learning_metrics(g.user.id),
        scenarios=ENGLISH_SCENARIOS,
        active_scenario=ENGLISH_SCENARIOS.get(preference.scenario_key, ENGLISH_SCENARIOS["free"]),
        active_scenario_key=preference.scenario_key,
        ai_runtime=english_ai_status(ENGLISH_AI_DIR, preference.local_ai_url),
        voice_runtime=discover_voice(ENGLISH_VOICE_DIR),
        pronunciation_attempts=attempts,
        pronunciation_phrases=phrases,
    )


@app.route("/api/ingles/preferencias", methods=["POST"])
@login_required
def ingles_preferences_api():
    data = request.get_json(silent=True) or {}
    preference = _english_preference(g.user.id)
    level = str(data.get("level", preference.level)).upper()
    if level not in {"A1", "A2", "B1", "B2"}:
        return jsonify({"ok": False, "error": "Nível de inglês inválido."}), 400
    engine = str(data.get("tutor_engine", preference.tutor_engine))
    if engine not in {"integrated", "local_ai"}:
        return jsonify({"ok": False, "error": "Motor do professor inválido."}), 400
    local_url = str(data.get("local_ai_url", preference.local_ai_url)).strip()[:500]
    if local_url:
        try:
            if urlparse(local_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
                return jsonify({"ok": False, "error": "A IA neural aceita somente um endereço local (localhost)."}), 400
        except ValueError:
            return jsonify({"ok": False, "error": "Endereço da IA local inválido."}), 400
    preference.level = level
    preference.objective = str(data.get("objective", preference.objective)).strip()[:300] or "Conversação e compreensão geral"
    preference.tutor_engine = engine
    preference.local_ai_url = local_url or "http://127.0.0.1:8080/v1/chat/completions"
    preference.local_ai_model = str(data.get("local_ai_model", preference.local_ai_model)).strip()[:160] or "local-model"
    db.session.commit()
    return jsonify({"ok": True, "level": preference.level, "tutor_engine": preference.tutor_engine})


@app.route("/api/ingles/professor/chat", methods=["POST"])
@login_required
def ingles_professor_chat_api():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"ok": False, "error": "Escreva uma mensagem para o professor."}), 400
    if len(message) > 4000:
        return jsonify({"ok": False, "error": "Envie no máximo 4.000 caracteres."}), 400
    preference = _english_preference(g.user.id)
    rows = (
        EnglishTutorMessage.query.filter_by(user_id=g.user.id)
        .order_by(EnglishTutorMessage.id.desc())
        .limit(6)
        .all()
    )
    history = [{"role": row.role, "content": row.content} for row in reversed(rows)]
    scenario_key = preference.scenario_key if preference.scenario_key in ENGLISH_SCENARIOS else "free"
    try:
        result = tutor_response(
            message,
            _english_preference_settings(preference),
            preference.level or "A1",
            preference.objective,
            history,
            _english_student_context(g.user.id),
            scenario_key,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    exercise = _store_english_tutor_result(g.user.id, message, result)
    return jsonify({
        "ok": True,
        "reply": result.get("reply", ""),
        "corrected_text": result.get("corrected_text", ""),
        "corrections": result.get("corrections", []),
        "engine": result.get("engine", "Professor integrado offline"),
        "notice": result.get("notice", ""),
        "exercise": exercise,
        "xp_earned": 3,
    })


@app.route("/api/ingles/professor/cenario", methods=["POST"])
@login_required
def ingles_professor_scenario_api():
    data = request.get_json(silent=True) or {}
    scenario_key = str(data.get("scenario", "free"))
    scenario = ENGLISH_SCENARIOS.get(scenario_key)
    if scenario is None:
        return jsonify({"ok": False, "error": "Cenário não encontrado."}), 404
    preference = _english_preference(g.user.id)
    changed = preference.scenario_key != scenario_key
    preference.scenario_key = scenario_key
    if changed:
        db.session.add(
            EnglishTutorMessage(
                user_id=g.user.id,
                role="assistant",
                content=scenario["opening"],
                engine="Simulação offline",
            )
        )
    db.session.commit()
    return jsonify({"ok": True, "scenario": scenario_key, **scenario})


@app.route("/api/ingles/professor/exercicio/<int:exercise_id>", methods=["POST"])
@login_required
def ingles_professor_exercise_api(exercise_id):
    data = request.get_json(silent=True) or {}
    response_text = str(data.get("response", "")).strip()[:1000]
    exercise = EnglishTutorExercise.query.filter_by(id=exercise_id, user_id=g.user.id).first()
    if exercise is None:
        return jsonify({"ok": False, "error": "Exercício não encontrado."}), 404
    correct = normalize_exercise_answer(response_text) == normalize_exercise_answer(exercise.answer)
    exercise.attempts += 1
    if correct:
        exercise.completed = True
        exercise.correct = True
    if exercise.mistake_rule_key:
        mistake = EnglishTutorMistake.query.filter_by(
            user_id=g.user.id,
            rule_key=exercise.mistake_rule_key,
        ).first()
        if mistake is not None:
            if correct:
                mistake.times_correct += 1
                intervals = (1, 3, 7, 14, 30)
                interval = intervals[min(mistake.times_correct - 1, len(intervals) - 1)]
                mistake.next_review = date.today() + timedelta(days=interval)
            else:
                mistake.next_review = date.today() + timedelta(days=1)
    xp_earned = _english_record_event(g.user.id, "tutor_exercise", f"exercise:{exercise.id}", 5) if correct else 0
    db.session.commit()
    next_exercise = None
    if correct:
        next_exercise = _serialize_english_exercise(
            EnglishTutorExercise.query.filter(
                EnglishTutorExercise.user_id == g.user.id,
                EnglishTutorExercise.completed.is_(False),
                EnglishTutorExercise.id != exercise.id,
            ).order_by(EnglishTutorExercise.id.desc()).first()
        )
    return jsonify({
        "ok": True,
        "correct": correct,
        "answer": exercise.answer,
        "explanation": exercise.explanation,
        "xp_earned": xp_earned,
        "next_exercise": next_exercise,
    })


@app.route("/api/ingles/local-ai/status")
@login_required
def ingles_local_ai_status_api():
    preference = _english_preference(g.user.id)
    return jsonify({
        "ok": True,
        **english_ai_status(ENGLISH_AI_DIR, preference.local_ai_url),
        "selected_model": preference.local_ai_model_file,
    })


@app.route("/api/ingles/local-ai/iniciar", methods=["POST"])
@login_required
def ingles_local_ai_start_api():
    data = request.get_json(silent=True) or {}
    preference = _english_preference(g.user.id)
    model = str(data.get("model", preference.local_ai_model_file))[:500]
    try:
        port = urlparse(preference.local_ai_url).port or 8080
        result = start_english_ai(ENGLISH_AI_DIR, model, port=port)
    except (ValueError, OSError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if model:
        preference.local_ai_model_file = model
        db.session.commit()
    return jsonify({"ok": True, **result})


@app.route("/api/ingles/local-ai/parar", methods=["POST"])
@login_required
def ingles_local_ai_stop_api():
    return jsonify({"ok": True, **stop_english_ai()})


@app.route("/api/ingles/pronuncia/status")
@login_required
def ingles_pronunciation_status_api():
    preference = _english_preference(g.user.id)
    return jsonify({
        "ok": True,
        **discover_voice(ENGLISH_VOICE_DIR),
        "selected_model": preference.voice_model_file,
    })


@app.route("/api/ingles/pronuncia/analisar", methods=["POST"])
@login_required
def ingles_pronunciation_analyze_api():
    target = request.form.get("target", "").strip()[:1000]
    audio = request.files.get("audio")
    if not target:
        return jsonify({"ok": False, "error": "Informe a frase que será pronunciada."}), 400
    if audio is None:
        return jsonify({"ok": False, "error": "A gravação não foi recebida."}), 400
    preference = _english_preference(g.user.id)
    wav_bytes = audio.read(16 * 1024 * 1024 + 1)
    try:
        transcript = transcribe_wav(ENGLISH_VOICE_DIR, wav_bytes, preference.voice_model_file)
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    result = pronunciation_score(target, transcript)
    attempt = EnglishPronunciationAttempt(
        user_id=g.user.id,
        target_text=target,
        transcript=transcript,
        score=result["score"],
        missing_json=json.dumps(result["missing"], ensure_ascii=False),
        extra_json=json.dumps(result["extra"], ensure_ascii=False),
    )
    db.session.add(attempt)
    db.session.flush()
    xp_earned = _english_record_event(g.user.id, "pronunciation", f"attempt:{attempt.id}", 5)
    db.session.commit()
    return jsonify({"ok": True, **result, "xp_earned": xp_earned})


@app.route("/api/ingles/traducao/memoria", methods=["GET", "POST"])
@login_required
def ingles_translation_memory_api():
    if request.method == "GET":
        source = request.args.get("text", "").strip()[:12000]
        return jsonify({"ok": True, "segments": _english_memory_segments(g.user.id, source)})
    data = request.get_json(silent=True) or {}
    source = str(data.get("source", "")).strip()[:12000]
    translation = str(data.get("translation", "")).strip()[:12000]
    if not source or not translation:
        return jsonify({"ok": False, "error": "Informe o texto em inglês e a tradução corrigida."}), 400
    _store_english_translation_pair(g.user.id, source, translation)
    source_units = _english_sentence_units(source)
    translated_units = _english_sentence_units(translation)
    if 1 < len(source_units) == len(translated_units) <= 80:
        for source_unit, translated_unit in zip(source_units, translated_units, strict=True):
            _store_english_translation_pair(g.user.id, source_unit, translated_unit)
    db.session.commit()
    return jsonify({"ok": True, "message": "Correção aprendida para este usuário."})


@app.route("/api/ingles/progresso", methods=["GET", "POST"])
@login_required
def ingles_progress_api():
    if request.method == "GET":
        rows = EnglishCourseProgress.query.filter_by(user_id=g.user.id).all()
        state = {}
        for row in rows:
            state.setdefault(row.item_type, {})[row.item_key] = {
                "completed": bool(row.completed),
                "score": row.score,
            }
        return jsonify({"ok": True, "progress": state, "metrics": _english_learning_metrics(g.user.id)})
    data = request.get_json(silent=True) or {}
    item_type = str(data.get("item_type", ""))[:40]
    item_key = str(data.get("item_key", "")).strip()[:220]
    if item_type not in {"module", "lesson", "quiz", "exam", "word"} or not item_key:
        return jsonify({"ok": False, "error": "Item de progresso inválido."}), 400
    completed = bool(data.get("completed", False))
    try:
        score = max(0, min(10000, int(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0
    row = EnglishCourseProgress.query.filter_by(
        user_id=g.user.id,
        item_type=item_type,
        item_key=item_key,
    ).first()
    if row is None:
        row = EnglishCourseProgress(user_id=g.user.id, item_type=item_type, item_key=item_key)
        db.session.add(row)
    row.completed = completed
    row.score = score
    xp_map = {"module": 120, "lesson": 25, "quiz": 30, "exam": 180, "word": 3}
    xp_earned = _english_record_event(g.user.id, f"progress_{item_type}", item_key, xp_map[item_type]) if completed else 0
    db.session.commit()
    return jsonify({"ok": True, "xp_earned": xp_earned, "metrics": _english_learning_metrics(g.user.id)})



def create_app():
    """Factory do curso. Evita rodar seed/create_all automaticamente só por importar o módulo."""
    if not app.config.get("_CURSO_DB_INITIALIZED"):
        init_database()
        app.config["_CURSO_DB_INITIALIZED"] = True
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
