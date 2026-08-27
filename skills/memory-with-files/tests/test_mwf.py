from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mwf.py"
SPEC = importlib.util.spec_from_file_location("mwf", MODULE_PATH)
assert SPEC and SPEC.loader
mwf = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mwf
SPEC.loader.exec_module(mwf)


def add_args(**overrides):
    values = {
        "type": "preference",
        "status": "stable",
        "title": "Keep the GT module out of formal documentation",
        "summary": "Do not document the auxiliary GT module unless explicitly requested.",
        "body": "## Context\n\nThe module is auxiliary.\n\n## Guidance\n\nKeep it out of formal documentation.",
        "body_file": None,
        "path": ["experiments/gt/**"],
        "file_type": None,
        "component": ["GT test module"],
        "tool": None,
        "operation": ["documentation"],
        "phase": None,
        "keyword": ["ground truth"],
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def recall_args(**overrides):
    values = {
        "query": "",
        "path": None,
        "file_type": None,
        "component": None,
        "tool": None,
        "operation": None,
        "phase": None,
        "limit": 10,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class MemoryWithFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mwf-unit-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def initialize(self, git_mode="track"):
        return mwf.initialize(self.root, git_mode, "en")

    def test_initialization_preserves_existing_files_and_is_idempotent(self):
        (self.root / "AGENTS.md").write_text("# Existing rules\n\nKeep this.\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("build/\n", encoding="utf-8")

        self.initialize("track")
        agents_first = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        ignore_first = (self.root / ".gitignore").read_text(encoding="utf-8")
        protocol_first = (self.root / ".mwf" / "protocol.md").read_text(encoding="utf-8")
        self.initialize("track")

        self.assertIn("Keep this.", agents_first)
        self.assertEqual(agents_first, (self.root / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual(ignore_first, (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(protocol_first, (self.root / ".mwf" / "protocol.md").read_text(encoding="utf-8"))
        self.assertEqual(1, agents_first.count(mwf.AGENTS_START))
        self.assertEqual(1, protocol_first.count(mwf.PROTOCOL_START))
        self.assertIn(".mwf/local/", ignore_first)

    def test_ignore_mode_ignores_the_entire_memory_tree(self):
        self.initialize("ignore")
        config = mwf.load_config(self.root)
        self.assertEqual("ignore", config["git_mode"])
        self.assertIn(".mwf/", (self.root / ".gitignore").read_text(encoding="utf-8"))

    def test_add_recall_and_doctor(self):
        self.initialize()
        preference = mwf.add_record(self.root, add_args())
        candidate = mwf.add_record(
            self.root,
            add_args(
                status="candidate",
                title="Avoid Pandoc",
                summary="The user said not to use Pandoc, but the durable scope is unclear.",
                body=None,
                path=None,
                component=None,
                tool=["pandoc"],
                operation=["conversion"],
                keyword=None,
            ),
        )

        matches = mwf.recall(
            self.root,
            recall_args(path="experiments/gt/runner.py", operation=["documentation"], query="update experiment docs"),
        )
        self.assertEqual("PREF-", matches[0]["id"][:5])
        self.assertTrue(preference.is_file())
        self.assertEqual("candidates", candidate.parent.name)

        errors, warnings = mwf.doctor(self.root)
        self.assertEqual([], errors)
        self.assertTrue(any("candidate" in warning for warning in warnings))

    def test_broad_file_type_needs_another_matching_signal(self):
        self.initialize()
        incident = add_args(
            type="incident",
            status="resolved",
            title="Preserve embedded objects during conversion",
            summary="Use LibreOffice headless when Pandoc loses embedded objects.",
            body=(
                "## Problem\n\nPandoc loses objects.\n\n"
                "## Resolution\n\nUse LibreOffice headless and verify the output.\n\n"
                "## Applicability\n\nUse this for DOCX files with embedded objects; Pandoc remains valid for text-only files.\n\n"
                "## Invalid when\n\nRe-evaluate if LibreOffice no longer preserves the embedded package."
            ),
            path=None,
            file_type=[".docx"],
            component=None,
            tool=["pandoc", "libreoffice"],
            operation=["conversion"],
            keyword=["embedded objects"],
        )
        mwf.add_record(self.root, incident)

        file_only = mwf.recall(self.root, recall_args(file_type=[".docx"]))
        with_operation = mwf.recall(self.root, recall_args(file_type=[".docx"], operation=["conversion"]))
        self.assertEqual([], file_only)
        self.assertEqual("INC-", with_operation[0]["id"][:4])
        self.assertIn("Pandoc remains valid", with_operation[0]["incident_boundaries"]["applicability"])

    def test_non_candidate_requires_body_and_secrets_are_rejected(self):
        self.initialize()
        with self.assertRaises(mwf.MWFError):
            mwf.add_record(self.root, add_args(body=None))
        with self.assertRaises(mwf.MWFError):
            mwf.add_record(self.root, add_args(body="api_key=sk-abcdefghijklmnopqrstuvwxyz123456"))

    def test_forget_is_dry_run_by_default(self):
        self.initialize()
        path = mwf.add_record(self.root, add_args())
        record_id = mwf.parse_record(path).metadata["id"]

        preview = mwf.forget(self.root, record_id, apply=False)
        self.assertIn("Would permanently delete", preview)
        self.assertTrue(path.exists())

        mwf.forget(self.root, record_id, apply=True)
        self.assertFalse(path.exists())
        errors, _ = mwf.doctor(self.root)
        self.assertEqual([], errors)

    def test_doctor_scans_non_record_memory_files_for_secrets(self):
        self.initialize()
        inbox = self.root / ".mwf" / "inbox.md"
        inbox.write_text(
            inbox.read_text(encoding="utf-8").replace("- [ ]", "- [ ] api_key=sk-abcdefghijklmnopqrstuvwxyz123456"),
            encoding="utf-8",
        )

        errors, _ = mwf.doctor(self.root)
        self.assertTrue(any(".mwf/inbox.md" in error and "sensitive" in error for error in errors))

    def test_process_inbox_redacts_sensitive_input_without_echoing_it(self):
        self.initialize()
        inbox = self.root / ".mwf" / "inbox.md"
        secret = "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"
        inbox.write_text(
            inbox.read_text(encoding="utf-8").replace("- [ ]", f"- [ ] {secret}"),
            encoding="utf-8",
        )

        with self.assertRaises(mwf.MWFError):
            mwf.process_inbox_item(self.root, 1, "Rejected", None, redact=False, apply=True)
        preview = mwf.process_inbox_item(self.root, 1, "Rejected credential-like input", None, redact=True, apply=False)
        self.assertNotIn(secret, preview)
        mwf.process_inbox_item(self.root, 1, "Rejected credential-like input", None, redact=True, apply=True)

        current = inbox.read_text(encoding="utf-8")
        self.assertNotIn(secret, current)
        self.assertIn("[sensitive input redacted]", current)
        errors, _ = mwf.doctor(self.root)
        self.assertEqual([], errors)

    def test_propose_parser_creates_a_typed_candidate(self):
        self.initialize()
        parser = mwf.build_parser()
        args = parser.parse_args(
            [
                "propose",
                "--root",
                str(self.root),
                "--type",
                "preference",
                "--title",
                "Clarify converter policy",
                "--summary",
                "The durable scope is unclear.",
                "--tool",
                "pandoc",
            ]
        )
        args.status = "candidate"
        path = mwf.add_record(self.root, args)
        record = mwf.parse_record(path)
        self.assertEqual("preference", record.metadata["type"])
        self.assertEqual("candidate", record.metadata["status"])
        self.assertEqual("candidates", path.parent.name)

    def test_duplicate_compaction_preserves_unique_scope_and_evidence(self):
        self.initialize()
        body = (
            "## Problem\n\nPandoc loses embedded objects.\n\n"
            "## Resolution\n\nUse LibreOffice headless.\n\n"
            "## Applicability\n\nLegacy DOCX with embedded objects; Pandoc remains valid for text-only files.\n\n"
            "## Invalid when\n\nRe-evaluate after converter upgrades."
        )
        first_path = mwf.add_record(
            self.root,
            add_args(
                type="incident",
                status="resolved",
                title="Preserve embedded DOCX objects",
                summary="Use LibreOffice when Pandoc drops embedded objects.",
                body=body,
                path=None,
                file_type=[".docx"],
                component=None,
                tool=["pandoc", "libreoffice"],
                operation=["conversion"],
                keyword=["embedded objects"],
            ),
        )
        second_path = mwf.add_record(
            self.root,
            add_args(
                type="incident",
                status="resolved",
                title="Legacy report conversion workaround",
                summary="LibreOffice avoids Pandoc object loss in legacy reports.",
                body=body + "\n\n## Validation\n\nA visual comparison preserved layout.",
                path=["reports/legacy/**"],
                file_type=[".docx"],
                component=None,
                tool=["pandoc", "libreoffice"],
                operation=["conversion"],
                keyword=None,
            ),
        )
        first_id = mwf.parse_record(first_path).metadata["id"]
        second_id = mwf.parse_record(second_path).metadata["id"]
        self.assertTrue(mwf.duplicate_candidates(self.root, threshold=0.35))

        preview = mwf.compact_duplicate(self.root, first_id, second_id, apply=False)
        self.assertIn("Would merge", preview)
        self.assertTrue(second_path.exists())
        mwf.compact_duplicate(self.root, first_id, second_id, apply=True)

        merged = mwf.parse_record(first_path)
        self.assertIn("reports/legacy/**", merged.scope["paths"])
        self.assertIn("visual comparison", merged.body)
        self.assertFalse(second_path.exists())
        self.assertTrue(any(path.name.startswith(second_id.lower()) for path in (self.root / ".mwf" / "archive").iterdir()))
        errors, _ = mwf.doctor(self.root)
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
