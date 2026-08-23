"""Stage 07 example 9: process timeout as an isolation boundary, not a full sandbox.

The command is fixed by application code. This example does not expose an
arbitrary shell tool to a model.
"""

import asyncio
import sys


async def main() -> None:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import time; print('child started', flush=True); time.sleep(10)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=0.1)
        print(stdout.decode())
    except asyncio.TimeoutError:
        # Python 3.10 exposes asyncio.TimeoutError here; newer Python aliases it
        # to the built-in TimeoutError. Using the asyncio name keeps this demo
        # compatible with the project's supported Python versions.
        process.terminate()
        await process.wait()
        print("Child process exceeded the deadline and was terminated.")

    print(
        "A subprocess gives a separately terminable process boundary, but it is NOT "
        "a security sandbox by itself. Real untrusted execution also needs OS/container/VM "
        "permissions, filesystem/network restrictions, resource limits, and auditing."
    )


if __name__ == "__main__":
    asyncio.run(main())
