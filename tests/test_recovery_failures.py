"""Disk failures must preserve routes and accurately reflect USB ownership."""
import json
import threading

import pytest

from pctelerc import fleet_window as ui
from pctelerc.config import AppSettings
from pctelerc.mission_widget import MissionDialog


@pytest.mark.parametrize('original', [b'{broken', b'\xff\xfe', b'{"version":99}', b' ' * 120001],
    ids=['malformed-json', 'invalid-encoding', 'future-version', 'oversized'])
def test_unreadable_draft_survives_untouched_shutdown(tmp_path, original):
    path = tmp_path/'rover-001.json'
    path.write_bytes(original)
    panel = MissionDialog(lambda: True, draft_path=path)
    assert not panel.plan.points and not panel.digest
    assert panel._shutdown()
    assert path.read_bytes() == original


def test_edit_after_failed_restore_preserves_original_before_saving(tmp_path):
    path = tmp_path/'rover-001.json'
    original = b'\xff\xfe damaged route'
    path.write_bytes(original)
    panel = MissionDialog(lambda: True, draft_path=path)
    panel._add(13.6, 123.2)
    assert panel._save_draft()
    backups = list(tmp_path.glob('rover-001.recovery-*.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert json.loads(path.read_text())['points'][0][:2] == [13.6, 123.2]
    panel._add(13.7, 123.3)
    assert panel._save_draft()
    assert list(tmp_path.glob('rover-001.recovery-*.json')) == backups
    assert not panel.digest and not panel.service.running
    assert panel._shutdown()


def test_failed_recovery_copy_cannot_replace_original(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path/'rover-001.json'
    path.write_bytes(b'{broken')
    panel = MissionDialog(lambda: True, draft_path=path)
    panel._add(13.6, 123.2)
    open_file = Path.open
    def fail_backup(self, *args, **kwargs):
        if '.recovery-' in self.name:
            raise OSError('disk full')
        return open_file(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_backup)
    assert not panel._save_draft()
    assert path.read_bytes() == b'{broken'
    monkeypatch.setattr(Path, 'open', open_file)
    assert panel._shutdown()


def test_partial_recovery_copy_is_removed_and_retry_keeps_exact_original(tmp_path, monkeypatch):
    from pctelerc import mission_widget
    path = tmp_path/'rover-001.json';original = b'{broken route with remaining data'
    path.write_bytes(original)
    panel = MissionDialog(lambda: True, draft_path=path)
    panel._add(13.6, 123.2)
    def partial(source, output):
        output.write(source.read(3))
        raise OSError('disk full during copy')
    with monkeypatch.context() as patch:
        patch.setattr(mission_widget.shutil, 'copyfileobj', partial)
        assert not panel._save_draft()
        assert path.read_bytes() == original
        assert not list(tmp_path.glob('*.recovery-*.json'))
    assert panel._save_draft()
    assert next(tmp_path.glob('*.recovery-*.json')).read_bytes() == original
    assert panel._shutdown()


def test_existing_recovery_file_is_never_removed_on_name_collision(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from pctelerc import mission_widget
    path = tmp_path/'rover-001.json';path.write_bytes(b'{broken')
    existing = tmp_path/'rover-001.recovery-existing.json';existing.write_bytes(b'older recovery')
    panel = MissionDialog(lambda: True, draft_path=path)
    panel._add(13.6, 123.2)
    with monkeypatch.context() as patch:
        patch.setattr(mission_widget.uuid, 'uuid4', lambda: SimpleNamespace(hex='existing'))
        assert not panel._save_draft()
        assert path.read_bytes() == b'{broken' and existing.read_bytes() == b'older recovery'
    assert panel._shutdown()


def test_rover_switch_cannot_discard_unsaved_route(tmp_path, monkeypatch):
    panel = MissionDialog(lambda: True, draft_path=tmp_path/'rover-001.json')
    panel._add(13.6, 123.2)
    before = panel._draft_text()
    with monkeypatch.context() as patch:
        patch.setattr(panel, '_save_draft', lambda: False)
        panel.rover.setValue(2)
        assert panel.rover.value() == 1 and panel._selected_rover == 1
        assert panel._draft_text() == before
    assert panel._shutdown()


class FakeHub:
    def __init__(self, _port):
        self.operation = threading.Lock()
        self.stopped = threading.Event()
        self.error = ''
        self.closed = False

    def close(self):
        self.closed = True
        self.stopped.set()


def test_open_base_setting_failure_keeps_truthful_owner_and_can_close(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, 'load_settings', lambda: AppSettings(map_online=False))
    monkeypatch.setattr(ui, 'save_settings', lambda _: (_ for _ in ()).throw(OSError('disk full')))
    window = ui.FleetWindow(hub_factory=FakeHub, draft_root=tmp_path/'plans')
    window.port.setCurrentText('COM9')
    window.toggle_base()
    hub = window.hub
    assert hub is not None and not hub.closed
    assert window.base_button.text() == 'Close BASE'
    assert not window.port.isEnabled() and not window.refresh.isEnabled()
    assert 'could not be saved' in window.status.text()
    assert all(p.service.operation_gate is hub.operation for p in window.panels.values())
    assert not any(p.service.running or p.digest for p in window.panels.values())
    window.toggle_base()
    assert hub.closed and window.hub is None
    assert window.base_button.text() == 'Open BASE' and window.port.isEnabled()
    assert window.close()
