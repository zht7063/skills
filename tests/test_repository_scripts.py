from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "_skill_tools.py"
SPEC = importlib.util.spec_from_file_location("skill_tools", MODULE_PATH)
assert SPEC and SPEC.loader
skill_tools = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = skill_tools
SPEC.loader.exec_module(skill_tools)


class RepositoryScriptTests(unittest.TestCase):
    def make_skill(self, root: Path, name: str = "demo-skill") -> Path:
        skill = root / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: A demo skill for installer tests.\n---\n\n# Demo\n",
            encoding="utf-8",
        )
        (skill / "assets").mkdir()
        (skill / "assets" / "data.txt").write_text("runtime", encoding="utf-8")
        (skill / "evals").mkdir()
        (skill / "evals" / "cases.json").write_text("[]", encoding="utf-8")
        (skill / "tests").mkdir()
        (skill / "tests" / "test_demo.py").write_text("# development only\n", encoding="utf-8")
        (skill / "__pycache__").mkdir()
        (skill / "__pycache__" / "demo.pyc").write_bytes(b"cache")
        return skill

    def test_target_profiles_respect_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_codex = os.environ.get("CODEX_HOME")
            old_pi = os.environ.get("PI_CODING_AGENT_DIR")
            try:
                os.environ["CODEX_HOME"] = str(root / "codex")
                os.environ["PI_CODING_AGENT_DIR"] = str(root / "pi")
                self.assertEqual(
                    skill_tools.resolve_target("codex", None), (root / "codex" / "skills").resolve()
                )
                self.assertEqual(
                    skill_tools.resolve_target("pi", None), (root / "pi" / "skills").resolve()
                )
                self.assertEqual(
                    skill_tools.resolve_target(None, str(root / "custom")), (root / "custom").resolve()
                )
            finally:
                if old_codex is None:
                    os.environ.pop("CODEX_HOME", None)
                else:
                    os.environ["CODEX_HOME"] = old_codex
                if old_pi is None:
                    os.environ.pop("PI_CODING_AGENT_DIR", None)
                else:
                    os.environ["PI_CODING_AGENT_DIR"] = old_pi

    def test_link_install_is_idempotent_and_uninstall_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_skill(root)
            metadata = skill_tools.require_valid_skill(source)
            target = root / "installed"

            installed = skill_tools.install_skill(source, metadata, target)
            self.assertEqual(installed.action, "installed")
            self.assertTrue(installed.destination.is_symlink())

            repeated = skill_tools.install_skill(source, metadata, target)
            self.assertEqual(repeated.action, "already-installed")

            preview = skill_tools.uninstall_skill(metadata.name, target)
            self.assertEqual(preview.action, "would-uninstall")
            self.assertTrue(installed.destination.is_symlink())

            removed = skill_tools.uninstall_skill(metadata.name, target, apply=True)
            self.assertEqual(removed.action, "uninstalled")
            self.assertFalse(installed.destination.exists())

    def test_copy_install_filters_development_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_skill(root)
            metadata = skill_tools.require_valid_skill(source)
            target = root / "installed"

            result = skill_tools.install_skill(source, metadata, target, mode="copy")
            self.assertTrue((result.destination / "assets" / "data.txt").is_file())
            self.assertFalse((result.destination / "evals").exists())
            self.assertTrue((result.destination / "tests" / "test_demo.py").is_file())
            self.assertFalse((result.destination / "__pycache__").exists())
            self.assertEqual(skill_tools.validate_skill(result.destination), [])

    def test_dry_run_does_not_create_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_skill(root)
            metadata = skill_tools.require_valid_skill(source)
            target = root / "not-created"

            result = skill_tools.install_skill(source, metadata, target, dry_run=True)
            self.assertEqual(result.action, "would-install")
            self.assertFalse(target.exists())

    def test_collision_refuses_by_default_and_replace_backs_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_skill(root)
            metadata = skill_tools.require_valid_skill(source)
            target = root / "installed"
            destination = target / metadata.name
            destination.mkdir(parents=True)
            (destination / "sentinel.txt").write_text("old", encoding="utf-8")

            with self.assertRaises(skill_tools.SkillToolError):
                skill_tools.install_skill(source, metadata, target)

            result = skill_tools.install_skill(source, metadata, target, replace=True)
            self.assertEqual(result.action, "replaced")
            self.assertIsNotNone(result.backup)
            assert result.backup
            self.assertEqual((result.backup / "sentinel.txt").read_text(encoding="utf-8"), "old")
            self.assertTrue(result.destination.is_symlink())
            self.assertNotEqual(result.backup.parent.parent.parent, target)

    def test_invalid_skill_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = self.make_skill(Path(temp), "actual-name")
            (skill / "SKILL.md").write_text(
                "---\nname: wrong-name\ndescription: mismatch\n---\n",
                encoding="utf-8",
            )
            issues = skill_tools.validate_skill(skill)
            self.assertTrue(any("does not match" in issue for issue in issues))

    def test_uninstall_refuses_mismatched_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "installed"
            destination = target / "demo-skill"
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_text(
                "---\nname: another-skill\ndescription: Do not remove this directory.\n---\n",
                encoding="utf-8",
            )

            with self.assertRaises(skill_tools.SkillToolError):
                skill_tools.uninstall_skill("demo-skill", target, apply=True)
            self.assertTrue(destination.is_dir())


if __name__ == "__main__":
    unittest.main()
