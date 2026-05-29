import os
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from security_config import get_admin_password, get_admin_user

from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = "prompt_user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="admin")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self) -> str:
        return f"prompt:{self.id}"

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return (self.role or "").lower() == "admin"

    @staticmethod
    def ensure_admin():
        username = get_admin_user()
        password = get_admin_password()
        existing = User.query.filter_by(username=username).first()
        if existing:
            existing.role = "admin"
            existing.name = existing.name or username
            existing.set_password(password)
            db.session.commit()
            return
        user = User(name=username, username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

class Project(db.Model):
    __tablename__ = "prompt_project"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("prompt_user.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    tech_stack = db.Column(db.String(200), default="auto")
    fixed_context = db.Column(db.Text, default="")
    file_structure = db.Column(db.Text, default="")
    preserve_rules = db.Column(db.Text, default="Preservar funcionalidades existentes. Alterar apenas o necessário.")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PromptHistory(db.Model):
    __tablename__ = "prompt_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("prompt_user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("prompt_project.id"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False)
    request_text = db.Column(db.Text, nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    short_message = db.Column(db.Text, default="")
    checklist = db.Column(db.Text, default="")
    history_entry = db.Column(db.Text, default="")
    quality_score = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    project = db.relationship("Project", lazy="joined")

class CustomTemplate(db.Model):
    __tablename__ = "prompt_custom_template"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("prompt_user.id"), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), default="geral")
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnownError(db.Model):
    __tablename__ = "prompt_known_error"
    id = db.Column(db.Integer, primary_key=True)
    signature = db.Column(db.String(180), nullable=False)
    cause = db.Column(db.Text, nullable=False)
    solution = db.Column(db.Text, nullable=False)
    prompt_hint = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatSession(db.Model):
    __tablename__ = "prompt_chat_session"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("prompt_user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("prompt_project.id"), nullable=True, index=True)
    title = db.Column(db.String(180), nullable=False, default="Chat executor")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    project = db.relationship("Project", lazy="joined")

class ChatMessage(db.Model):
    __tablename__ = "prompt_chat_message"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("prompt_chat_session.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship("ChatSession", lazy="joined")

class GeneratedFile(db.Model):
    __tablename__ = "prompt_generated_file"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("prompt_chat_session.id"), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey("prompt_chat_message.id"), nullable=True, index=True)
    path = db.Column(db.String(260), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session = db.relationship("ChatSession", lazy="joined")


class AppSetting(db.Model):
    __tablename__ = "prompt_app_setting"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("prompt_user.id"), nullable=False, index=True)
    key = db.Column(db.String(120), nullable=False, index=True)
    value = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "key", name="uq_prompt_user_setting_key"),)
