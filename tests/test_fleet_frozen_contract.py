"""Exercise the exact standalone map-only verifier on Windows as well as Linux."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_standalone_fleet_verifier_closes_map_database_and_avoids_video(tmp_path):
    report=tmp_path/'fleet-check.json'
    result=subprocess.run([sys.executable,'-m','pctelerc','--self-test-ui',str(report)],
        env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=30)
    assert result.returncode==0, report.read_text() if report.exists() else result.stderr
    data=json.loads(report.read_text())
    assert data['passed'] and data['checks']['no_video_runtime']
    assert data['checks']['close_cleans_sessions']
