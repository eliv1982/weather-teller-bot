"""Static guards: README, env templates, dependency files and CI must agree with the repository."""

import pathlib
import re

from ai_weather_service import AiWeatherService

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _parse_env(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _readme_env_block() -> dict[str, str]:
    match = re.search(r"```env\n(.*?)```", _read("README.md"), re.DOTALL)
    assert match, "README has no ```env block"
    return _parse_env(match.group(1))


def _readme_tree_paths() -> list[str]:
    """Paths listed in the README project tree (```text block), rebuilt from the box-drawing indentation."""
    match = re.search(r"```text\n(.*?)```", _read("README.md"), re.DOTALL)
    assert match, "README has no ```text project tree"
    paths, stack = [], []
    for line in match.group(1).splitlines()[1:]:  # first line is the repository root
        entry = re.match(r"^((?:│   |    )*)(?:├── |└── )(\S+)", line)
        if not entry:
            continue
        depth = len(entry.group(1)) // 4
        name = entry.group(2)
        del stack[depth:]
        if name != "...":
            paths.append("/".join(stack + [name]).rstrip("/"))
        stack.append(name.rstrip("/"))
    return paths


def test_readme_env_example_matches_env_example_file():
    assert _readme_env_block() == _parse_env(_read(".env.example"))


def test_env_templates_define_the_same_keys_and_differ_only_in_pghost():
    local = _parse_env(_read(".env.example"))
    docker = _parse_env(_read(".env.docker.example"))

    assert local.keys() == docker.keys()
    assert {key for key in local if local[key] != docker[key]} == {"PGHOST"}
    assert docker["PGHOST"] == "postgres"  # the docker-compose service name


def test_documented_default_openai_model_matches_code_default(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert AiWeatherService().model == _parse_env(_read(".env.example"))["OPENAI_MODEL"]


def test_readme_project_tree_lists_only_existing_paths():
    paths = _readme_tree_paths()

    assert "handlers/history.py" in paths and "formatters/weather.py" in paths  # parser sanity check
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f"README project tree mentions paths that do not exist: {missing}"


def test_production_requirements_are_exactly_pinned():
    lines = [line.strip() for line in _read("requirements.txt").splitlines() if line.strip() and not line.startswith("#")]

    assert lines
    assert all(re.match(r"^[A-Za-z0-9_.\-]+(\[[A-Za-z0-9_,\-]+\])?==\d[\w.]*$", line) for line in lines), lines
    names = {re.split(r"[\[=]", line)[0].lower() for line in lines}
    assert {"requests", "python-dotenv", "pytelegrambotapi", "psycopg", "openai"} <= names


def test_dev_requirements_extend_production_and_declare_pytest_without_leaking_into_production():
    dev = [line.strip() for line in _read("requirements-dev.txt").splitlines() if line.strip() and not line.startswith("#")]

    assert "-r requirements.txt" in dev
    assert any(re.match(r"^pytest==\d[\w.]*$", line) for line in dev)
    assert "pytest" not in _read("requirements.txt").lower()


def test_ci_workflow_runs_the_documented_checks_without_secrets():
    workflow = _read(".github/workflows/ci.yml")

    assert "pull_request:" in workflow and "push:" in workflow
    assert 'python-version: "3.12"' in workflow
    for command in (
        "pip install -r requirements-dev.txt",
        "python -m pip check",
        "python -m compileall",
        "git diff --check",
        "python -m pytest",
    ):
        assert command in workflow, f"CI does not run {command!r}"
    assert "secrets." not in workflow  # tests must never need production credentials
