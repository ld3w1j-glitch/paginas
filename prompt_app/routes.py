from __future__ import annotations
import io, json, zipfile
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, User, Project, PromptHistory, CustomTemplate, ChatSession, ChatMessage, GeneratedFile, AppSetting
from .prompt_engine import PromptData, build_prompt, analyze_zip, analyze_error, call_gemini, list_gemini_models, build_chat_system_prompt, extract_generated_files


prompt_bp = Blueprint('prompt', __name__, template_folder='templates', static_folder='static')


def _safe_zip_path(path: str) -> str | None:
    """Valida caminhos gerados pela IA antes de colocar dentro de um ZIP."""
    cleaned = (path or '').replace('\\', '/').strip().lstrip('/')
    parts = [part for part in cleaned.split('/') if part]
    if not parts or any(part in {'.', '..'} for part in parts):
        return None
    if any('\x00' in part for part in parts):
        return None
    return '/'.join(parts)[:240]


def _session_files_for_user(session_id: int, user_id: int):
    session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
    files = GeneratedFile.query.filter_by(session_id=session.id).order_by(GeneratedFile.created_at.asc()).all()
    return session, files


def _build_chat_workspace_zip(session, messages, files, base_zip_file=None):
    mem = io.BytesIO()
    overwrite_paths = {_safe_zip_path(f.path) for f in files}
    overwrite_paths.discard(None)
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        if base_zip_file and base_zip_file.filename.lower().endswith('.zip'):
            with zipfile.ZipFile(base_zip_file) as original:
                for item in original.infolist():
                    if item.is_dir():
                        continue
                    safe_name = _safe_zip_path(item.filename)
                    if not safe_name or safe_name in overwrite_paths:
                        continue
                    zf.writestr(safe_name, original.read(item.filename))
        transcript = '# Chat Executor - Workspace\n\n' + '\n\n'.join([f"## {m.role}\n\n{m.content}" for m in messages])
        zf.writestr('workspace/CONVERSA.md', transcript)
        zf.writestr('workspace/README_WORKSPACE.md', 'Arquivos gerados/aplicados pelo Chat Executor. Revise e teste antes de usar em produção.\n')
        for f in files:
            safe_path = _safe_zip_path(f.path)
            if safe_path:
                zf.writestr(safe_path, f.content)
                zf.writestr(f'workspace/arquivos_gerados/{safe_path}', f.content)
    mem.seek(0)
    return mem



def _get_user_setting(user_id: int, key: str, default: str = "") -> str:
    setting = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    return setting.value if setting and setting.value is not None else default


def _set_user_setting(user_id: int, key: str, value: str) -> None:
    setting = AppSetting.query.filter_by(user_id=user_id, key=key).first()
    if not setting:
        setting = AppSetting(user_id=user_id, key=key)
        db.session.add(setting)
    setting.value = value or ""


def _admin_user_id() -> int | None:
    admin = User.query.filter_by(role='admin').order_by(User.id.asc()).first()
    return admin.id if admin else None


def _get_gemini_config(user_id: int) -> tuple[str, str]:
    import os
    admin_id = _admin_user_id()
    # Usuário comum usa a chave cadastrada pelo admin, sem enxergar a chave.
    # Se o próprio usuário tiver uma chave salva, ela tem prioridade.
    api_key = _get_user_setting(user_id, 'google_api_key')
    model = _get_user_setting(user_id, 'gemini_model')
    if not api_key and admin_id and admin_id != user_id:
        api_key = _get_user_setting(admin_id, 'google_api_key')
    if not model and admin_id and admin_id != user_id:
        model = _get_user_setting(admin_id, 'gemini_model')
    api_key = api_key or os.getenv('GOOGLE_API_KEY', '')
    model = model or os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    return api_key.strip(), model.strip() or 'gemini-2.5-flash'




def _is_prompt_user() -> bool:
    try:
        return current_user.is_authenticated and str(current_user.get_id()).startswith("prompt:")
    except Exception:
        return False

def _require_admin():
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        abort(403)

