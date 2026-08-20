import pytest

from portal_core.services.agent_policy import validate_relative_agent_path


def test_agent_policy_accepts_project_relative_paths():
    assert validate_relative_agent_path("src/app.py") == "src/app.py"


@pytest.mark.parametrize("path", ["C:/Users/test/secrets.txt", "/etc/passwd", "../../etc/passwd", ".ssh/id_rsa", ".env"])
def test_agent_policy_rejects_sensitive_or_absolute_paths(path):
    with pytest.raises(ValueError):
        validate_relative_agent_path(path)
