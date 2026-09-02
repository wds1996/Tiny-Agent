from pathlib import Path
from tempfile import TemporaryDirectory

from tiny_agent.workspace import AgentWorkspace, DockerSandboxRunner


with TemporaryDirectory() as tmp:
    workspace = AgentWorkspace(Path(tmp) / "workspace")
    workspace.write_text("input.txt", "hello from the governed workspace")

    runner = DockerSandboxRunner(workspace)
    command = runner.build_command(
        ["python", "-c", "from pathlib import Path; print(Path('input.txt').read_text())"]
    )
    print("container command:")
    print(" ".join(command))
    print("\nRun the following only on a machine with Docker installed:")
    print("python -c 'from tiny_agent.workspace import ...'  # see this source file")

    # Deliberately not auto-running Docker in the public learning example.
    # `runner.run([...])` performs the real container call when Docker is available.
