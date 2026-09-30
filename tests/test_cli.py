"""Tests for the command-line interface."""

from __future__ import annotations

from typer.testing import CliRunner

from nfv_mano.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output
    assert "demo" in result.output


def test_serve_rejects_unknown_component() -> None:
    result = runner.invoke(app, ["serve", "bogus"])
    assert result.exit_code != 0
    assert "component must be one of" in result.output