def register_routes(target=prompt_bp):
    @target.before_request
    def isolate_prompt_session():
        if current_user.is_authenticated and not _is_prompt_user():
            logout_user()
            flash('Entre no Prompt Profissional para continuar.', 'warning')
            return redirect(url_for('prompt.login', next=request.url))

    @target.route('/login', methods=['GET','POST'])
    def login():
        if _is_prompt_user():
            if getattr(current_user, 'is_admin', False):
                return redirect(url_for('prompt.admin_panel'))
            return redirect(url_for('prompt.index'))
        if request.method == 'POST':
            username = request.form.get('username','').strip()
            password = request.form.get('password','')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                if getattr(user, 'is_admin', False):
                    return redirect(url_for('prompt.admin_panel'))
                return redirect(url_for('prompt.index'))
            flash('Usuário ou senha inválidos.', 'error')
        return render_template('prompt/login.html')

    @target.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('prompt.login'))

    @target.route('/', methods=['GET','POST'])
    @login_required
    def index():
        projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.updated_at.desc()).all()
        templates = CustomTemplate.query.filter_by(user_id=current_user.id).order_by(CustomTemplate.updated_at.desc()).all()
        result = None
        selected_project = None
        if request.method == 'POST':
            project_id = request.form.get('project_id') or None
            if project_id:
                selected_project = Project.query.filter_by(id=int(project_id), user_id=current_user.id).first()
            zip_analysis = request.form.get('zip_analysis','')
            upload = request.files.get('zip_file')
            if upload and upload.filename.lower().endswith('.zip'):
                try:
                    zip_analysis = analyze_zip(upload)
                except Exception as exc:
                    zip_analysis = f'Falha ao analisar ZIP: {exc}'
            template_text = ''
            template_id = request.form.get('template_id') or None
            if template_id:
                tmpl = CustomTemplate.query.filter_by(id=int(template_id), user_id=current_user.id).first()
                if tmpl: template_text = tmpl.content
            data = PromptData(
                pedido=request.form.get('pedido',''),
                contexto=request.form.get('contexto','') or (selected_project.fixed_context if selected_project else ''),
                arquivos=request.form.get('arquivos','') or (selected_project.file_structure if selected_project else ''),
                erro_codigo=request.form.get('erro_codigo',''),
                modo=request.form.get('modo','novo'),
                destino=request.form.get('destino','chatgpt'),
                resultado=request.form.get('resultado','zip'),
                economico=bool(request.form.get('economico')),
                preservar=bool(request.form.get('preservar')),
                railway=bool(request.form.get('railway')),
                equipe=bool(request.form.get('equipe')),
                projeto_nome=(selected_project.name if selected_project else request.form.get('projeto_nome','')),
                modelo_extra=template_text,
                zip_analysis=zip_analysis,
            )
            result = build_prompt(data)
            title = (data.pedido[:80] or 'Prompt gerado').strip()
            hist = PromptHistory(user_id=current_user.id, project_id=selected_project.id if selected_project else None, title=title, request_text=data.pedido, prompt_text=result['prompt'], short_message=result['short'], checklist=result['checklist'], history_entry=result['history_entry'], quality_score=result['score'])
            db.session.add(hist)
            db.session.commit()
            flash('Prompt gerado e salvo no histórico.', 'success')
        histories = PromptHistory.query.filter_by(user_id=current_user.id).order_by(PromptHistory.created_at.desc()).limit(80).all()
        chats = ChatSession.query.filter_by(user_id=current_user.id).order_by(ChatSession.updated_at.desc()).limit(20).all()
        
        api_key, gemini_model = _get_gemini_config(current_user.id)
        return render_template(
            'prompt/index.html',
            projects=projects, templates=templates, histories=histories, chats=chats,
            result=result, selected_project=selected_project,
            gemini_configured=bool(api_key), gemini_model=gemini_model, is_admin=getattr(current_user, 'is_admin', False),
        )



    @target.route('/admin', methods=['GET'])
    @login_required
    def admin_panel():
        _require_admin()
        api_key, gemini_model = _get_gemini_config(current_user.id)
        return render_template(
            'prompt/admin.html',
            gemini_configured=bool(api_key),
            gemini_model=gemini_model,
            admin_username=current_user.username,
        )

    @target.route('/projects', methods=['POST'])
    @login_required
    def save_project():
        pid = request.form.get('id')
        if pid:
            p = Project.query.filter_by(id=int(pid), user_id=current_user.id).first_or_404()
        else:
            p = Project(user_id=current_user.id)
            db.session.add(p)
        p.name = request.form.get('name','Projeto sem nome').strip() or 'Projeto sem nome'
        p.description = request.form.get('description','')
        p.tech_stack = request.form.get('tech_stack','auto')
        p.fixed_context = request.form.get('fixed_context','')
        p.file_structure = request.form.get('file_structure','')
        p.preserve_rules = request.form.get('preserve_rules','')
        db.session.commit()
        flash('Projeto salvo.', 'success')
        return redirect(url_for('prompt.index') + '#projetos')

    @target.route('/projects/<int:project_id>/delete', methods=['POST'])
    @login_required
    def delete_project(project_id):
        p = Project.query.filter_by(id=project_id, user_id=current_user.id).first_or_404()
        PromptHistory.query.filter_by(project_id=p.id).update({'project_id': None})
        db.session.delete(p); db.session.commit()
        flash('Projeto removido.', 'success')
        return redirect(url_for('prompt.index') + '#projetos')

    @target.route('/templates', methods=['POST'])
    @login_required
    def save_template():
        t = CustomTemplate(user_id=current_user.id, name=request.form.get('name','Modelo sem nome'), category=request.form.get('category','geral'), content=request.form.get('content',''))
        db.session.add(t); db.session.commit()
        flash('Modelo personalizado salvo.', 'success')
        return redirect(url_for('prompt.index') + '#modelos')

    @target.route('/templates/<int:template_id>/delete', methods=['POST'])
    @login_required
    def delete_template(template_id):
        t = CustomTemplate.query.filter_by(id=template_id, user_id=current_user.id).first_or_404()
        db.session.delete(t); db.session.commit()
        flash('Modelo removido.', 'success')
        return redirect(url_for('prompt.index') + '#modelos')

    @target.route('/history/<int:history_id>/delete', methods=['POST'])
    @login_required
    def delete_history(history_id):
        h = PromptHistory.query.filter_by(id=history_id, user_id=current_user.id).first_or_404()
        db.session.delete(h); db.session.commit()
        flash('Histórico removido.', 'success')
        return redirect(url_for('prompt.index') + '#historico')

    @target.route('/export/history/<int:history_id>/<fmt>')
    @login_required
    def export_history(history_id, fmt):
        h = PromptHistory.query.filter_by(id=history_id, user_id=current_user.id).first_or_404()
        if fmt == 'json':
            data = json.dumps({'title': h.title, 'prompt': h.prompt_text, 'short': h.short_message, 'checklist': h.checklist, 'history_entry': h.history_entry}, ensure_ascii=False, indent=2)
            mimetype, filename = 'application/json', 'prompt.json'
        elif fmt == 'md':
            data = f"# {h.title}\n\n## Prompt\n\n{h.prompt_text}\n\n## Checklist\n\n{h.checklist}\n\n## Histórico\n\n{h.history_entry}"
            mimetype, filename = 'text/markdown', 'prompt.md'
        else:
            data = h.prompt_text
            mimetype, filename = 'text/plain', 'prompt.txt'
        return send_file(io.BytesIO(data.encode('utf-8')), as_attachment=True, download_name=filename, mimetype=mimetype)

    @target.route('/export/package/<int:history_id>')
    @login_required
    def export_package(history_id):
        h = PromptHistory.query.filter_by(id=history_id, user_id=current_user.id).first_or_404()
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('PROMPT.md', h.prompt_text)
            zf.writestr('MENSAGEM_CURTA.md', h.short_message)
            zf.writestr('CHECKLIST_TESTE.md', h.checklist)
            zf.writestr('HISTORICO_DO_PROJETO.md', h.history_entry)
            if h.project:
                zf.writestr('CONTEXTO_DO_PROJETO.md', h.project.fixed_context or '')
                zf.writestr('ESTRUTURA_ARQUIVOS.md', h.project.file_structure or '')
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name='pacote_prompt_ia.zip', mimetype='application/zip')



    @target.route('/api/chat/start', methods=['POST'])
    @login_required
    def api_chat_start():
        payload = request.json or {}
        project_id = payload.get('project_id') or None
        project = None
        if project_id:
            project = Project.query.filter_by(id=int(project_id), user_id=current_user.id).first()
        title = (payload.get('title') or 'Chat executor').strip()[:160] or 'Chat executor'
        session = ChatSession(user_id=current_user.id, project_id=project.id if project else None, title=title)
        db.session.add(session)
        db.session.commit()
        return jsonify({'session_id': session.id, 'title': session.title})

    @target.route('/api/chat/send', methods=['POST'])
    @login_required
    def api_chat_send():
        payload = request.json or {}
        text = (payload.get('message') or '').strip()
        if not text:
            return jsonify({'error': 'Mensagem vazia.'}), 400
        session_id = payload.get('session_id')
        project_id = payload.get('project_id') or None
        session = None
        project = None
        if project_id:
            project = Project.query.filter_by(id=int(project_id), user_id=current_user.id).first()
        if session_id:
            session = ChatSession.query.filter_by(id=int(session_id), user_id=current_user.id).first()
        if not session:
            session = ChatSession(user_id=current_user.id, project_id=project.id if project else None, title=text[:120] or 'Chat executor')
            db.session.add(session); db.session.commit()
        elif project and not session.project_id:
            session.project_id = project.id
        session.updated_at = datetime.utcnow()
        user_msg = ChatMessage(session_id=session.id, role='user', content=text)
        db.session.add(user_msg); db.session.commit()

        project = session.project or project
        response_type = payload.get('response_type') or 'gerar_arquivos'
        system_prompt = build_chat_system_prompt(
            project_name=project.name if project else '',
            context=project.fixed_context if project else '',
            files=project.file_structure if project else '',
            response_type=response_type,
        )
        last_messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.desc()).limit(8).all()[::-1]
        conversation = '\n\n'.join([f"{m.role.upper()}: {m.content}" for m in last_messages])
        full_prompt = f"{system_prompt}\n\nCONVERSA RECENTE:\n{conversation}\n\nResponda agora ao último pedido do usuário."
        api_key, model_name = _get_gemini_config(current_user.id)
        answer = call_gemini('chat', full_prompt, api_key=api_key, model_name=model_name)
        assistant_msg = ChatMessage(session_id=session.id, role='assistant', content=answer)
        db.session.add(assistant_msg); db.session.commit()
        extracted = extract_generated_files(answer)
        generated_rows = []
        for f in extracted:
            gf = GeneratedFile(session_id=session.id, message_id=assistant_msg.id, path=f['path'], content=f['content'])
            db.session.add(gf)
            generated_rows.append(gf)
        db.session.commit()
        saved_files = [{'id': gf.id, 'path': gf.path, 'size': len(gf.content)} for gf in generated_rows]
        return jsonify({'session_id': session.id, 'answer': answer, 'files': saved_files})

    @target.route('/api/chat/<int:session_id>')
    @login_required
    def api_chat_get(session_id):
        session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
        messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.asc()).all()
        files = GeneratedFile.query.filter_by(session_id=session.id).order_by(GeneratedFile.created_at.desc()).all()
        return jsonify({
            'session_id': session.id,
            'title': session.title,
            'messages': [{'role': m.role, 'content': m.content, 'created_at': m.created_at.isoformat()} for m in messages],
            'files': [{'id': f.id, 'path': f.path, 'size': len(f.content)} for f in files],
        })

    @target.route('/export/chat/<int:session_id>')
    @login_required
    def export_chat(session_id):
        session = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
        messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.asc()).all()
        files = GeneratedFile.query.filter_by(session_id=session.id).order_by(GeneratedFile.created_at.asc()).all()
        mem = _build_chat_workspace_zip(session, messages, files)
        return send_file(mem, as_attachment=True, download_name='chat_executor_workspace.zip', mimetype='application/zip')

    @target.route('/api/generated-file/<int:file_id>')
    @login_required
    def api_generated_file(file_id):
        gf = GeneratedFile.query.filter_by(id=file_id).first_or_404()
        if gf.session.user_id != current_user.id:
            return jsonify({'error': 'Arquivo não encontrado.'}), 404
        return jsonify({'id': gf.id, 'path': gf.path, 'content': gf.content, 'size': len(gf.content)})

    @target.route('/export/generated-file/<int:file_id>')
    @login_required
    def export_generated_file(file_id):
        gf = GeneratedFile.query.filter_by(id=file_id).first_or_404()
        if gf.session.user_id != current_user.id:
            return jsonify({'error': 'Arquivo não encontrado.'}), 404
        filename = (_safe_zip_path(gf.path) or 'arquivo.txt').split('/')[-1]
        return send_file(io.BytesIO(gf.content.encode('utf-8')), as_attachment=True, download_name=filename, mimetype='text/plain')

    @target.route('/export/chat/<int:session_id>/apply', methods=['POST'])
    @login_required
    def export_chat_apply(session_id):
        session, files = _session_files_for_user(session_id, current_user.id)
        messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.asc()).all()
        base_zip = request.files.get('base_zip')
        mem = _build_chat_workspace_zip(session, messages, files, base_zip_file=base_zip)
        return send_file(mem, as_attachment=True, download_name='projeto_atualizado_pelo_executor.zip', mimetype='application/zip')

    @target.route('/export/backup')
    @login_required
    def export_backup():
        projects = Project.query.filter_by(user_id=current_user.id).all()
        histories = PromptHistory.query.filter_by(user_id=current_user.id).all()
        templates = CustomTemplate.query.filter_by(user_id=current_user.id).all()
        sessions = ChatSession.query.filter_by(user_id=current_user.id).all()
        payload = {
            'user': current_user.username,
            'created_at': datetime.utcnow().isoformat(),
            'projects': [{'id': p.id, 'name': p.name, 'description': p.description, 'tech_stack': p.tech_stack, 'fixed_context': p.fixed_context, 'file_structure': p.file_structure, 'preserve_rules': p.preserve_rules} for p in projects],
            'histories': [{'title': h.title, 'request_text': h.request_text, 'prompt_text': h.prompt_text, 'short_message': h.short_message, 'checklist': h.checklist, 'history_entry': h.history_entry, 'quality_score': h.quality_score} for h in histories],
            'templates': [{'name': t.name, 'category': t.category, 'content': t.content} for t in templates],
            'chat_sessions': []
        }
        for session in sessions:
            messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at.asc()).all()
            files = GeneratedFile.query.filter_by(session_id=session.id).order_by(GeneratedFile.created_at.asc()).all()
            payload['chat_sessions'].append({
                'title': session.title,
                'project_id': session.project_id,
                'messages': [{'role': m.role, 'content': m.content} for m in messages],
                'files': [{'path': f.path, 'content': f.content} for f in files],
            })
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('backup_prompt_profissional.json', json.dumps(payload, ensure_ascii=False, indent=2))
            zf.writestr('LEIA_ME_BACKUP.txt', 'Backup exportado pelo Prompt Profissional. Guarde este arquivo em local seguro.\n')
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name='backup_prompt_profissional.zip', mimetype='application/zip')



    @target.route('/settings/api', methods=['POST'])
    @login_required
    def save_api_settings():
        _require_admin()
        api_key = (request.form.get('google_api_key') or '').strip()
        model = (request.form.get('gemini_model') or 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'
        clear_key = bool(request.form.get('clear_google_api_key'))
        if clear_key:
            _set_user_setting(current_user.id, 'google_api_key', '')
            flash('Chave Google removida das configurações internas.', 'success')
        elif api_key:
            _set_user_setting(current_user.id, 'google_api_key', api_key)
            flash('Chave Google salva. Agora o Chat Executor pode usar a API.', 'success')
        else:
            flash('Modelo salvo. A chave foi mantida como estava.', 'success')
        _set_user_setting(current_user.id, 'gemini_model', model)
        db.session.commit()
        return redirect(url_for('prompt.admin_panel') + '#config-api')


    @target.route('/api/gemini/models', methods=['POST'])
    @login_required
    def api_gemini_models():
        _require_admin()
        api_key, _model_name = _get_gemini_config(current_user.id)
        if not api_key:
            return jsonify({'ok': False, 'error': 'Nenhuma Google API Key salva. Cole a chave e clique em Salvar configuração da API.', 'models': []})
        try:
            return jsonify(list_gemini_models(api_key=api_key))
        except Exception as exc:
            return jsonify({'ok': False, 'error': f'Erro interno ao buscar modelos: {exc}', 'models': []})

    @target.route('/api/test-gemini', methods=['POST'])
    @login_required
    def api_test_gemini():
        _require_admin()
        api_key, model_name = _get_gemini_config(current_user.id)
        if not api_key:
            return jsonify({
                'ok': False,
                'model': model_name or '',
                'text': 'Nenhuma Google API Key salva. Cole a chave, clique em Salvar configuração da API e depois teste novamente.'
            })
        try:
            text = call_gemini('melhorar', 'Responda apenas: Conexão com Gemini funcionando.', api_key=api_key, model_name=model_name)
            lower = (text or '').lower()
            ok = ('funcionando' in lower) and not lower.startswith('erro') and 'não foi encontrado' not in lower and 'quota' not in lower and 'recusada' not in lower
            return jsonify({'ok': ok, 'model': model_name, 'text': text})
        except Exception as exc:
            return jsonify({
                'ok': False,
                'model': model_name or '',
                'text': f'Erro interno no teste Gemini: {exc}'
            })

    @target.route('/api/analyze-error', methods=['POST'])
    @login_required
    def api_analyze_error():
        return jsonify(analyze_error(request.json.get('text','')))

    @target.route('/api/gemini', methods=['POST'])
    @login_required
    def api_gemini():
        payload = request.json or {}
        api_key, model_name = _get_gemini_config(current_user.id)
        return jsonify({'text': call_gemini(payload.get('action','melhorar'), payload.get('text',''), api_key=api_key, model_name=model_name)})
