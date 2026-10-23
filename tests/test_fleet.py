from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from pctelerc.fleet import draft_path
from pctelerc.mission_plan import Point
from pctelerc.mission_widget import MissionDialog


@pytest.mark.parametrize("invalid", [0, 21, -1, True, "1", "../secret", 1.5])
def test_invalid_identity_cannot_select_storage(invalid):
    with pytest.raises(ValueError):
        draft_path(Path("plans"), invalid)


def test_twenty_plan_paths_are_distinct():
    assert len({draft_path(Path("plans"), i) for i in range(1, 21)}) == 20


def test_rover_selection_isolates_drafts_and_never_restores_authority(tmp_path):
    app = QApplication.instance() or QApplication([])
    dialog = MissionDialog(lambda: pytest.fail("Offline selection opened radio"), draft_path=tmp_path / "rover-001.json")
    dialog.plan.points = [Point(13.6, 123.2)]
    dialog.digest = "old verified digest"
    dialog.aux.setChecked(True)
    dialog.continue_loss.setChecked(True)
    dialog.rover.setValue(2)
    assert not dialog.plan.points
    assert dialog.digest == "" and not dialog.connected
    assert not dialog.aux.isChecked() and not dialog.continue_loss.isChecked()
    dialog.plan.points = [Point(14.0, 124.0)]
    dialog.rover.setValue(1)
    assert dialog.plan.points[0].latitude == 13.6
    dialog.rover.setValue(2)
    assert dialog.plan.points[0].latitude == 14.0
    assert not dialog.service.running
    dialog.close()
