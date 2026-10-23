import io
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile

from release_safety import check_archive, check_content, check_directory, check_file, check_name


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as writer:
        for name, value in entries:
            writer.writestr(name, value)
    data.seek(0)
    return data


class ReleaseSafetyTests(unittest.TestCase):
    def test_public_examples_and_certificates_are_permitted(self):
        for name in [".env.example", "Config.example.h", "certs/cacert.pem"]:
            check_name(name)
        check_content("Config.h", b"#define PROVISIONED 0\n")
        check_content("cacert.pem", b"-----BEGIN CERTIFICATE-----\npublic\n")

    def test_private_file_variants_are_rejected(self):
        for name in [".env", ".env.production", "keys/a.jks", "signing.keystore",
                     "fleet/Config.private.h", "TeleRCLoRaConfigLocal.h", "local.properties"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_name(name)

    def test_unsafe_paths_are_rejected(self):
        for name in ["../secret", "/absolute", "C:/secret", "a\\b", "a/./b", "a//b"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                check_name(name)

    def test_provisioned_or_ambiguous_profile_is_rejected(self):
        for data in [b"#define PROVISIONED 1\n", b"#define PROVISIONED (0)\n",
                     b"#define PROVISIONED 0\n#define PROVISIONED 1\n",
                     b"/* #define PROVISIONED 0 */\n#define PROVISIONED 1\n"]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                check_content("Config.h", data)

    def test_disguised_private_key_is_rejected(self):
        with self.assertRaises(ValueError):
            check_content("settings.txt", b"-----BEGIN " + b"PRIVATE KEY-----\n")

    def test_nested_private_material_is_rejected(self):
        inner = archive([(".env.production", b"test-only")]).getvalue()
        with self.assertRaises(ValueError):
            check_archive(archive([("source.zip", inner)]))

    def test_nested_public_archive_passes(self):
        inner = archive([("Config.h", b"#define PROVISIONED 0\n")]).getvalue()
        check_archive(archive([("source.zip", inner)]))

    def test_case_colliding_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            check_archive(archive([("a.txt", b"1"), ("A.txt", b"2")]))

    def test_android_case_sensitive_resources_are_permitted(self):
        apk = archive([("res/A.png", b"1"), ("res/a.png", b"2")]).getvalue()
        check_archive(archive([("app.apk", apk)]))

    def test_archive_symlink_is_rejected(self):
        entry = zipfile.ZipInfo("link")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(ValueError):
            check_archive(archive([(entry, b"target")]))

    def test_empty_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as root, self.assertRaises(ValueError):
            check_directory(root)

    def test_source_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / "public.txt").write_text("public")
            (path / "link.txt").symlink_to("public.txt")
            with self.assertRaises(ValueError):
                check_file(path / "link.txt", "link.txt")

    def test_archive_size_limit_is_enforced(self):
        import release_safety
        old = release_safety.MAX_EXPANDED
        try:
            release_safety.MAX_EXPANDED = 4
            with self.assertRaises(ValueError):
                check_archive(archive([("text.txt", b"12345")]))
        finally:
            release_safety.MAX_EXPANDED = old


if __name__ == "__main__":
    unittest.main()
