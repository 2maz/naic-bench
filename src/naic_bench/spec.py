from __future__ import annotations

from pathlib import Path
import subprocess
import logging
import os
import yaml
from pydantic import BaseModel, Field, computed_field, SkipValidation
from pydantic_settings import BaseSettings
from typing import Any
from typing_extensions import Annotated
import re
import math
import platform

from naic_bench.package_manager import PackageManager
from naic_bench.config import Config

logger = logging.getLogger(__name__)

BENCHMARK_SPEC_SUFFIX = ".yaml"

class Repository(BaseModel):
    url: str
    branch: str = Field(default=None)
    commit: str | None = Field(default=None)

    def clone(self, workdir: Path | str, name: str | None = None):
        cmd = ["git", "clone"]
        if self.branch:
            cmd += ["-b", self.branch]
        cmd += [self.url]

        if name is None:
            name = Path(self.url).stem

        repo_dir = str(Path(workdir) / name)
        cmd += [ repo_dir ]

        subprocess.run(cmd)

        if self.commit:
            logger.info(f"Setting repo={repo_dir} to {self.commit}")
            subprocess.Popen(["git", "reset", "--hard", self.commit], cwd=repo_dir)

class VirtualEnv(BaseModel):
    python_path: str
    path: Path

    @computed_field
    @property
    def name(self) -> str:
        return self.path.name

class Metric(BaseModel):
    name: str
    pattern: str
    split_by: str | None = Field(default=None)
    match_group_index: int = Field(default=0)


class BatchSize(BaseModel):
    # batch_size for 1GB
    size_1gb: float
    multiple_gpu_scaling_factor: float = Field(default=1.0)

    apply_via: str = Field(default="--batch-size")

    @computed_field
    @property
    def device_memory_in_gb(self) -> int:
        if "GPU_SIZE_IN_GB" not in os.environ:
            from slurm_monitor.utils.system_info import SystemInfo

            si = SystemInfo()
            gpu_size_in_gb = int(si.gpu_info.memory_total / 1024**3)
        else:
            gpu_size_in_gb = int(os.environ["GPU_SIZE_IN_GB"])

        return gpu_size_in_gb

    def estimate(self, gpu_count: int = 0, device_type: str | None = None):
        if device_type == 'cpu':
            if gpu_count != 0:
                raise ValueError("If device type is cpu, then gpu_count must be 0")

            device_memory_in_gb = 24
        else:
            device_memory_in_gb = self.device_memory_in_gb

        batch_size = self.size_1gb * device_memory_in_gb
        if gpu_count > 1:
            batch_size = 2*self.multiple_gpu_scaling_factor

        if device_type:
            # vendor specific corrections (heuristic)
            if device_type == 'xpu':
                batch_size *= 0.85

        return math.ceil(batch_size)

class Report(BaseModel):
    benchmark: str
    variant: str

    start_time: int
    end_time: int

    exit_code: int = Field(default=0)
    slurm_job_id: int = Field(default=0)

    device_type: str
    gpu_model: str | None = Field(default=None)
    gpu_count: int
    metrics: dict[str, float]

    @computed_field
    @property
    def node(self) -> str:
        return platform.node()

