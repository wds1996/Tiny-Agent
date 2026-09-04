from pathlib import Path
from tempfile import TemporaryDirectory

from tiny_agent.workspace import AgentWorkspace, WorkspacePathError


with TemporaryDirectory() as tmp:
    workspace = AgentWorkspace(Path(tmp) / "workspace")
    workspace.write_text("notes/progress.md", "# Progress\n- inspected inputs")
    workspace.write_text("artifacts/report.md", "# Final report")

    print(workspace.read_text("notes/progress.md"))
    print("files:", workspace.list_files())

    try:
        workspace.read_text("../../etc/passwd")
    except WorkspacePathError as exc:
        print("blocked path escape:", exc)
