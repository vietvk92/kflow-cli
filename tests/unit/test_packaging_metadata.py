from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


def test_pyproject_uses_readme_and_expected_project_name() -> None:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    assert project["name"] == "kflow"
    assert project["readme"] == "README.md"
    assert "kflow" in project["scripts"]


def test_readme_mentions_install_and_quick_start() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "python3 -m pip install ." in readme
    assert "kflow init" in readme
    assert "schema_version" in readme


def test_changelog_mentions_current_foundation_scope() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "0.1.0" in changelog
    assert "KFlow Python CLI foundation" in changelog
