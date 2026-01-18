from rich import print as print
from argparse import ArgumentParser
from docker import from_env
import logging
from logging import basicConfig, getLogger

from naic_bench.utils import Command
from pathlib import Path
import platform
import os
import sys


logger = getLogger(__name__)
logger.setLevel(logging.INFO)

#        $DOCKER_CUDA_SETUP \
#        $DOCKER_VOLUMES \
#        $DOCKER_ENVIRONMENT \
#"--rm",
# "--shm-size","1024g" \
# "--cpus","{{CPU_COUNT}}",

# Dockerfile.<devicetype>

DOCKER_DEFAULT_ARGS = [
  #"--rm",
  "--shm-size", "64g",
  #"--cpus, "{{CPU_COUNT}}"
]
DOCKER_DEVICE_TYPE_ARGS = {
    'nvidia': [],
    'habana': [
        "--runtime", "habana",
        "-e", "OMPI_MCA_btl_vader_single_copy_mechanism=none",
        "--cap-add", "sys_nice",
        "--net", "host"

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

def device_uuids_nvidia():
    result = Command.run(["nvidia-smi","--query-gpu=uuid", "--format=csv,noheader"])
    return result.splitlines()

class Docker:
    def __init__(self):
        self.client = from_env()

    @classmethod
    def device_setup_args(cls, device_type: str) -> list[str]:
        env = os.environ.copy()

        docker_args = []
        if device_type == "cpu":
            return docker_args

        if "CUDA_VISIBLE_DEVICES" in env:
            if device_type.startswith("nvidia"):
                uuids = device_uuids_nvidia()
                docker_args = ["--gpus", f"device='\"{','.join(uuids)}\"'"]
            else:
                docker_args += ["-e", f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']}"]
        elif device_type not in ["xpu"]:
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

def run():
    basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    parser = ArgumentParser(description="naic-bench in docker")
    parser.add_argument("--rebuild", action="store_true", default=False)
    parser.add_argument("--restart", action="store_true", default=False)

    parser.add_argument("--device-type", required=True, type=str, default=None)
    parser.add_argument("--container", required=True, type=str, default=None)
    parser.add_argument("--data-dir", type=str, default=None)

    args, options = parser.parse_known_args()

    exec_args = []
    if options and options[0] == "--":
        exec_args = options[1:]

    device_type = args.device_type

    image_name = f"naic-bench/{device_type}-{platform.machine()}"
    dockerfile = Path(__file__).parent.parent / "resources" / "docker" / f"Dockerfile.{device_type}"
    if not dockerfile.exists():
        raise RuntimeError(f"Dockerfile {dockerfile} not found")

    build = False
    start = False

    docker = Docker()
    image = docker.image(image_name)
    container = docker.container(args.container)

    if not image:
        build = True
        start = True
    elif not container:
        start = True
    elif args.rebuild:
        logger.info(f"docker: rebuild requested - stopping and removing container '{container.name}'")
        container.stop()
        container.remove()
        build = True
        start = True
    elif args.restart:
        logger.info(f"docker: restart requested - stopping and removing container '{container.name}'")
        container.stop()
        container.remove()
        start = True
    elif container.status == "running":
        print(f"Docker container '{args.container}' exists - reusing")
    elif not container.status == "running":
        print(f"Container {args.container} exists - but status={container.status}")
        print(f"Please remove the container first: docker rm {args.container} or call with --restart")
        sys.exit(10)

    if build:
        Command.run_with_progress(["docker", "build", "--no-cache", "-t", image_name, "-f", str(dockerfile), "."])

    if start:
        # start the container with the correct mounted volumes
        docker_run = ["docker", "run", "-d", "--name", args.container]
        if args.data_dir:
            docker_run += ["-v", f"{Path(args.data_dir).resolve()}:/data"]
        docker_run += DOCKER_DEFAULT_ARGS

        docker_run += Docker.device_specific_args(device_type)
        docker_run += [image_name]
        docker_run += ["tail", "-f", "/dev/null"]

        Command.run_with_progress(docker_run)


    if exec_args:
        container = docker.container(args.container)
        mounts = container.attrs["Mounts"]
        if mounts:
            print("    mounted:")
            [print(f"     - {x['Source']}:{x['Destination']}") for x in mounts]
        print()

        docker_exec = ["docker", "exec", args.container]
        docker_exec += exec_args
        Command.run_with_progress(docker_exec)
    else:
        print("No command provide to execute in docker: if required append '-- <command>'")

if __name__ == "__main__":
    run()
