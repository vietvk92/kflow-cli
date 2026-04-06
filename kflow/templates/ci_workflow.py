"""CI workflow templates."""

from __future__ import annotations


def render_github_actions_ci() -> str:
    """Render a practical GitHub Actions workflow for KFlow CI gates."""
    return """name: KFlow CI

on:
  push:
    branches:
      - main
      - master
  pull_request:

jobs:
  kflow:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          python -m pip install .[dev]

      - name: Repo doctor
        run: python -m kflow.main doctor repo --json

      - name: Repo CI gates
        run: python -m kflow.main doctor ci --repo --json

      - name: Repo doctor report
        run: python -m kflow.main doctor report --json

      - name: Upload doctor report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: kflow-doctor-report
          path: .kflow/artifacts/doctor-report.json
          if-no-files-found: ignore
"""
