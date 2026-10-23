"""Reject private configuration and unsafe paths before publishing release assets.

This is a packaging boundary, not a general secret detector or vehicle safety test.
"""

import argparse
import io
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

PRIVATE_SUFFIXES = {".jks", ".keystore", ".key", ".p12", ".pfx"}
PRIVATE_NAMES = {"config.private.h", "telercloraconfiglocal.h", "local.properties"}
PRIVATE_KEY = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)
MAX_EXPANDED = 2 * 1024**3
MAX_MEMBER = 512 * 1024**2
MAX_MEMBERS = 50000
MAX_DEPTH = 3


def check_name(name):
    relative = PurePosixPath(name)
    if (not name or "\\" in name or ":" in name or "\0" in name
            or relative.is_absolute() or ".." in relative.parts
            or any(part in ("", ".") for part in name.rstrip("/").split("/"))):
        raise ValueError("Unsafe release path: " + repr(name))
    for part in relative.parts:
        lower = part.lower()
        if (lower in PRIVATE_NAMES or PurePosixPath(lower).suffix in PRIVATE_SUFFIXES
                or (lower.startswith(".env") and lower != ".env.example")):
            raise ValueError("Private configuration/signing file in release: " + name)


def check_content(name, data):
    if PRIVATE_KEY.search(data):
        raise ValueError("Private key material in release: " + name)
    if PurePosixPath(name).suffix.lower() == ".h":
        text = data.decode("utf-8", errors="strict")
        text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
        values = re.findall(r"^\s*#\s*define\s+PROVISIONED\s+(.*?)\s*$", text, re.M)
        if values and values != ["0"]:
            raise ValueError("Refusing private or ambiguous mission Config.h: " + name)


def check_file(path, relative):
    path = Path(path)
    check_name(relative)
    if path.is_symlink():
        raise ValueError("Symlink in release: " + relative)
    # Text/key files are inspected in full; opaque compiled binaries remain
    # subject to their independent signature/hash/provenance build gates.
    if path.suffix.lower() not in {".zip", ".apk", ".exe", ".dll", ".so", ".bin", ".elf", ".pdb"}:
        if path.stat().st_size > MAX_MEMBER:
            raise ValueError("Oversized release source file")
        check_content(relative, path.read_bytes())


def check_archive(archive, depth=0, budget=None, windows_paths=True):
    if depth > MAX_DEPTH:
        raise ValueError("Excessive nested release archives")
    budget = [0, 0] if budget is None else budget
    with zipfile.ZipFile(archive) as reader:
        seen = set()
        for entry in reader.infolist():
            check_name(entry.filename)
            normalized = entry.filename.rstrip("/")
            if windows_paths:
                normalized = normalized.casefold()
            if normalized in seen:
                raise ValueError("Duplicate/case-colliding archive path")
            seen.add(normalized)
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Symlink in release archive")
            if entry.flag_bits & 1:
                raise ValueError("Encrypted release member cannot be audited")
            budget[0] += entry.file_size
            budget[1] += 1
            if (entry.file_size > MAX_MEMBER or budget[0] > MAX_EXPANDED
                    or budget[1] > MAX_MEMBERS):
                raise ValueError("Release archive exceeds audit limits")
            if entry.is_dir():
                continue
            suffix = PurePosixPath(entry.filename).suffix.lower()
            if suffix in {".zip", ".apk"}:
                check_archive(io.BytesIO(reader.read(entry)), depth + 1, budget,
                              windows_paths=(suffix != ".apk"))
            elif suffix not in {".exe", ".dll", ".so", ".bin", ".elf", ".pdb"}:
                check_content(entry.filename, reader.read(entry))
        if reader.testzip() is not None:
            raise ValueError("Release archive CRC failure")


def check_directory(root):
    root = Path(root)
    files = sorted(root.rglob("*"))
    if not root.is_dir() or not any(path.is_file() for path in files):
        raise ValueError("Empty/missing release directory")
    for path in files:
        relative = path.relative_to(root).as_posix()
        check_name(relative)
        if path.is_symlink():
            raise ValueError("Symlink in release output")
        if not path.is_file():
            continue
        check_file(path, relative)
        if path.suffix.lower() in {".zip", ".apk"}:
            # Android's signed APK ZIP namespace is case-sensitive. aapt may
            # legitimately produce both res/A.png and res/a.png.
            check_archive(path, windows_paths=(path.suffix.lower() != ".apk"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory")
    check_directory(parser.parse_args().directory)
    print("PASS: release paths, private-file exclusions, nested archives and public radio profiles")
