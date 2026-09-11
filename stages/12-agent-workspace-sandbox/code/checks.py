from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from demo import BRIEF, FIRST_DRAFT, FINAL_DRAFT, run_demo
from report_check import analyze_report
from report_tools import ArtifactError, ReportCheckError, ReportReview, ReportTools, export_report
from runner import CommandResult, CommandRunner, _Capture
from sandbox_demo import build_command, run_container
from workspace import AgentWorkspace, FileBudgetError, WorkspaceEscapeError

CODE = Path(__file__).resolve().parent


class WithWorkspace(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="stage12-check-")
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name)
        self.ws = AgentWorkspace.create(self.parent / "run")

    def link(self, target: Path, link: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as exc:
            self.skipTest(f"symlink creation is unavailable: {exc}")


class WorkspaceChecks(WithWorkspace):
    def test_utf8_round_trip(self):
        path = self.ws.write_text("work/报告.md", "背景、风险、建议")
        self.assertTrue(path.is_relative_to(self.ws.root))
        self.assertEqual(self.ws.read_text("work/报告.md"), "背景、风险、建议")

    def test_host_import_is_readable_and_cannot_overwrite(self):
        self.ws.import_input("inputs/brief.txt", BRIEF)
        self.assertEqual(self.ws.read_text("inputs/brief.txt"), BRIEF)
        with self.assertRaises(FileExistsError):
            self.ws.import_input("inputs/brief.txt", "replacement")

    def test_write_cannot_modify_inputs_even_after_normalization(self):
        self.ws.import_input("inputs/brief.txt", BRIEF)
        for path in ("inputs/brief.txt", "work/../inputs/brief.txt"):
            with self.subTest(path=path), self.assertRaises(PermissionError):
                self.ws.write_text(path, "replacement")
        self.assertEqual(self.ws.read_text("inputs/brief.txt"), BRIEF)

    def test_host_import_rejects_other_areas(self):
        with self.assertRaises(WorkspaceEscapeError):
            self.ws.import_input("work/brief.txt", BRIEF)

    def test_parent_and_sibling_prefix_escape(self):
        for path in ("../secret.txt", "../run-copy/secret.txt", "work/../../secret.txt"):
            with self.subTest(path=path), self.assertRaises(WorkspaceEscapeError):
                self.ws.write_text(path, "no")
        self.assertFalse((self.parent / "secret.txt").exists())

    def test_absolute_and_windows_paths(self):
        for path in (str(self.parent / "outside.txt"), "C:/private.txt", "C:private.txt", "\\secret", "\\\\host\\share\\x"):
            with self.subTest(path=path), self.assertRaises(WorkspaceEscapeError):
                self.ws.resolve(path)

    def test_empty_nul_and_unrecognized_area(self):
        for path in ("", " ", ".", "work/\x00", "private/secret.txt", "work/stream:name"):
            with self.subTest(path=path), self.assertRaises(WorkspaceEscapeError):
                self.ws.resolve(path)

    def test_internal_normalization(self):
        self.assertEqual(self.ws.resolve("work/nested/../draft.md"), self.ws.root / "work/draft.md")

    def test_external_symlink_and_inventory(self):
        outside = self.parent / "canary.txt"
        outside.write_text("not a real secret", encoding="utf-8")
        self.link(outside, self.ws.root / "work/link.md")
        with self.assertRaises(WorkspaceEscapeError):
            self.ws.read_text("work/link.md")
        self.assertNotIn("work/link.md", self.ws.list_files())

    def test_internal_symlinks_are_also_disallowed(self):
        target = self.ws.write_text("work/a.md", "a")
        self.link(target, self.ws.root / "work/link.md")
        with self.assertRaises(WorkspaceEscapeError):
            self.ws.read_text("work/link.md")

    def test_write_budget_counts_bytes_and_preserves_existing(self):
        small = AgentWorkspace.create(self.parent / "small", max_file_bytes=4)
        small.write_text("work/a.txt", "old")
        with self.assertRaises(FileBudgetError):
            small.write_text("work/a.txt", "中文")
        self.assertEqual(small.read_text("work/a.txt"), "old")

    def test_read_budget_applies_to_directly_created_file(self):
        small = AgentWorkspace.create(self.parent / "small", max_file_bytes=4)
        (small.root / "work/a.txt").write_bytes(b"x" * 5)
        with self.assertRaises(FileBudgetError):
            small.read_text("work/a.txt")

    def test_regular_file_required(self):
        with self.assertRaises(ValueError):
            self.ws.read_bytes("work")
        with self.assertRaises(ValueError):
            self.ws.write_text("work", "cannot replace a directory")

    def test_existing_workspace_is_not_reused(self):
        self.ws.write_text("work/a.md", "keep")
        with self.assertRaises(FileExistsError):
            AgentWorkspace.create(self.ws.root)
        self.assertEqual(self.ws.read_text("work/a.md"), "keep")

    def test_temporary_cleanup_on_exception_leaves_external_files(self):
        sentinel = self.parent / "keep.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            with AgentWorkspace.temporary() as ws:
                root = ws.root
                ws.write_text("work/a.txt", "discard")
                raise RuntimeError("a report step failed")
        self.assertFalse(root.exists())
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


class RunnerChecks(WithWorkspace):
    def runner(self, budget=16_384):
        return CommandRunner(self.ws, allowed_executables={"python": sys.executable}, max_output_bytes=budget)

    def run_python(self, code, *, timeout=5.0, budget=16_384):
        return self.runner(budget).run(["python", "-I", "-S", "-c", code], timeout_seconds=timeout)

    def test_alias_required(self):
        for alias in ("shell", "./python", sys.executable):
            with self.subTest(alias=alias), self.assertRaises(PermissionError):
                self.runner().run([alias, "-c", "print('no')"])

    def test_registered_program_requires_absolute_path(self):
        with self.assertRaises(ValueError):
            CommandRunner(self.ws, allowed_executables={"python": "python"})

    def test_batch_files_are_not_accepted(self):
        batch = self.parent / "a.cmd"
        batch.write_text("echo no", encoding="utf-8")
        with self.assertRaises(ValueError):
            CommandRunner(self.ws, allowed_executables={"batch": batch})

    def test_command_and_timeout_validation(self):
        for command in ([], "python -c pass", ["python", 42], ["python", "bad\x00arg"]):
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.runner().run(command)
        for duration in (0, -1, math.inf, math.nan, True):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                self.runner().run(["python", "-c", "pass"], timeout_seconds=duration)

    def test_cwd_is_run_root(self):
        result = self.run_python("from pathlib import Path; print(Path.cwd())")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(Path(result.stdout.strip()), self.ws.root)

    def test_shell_metacharacters_remain_one_argument(self):
        text = "hello && echo unexpected > injected.txt"
        result = self.runner().run(["python", "-I", "-S", "-c", "import sys; print(sys.argv[1])", text])
        self.assertEqual(result.stdout.strip(), text)
        self.assertFalse((self.ws.root / "injected.txt").exists())

    def test_environment_does_not_inherit_secret(self):
        with patch.dict(os.environ, {"STAGE12_SECRET": "synthetic", "DEEPSEEK_API_KEY": "synthetic"}):
            result = self.run_python("import os; print(os.getenv('STAGE12_SECRET')); print(os.getenv('DEEPSEEK_API_KEY'))")
        self.assertEqual(result.stdout.splitlines(), ["None", "None"])

    def test_stdin_is_eof(self):
        result = self.run_python("import sys; print(repr(sys.stdin.read()))")
        self.assertEqual(result.stdout.strip(), "''")

    def test_nonzero_return_code_and_stderr_are_retained(self):
        result = self.run_python("import sys; print('failed', file=sys.stderr); sys.exit(7)")
        self.assertEqual(result.returncode, 7)
        self.assertIn("failed", result.stderr)
        self.assertFalse(result.timed_out)

    def test_both_pipes_are_drained_under_a_byte_budget(self):
        result = self.run_python("import sys; sys.stdout.buffer.write(b'x'*200000); sys.stderr.buffer.write(b'y'*200000)", budget=73)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "x" * 73)
        self.assertEqual(result.stderr, "y" * 73)
        self.assertTrue(result.stdout_truncated and result.stderr_truncated)
        self.assertTrue(result.output_complete)

    def test_exact_output_limit_is_not_truncated(self):
        capture = _Capture(4)
        capture.add(b"1234")
        self.assertEqual(capture.snapshot(), ("1234", False, False))
        capture.add(b"5")
        self.assertEqual(capture.snapshot(), ("1234", True, False))

    def test_invalid_log_utf8_is_diagnostic_not_a_crash(self):
        result = self.run_python("import sys; sys.stdout.buffer.write(b'\\xff')")
        self.assertEqual(result.stdout, "\ufffd")
        self.assertTrue(result.output_complete)

    def test_timeout_does_not_roll_back_existing_file(self):
        result = self.run_python(
            "from pathlib import Path; import time; Path('work/marker.txt').write_text('written'); time.sleep(20)",
            timeout=0.5,
        )
        self.assertTrue(result.timed_out)
        self.assertTrue(result.cleanup_complete)
        self.assertEqual(self.ws.read_text("work/marker.txt"), "written")
        self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(os.name == "posix", "POSIX process-group probe")
    def test_inherited_pipe_is_not_an_unbounded_join(self):
        started = time.monotonic()
        result = self.run_python(
            "import subprocess, sys; subprocess.Popen([sys.executable, '-I', '-S', '-c', 'import time; time.sleep(20)']); print('parent finished')",
            timeout=0.5,
        )
        self.assertTrue(result.timed_out)
        self.assertTrue(result.cleanup_complete)
        self.assertIn("parent finished", result.stdout)
        self.assertLess(time.monotonic() - started, 4)

    def test_local_runner_is_not_filesystem_isolation(self):
        canary = self.parent / "canary.txt"
        canary.write_text("synthetic", encoding="utf-8")
        result = self.runner().run([
            "python", "-I", "-S", "-c", "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())", str(canary),
        ])
        self.assertEqual(result.stdout.strip(), "synthetic")


