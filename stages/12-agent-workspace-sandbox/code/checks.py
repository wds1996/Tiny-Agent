from pathlib import Path
import os
import sys
import tempfile
import unittest

from runner import CommandRunner
from workspace import AgentWorkspace, WorkspaceEscapeError


class Stage12Checks(unittest.TestCase):
    def test_relative_file_stays_inside_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            target = ws.write_text("notes/a.txt", "hello")
            self.assertTrue(target.is_relative_to(ws.root))
            self.assertEqual(ws.read_text("notes/a.txt"), "hello")

    def test_parent_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            with self.assertRaises(WorkspaceEscapeError):
                ws.write_text("../secret.txt", "no")

    def test_absolute_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            absolute_outside_path = Path(Path(tmp).anchor) / "outside.txt"
            with self.assertRaises(WorkspaceEscapeError):
                ws.read_text(absolute_outside_path)

    def test_executable_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            runner = CommandRunner(ws, allowed_executables={"python": sys.executable})
            with self.assertRaises(PermissionError):
                runner.run(["shell", "-c", "echo nope"])

    def test_command_runs_with_workspace_as_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("show.py", "from pathlib import Path; print(Path.cwd().name)")
            runner = CommandRunner(ws, allowed_executables={"python": sys.executable})
            result = runner.run(["python", "show.py"])
            self.assertEqual(result.returncode, 0)
            self.assertIn("ws", result.stdout)

    def test_timeout_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("sleep.py", "import time; time.sleep(2)")
            runner = CommandRunner(ws, allowed_executables={"python": sys.executable})
            result = runner.run(["python", "sleep.py"], timeout_seconds=0.05)
            self.assertTrue(result.timed_out)

    def test_output_is_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("loud.py", "print('x' * 10000)")
            runner = CommandRunner(ws, allowed_executables={"python": sys.executable}, max_output_chars=10)
            result = runner.run(["python", "loud.py"])
            self.assertTrue(result.truncated)
            self.assertIn("[truncated]", result.stdout)
            self.assertLessEqual(len(result.stdout), 10 + len("\n...[truncated]"))

    def test_environment_is_not_automatically_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("env.py", "import os; print(os.environ.get('STAGE12_SECRET', 'missing'))")
            original = os.environ.get("STAGE12_SECRET")
            try:
                os.environ["STAGE12_SECRET"] = "private"
                runner = CommandRunner(ws, allowed_executables={"python": sys.executable})
                result = runner.run(["python", "env.py"])
                self.assertIn("missing", result.stdout)
            finally:
                if original is None:
                    os.environ.pop("STAGE12_SECRET", None)
                else:
                    os.environ["STAGE12_SECRET"] = original

    def test_path_like_executable_is_not_an_allowlist_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("python", "not a real executable")
            runner = CommandRunner(ws, allowed_executables={"python": sys.executable})
            with self.assertRaises(PermissionError):
                runner.run(["./python", "show.py"])

    def test_symlink_that_points_outside_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outside = tmp_path / "outside.txt"
            outside.write_text("private", encoding="utf-8")
            ws = AgentWorkspace.create(tmp_path / "ws")
            link = ws.root / "outside-link"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks are unavailable in this environment: {exc}")
            with self.assertRaises(WorkspaceEscapeError):
                ws.read_text("outside-link")


if __name__ == "__main__":
    unittest.main(verbosity=2)
