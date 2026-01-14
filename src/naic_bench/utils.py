import subprocess
import logging
import os
import shutil
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
    def run(cls, command: list[str], env: dict[str, any] = {}, requires_root: bool = True):
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

        logger.info(f"Running {cmd}")
        result = subprocess.run(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=environ)

        if result.returncode != 0:
            error_msg = result.stderr.decode("UTF-8").strip()
            raise RuntimeError(f"Failed to execute: {cmd} - {error_msg}")

        return result.stdout.decode("UTF-8").strip()


def pipe_has_data(pipe, selector) -> bool:
    """Check if the pipe has data available for reading (Linux/macOS)."""
    events = selector.select(timeout=0)  # Non-blocking check
    for key, _ in events:
        if key.fileobj == pipe:
            return True
    return False
