import os
import importlib


def test_required_modules_import():
    for module_name in ["security_config", "extensions", "ai_service", "storage_service", "portal"]:
        importlib.import_module(module_name)


def test_course_search_helper_returns_expected_shape():
    from curso_ingles_app.course_utils import search_collection

    items = [
        {"title": "Módulo de teste", "summary": "Aprender rotas Flask", "lessons": [{"title": "Rotas", "focus": "Blueprints"}]},
    ]
    results = search_collection(
        "blueprint",
        items,
        text_fields=["title", "summary"],
        result_key="module",
        nested_list_field="lessons",
        nested_text_fields=["title", "focus"],
    )
    assert results
    assert "module" in results[0]
    assert isinstance(results[0]["matches"], list)


def test_env_example_documents_required_secrets():
    content = open(".env.example", encoding="utf-8").read()
    for key in ["SECRET_KEY", "ADMIN_USER", "ADMIN_PASSWORD", "DATABASE_URL"]:
        assert key in content
