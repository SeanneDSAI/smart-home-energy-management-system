"""
Tests for main_cli.py: drive the interactive menu with scripted input and
check each option prints what it should.
Run from the repository root:
    pytest tests/test_cli.py
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main_cli                                               # noqa: E402


def run_menu(monkeypatch, capsys, inputs):
    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    monkeypatch.setattr(sys, "argv", ["main_cli.py"])
    code = main_cli.main()
    return code, capsys.readouterr().out


def test_quit(monkeypatch, capsys):
    code, out = run_menu(monkeypatch, capsys, ["q"])
    assert code == 0 and "Bye!" in out


def test_show_scenario(monkeypatch, capsys):
    _, out = run_menu(monkeypatch, capsys, ["1", "", "q"])
    assert "washing_machine" in out


def test_find_best_schedule(monkeypatch, capsys):
    _, out = run_menu(monkeypatch, capsys, ["2", "", "q"])
    assert "Best schedule" in out


def test_run_controller(monkeypatch, capsys):
    _, out = run_menu(monkeypatch, capsys, ["3", "", "q"])
    assert "Battery controller" in out