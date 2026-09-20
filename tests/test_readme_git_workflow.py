"""Read-only checks for the copyable Git onboarding instructions."""

from pathlib import Path
import re
import shlex
import unittest


class ReadmeGitWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Как коммитить изменения\n", 1)[1].split("\n## ", 1)[0]
        matches = re.finditer(r"`(git [^`\n]+)`|^\s*(git [^\n]+)$", section, re.MULTILINE)
        cls.commands = [shlex.split(match.group(1) or match.group(2)) for match in matches]

    def test_section_includes_local_review_and_commit_commands(self):
        self.assertTrue(any(command[:2] == ["git", "status"] for command in self.commands))
        self.assertTrue(any(command[:2] == ["git", "commit"] for command in self.commands))

    def test_http_command_urls_do_not_embed_credentials(self):
        for command in self.commands:
            for argument in command:
                self.assertNotRegex(argument, r"https?://[^/\s]+@", "Keep authentication out of command URLs")

    def test_no_plaintext_credential_storage_is_recommended(self):
        for command in self.commands:
            if command[:2] == ["git", "config"] and "credential.helper" in command:
                helper = command[command.index("credential.helper") + 1]
                self.assertNotEqual(helper.split()[0], "store", "Use secure credential storage")

    def test_staging_is_scoped_to_explicit_paths(self):
        for command in self.commands:
            if command[:2] == ["git", "add"]:
                self.assertFalse(set(command[2:]) & {".", "-A", "--all"}, "Preserve unrelated worktree changes")

    def test_staged_review_precedes_local_commit(self):
        commit_index = next(index for index, command in enumerate(self.commands) if command[:2] == ["git", "commit"])
        before_commit = self.commands[:commit_index]
        self.assertIn(["git", "diff", "--cached", "--check"], before_commit)
        self.assertIn(["git", "diff", "--cached"], before_commit)

    def test_push_examples_do_not_target_a_hardcoded_main_branch(self):
        for command in self.commands:
            if command[:2] == ["git", "push"]:
                self.assertFalse(set(command[2:]) & {"main", "master"}, "Publish only the separately approved branch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
