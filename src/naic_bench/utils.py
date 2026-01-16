import subprocess
import logging
import os
import selectors
import shutil
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

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
                          requires_root: bool = False):
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

        stdout = []
        stderr = []
        with subprocess.Popen(
                    cmd,
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

                time.sleep(0.1)

            # Get remaining lines
            for line in process.stdout:
                output_line = line.decode("UTF-8").rstrip()
                stdout.append(output_line)
                print(output_line, flush=True, file=sys.stdout)

            for line in process.stderr:
                output_line = line.decode("UTF-8").rstrip()
                stderr.append(output_line)
                print(output_line, flush=True, file=sys.stderr)

            if process.returncode != 0:
                error_details = '\n'.join(stderr)
                raise RuntimeError(f"Execution of '{' '.join(cmd)}' failed -- details: {error_details}")

            return stdout

def pipe_has_data(pipe, selector) -> bool:
    """Check if the pipe has data available for reading (Linux/macOS)."""
    events = selector.select(timeout=0)  # Non-blocking check
    for key, _ in events:
        if key.fileobj == pipe:
            return True
    return False
