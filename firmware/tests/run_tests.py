"""Run actual sketches against host mocks; requires Python 3 and g++."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parent
jobs = []
for version in (2, 3):
    for name in ("test_converter", "test_power", "test_dropouts"):
        jobs.append((f"{name}-api{version}", root / f"{name}.cpp", root,
                     f"-DESP_ARDUINO_VERSION_MAJOR={version}"))
for mode in (0, 1):
    jobs.append((f"bridge-mode{mode}", root / "test_bridge.cpp", root / "bridge_mocks",
                 f"-DTELERC_LINK_MODE={mode}"))
jobs.append(("wifi-recovery", root / "test_wifi.cpp", root / "bridge_mocks",
             "-DTELERC_LINK_MODE=0"))
with tempfile.TemporaryDirectory(prefix="telerc-tests-") as tmp:
    for label, source, includes, define in jobs:
        binary = Path(tmp) / label
        subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", define, "-I", str(includes),
                        str(source), "-o", str(binary)], check=True)
        print(label, flush=True)
        # LeakSanitizer cannot inspect task lists in the hosted container.
        subprocess.run([str(binary)], check=True,
                       env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"})
