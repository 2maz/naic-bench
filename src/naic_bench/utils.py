from pathlib import Path
import subprocess
import logging
import os
import yaml
from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
import tempfile
import re
import math
import platform
import site
import sys
import time
import datetime as dt

logger = logging.getLogger(__name__)

def run_command(command: list[str], env: dict[str, any] = {}, requires_root: bool = True):
    environ = os.environ.copy()
    for k,v in env.items():
        environ[k] = v

    result = subprocess.run(["id","-u"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environ)
    with_sudo = False
    user_id = int(result.stdout.decode("UTF-8").strip())
    if user_id != 0 and requires_root:
        logger.info(f"User ({user_id=}) requires to run command as sudo")
        with_sudo = True
        cmd = ["sudo"] + command
    else:
        cmd = command

    result = subprocess.run(cmd, stdout=subprocess.PIPE, env=environ)
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

