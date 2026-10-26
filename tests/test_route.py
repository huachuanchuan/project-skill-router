"""Behavioral checks for skill discovery and shortlisting."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "route.py"


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRIPT.parents[1])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.catalog = self.root / "catalog"
        self.project.mkdir()
        self.catalog.mkdir()

    def skill(self, folder, name, description):
        directory = self.catalog / folder
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n",
            encoding="utf-8",
        )

    def route(self, task, *extra):
        command = [
            sys.executable, str(SCRIPT), "--task", task,
            "--project", str(self.project), "--catalog-root", str(self.catalog),
            "--only-catalog-roots", "--json", *extra,
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(completed.stdout)

    def test_chinese_task_recalls_specialist_skill(self):
        self.skill("paper", "paper-review", "Review scientific papers and manuscripts")
        self.skill("web", "web-design", "Design websites and user interfaces")
        names = [item["name"] for item in self.route("帮我审阅科研论文")["candidates"]]
        self.assertIn("paper-review", names)
        self.assertNotIn("web-design", names)

    def test_project_context_does_not_create_unrelated_match(self):
        (self.project / "package.json").write_text('{"dependencies":{"react":"*"}}', encoding="utf-8")
        self.skill("react", "react-ui", "Build React user interfaces")
        self.assertEqual(self.route("translate a paragraph")["candidates"], [])

    def test_duplicate_skill_name_returns_one_candidate(self):
        self.skill("a", "paper-review", "Review scientific papers")
        self.skill("b", "paper-review", "Review research manuscripts")
        output = self.route("review a scientific paper")
        self.assertEqual(output["catalog_size"], 2)
        self.assertEqual(len(output["candidates"]), 1)
        self.assertEqual(len(output["candidates"][0]["alternates"]), 1)

    def test_skips_incomplete_metadata(self):
        bad = self.catalog / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text("# no frontmatter", encoding="utf-8")
        self.assertEqual(self.route("anything")["catalog_size"], 0)


if __name__ == "__main__":
    unittest.main()

