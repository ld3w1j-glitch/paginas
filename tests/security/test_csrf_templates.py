from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_TEMPLATES = (
    ROOT / "curso_ingles_app" / "templates" / "base.html",
    ROOT / "curso_ingles_app" / "templates" / "ingles" / "base.html",
    ROOT / "curso_ingles_app" / "templates" / "portugues" / "base.html",
)


def test_all_root_templates_load_csrf_runtime():
    for template in BASE_TEMPLATES:
        source = template.read_text(encoding="utf-8")
        assert 'name="csrf-token"' in source, template
        assert "js/security.js" in source, template
