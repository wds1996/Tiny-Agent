from pathlib import Path
import sys
import tempfile

from runner import CommandRunner
from workspace import AgentWorkspace


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = AgentWorkspace.create(Path(tmp) / "run-001")
        workspace.write_text(
            "work/check.py",
            "from pathlib import Path\n"
            "text = Path('input.txt').read_text()\n"
            "Path('artifacts/result.txt').parent.mkdir(parents=True, exist_ok=True)\n"
            "Path('artifacts/result.txt').write_text(text.upper())\n"
            "print('processed', len(text), 'characters')\n",
        )
        workspace.write_text("input.txt", "tiny agent workspace")

        runner = CommandRunner(
            workspace,
            allowed_executables={Path(sys.executable).name},
            max_output_chars=500,
        )
        result = runner.run([sys.executable, "work/check.py"], timeout_seconds=2)
        print("command:", result)
        print("files:", workspace.list_files())
        print("artifact:", workspace.read_text("artifacts/result.txt"))


if __name__ == "__main__":
    main()
