import json
import os
from pathlib import Path
import pytest
from kflow.services.init_service import InitService
from kflow.services.plan_service import PlanService


def test_plan_service_proposes_state_without_phases(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product-spec.md").write_text("# Spec\nRequirements\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    
    # Needs a config file to not error out from default loading, but mostly AnalyzeService will mock it up 
    # if it's missing or handle it.
    # We should let AnalyzeService do its thing.
    
    service = PlanService(tmp_path)
    result = service.plan()
    
    assert result.status == "ok"
    assert result.data["sprint_stage"] == "intake"
    assert len(result.data["proposed_tasks"]) == 1
    assert result.data["proposed_tasks"][0]["name"] == "Implementation for product-spec"
    assert result.data["is_dry_run"] is True


def test_plan_service_proposes_state_with_existing_planning(tmp_path: Path, monkeypatch) -> None:
    legacy_phase_dir = tmp_path / ".planning" / "01-feature-name"
    legacy_phase_dir.mkdir(parents=True)
    (legacy_phase_dir / "05-CONTEXT.md").write_text("# Context\nLegacy context\n", encoding="utf-8")
    (legacy_phase_dir / "PLAN.md").write_text("# Plan\nLegacy plan\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    
    service = PlanService(tmp_path)
    result = service.plan()
    
    assert result.status == "ok"
    assert result.data["sprint_stage"] == "execution"
    assert len(result.data["phase_mappings"]) == 1
    assert result.data["phase_mappings"][0]["phase"] == "1"
    assert result.data["is_dry_run"] is True


def test_plan_service_apply_creates_tasks_and_manifest(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product-spec.md").write_text("# Spec\nRequirements\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    
    service = PlanService(tmp_path)
    result = service.plan(apply=True)
    
    assert result.status == "ok"
    assert result.data["is_dry_run"] is False
    assert (tmp_path / ".kflow" / "artifacts" / "planning_attach_manifest.json").exists()
    
    manifest = json.loads((tmp_path / ".kflow" / "artifacts" / "planning_attach_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sprint_stage"] == "intake"
    assert len(manifest["proposed_tasks"]) == 1
    
    assert (tmp_path / ".kflow" / "state" / "tasks" / "implementation-for-product-spec.yaml").exists()
