from rich import print as print
from argparse import ArgumentParser
from pathlib import Path
import re
import subprocess

import logging
from logging import basicConfig, getLogger

import naic_bench.cli.docker as cli_docker
from naic_bench.utils import Command

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

def run():
    basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    parser = ArgumentParser(description="naic-bench in singularity (derived from docker image)")
    parser.add_argument("--rebuild", action="store_true", default=False)
    parser.add_argument("--build-only", action="store_true", default=False,
            help="Build only the singularity (*.sif) image")
    parser.add_argument("--restart", action="store_true", default=False,
            help="Restart the singularity instance")

    parser.add_argument("--device-type", required=True, type=str, default=None)
    parser.add_argument("--sif-image",
        help="The singularity image name, default is 'naic-bench-<device-type>.sif'",
        required=False,
        type=str,
        default=None
    )
    parser.add_argument("--instance-name",
        help="The singularity instance name, default is 'naic-bench-<device-type>'",
        required=False,
        type=str,
        default=None
    )

    parser.add_argument("--docker-image",
        help="The docker image name, default is 'naic-bench/<device-type>-<arch>'",
        required=False,
        type=str,
        default=None
    )
    parser.add_argument("--data-dir", type=str, default=None)

    args, options = parser.parse_known_args()

    exec_args = options
    if options and options[0] == "--":
        exec_args = options[1:]

    _run(image_name=args.sif_image,
         instance_name=args.instance_name,
         device_type=args.device_type,
         data_dir=args.data_dir,
         exec_args=exec_args,
         docker_image=args.docker_image,
         rebuild=args.rebuild,
         restart=args.restart
    )

def canonized_name(name: str):
    return re.sub(r"[/:]",'-', name)

class Singularity:
    @classmethod
    def status(cls, instance_name, image_name: str | None) -> tuple[str, bool] | None:
        """
        :return tuple[str,bool] describing image name and whether an the instance
        """
        response = Command.run(["singularity", "instance", "list", instance_name])
        instance_running = False
        # check running instance and the associated image
        for line in response.splitlines():
            m = re.match(r"" + instance_name + r"\s+([0-9]+)\s+([0-9.]+)?\s+(.+)", line)
            if m:
                instance_image_name = m.groups()[2]
                if image_name and Path(image_name.resolve()) != instance_image_name:
                    raise RuntimeError("Instance {instance_name} is already used with image {image_name} "
                        " -- either change image name or align image name")
                image_name = instance_image_name
                instance_running = True
                return image_name, instance_running
        return image_name, False

    @classmethod
    def stop(cls, instance_name):
        logger.info(f"singularity: stopping instance '{instance_name}'")
        Command.run_with_progress(["singularity", "instance", "stop", instance_name])

    @classmethod
    def build(cls, device_type: str, docker_image: str, sif_image: str):

        # First we require the docker image to be available / build
        dockerfile = cli_docker.Docker.dockerfile(device_type=device_type)

        logger.info(f"Building docker image '{docker_image}' from '{dockerfile}'")
        Command.run_with_progress(["docker", "build", "--no-cache", "-t", docker_image, "-f", str(dockerfile), dockerfile.parent])

        canonized_docker_name = canonized_name(docker_image)

        # Export the docker image to tar / archive
        Command.run_with_progress(["docker", "save", "-o", f"{canonized_docker_name}.tar", docker_image])

        # Convert archive to sif format
        Command.run_with_progress(["singularity", "build", sif_image, f"docker-archive://{canonized_docker_name}.tar"])


def _run(device_type: str,
         data_dir: str,
         rebuild: bool = False,
         restart: bool = False,
         image_name: str | None = None,
         exec_args: str | None = None,
         instance_name: str | None = None,
         docker_image: str | None = None,
         build_only: bool = False
):
    if not docker_image:
        docker_image = cli_docker.Docker.image_name(device_type=device_type)

    if not instance_name:
        instance_name = f"{canonized_name(docker_image)}"

    image_name, instance_running = Singularity.status(instance_name=instance_name, image_name=image_name)
    if not image_name:
        image_name = f"{canonized_name(docker_image)}.sif"
    elif not image_name.endswith(".sif"):
        image_name += ".sif"

    start = False
    if not instance_running:
        start = True
        if not Path(image_name).exists():
            rebuild = True

    if instance_running and restart:
        logger.info("singularity: restart requested")
        Singularity.stop(instance_name)
        start = True

    if rebuild:
        Singularity.build(device_type=device_type,
                docker_image=docker_image,
                sif_image=image_name
        )

    if build_only:
        return

    if start:
        # start the container with the correct mounted volumes
        singularity_run = ["singularity", "instance", "start"]
        if data_dir:
            singularity_run += ["-B", f"{Path(data_dir).resolve()}:/data"]

        work_dir = Path("naic-workspace")
        work_dir.mkdir(parents=True, exist_ok=True)

        singularity_run += ["-B", f"{str(work_dir)}:/naic-workspace/writeable"]

        if device_type.startswith("nvidia"):
            singularity_run += [ "--nv"]

        singularity_run += [ str(Path(image_name).resolve()), instance_name]
        logger.info(f"Starting singularity instance: {singularity_run}")
        Command.run_with_progress(singularity_run)

    if exec_args:
        singularity_exec = ["singularity", "exec", f"instance://{instance_name}"] + exec_args
        Command.run_with_progress(singularity_exec)
    else:
        print("No command provided to execute in singularity: if required append '-- <command>'")
        singularity_cmd = ["singularity", "shell", f"instance://{instance_name}"]
        print(f"Entering instance '{instance_name}' in interactive mode (quit with CTRL-D)")
        subprocess.run(' '.join(singularity_cmd), shell=True)

if __name__ == "__main__":
    run()
