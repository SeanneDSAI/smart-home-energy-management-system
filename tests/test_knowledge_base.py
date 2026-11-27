"""
Unit tests for src/knowledge_base.py. Run from the repository root:
    python tests/test_knowledge_base.py
"""

import copy
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.knowledge_base import (load_knowledge_base, time_to_slot, slots_between,  # noqa: E402
                                query_graph, appliances_of_type, price, facts_at,
                                hourly_value, slot_to_time, describe_kb, _hourly)

KB = load_knowledge_base(os.path.join(ROOT, "data", "scenarios", "example"))


def test_time_to_slot():
    assert time_to_slot("00:00") == 0
    assert time_to_slot("07:30") == 15
    assert time_to_slot("23:30") == 47
    assert time_to_slot("24:00") == 0


def test_bad_times_rejected():
    # Each of these used to be silently turned into a wrong slot (or crash)
    for bad in ("07:15", "25:00", "24:30", "12:60", "7pm", "12", "aa:bb", "-1:00"):
        try:
            time_to_slot(bad)
        except ValueError:
            continue
        raise AssertionError(bad + " should have been rejected")


def test_slots_wrap_past_midnight():
    assert slots_between("23:00", "01:00") == [46, 47, 0, 1]


def test_query_graph():
    graph = KB["graph"]
    assert query_graph(graph, "washing_machine", "is_a") == "FlexibleAppliance"
    assert query_graph(graph, "washing_machine", "duration_slots") == 3
    assert query_graph(graph, "FlexibleAppliance", "is_a") == "Appliance"
    assert query_graph(graph, "toaster", "power_kw") is None


def test_appliance_types():
    assert appliances_of_type(KB, "FixedAppliance") == ["oven"]
    assert "ev_charger" in appliances_of_type(KB, "FlexibleAppliance")


def test_tariff_boundaries():
    assert KB["tariff"][time_to_slot("07:30")] == "night"
    assert KB["tariff"][time_to_slot("08:00")] == "day"
    assert KB["tariff"][time_to_slot("17:00")] == "peak"
    assert KB["tariff"][time_to_slot("19:00")] == "day"
    assert KB["tariff"][time_to_slot("23:00")] == "night"
    assert price(KB, time_to_slot("17:30")) == 0.42


def test_facts_at():
    assert facts_at(KB, time_to_slot("17:30")) >= {"tariff_peak", "occupied", "has_battery"}
    night = facts_at(KB, time_to_slot("02:00"))
    assert "quiet_hours" in night and "solar_generating" not in night


def test_unknown_appliance_type_rejected():
    for bad in ("FlexibleAppliances", "flexibleappliance", "Battery", "toaster"):
        try:
            appliances_of_type(KB, bad)
        except ValueError:
            continue
        raise AssertionError(bad + " should have been rejected")


def test_solar():
    assert hourly_value(KB, "solar", time_to_slot("12:00")) == 3.5
    assert hourly_value(KB, "solar", time_to_slot("12:30")) == 3.5   # same hour, second slot
    assert hourly_value(KB, "solar", time_to_slot("02:00")) == 0
    assert "solar_generating" in facts_at(KB, time_to_slot("12:00"))


def test_battery_specs():
    graph = KB["graph"]
    assert query_graph(graph, "battery", "is_a") == "Battery"
    assert query_graph(graph, "battery", "capacity_kwh") == 10.0
    assert query_graph(graph, "battery", "max_discharge_kw") == 5.0
    assert query_graph(graph, "battery", "efficiency") == 0.9


def test_house_without_solar_or_battery():
    # Copy the example scenario and strip out the solar curve and the battery
    folder = tempfile.mkdtemp()
    try:
        example = os.path.join(ROOT, "data", "scenarios", "example")
        for name in ("appliances", "tariff", "occupancy", "home"):
            shutil.copy(os.path.join(example, name + ".json"), folder)
        with open(os.path.join(folder, "home.json")) as file:
            home = json.load(file)
        del home["solar_kw_hourly"], home["battery"]
        with open(os.path.join(folder, "home.json"), "w") as file:
            json.dump(home, file)

        kb = load_knowledge_base(folder)
        assert kb["solar"] == [0] * 24
        assert "battery" not in kb["graph"]
        noon = facts_at(kb, time_to_slot("12:00"))
        assert "solar_generating" not in noon and "has_battery" not in noon
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_bad_hourly_profiles_rejected():
    # A short or broken hourly list used to load fine, then crash later with an
    # IndexError. It should now be rejected with a clear ValueError.
    for bad in ([0.3] * 23, [0.3] * 25, [0.3] * 23 + ["0.3"], "0.3"):
        try:
            _hourly({"base_load_kw_hourly": bad}, "base_load_kw_hourly", "home.json")
        except ValueError as error:
            assert "base_load_kw_hourly" in str(error)
            continue
        raise AssertionError("%r should have been rejected" % (bad,))
    assert _hourly({}, "solar_kw_hourly", "home.json", default=[0] * 24) == [0] * 24


def test_describe_kb_battery_without_efficiency():
    # The controller treats a missing efficiency as 1.0, but describe_kb used to
    # crash with a KeyError on it. It should now show the battery as 100% efficient.
    kb = copy.deepcopy(KB)
    del kb["graph"]["battery"]["efficiency"]
    assert "100% efficient" in describe_kb(kb)


def test_slot_to_time():
    assert slot_to_time(0) == "00:00"
    assert slot_to_time(15) == "07:30"
    assert slot_to_time(48) == "00:00"
    for slot in range(48):
        assert time_to_slot(slot_to_time(slot)) == slot


def test_describe_kb():
    text = describe_kb(KB)
    assert "washing_machine" in text and "oven" in text
    assert "peak   EUR 0.42/kWh  17:00-19:00" in text
    assert "night  EUR 0.18/kWh  23:00-08:00" in text      # joined across midnight
    assert "Quiet hours: 23:00-07:00" in text
    assert "10.0 kWh capacity" in text


if __name__ == "__main__":
    tests = [test for name, test in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(len(tests), "tests passed")
