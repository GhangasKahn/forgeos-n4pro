"""Moonraker client unit tests (no live printer)."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from forgeos.moonraker_client import MoonrakerClient, MoonrakerError


def _resp(payload):
    raw = json.dumps(payload).encode("utf-8")

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return raw

    return _R()


def test_objects_status_unwraps():
    client = MoonrakerClient(host="127.0.0.1", port=7125)
    payload = {
        "result": {
            "status": {
                "print_stats": {"state": "standby"},
                "heater_bed": {"temperature": 65.0, "target": 65.0},
            }
        }
    }
    with mock.patch("urllib.request.urlopen", return_value=_resp(payload)):
        st = client.objects_status(["print_stats", "heater_bed"])
    assert st["print_stats"]["state"] == "standby"
    assert not client.is_printing()


def test_temps_dual_bed():
    client = MoonrakerClient(host="x", port=1)
    payload = {
        "result": {
            "status": {
                "extruder": {"temperature": 214.0, "target": 214.0},
                "heater_bed": {"temperature": 65.0, "target": 65.0},
                "heater_generic heater_bed_outer": {"temperature": 64.5, "target": 65.0},
            }
        }
    }
    with mock.patch("urllib.request.urlopen", return_value=_resp(payload)):
        t = client.temps()
    assert t["extruder"] == 214.0
    assert t["bed_outer"] == 64.5


def test_mesh_peak_to_peak():
    client = MoonrakerClient(host="x", port=1)
    payload = {
        "result": {
            "status": {
                "bed_mesh": {"probed_matrix": [[0.0, 0.1], [-0.05, 0.05]]},
            }
        }
    }
    with mock.patch("urllib.request.urlopen", return_value=_resp(payload)):
        assert client.mesh_peak_to_peak() == pytest.approx(0.15)


def test_from_url_and_bus_compat():
    c = MoonrakerClient.from_url("http://192.168.1.178:7125")
    assert c.base == "http://192.168.1.178:7125"
    from forgeos.vision.bus import MoonrakerBus

    bus = MoonrakerBus("http://example:7125")
    assert isinstance(bus, MoonrakerClient)


def test_gcode_error():
    client = MoonrakerClient(host="x", port=1, timeout_s=0.1)

    def boom(*a, **k):
        raise TimeoutError("nope")

    with mock.patch("urllib.request.urlopen", side_effect=boom):
        with pytest.raises(MoonrakerError):
            client.gcode("G28")
