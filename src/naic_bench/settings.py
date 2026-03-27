from __future__ import annotations
import logging
import os
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import sys

logger = logging.getLogger(__name__)

class ContainerConfig(BaseModel):
    image_dir: Path = Field(default=Path("./sif-images"))
    workspace_dir: Path = Field(default=Path("/naic-workspace"),
            description="Containers folder to consider as workspace directory")

class Config(BaseSettings):
    # export NAIC_BENCH_ENVFILE='.dev.env' in order to change the default
    # .env file that is being loaded
    model_config = SettingsConfigDict(
                    env_file='.env',
                    env_nested_delimiter='__',
                    env_prefix='NAIC_BENCH__',
                    extra='ignore'
                )

    output_base_dir: Path = Path(tempfile.gettempdir()) / "naic-bench"
    docker: ContainerConfig = ContainerConfig(workspace_dir=Path("/naic-workspace"))
    sif: ContainerConfig = ContainerConfig(workspace_dir=Path("/naic-workspace/writeable"))
    workspace_dir: Path = Field(
                            default="naic-workspace",
                            description="Local folder that will be mounted as workspace in the container"
                          )

    @classmethod
    def get_instance(cls) -> Config:
        if not hasattr(cls, "_instance") or not cls._instance:
            raise RuntimeError(
                "Config: instance is not accessible. Please call Config.initialize() first."
            )

        return cls._instance

    @classmethod
    def initialize(cls, force: bool = False, env_file_required: bool = False, **kwargs) -> Config:
        if not force and hasattr(cls, "_instance") and cls._instance:
            return cls._instance

        env_file = None
        if "NAIC_BENCH_ENVFILE" in os.environ:
            env_file = os.environ["NAIC_BENCH_ENVFILE"]
            if not Path(env_file).exists():
                raise FileNotFoundError(
                    f"Config.initialize: could not find {env_file=} set via env NAIC_BENCH_ENVFILE"
                )

        if "--env-file" in sys.argv:
            idx = sys.argv.index("--env-file")
            env_file = sys.argv[idx + 1]

            if not Path(env_file).exists():
                raise FileNotFoundError(
                    f"Config.initialize: could not find {env_file=} provided via --env-file"
                )

        if env_file_required and not env_file:
            env_file = ".env"

        if env_file:
            logger.info(f"Config.initialize: loading {env_file=}")
            cls._instance = Config(_env_file=env_file, **kwargs)
        else:
            cls._instance = Config(**kwargs)

        return cls._instance

if __name__ == "__main__":
  config = Config.initialize()
  print(config)
