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


def test_lists_every_scenario(monkeypatch, capsys):
    _, out = run_menu(monkeypatch, capsys, ["5", "", "", "q"])
    for name in ("example", "high_solar", "no_solar_battery", "restricted_supply"):
        assert name in out
    assert "example  (current)" in out


def test_switch_scenario(monkeypatch, capsys):
    number = str(main_cli.list_scenarios().index("high_solar") + 1)
    _, out = run_menu(monkeypatch, capsys, ["5", number, "", "1", "", "q"])
    assert "Switched to" in out and "high_solar" in out
    assert "outputs/high_solar/" in out             # the menu shows where its charts go
    assert "7.0 kW at" in out                       # option 1 now describes high_solar's solar peak


def test_switch_scenario_bad_number(monkeypatch, capsys):
    _, out = run_menu(monkeypatch, capsys, ["5", "99", "", "q"])
    assert "Pick a number" in out and "Switched to" not in out


def test_outputs_go_to_scenario_folder(monkeypatch, capsys, tmp_path):
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    monkeypatch.setattr(main_cli, "OUTPUTS", str(tmp_path))
    number = str(main_cli.list_scenarios().index("no_solar_battery") + 1)
    _, out = run_menu(monkeypatch, capsys, ["5", number, "", "4", "", "", "q"])
    folder = tmp_path / "no_solar_battery"
    assert (folder / "images" / "dashboard.png").exists()
    assert (folder / "data" / "day.csv").exists()
    assert not (tmp_path / "example").exists()          # other scenarios are left alone
    assert "data/day.csv" in out                        # data files are listed too


def test_every_scenario_has_its_own_outputs():
    for name in main_cli.list_scenarios():
        session = main_cli.load_session(os.path.join(main_cli.SCENARIOS, name))
        assert session["outputs"] == os.path.join(main_cli.OUTPUTS, name)