from pathlib import Path

from kflow.config.loader import load_config_with_meta


def test_load_config_with_meta_migrates_legacy_payload(tmp_path: Path) -> None:
    config_dir = tmp_path / ".kflow"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        """
project_name: LegacyApp
project_type: generic
repo_root: /tmp/legacy
workflow_file: WORKFLOW_v2_PRO.md
policy: {}
output:
  json_enabled: true
""".strip(),
        encoding="utf-8",
    )

    config, migration = load_config_with_meta(tmp_path)

    assert config.version == 1
    assert config.output.json_enabled is True
    assert config.policy.file == "WORKFLOW_v2_PRO.md"
    assert migration["migrated"] is True
    assert "set version=1" in migration["changes"]
    assert "migrated output.json_enabled to output.json" in migration["changes"]
