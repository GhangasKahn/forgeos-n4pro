import pytest

from forgeos.campaigns.full_cal import CalStep, FullCalCampaign
from forgeos.journal import Journal
from forgeos.safety import SafetyError, SafetyGate


def test_campaign_requires_arm(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g)
    with pytest.raises(SafetyError):
        c.start("bad")
    tok = g.arm("campaign")
    c.start(tok)
    assert c.step == CalStep.PID


def test_campaign_advances_to_done(tmp_path):
    j = Journal(tmp_path / "j.sqlite3")
    g = SafetyGate()
    c = FullCalCampaign(journal=j, safety=g, skip_shaper=True)
    tok = g.arm("campaign")
    c.start(tok)
    c.advance(True)  # PID -> PROBE_Z (shaper skipped)
    assert c.step == CalStep.PROBE_Z
    while c.step not in {CalStep.DONE, CalStep.FAILED, CalStep.MEASURE}:
        c.advance(True)
    c.advance(True)
    assert c.step == CalStep.DONE
