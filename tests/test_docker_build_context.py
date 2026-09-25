"""Static guards for the Docker build context and runtime user (no Docker daemon needed)."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _dockerignore_patterns() -> set[str]:
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.strip().startswith("#")}


def test_dockerignore_excludes_secrets_vcs_caches_venv_and_logs():
    patterns = _dockerignore_patterns()

    for required in (".env", ".env.*", ".git", "**/__pycache__", "**/*.pyc", "venv", ".venv", ".cache", "**/*.log"):
        assert required in patterns, f"{required!r} missing from .dockerignore"


def test_dockerignore_does_not_re_include_env_files():
    assert not [p for p in _dockerignore_patterns() if p.startswith("!")]


def test_dockerignore_does_not_exclude_runtime_sources():
    patterns = _dockerignore_patterns()

    for needed in ("bot.py", "requirements.txt", "weather", "handlers", "utils", "workers", "formatters", "ai"):
        assert needed not in patterns


def test_dockerfile_runs_as_non_root_user_that_owns_the_workdir():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert re.search(r"^USER\s+(?!root\b)\S+", dockerfile, re.MULTILINE), "container must not run as root"
    # bot.log and its rotated backups are created next to bot.py, so /app must be writable by that user.
    assert re.search(r"chown\s+\S+\s+/app\b", dockerfile)
    assert "COPY --chown=" in dockerfile
    user_line = dockerfile.index("USER ")
    assert dockerfile.index("pip install") < user_line, "dependencies must be installed before dropping privileges"
    assert dockerfile.rstrip().endswith('CMD ["python", "bot.py"]')


def test_docker_compose_still_injects_secrets_via_env_file_not_build_context():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "env_file:" in compose
    assert ".env" in compose
