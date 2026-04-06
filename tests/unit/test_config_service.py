from pathlib import Path

import yaml

from kflow.services.config_service import ConfigService
from kflow.services.init_service import InitService


def test_config_set_updates_nested_value(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = ConfigService(tmp_path).set_value("adapters.build.enabled", "true")

    assert result.status == "ok"
    payload = yaml.safe_load((tmp_path / ".kflow" / "config.yaml").read_text(encoding="utf-8"))
    assert payload["adapters"]["build"]["enabled"] is True


def test_config_set_updates_string_command(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    ConfigService(tmp_path).set_value("adapters.build.command", 'python3 -c "print(1)"')

    payload = yaml.safe_load((tmp_path / ".kflow" / "config.yaml").read_text(encoding="utf-8"))
    assert payload["adapters"]["build"]["command"] == 'python3 -c "print(1)"'


def test_config_show_uses_json_aliases(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = ConfigService(tmp_path).show()

    assert "json_enabled" not in result.messages[0].text
    assert '"json": false' in result.messages[0].text
