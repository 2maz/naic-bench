import datetime as dt
import subprocess
import logging
import os
import psutil
import selectors
import signal
import shutil
import sys
import time
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ExecutionResult(BaseModel):
    pid: int
    returncode: int

    stdout: list[str] | None
    stderr: list[str] | None
    start_time: dt.datetime
    end_time: dt.datetime

class Command:
    @classmethod
    def find(cls, *, command, hints: list[str] | None = None, do_throw = True ) -> str | None:
        search_paths = []
        if hints:
            for x in hints:
                search_paths.append(Path(x) / command)

        # default
        search_paths.append(Path(command))

        for search_path in search_paths:
            path = shutil.which(cmd=search_path)
            if path:
                return path
        if do_throw:
            raise RuntimeError(f"Command: could not find '{command}' on this system")

        return None

    @classmethod
    def run(cls, command: list[str], env: dict[str, str | int | float] = {}, requires_root: bool = False):
        environ = os.environ.copy()
        for k,v in env.items():
            environ[k] = v

        result = subprocess.run(["id","-u"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environ)
        user_id = int(result.stdout.decode("UTF-8").strip())
        if user_id != 0 and requires_root:
            logger.info(f"User ({user_id=}) requires to run command as sudo")
            cmd = ["sudo"] + command
        else:
            cmd = command

        logger.info(f"Trying to run {cmd}")
        result = subprocess.run(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=environ)

        if result.returncode != 0:
            error_msg = result.stderr.decode("UTF-8").strip()
            raise RuntimeError(f"Failed to execute: {cmd} - {error_msg}")

        return result.stdout.decode("UTF-8").strip()

    @classmethod
    def run_with_progress(cls,
                          command: list[str],
                          env: dict[str, any] = {},
                          shell: bool = False,
                          requires_root: bool = False,
                          raise_on_error: bool = True) -> ExecutionResult:
        environ = os.environ.copy()
        for k,v in env.items():
            environ[k] = v

        if type(command) is str and not shell:
            raise ValueError("Command.run_with_progress: "
                             "command as string, requires shell=True")

        result = subprocess.run(["id","-u"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environ)
        user_id = int(result.stdout.decode("UTF-8").strip())

        if user_id != 0 and requires_root:
            logger.info(f"User ({user_id=}) requires to run command as sudo")
            cmd = ["sudo"] + command
        else:
            cmd = command

        start_time = dt.datetime.now(tz=dt.timezone.utc)

        stdout = []
        stderr = []

        if shell and type(cmd) is list[str]:
            cmd = ' '.join(cmd)

        with subprocess.Popen(
                    args=cmd,
                    shell=shell,
                    env=environ,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ) as process:

            os.set_blocking(process.stdout.fileno(), False)
            stdout_selector = selectors.DefaultSelector()
            stdout_selector.register(process.stdout, selectors.EVENT_READ)

            os.set_blocking(process.stderr.fileno(), False)
            stderr_selector = selectors.DefaultSelector()
            stderr_selector.register(process.stderr, selectors.EVENT_READ)

            while process.poll() is None:
                if pipe_has_data(process.stdout, stdout_selector):
                    stdout_line = process.stdout.readline()
                    if stdout_line:
                        output_line = stdout_line.decode("UTF-8").rstrip()
                        print(output_line, flush=True, file=sys.stdout)
                        stdout.append(output_line)

                if pipe_has_data(process.stderr, stderr_selector):
                    stderr_line = process.stderr.readline()
                    if stderr_line:
                        output_line = stderr_line.decode("UTF-8").rstrip()
                        print(output_line, flush=True, file=sys.stderr)
                        stderr.append(output_line)

                time.sleep(0.05)

            end_time = dt.datetime.now(tz=dt.timezone.utc)

            # Get remaining lines
            for line in process.stdout:
                output_line = line.decode("UTF-8").rstrip()
                stdout.append(output_line)
                print(output_line, flush=True, file=sys.stdout)

            for line in process.stderr:
                output_line = line.decode("UTF-8").rstrip()
                stderr.append(output_line)
                print(output_line, flush=True, file=sys.stderr)

            if raise_on_error and process.returncode != 0:
                error_details = '\n'.join(stderr)
                raise RuntimeError(f"Execution of '{' '.join(cmd)}' failed -- details: {error_details}")

            return ExecutionResult(
                       pid=process.pid,
                       returncode=process.returncode,
                       stdout=stdout,
                       stderr=stderr,
                       start_time=start_time,
                       end_time=end_time
                   )

def pipe_has_data(pipe, selector) -> bool:
    """Check if the pipe has data available for reading (Linux/macOS)."""
    events = selector.select(timeout=0)  # Non-blocking check
    for key, _ in events:
        if key.fileobj == pipe:
            return True
    return False

def find_confd() -> Path | None:
    hints = [
        Path() / "conf.d",
        Path(__file__).parent / "resources" / "conf.d"
    ]

    for hint in hints:
        if hint.exists():
            return hint

    return None
