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
