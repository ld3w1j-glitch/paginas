import os

import pytest

os.environ.setdefault("CURSO_INGLES_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_USER", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin-local-change-me")


@pytest.fixture(scope="module")
def client():
    from app import application

    application.config.update(TESTING=True)
    with application.test_client() as test_client:
        yield test_client


def test_public_pages_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/login").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json() == {"ok": True, "service": "portal-de-cursos"}


def test_login_and_courses(client):
    response = client.post(
        "/login",
        data={"email": "admin", "password": "admin-local-change-me"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/area")
    assert client.get("/area").status_code == 200
    assert client.get("/area/portugues").status_code == 200
    assert client.get("/area/ingles").status_code == 200


def test_compact_navigation_and_course_homes(client):
    dashboard = client.get("/area").get_data(as_text=True)
    assert "compact-dashboard" in dashboard
    assert 'aria-current="page"' in dashboard
    assert "mobile-bottom-nav" in dashboard

    english = client.get("/area/ingles").get_data(as_text=True)
    assert "course-command-card" in english
    assert "phase-accordion" in english
    assert "compact-layout.css" in english

    portuguese = client.get("/area/portugues").get_data(as_text=True)
    assert "portuguese-compact-home" in portuguese
    assert "fonts.googleapis.com" not in portuguese

    lab = client.get("/area/ingles/laboratorio").get_data(as_text=True)
    assert 'data-lab-tab="professor"' in lab
    assert 'data-lab-panel="configuracoes"' in lab


@pytest.mark.parametrize("path", ["/prompt/", "/financeiro/", "/editor-admin/"])
def test_removed_programs_are_not_available(client, path):
    assert client.get(path).status_code == 404


def test_course_assets_do_not_use_old_mount_prefix():
    paths = [
        "curso_ingles_app/static/js/agent_chat.js",
        "curso_ingles_app/static/js/portal_mcp.js",
    ]
    for path in paths:
        with open(path, encoding="utf-8") as source:
            assert "/curso-ingles" not in source.read()


def test_english_offline_lab_and_adaptive_memory(client):
    lab = client.get("/area/ingles/laboratorio")
    assert lab.status_code == 200
    assert "Laboratório de inglês offline" in lab.get_data(as_text=True)

    preference = client.post(
        "/api/ingles/preferencias",
        json={
            "level": "A2",
            "objective": "Conversação para viagens",
            "tutor_engine": "integrated",
        },
    )
    assert preference.status_code == 200
    assert preference.get_json()["level"] == "A2"

    correction = client.post(
        "/api/ingles/professor/chat",
        json={"message": "I have 27 years."},
    )
    payload = correction.get_json()
    assert correction.status_code == 200
    assert payload["ok"] is True
    assert payload["corrected_text"] == "I am 27 years old."
    assert payload["exercise"]["id"] > 0

    exercise = client.post(
        f"/api/ingles/professor/exercicio/{payload['exercise']['id']}",
        json={"response": payload["exercise"]["answer"]},
    )
    assert exercise.status_code == 200
    assert exercise.get_json()["correct"] is True

    saved = client.post(
        "/api/ingles/traducao/memoria",
        json={
            "source": "Learning takes time.",
            "translation": "Aprender leva tempo.",
        },
    )
    assert saved.status_code == 200
    memory = client.get("/api/ingles/traducao/memoria?text=Learning%20takes%20time.")
    assert memory.get_json()["segments"][0]["translation"] == "Aprender leva tempo."

    progress = client.post(
        "/api/ingles/progresso",
        json={"item_type": "lesson", "item_key": "foundation:0", "completed": True},
    )
    assert progress.status_code == 200
    state = client.get("/api/ingles/progresso").get_json()
    assert state["progress"]["lesson"]["foundation:0"]["completed"] is True
    assert state["metrics"]["xp"] >= 33

    assert client.get("/api/ingles/local-ai/status").status_code == 200
    assert client.get("/api/ingles/pronuncia/status").status_code == 200


def test_english_learning_data_is_isolated_by_user(client):
    from curso_ingles_app.app import Role, User, db

    with client.application.app_context():
        role = Role.query.filter_by(level=1).first()
        student = User(
            name="Aluno de teste",
            email="student@example.com",
            is_admin=False,
            role_id=role.id,
        )
        student.set_password("student-password")
        db.session.add(student)
        db.session.commit()

    with client.application.test_client() as second_client:
        login = second_client.post(
            "/login",
            data={"email": "student@example.com", "password": "student-password"},
        )
        assert login.status_code == 302
        state = second_client.get("/api/ingles/progresso").get_json()
        assert state["progress"] == {}
        lab = second_client.get("/area/ingles/laboratorio").get_data(as_text=True)
        assert "I am 27 years old." not in lab


def test_external_next_redirect_is_blocked(client):
    from app import application

    with application.test_client() as isolated:
        isolated.get("/logout")
        response = isolated.post(
            "/login?next=https://example.com/phishing",
            data={"email": "admin", "password": "admin-local-change-me"},
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/area")
        assert "example.com" not in response.headers["Location"]


def test_non_admin_cannot_control_shared_ai_runtime(client):
    from app import application
    from curso_ingles_app.app import Role, User, db

    with application.app_context():
        role = Role.query.filter_by(level=1).first()
        user = User.query.filter_by(email="runtime-student@example.com").first()
        if user is None:
            user = User(name="Aluno runtime", email="runtime-student@example.com", is_admin=False, role_id=role.id)
            user.set_password("student-password")
            db.session.add(user)
            db.session.commit()

    with application.test_client() as isolated:
        isolated.post("/login", data={"email": "runtime-student@example.com", "password": "student-password"})
        response = isolated.post("/api/ingles/local-ai/iniciar", json={"model": "qualquer.gguf"})
        assert response.status_code == 403
        assert response.get_json()["ok"] is False


def test_admin_delete_user_removes_related_learning_and_agent_data(client):
    from app import application
    from curso_ingles_app.app import (
        AgentConversation,
        AgentMessage,
        EnglishCourseProgress,
        EnglishTutorMessage,
        EnglishTutorPreference,
        Role,
        User,
        db,
    )

    with application.app_context():
        role = Role.query.filter_by(level=1).first()
        user = User(name="Excluir teste", email="delete-me@example.com", is_admin=False, role_id=role.id)
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        user_id = user.id
        db.session.add(EnglishTutorPreference(user_id=user_id))
        db.session.add(EnglishTutorMessage(user_id=user_id, role="user", content="hello"))
        db.session.add(EnglishCourseProgress(user_id=user_id, item_type="lesson", item_key="x", completed=True))
        conversation = AgentConversation(user_id=user_id, title="teste")
        db.session.add(conversation)
        db.session.flush()
        db.session.add(AgentMessage(conversation_id=conversation.id, role="user", content="teste"))
        db.session.commit()

    with application.test_client() as isolated:
        isolated.post("/login", data={"email": "admin", "password": "admin-local-change-me"})
        response = isolated.post("/admin", data={"action": "delete_user", "user_id": str(user_id)})
        assert response.status_code == 302

    with application.app_context():
        assert db.session.get(User, user_id) is None
        assert EnglishTutorPreference.query.filter_by(user_id=user_id).count() == 0
        assert EnglishTutorMessage.query.filter_by(user_id=user_id).count() == 0
        assert EnglishCourseProgress.query.filter_by(user_id=user_id).count() == 0
        assert AgentConversation.query.filter_by(user_id=user_id).count() == 0
