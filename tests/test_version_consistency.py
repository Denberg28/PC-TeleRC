from pathlib import Path
import tomllib

import pctelerc


def test_package_version_matches_pyproject():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert pctelerc.__version__ == data["project"]["version"]
