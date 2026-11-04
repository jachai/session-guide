#!/usr/bin/env python3
"""Installer tests use temporary homes; they never touch real Claude or Codex config."""
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install.sh")


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="session-guide-install-")
        self.env = dict(os.environ, HOME=self.home)
        self.env.pop("CLAUDE_CONFIG_DIR", None)
        self.env.pop("CODEX_HOME", None)

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_install(self, *args):
        result = subprocess.run(["sh", INSTALL] + list(args), env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_default_installs_claude_skill(self):
        self.run_install()
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".claude", "skills", "session-guide", "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".codex", "skills", "session-guide")))

    def test_codex_install_and_uninstall_keep_ledger(self):
        self.run_install("--codex")
        skill = os.path.join(self.home, ".codex", "skills", "session-guide")
        ledger = os.path.join(self.home, ".codex", "session-guide", "release", "ledger.md")
        os.makedirs(os.path.dirname(ledger))
        with open(ledger, "w") as f:
            f.write("durable state\n")
        self.assertTrue(os.path.isfile(os.path.join(skill, "SKILL.md")))
        self.run_install("--codex", "--uninstall")
        self.assertFalse(os.path.exists(skill))
        self.assertTrue(os.path.isfile(ledger))

    def test_codex_link_points_at_repository_skill(self):
        self.run_install("--link", "--codex")
        skill = os.path.join(self.home, ".codex", "skills", "session-guide")
        self.assertTrue(os.path.islink(skill))
        self.assertEqual(os.path.realpath(skill), os.path.join(ROOT, "skills", "session-guide"))


if __name__ == "__main__":
    unittest.main()
