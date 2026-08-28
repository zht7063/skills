from __future__ import annotations

import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


class MihomoRemoteLinuxSkillTests(unittest.TestCase):
    def test_is_self_contained(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("canonical repository note", skill)
        self.assertNotIn("tianyubai", skill)
        self.assertTrue((SKILL_DIR / "references" / "operations.md").is_file())
        self.assertTrue((SKILL_DIR / "references" / "service-and-recovery.md").is_file())

    def test_private_config_boundary_allows_only_on_host_tun_backup(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        recovery = (SKILL_DIR / "references" / "service-and-recovery.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("sole exception", skill)
        self.assertIn("same target host", skill)
        self.assertIn("must never be copied to the local machine or repository", recovery)

    def test_evals_cover_install_audit_update_tun_and_migration(self) -> None:
        evals = json.loads((SKILL_DIR / "evals" / "evals.json").read_text(encoding="utf-8"))
        self.assertEqual(evals["skill_name"], "mihomo-remote-linux")
        self.assertEqual(
            {item["id"] for item in evals["evals"]},
            {
                "audit-local-port-proxy",
                "global-tun-cutover",
                "safe-update",
                "install-without-config",
                "migrate-legacy-clash",
            },
        )


if __name__ == "__main__":
    unittest.main()
