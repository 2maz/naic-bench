from rich import print as print
from pathlib import Path
import re
import subprocess

import logging
from logging import getLogger

from naic_bench.docker import Docker
from naic_bench.utils import Command, canonized_name

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

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
    def build(cls, device_type: str, sif_image: str, docker_image: str, rebuild_docker: bool = False):

        # First we require the docker image to be available / build
        dockerfile = Docker.dockerfile(device_type=device_type)

        if rebuild_docker:
            logger.info(f"Building docker image '{docker_image}' from '{dockerfile}'")
            Command.run_with_progress(["docker", "build", "--no-cache", "-t", docker_image, "-f", str(dockerfile), str(dockerfile.parent)])
        else:
            logger.info(f"Skipping building docker image '{docker_image}' from '{dockerfile}'")

        canonized_docker_name = canonized_name(docker_image)

        # Export the docker image to tar / archive
        logger.info(f"Exporting docker to '{canonized_docker_name}.tar'")
        Command.run_with_progress(["docker", "save", "-o", f"{canonized_docker_name}.tar", docker_image])

        # Convert archive to sif format
        logger.info(f"Creating singularity image {sif_image} from '{canonized_docker_name}.tar'")
        Command.run_with_progress(["singularity", "build", sif_image, f"docker-archive://{canonized_docker_name}.tar"])

    @classmethod
    def run(cls,
         data_dir: str,
         device_type: str | None = None,
         rebuild_docker: bool = False,
         rebuild_singularity: bool = False,
         restart: bool = False,
         image_name: str | None = None,
         exec_args: str | None = None,
         instance_name: str | None = None,
         docker_image: str | None = None,
         build_only: bool = False
    ):
        if not device_type:
            device_type = Docker.autodetect_device_type()

        if not docker_image:
            docker_image = Docker.image_name(device_type=device_type)

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
                rebuild_singularity = True

        if instance_running and (restart or rebuild_singularity):
            logger.info("singularity: restart requested")
            Singularity.stop(instance_name)
            start = True

        if rebuild_docker or rebuild_singularity:
            Singularity.build(
                    device_type=device_type,
                    docker_image=docker_image,
                    sif_image=image_name,
                    rebuild_docker=rebuild_docker
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
            singularity_exec = ["singularity", "exec", "--cwd", "/naic-workspace/writeable", f"instance://{instance_name}"] + exec_args
            Command.run_with_progress(singularity_exec)
        else:
            print("No command provided to execute in singularity: if required append '-- <command>'")
            singularity_cmd = ["singularity", "shell", f"instance://{instance_name}"]
            print(f"Entering instance '{instance_name}' in interactive mode (quit with CTRL-D)")
            subprocess.run(' '.join(singularity_cmd), shell=True)