class BenchmarkSpec(BaseSettings):
    name: str
    variant: str
    command: str
    command_distributed: str
    base_dir: str

    repo: Repository

    # list of os dependencies, by identifier of package manager, e.g. 'apt', 'dnf'
    osdeps: dict[PackageManager.Identifier, list[str]] = Field(default={})
    prepare: dict[str, list[str]] = Field(default={})
    metrics: dict[str, Metric] = Field(default={})

    environment: dict[str, str | int] = Field(default={})
    batch_size: BatchSize
    arguments: dict[str, Annotated[Any, SkipValidation]] = Field(default={})

    data_dir: str | None = Field(default=None)

    @computed_field
    @property
    def identifier(self) -> str:
        name = self.name.replace('/','_')
        return f"{name}_{self.variant}"

    def expand_placeholders(self, *args, **kwargs):
        updated_arguments = {}
        for k,v in kwargs.items():
            pattern = "{{" + f"{k}" + "(:([<=>]+)(.*))?}}"

            for argument_name, argument_value in self.arguments.items():
                if argument_value is None or type(argument_value) is not str:
                    updated_arguments[argument_name] = argument_value
                    continue
                else:
                    m = re.match(pattern, argument_value)
                    if m and m.groups()[1] is not None:
                        operator = m.groups()[1]
                        rhs = m.groups()[2]
                        if '.' in rhs:
                            rhs = float(rhs)
                        else:
                            rhs = int(rhs)

                        if operator == "<=":
                            v = min(v, rhs)
                        elif operator == ">=":
                            v = max(v, rhs)

                    updated_arguments[argument_name] = re.sub(pattern, str(v), argument_value)

            self.command = re.sub(pattern, str(v), self.command)
            self.command_distributed = re.sub(pattern, str(v), self.command_distributed)
            self.arguments = updated_arguments

    def device_arguments(self, device_type: str | None = None):
        extra_args = ""
        if not device_type:
            device_type = "cpu"
        elif device_type == "rocm":
            logger.info("gpu_argument: rocm -> use as 'cuda' in torch")
            device_type = "cuda"
        # enforce autocast for xpu (for nvidia this is not always useful it seems)
        elif device_type == "xpu":
            extra_args = "--autocast"

        return f"--device-type {device_type} {extra_args}".strip()

    def get_command(self, *,
                    gpu_count: int = 0,
                    device_type: str = "cpu"
        ):
        cmd = self.command.strip()
        for argument_name, argument_value in self.arguments.items():
            if argument_value is not None:
                cmd += f" --{argument_name} {argument_value}"
            else:
                cmd += f" --{argument_name}"

        # Required interface "--device-type <device-type>"
        cmd += f" {self.device_arguments(device_type=device_type)}"
        cmd += f" {self.batch_size.apply_via} {self.batch_size.estimate(gpu_count=gpu_count, device_type=device_type)}"
        return cmd

    def get_prepare(self, category: str) -> str:
        """
        Retrieve the list of preparation scripts that need to be run
        """
        return self.prepare.get(category, [])

    def extract_metrics(self, output: list[str]):
        metrics = {}
        for metric in self.metrics.values():
            value = None
            for i, line in enumerate(output):
                for m in re.finditer(metric.pattern, line):
                    if metric.split_by is not None:
                        value = float(m.group().split(metric.split_by)[metric.match_group_index])
                    else:
                        value = float(m.groups()[metric.match_group_index])
            metrics[metric.name] = value
        return metrics

    @computed_field
    @property
    def temp_dir(self) -> Path:
        temp_dir = Config.output_base_dir / f"{self.identifier}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    @classmethod
    def load(cls, config_filename: Path | str, data_dir: Path | str):
        benchmark_specs = {}
        with open(config_filename, 'r') as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)

        for framework, benchmarks in data.items():
            if framework not in benchmark_specs:
                benchmark_specs[framework] = {}

            for benchmark_name, config in benchmarks.items():
                if benchmark_name not in benchmark_specs[framework]:
                    benchmark_specs[framework][benchmark_name] = {}

                env = {}
                if 'environment' in config:
                    env = config['environment']

                missing_fields = []
                for f in ['command', 'repo', 'metrics']:
                    if f not in config:
                        missing_fields.append(f)

                if missing_fields:
                    raise RuntimeError(f"Fields '{','.join(missing_fields)}' missing in run configuration of {benchmark_name}")

                command = config['command']
                command_distributed = config['command_distributed']

                repo = Repository(**config['repo'])
                metrics = {}
                for metric_name, metric_spec in config['metrics'].items():
                    value = metric_spec.copy()
                    value['name'] = metric_name

                    metrics[metric_name] = Metric(**value)

                if 'variants' not in config:
                    raise RuntimeError(f"No 'variants' found for {benchmark_name}")

                for variant, run_config in config['variants'].items():
                    if 'environment' not in run_config:
                        run_config['environment'] = env

                    if 'prepare' in config:
                        prepare = config['prepare']
                        for k, v in prepare.items():
                            if type(v) is str:
                                prepare[k] = [v]
                        run_config['prepare'] = prepare

                    run_config['name'] = benchmark_name
                    run_config['variant'] = variant
                    run_config['command'] = command
                    run_config['command_distributed'] = command_distributed
                    run_config['repo'] = repo
                    run_config['metrics'] = metrics

                    bc = BenchmarkSpec(**run_config)
                    bc.expand_placeholders(
                            DATA_DIR=data_dir,
                            TMP_DIR=str(bc.temp_dir)
                    )
                    bc.data_dir = data_dir
                    benchmark_specs[framework][benchmark_name][variant] = bc
            return benchmark_specs

    @classmethod
    def all_as_list(cls, confd_dir: Path | str, data_dir: Path | str) -> dict[str, BenchmarkSpec]:
        specs = []
        framework_benchmark_specs = cls.load_all(confd_dir=confd_dir, data_dir=data_dir)
        for framework, benchmark_specs in framework_benchmark_specs.items():
            for benchmark_name, variants in benchmark_specs.items():
                for variant, benchmark_spec in variants.items():
                    specs.append([framework, benchmark_name, variant, benchmark_spec])
        return specs

    @classmethod
    def load_all(cls, confd_dir: Path | str, data_dir: Path | str) -> dict[str, BenchmarkSpec]:
        confd_dir = Path(confd_dir)

        if not confd_dir.exists():
            raise FileNotFoundError(f"BenchmarkSpec.load_all: could not find {confd_dir}")

        benchmark_specs = {}
        run_configs = [x for x in confd_dir.glob(f"*{BENCHMARK_SPEC_SUFFIX}")]

        for config in run_configs:
            loaded_specs = cls.load(config, data_dir=data_dir)
            for framework, benchmarks in loaded_specs.items():
                if framework in benchmark_specs:
                    benchmark_specs[framework].update(benchmarks)
                else:
                    benchmark_specs[framework] = benchmarks
        return benchmark_specs

    def git_target_dir(self, prefix_path: Path | str):
        url_txt = re.sub(r"[/(&:,;. ]",'_', self.repo.url)
        if self.repo.branch:
            branch_txt = re.sub(r"[/(&:,;. ]",'_', self.repo.branch)
            url_txt += f"__{branch_txt}"

        return Path(prefix_path) / url_txt
