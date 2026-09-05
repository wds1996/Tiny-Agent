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
            with self.assertRaises(WorkspaceEscapeError):
                ws.read_text("/etc/passwd")

    def test_executable_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            runner = CommandRunner(ws, allowed_executables={"python"})
            with self.assertRaises(PermissionError):
                runner.run(["sh", "-c", "echo nope"])

    def test_command_runs_with_workspace_as_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("show.py", "from pathlib import Path; print(Path.cwd().name)")
            runner = CommandRunner(ws, allowed_executables={Path(sys.executable).name})
            result = runner.run([sys.executable, "show.py"])
            self.assertEqual(result.returncode, 0)
            self.assertIn("ws", result.stdout)

    def test_timeout_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("sleep.py", "import time; time.sleep(2)")
            runner = CommandRunner(ws, allowed_executables={Path(sys.executable).name})
            result = runner.run([sys.executable, "sleep.py"], timeout_seconds=0.05)
            self.assertTrue(result.timed_out)

    def test_output_is_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("loud.py", "print('x' * 100)")
            runner = CommandRunner(ws, allowed_executables={Path(sys.executable).name}, max_output_chars=10)
            result = runner.run([sys.executable, "loud.py"])
            self.assertTrue(result.truncated)
            self.assertIn("[truncated]", result.stdout)

    def test_environment_is_not_automatically_forwarded(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = AgentWorkspace.create(Path(tmp) / "ws")
            ws.write_text("env.py", "import os; print(os.environ.get('STAGE12_SECRET', 'missing'))")
            os.environ["STAGE12_SECRET"] = "private"
            runner = CommandRunner(ws, allowed_executables={Path(sys.executable).name})
            result = runner.run([sys.executable, "env.py"])
            self.assertIn("missing", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
