from pathlib import Path

import pytest

from tiny_agent.workspace import (
    AgentWorkspace,
    DockerSandboxPolicy,
    DockerSandboxRunner,
    WorkspacePathError,
)


def test_workspace_confines_paths_and_uses_exclusive_create(tmp_path: Path) -> None:
    workspace = AgentWorkspace(tmp_path / "workspace")
    artifact = workspace.write_text("reports/a.md", "hello")
    assert artifact.relative_path == "reports/a.md"
    assert workspace.read_text("reports/a.md") == "hello"
    with pytest.raises(FileExistsError):
        workspace.write_text("reports/a.md", "again")
    with pytest.raises(WorkspacePathError):
        workspace.write_text("../escape.txt", "no")


def test_docker_sandbox_command_is_default_deny(tmp_path: Path) -> None:
    workspace = AgentWorkspace(tmp_path)
    runner = DockerSandboxRunner(workspace, DockerSandboxPolicy())
    command = runner.build_command(["python", "-c", "print('ok')"])
    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert "ALL" in command
    assert "no-new-privileges" in command
    assert str(workspace.root) in " ".join(command)
