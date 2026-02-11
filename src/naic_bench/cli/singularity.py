from rich import print as print
from argparse import ArgumentParser

import logging
from logging import getLogger

from naic_bench.cli.base import BaseParser
from naic_bench.singularity import Singularity

logger = getLogger(__name__)
logger.setLevel(logging.INFO)

class SingularityParser(BaseParser):
    def __init__(self, parser: ArgumentParser):
        super().__init__(parser=parser)

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


    def execute(self, args, options):
        super().execute(args, options)

        exec_args = options
        if options and options[0] == "--":
            exec_args = options[1:]

        Singularity.run(
             image_name=args.sif_image,
             instance_name=args.instance_name,
             device_type=args.device_type,
             data_dir=args.data_dir,
             exec_args=exec_args,
             docker_image=args.docker_image,
             rebuild=args.rebuild,
             restart=args.restart,
             build_only=args.build_only
        )
