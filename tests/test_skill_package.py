from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).parents[1] / "skills" / "zhihu-memory"


class SkillPackageTests(unittest.TestCase):
    def test_skill_metadata_and_workflow_contract(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("TODO", content)
        self.assertRegex(content, r"(?m)^name: zhihu-memory$")
        self.assertRegex(content, r"(?m)^description: Use when ")
        for required in (
            "two consecutive empty pages",
            "2–6",
            "Do not infer endorsement",
            "Do not mix public Zhihu search",
            "seven days",
        ):
            self.assertIn(required, content)

    def test_agent_metadata_mentions_skill(self):
        content = (SKILL_DIR / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("$zhihu-memory", content)
        self.assertNotIn("TODO", content)

    def test_package_has_no_auxiliary_readme(self):
        self.assertFalse((SKILL_DIR / "README.md").exists())
