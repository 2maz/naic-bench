from rich import print as print
from docker import from_env
from docker.errors import APIError, NotFound
import logging
from logging import getLogger

from pathlib import Path
import platform
import os
import re
import subprocess
import sys

from naic_bench.utils.command import Command
import naic_bench.utils.gpus as gpus

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

# Relate device_type to startup options
# Dockerfile.<devicetype>
DOCKER_DEVICE_TYPE_ARGS = {
    'nvidia': [],
    'nvidia-volta': [],
    'habana': [
        "--runtime", "habana",
        "-e", "OMPI_MCA_btl_vader_single_copy_mechanism=none",
        "--cap-add", "sys_nice",
        "--net", "host",
        "--ipc", "host",
        "-v", "var-log-habana:/var/log/habana_logs",
    ],
    'rocm': [
        "--cap-add","SYS_PTRACE",
        "--security-opt", "seccomp=unconfined"
        "--device", "/dev/kfd",
        "--device", "/dev/dri"
        "--group-add", "video",
        "--ipc", "host"
    ],
    'xpu': [
        "--device", "/dev/dri",
        "-v", "/dev/dri/by-path:/dev/dri/by-path",
        "--ipc","host",
    ]
}

class Docker:
    def __init__(self):
        self.client = from_env()

    @classmethod
    def runtimes(cls):
        result = Command.run(["docker", "info"])
        for line in result.splitlines():
            m = re.search(r"Runtimes: (.*)", line)
            if m:
                return m.groups()[0].split(' ')

        return False

    @classmethod
    def default_args(cls,
            cpus: int = os.cpu_count(),
            shm_size: str = '16g') -> list[str]:
        args = [
            "--rm",
            "--shm-size", shm_size,
            "--cpus", str(cpus)
        ]

        if "SLURM_JOB_ID" in os.environ:
            args += [
                "-e", f"SLURM_JOB_ID={os.environ['SLURM_JOB_ID']}"
            ]

        return args

    @classmethod
    def device_setup_args(cls, device_type: str) -> list[str]:
        env = os.environ.copy()

        docker_args = []
        if device_type == "cpu":
            return docker_args

        if "CUDA_VISIBLE_DEVICES" in env:
            docker_args += ["-e", f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}"]
            if device_type.startswith("nvidia"):
                if 'nvidia' in cls.runtimes():
                    docker_args += ["--runtime", "nvidia"]
                else:
                    uuids = gpus.Nvidia.device_uuids_nvidia()
                    device_list = f"device={','.join(uuids)}"
                    docker_args += ["--gpus", f'"{device_list}"']
            else:
                docker_args += ["--gpus", "all"]
        elif device_type not in ["xpu", "habana"]:
            docker_args += ["--gpus", "all"]

        if "HABANA_VISIBLE_DEVICES" in env:
            docker_args += ["-e", f"HABANA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}"]

        return docker_args

    @classmethod
    def device_specific_args(cls, device_type: str) -> list[str]:
        """
        Get special docker argument when a docker for a particular device type is requested
        """

        docker_args = cls.device_setup_args(device_type)
        available_types = sorted(DOCKER_DEVICE_TYPE_ARGS.keys())
        if device_type in available_types:
            docker_args += DOCKER_DEVICE_TYPE_ARGS[device_type]
            return docker_args

        for docker_type in sorted(DOCKER_DEVICE_TYPE_ARGS.keys()):
            if device_type.startswith(docker_type):
                docker_args += DOCKER_DEVICE_TYPE_ARGS[device_type]

        return docker_args

    def container(self, name: str):
        """
        Retrieve container or none if is does not exist
        """
        for x in self.client.containers.list(all=True, filters={'name': name}):
            if x.name == name:
                return x

        return None

    def image(self, name: str):
        for x in self.client.images.list(all=True):
            for tag in x.tags:
                if tag.startswith(name):
                    return x

        return None

    @classmethod
    def container_uuid(cls, name: str) -> str | None:
        """
        Get the container uuid or None if it does not exist
        """
        uuid = Command.run(["docker", "ps", "-q", "--filter", f"name={name}"])
        return uuid

    @classmethod
    def container_running(cls, name: str) -> str | None:
        """
        Get the container uuid or None if it does not exist
        """
        result = Command.run(["docker", "inspect", "-f", "{{.State.Running}}", name])
        return result == "true"

    @classmethod
    def image_name(cls, device_type: str) -> str:
        return f"naic-bench/{device_type}-{platform.machine()}"

    @classmethod
    def dockerfile(cls, device_type: str) -> Path:
        return Path(__file__).parent.parent / "resources" / "docker" / f"Dockerfile.{device_type}"

    @classmethod
    def run(cls,
            data_dir: Path | str,
            cpus: int,
            shm_size: int,
            rebuild: bool,
            restart: bool,
            device_type: str,
            container_name: str,
            exec_args: list[str]
    ):
        image_name = Docker.image_name(device_type=device_type)
        dockerfile = Docker.dockerfile(device_type=device_type)

        if not dockerfile.exists():
            raise RuntimeError(f"Dockerfile {dockerfile} not found")

        build = False
        start = False

        docker = Docker()
        image = docker.image(image_name)

        if container_name is None:
            container_name = f"naic-bench-{device_type}"

        container = docker.container(container_name)

        if not image:
            build = True
            start = True
        elif not container:
            start = True
        elif rebuild:
            logger.info(f"docker: rebuild requested - stopping and removing container '{container.name}'")
            container.stop()
            try:
                container.remove()
            except (NotFound, APIError):
                pass
            build = True
            start = True
        elif restart:
            logger.info(f"docker: restart requested - stopping and removing container '{container.name}'")
            container.stop()
            try:
                container.remove()
            except (NotFound, APIError):
                pass
            start = True
        elif container.status == "running":
            print(f"Docker container '{container_name}' exists - reusing")
        elif not container.status == "running":
            print(f"Container {container_name} exists - but status={container.status}")
            print(f"Please remove the container first: docker rm {container_name} or call with --restart")
            sys.exit(10)

        Command.find(command="docker", do_throw=True)

        if build:
            Command.run_with_progress(["docker", "build", "--no-cache", "-t", image_name, "-f", str(dockerfile), dockerfile.parent])

        if start:
            # start the container with the correct mounted volumes
            docker_run = ["docker", "run", "-d", "--name", container_name]
            if data_dir:
                docker_run += ["-v", f"{Path(data_dir).resolve()}:/data"]
            docker_run += Docker.default_args(cpus=cpus, shm_size=shm_size)

            docker_run += Docker.device_specific_args(device_type)
            docker_run += [image_name]
            docker_run += ["tail", "-f", "/dev/null"]

            Command.run_with_progress(docker_run)


        container = docker.container(container_name)
        mounts = container.attrs["Mounts"]
        if mounts:
            print("    mounted:")
            [print(f"     - {x['Source']}:{x['Destination']}") for x in mounts]
        print()

        if exec_args:
            container = docker.container(container_name)
            mounts = container.attrs["Mounts"]
            if mounts:
                print("    mounted:")
                [print(f"     - {x['Source']}:{x['Destination']}") for x in mounts]
            print()

            docker_exec = ["docker", "exec", container_name]
            docker_exec += exec_args
            Command.run_with_progress(docker_exec)
        else:
            print("No command provide to execute in docker: if required append '-- <command>'")
            docker_exec = ["docker", "exec", "-it", container_name, "bash" ]
            print(f"Entering container '{container_name}' in interactive mode (quit with CTRL-D)")
            subprocess.run(' '.join(docker_exec), shell=True)
