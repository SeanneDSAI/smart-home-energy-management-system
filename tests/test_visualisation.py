import os
import sys

import matplotlib
matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import load_knowledge_base            # noqa: E402
from src.csp import make_problem                              # noqa: E402
from src.visualisation import pretty_name, day_data, make_all # noqa: E402

KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))
BASELINE = [d[0] for d in make_problem(KB)["domains"]]


def test_pretty_name():
    assert pretty_name("ev_charger") == "EV charger"


def test_day_data_has_48_slots():
    _, _, rows = day_data(KB, BASELINE)
    assert len(rows) == 48


def test_make_all_writes_files(tmp_path):
    schedules = {"baseline": BASELINE, "hill": BASELINE}
    make_all(KB, str(tmp_path), schedules=schedules)
    assert (tmp_path / "energy_use.png").exists()
    assert (tmp_path / "day_slots.csv").exists()


def test_make_all_writes_dashboard(tmp_path):
    schedules = {"baseline": BASELINE, "hill": BASELINE}
    make_all(KB, str(tmp_path), schedules=schedules)
    assert (tmp_path / "dashboard.png").stat().st_size > 0