class ReportChecks(WithWorkspace):
    def setUp(self):
        super().setUp()
        self.ws.write_text("work/report.md", FINAL_DRAFT)
        self.tools = ReportTools(self.ws)

    def test_missing_risk_is_a_real_content_failure(self):
        self.ws.write_text("work/report.md", FIRST_DRAFT)
        review = self.tools.check_report("work/report.md")
        self.assertFalse(review.passed)
        self.assertEqual(review.missing_sections, ("Risks",))

    def test_valid_report_and_path_with_spaces(self):
        self.ws.write_text("work/report with spaces.md", FINAL_DRAFT)
        review = self.tools.execute({"action": "check_report", "path": "work/report with spaces.md"})
        self.assertTrue(review.passed)
        self.assertEqual(review.sha256, hashlib.sha256(FINAL_DRAFT.encode()).hexdigest())

    def test_unknown_or_extra_arguments_are_rejected_before_launch(self):
        proposals = [
            {"action": "python", "path": "work/report.md"},
            {"action": "check_report", "path": "work/report.md", "args": ["-c", "pass"]},
            {"action": "check_report", "path": 1},
            {"action": "check_report"},
        ]
        with patch.object(self.tools.runner, "run") as run:
            for proposal in proposals:
                with self.subTest(proposal=proposal), self.assertRaises((ValueError, PermissionError)):
                    self.tools.execute(proposal)
            run.assert_not_called()

    def test_checker_is_not_loaded_from_workspace(self):
        self.ws.write_text("work/report_check.py", "raise RuntimeError('must not execute')")
        self.assertFalse(self.tools.checker.is_relative_to(self.ws.root))
        self.assertTrue(self.tools.check_report("work/report.md").passed)

    def test_input_and_script_paths_are_not_checker_arguments(self):
        self.ws.import_input("inputs/brief.md", BRIEF)
        self.ws.write_text("work/a.py", "print(42)")
        for path in ("inputs/brief.md", "work/a.py"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.tools.check_report(path)

    def test_oversized_file_rejected_before_subprocess(self):
        (self.ws.root / "work/report.md").write_bytes(b"x" * 65_537)
        with patch.object(self.tools.runner, "run") as run, self.assertRaises(FileBudgetError):
            self.tools.check_report("work/report.md")
        run.assert_not_called()

    def test_empty_section_and_code_block_heading_do_not_pass(self):
        for text in (
            "## Background\na\n## Risks\n\n## Recommendation\nb",
            "## Background\na\n```text\n## Risks\nx\n```\n## Recommendation\nb",
        ):
            self.assertEqual(analyze_report(text.encode())["missing_sections"], ["Risks"])

    def test_duplicate_unclosed_fence_and_invalid_utf8_fail(self):
        for data in (b"## Risks\na\n## Risks\nb", b"```\nx", b"\xff"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                analyze_report(data)

    def test_bad_checker_output_is_not_accepted(self):
        good = CommandResult(0, json.dumps(analyze_report(FINAL_DRAFT.encode())), "", False, False, False, True, True)
        bad = [
            replace(good, stdout="not json"), replace(good, stdout=""),
            replace(good, timed_out=True), replace(good, stdout_truncated=True),
            replace(good, returncode=2), replace(good, returncode=3),
            replace(good, output_complete=False), replace(good, cleanup_complete=False),
            replace(good, stdout=good.stdout.replace('"passed": true', '"passed": 1')),
        ]
        for result in bad:
            with self.subTest(result=result), patch.object(self.tools.runner, "run", return_value=result):
                with self.assertRaises(ReportCheckError):
                    self.tools.check_report("work/report.md")

    def test_report_rewrite_during_check_does_not_reuse_result(self):
        old = json.dumps(analyze_report(FINAL_DRAFT.encode()))
        def changed(*args, **kwargs):
            self.ws.write_text("work/report.md", FIRST_DRAFT)
            return CommandResult(0, old, "", False, False, False, True, True)
        with patch.object(self.tools.runner, "run", side_effect=changed), self.assertRaises(ReportCheckError):
            self.tools.check_report("work/report.md")

    def test_export_binds_to_same_bytes_and_survives_cleanup(self):
        with AgentWorkspace.temporary() as ws:
            root = ws.root
            ws.write_text("work/report.md", FINAL_DRAFT)
            review = ReportTools(ws).check_report("work/report.md")
            artifact = export_report(ws, review, self.parent / "deliveries/report.md")
        self.assertFalse(root.exists())
        self.assertEqual(artifact.path.read_bytes(), FINAL_DRAFT.encode())
        self.assertEqual(artifact.size_bytes, len(FINAL_DRAFT.encode()))
        self.assertEqual(artifact.sha256, hashlib.sha256(artifact.path.read_bytes()).hexdigest())

    def test_rejected_report_has_no_deliverable(self):
        self.ws.write_text("work/report.md", FIRST_DRAFT)
        review = self.tools.check_report("work/report.md")
        destination = self.parent / "report.md"
        with self.assertRaises(ArtifactError):
            export_report(self.ws, review, destination)
        self.assertFalse(destination.exists())

    def test_modification_after_check_requires_new_review(self):
        review = self.tools.check_report("work/report.md")
        self.ws.write_text("work/report.md", FINAL_DRAFT + "\nNew sentence.\n")
        with self.assertRaises(ArtifactError):
            export_report(self.ws, review, self.parent / "report.md")

    def test_no_overwrite_of_existing_delivery(self):
        destination = self.parent / "report.md"
        destination.write_text("original", encoding="utf-8")
        review = self.tools.check_report("work/report.md")
        with self.assertRaises(FileExistsError):
            export_report(self.ws, review, destination)
        self.assertEqual(destination.read_text(encoding="utf-8"), "original")

    def test_export_inside_workspace_is_rejected(self):
        review = self.tools.check_report("work/report.md")
        with self.assertRaises(ArtifactError):
            export_report(self.ws, review, self.ws.root / "artifacts/report.md")

    def test_destination_symlink_is_not_followed(self):
        destination = self.parent / "report.md"
        existing = self.parent / "keep.md"
        existing.write_text("keep", encoding="utf-8")
        self.link(existing, destination)
        with self.assertRaises(FileExistsError):
            export_report(self.ws, self.tools.check_report("work/report.md"), destination)
        self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_fabricated_pass_cannot_export_structurally_invalid_report(self):
        self.ws.write_text("work/report.md", FIRST_DRAFT)
        review = ReportReview("work/report.md", hashlib.sha256(FIRST_DRAFT.encode()).hexdigest(), True, ())
        with self.assertRaises(ArtifactError):
            export_report(self.ws, review, self.parent / "report.md")

    def test_full_demo_produces_only_one_selected_report(self):
        with patch("builtins.print"):
            destination = run_demo(self.parent / "delivery")
        self.assertEqual(destination.read_text(encoding="utf-8"), FINAL_DRAFT)
        self.assertEqual(len(list(destination.parent.iterdir())), 1)


class SandboxChecks(WithWorkspace):
    def command(self):
        report = self.ws.write_text("work/report.md", FINAL_DRAFT)
        return build_command(CODE / "report_check.py", report, image="python:3.12-slim", name="stage12-" + "a" * 32)

    def test_profile_has_readonly_files_and_no_host_directory_mount(self):
        command = self.command()
        for flag in ("--network=none", "--read-only", "--user=65534:65534", "--cap-drop=ALL",
                     "--security-opt=no-new-privileges", "--memory=128m", "--memory-swap=128m",
                     "--cpus=0.5", "--pids-limit=32", "--pull=never"):
            self.assertIn(flag, command)
        mounts = [command[i + 1] for i, arg in enumerate(command) if arg == "--mount"]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(mount.endswith(",readonly") for mount in mounts))
        self.assertFalse(any("docker.sock" in arg or arg == "--privileged" for arg in command))

    def test_profile_rejects_flag_injection_and_mount_separator(self):
        report = self.ws.write_text("work/report.md", FINAL_DRAFT)
        with self.assertRaises(ValueError):
            build_command(CODE / "report_check.py", report, image="--privileged", name="stage12-" + "a" * 32)
        comma = self.ws.write_text("work/a,b.md", FINAL_DRAFT)
        with self.assertRaises(ValueError):
            build_command(CODE / "report_check.py", comma, image="python:3.12-slim", name="stage12-" + "a" * 32)

    def test_no_docker_never_falls_back_to_local_checker(self):
        with patch("sandbox_demo.shutil.which", return_value=None), patch("subprocess.Popen") as popen:
            with self.assertRaises(RuntimeError):
                run_container(self.ws, self.command(), name="stage12-" + "a" * 32)
            popen.assert_not_called()

    def test_container_timeout_still_requests_daemon_cleanup(self):
        command = self.command()
        timeout = CommandResult(-9, "", "", True, False, False, True, True)
        cleanup = CommandResult(0, "removed", "", False, False, False, True, True)
        with patch("sandbox_demo.shutil.which", return_value=sys.executable), patch("sandbox_demo.CommandRunner") as factory:
            factory.return_value.run.side_effect = [timeout, cleanup]
            with self.assertRaises(RuntimeError):
                run_container(self.ws, command, name="stage12-" + "a" * 32)
            self.assertEqual(factory.return_value.run.call_args_list[1].args[0],
                             ["docker", "rm", "--force", "stage12-" + "a" * 32])

    def test_unconfirmed_container_cleanup_rejects_success(self):
        command = self.command()
        checked = CommandResult(0, json.dumps(analyze_report(FINAL_DRAFT.encode())), "", False, False, False, True, True)
        cleanup = CommandResult(1, "", "daemon unavailable", False, False, False, True, True)
        with patch("sandbox_demo.shutil.which", return_value=sys.executable), patch("sandbox_demo.CommandRunner") as factory:
            factory.return_value.run.side_effect = [checked, cleanup]
            with self.assertRaises(RuntimeError):
                run_container(self.ws, command, name="stage12-" + "a" * 32)

    def test_container_launch_error_still_requests_cleanup(self):
        command = self.command()
        cleanup = CommandResult(0, "removed", "", False, False, False, True, True)
        with patch("sandbox_demo.shutil.which", return_value=sys.executable), patch("sandbox_demo.CommandRunner") as factory:
            factory.return_value.run.side_effect = [OSError("launch failed"), cleanup]
            with self.assertRaises(OSError):
                run_container(self.ws, command, name="stage12-" + "a" * 32)
            self.assertEqual(factory.return_value.run.call_count, 2)

    def test_container_result_is_checked_against_report(self):
        command = self.command()
        checked = CommandResult(0, json.dumps(analyze_report(FINAL_DRAFT.encode())), "", False, False, False, True, True)
        cleanup = CommandResult(0, "removed", "", False, False, False, True, True)
        with patch("sandbox_demo.shutil.which", return_value=sys.executable), patch("sandbox_demo.CommandRunner") as factory:
            factory.return_value.run.side_effect = [checked, cleanup]
            review = run_container(self.ws, command, name="stage12-" + "a" * 32)
            self.assertTrue(review["passed"])

    def test_profile_command_is_dry_run_by_default(self):
        result = subprocess.run([sys.executable, "-S", str(CODE / "sandbox_demo.py")], capture_output=True, timeout=10, check=True)
        self.assertIn(b"PROFILE ONLY", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
