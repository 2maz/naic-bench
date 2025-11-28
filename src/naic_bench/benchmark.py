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

from naic_bench.spec import (
    Repository,
    VirtualEnv,
    Metric,
    BatchSize,
    Report,
    BenchmarkRunConfig
)

logger = logging.getLogger(__name__)

class BenchmarkRunner:
    benchmarks: dict[str, any]

    def __init__(self, *,
            data_dir: Path | str,
            benchmarks_dir: Path | str,
            confd_dir: Path | str
            ):
        self.data_dir = Path(data_dir)
        self.benchmarks_dir = Path(benchmarks_dir)
        self.confd_dir = Path(confd_dir)

        self.benchmarks = {}

    def load(self, config_filename: Path | str):
        with open(config_filename, 'r') as f:
            data = yaml.load(f, Loader=yaml.SafeLoader)

        for framework, benchmarks in data.items():
            if not framework in self.benchmarks:
                self.benchmarks[framework] = {}

            for benchmark_name, config in benchmarks.items():
                if not benchmark_name in self.benchmarks[framework]:
                    self.benchmarks[framework][benchmark_name] = {}

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
                repo = Repository(**config['repo'])
                metrics = {}
                for metric_name, metric_spec in config['metrics'].items():
                    value = metric_spec.copy()
                    value['name'] = metric_name

                    metrics[metric_name] = Metric(**value)

                if not 'variants' in config:
                    raise RuntimeError(f"No 'variants' found for {benchmark_name}")

                for variant, run_config in config['variants'].items():
                    if 'environment' not in run_config:
                        run_config['environment'] = env

                    run_config['name'] = benchmark_name
                    run_config['variant'] = variant
                    run_config['command'] = command
                    run_config['repo'] = repo
                    run_config['metrics'] = metrics

                    bc = BenchmarkRunConfig(**run_config)
                    bc.expand_placeholders(
                            DATA_DIR=self.data_dir,
                            TMP_DIR=str(bc.temp_dir)
                    )
                    self.benchmarks[framework][benchmark_name][variant] = bc

    def load_all(self):
        run_configs = [x for x in self.confd_dir.glob("*.run.yaml")]
        for config in run_configs:
            self.load(config)

    def prepare_venv(self, benchmark_name: str, workdir: Path | str) -> str:
        """
        Prepare venv and return python path setting
        """
        venv_name = f"venv-{benchmark_name}-{platform.machine()}"

        # plain execution of the benchmark
        result = subprocess.run(["which", "python"], stdout=subprocess.PIPE)
        python_path = result.stdout.decode("UTF-8").strip()
        version = '.'.join(platform.python_version_tuple()[:2])
        site_packages = "lib/python" + version + "/site-packages"

        python_site_packages = python_path.replace(r"bin/python", site_packages)
        python_path = f"{Path(venv_name).resolve()}/{site_packages}:{python_site_packages}"
        venv = VirtualEnv(name=venv_name, python_path=python_path)

        if not Path(venv_name).exists():
            subprocess.run(["python3", "-m", "venv", venv_name],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
            
            requirements_txt = workdir / "requirements.txt"
            if requirements_txt.exists():
                subprocess.run(f". {venv_name}/bin/activate; PYTHONPATH={venv.python_path} pip install -r {requirements_txt}", shell=True)

        return venv


    def execute(self,
            framework: str,
            name: str,
            variant: str,
            device_type: str = "cpu",
            gpu_count: int = 1,
            timeout_in_s: int = 1200):
        config = self.benchmarks[framework][name][variant]
        config.expand_placeholders(GPU_COUNT=gpu_count)

        workdir = self.benchmarks_dir / config.base_dir

        cmd = config.get_command(device_type=device_type, gpu_count=gpu_count)
        logger.info(f"Execute: {cmd} in {workdir}")

        venv = self.prepare_venv(benchmark_name=name, workdir=workdir)

        #env = os.environ.copy()
        #venv_path = Path(venv_name) / "lib" / f"python{version}" / "site-packages"
        #if 'PYTHONPATH' in env:
        #    env["PYTHONPATH"] = f"{venv_path}:{env['PYTHONPATH']}"
        #else:
        #    env["PYTHONPATH"] = f"{venv_path}"

        metrics = {}

        stdout = []
        stderr = []
        start_time = dt.datetime.now(tz=dt.timezone.utc)
        with subprocess.Popen(
                    f". {venv.name}/bin/activate; cd {workdir}; PYTHONPATH={venv.python_path} {cmd}",
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ) as process:

            stdout_iter = iter(process.stdout)
            stderr_iter = iter(process.stderr)

            while process.poll() is None:
                try:
                    stdout_line = next(stdout_iter)
                    if stdout_line:
                        output_line = stdout_line.decode("UTF-8").strip()
                        stdout.append(output_line)
                        print(output_line, flush=True, file=sys.stdout)
                except StopIteration:
                    pass

                try:
                    stderr_line = next(stderr_iter)
                    if stderr_line:
                        output_line = stderr_line.decode("UTF-8").strip()
                        stderr.append(output_line)
                        print(output_line, flush=True, file=sys.stderr)
                except StopIteration:
                    pass

                time.sleep(0.1)
            
            end_time = dt.datetime.now(tz=dt.timezone.utc)
            # Get remaining lines
            for line in process.stdout:
                output_line = line.decode("UTF-8").strip()
                stdout.append(output_line)
                print(output_line, flush=True, file=sys.stdout)

            for line in process.stderr:
                output_line = line.decode("UTF-8").strip()
                stderr.append(output_line)
                print(output_line, flush=True, file=sys.stderr)

            if process.returncode != 0:
                error_details = '\n'.join(stderr)
                raise RuntimeError(f"Benchmark {name=} {variant=} failed -- details: {error_details}")
       
        with open(config.temp_dir / "stdout.log", "w") as f:
            for line in stdout:
                f.write(f"{line}\n")

        with open(config.temp_dir / "stderr.log", "w") as f:
            for line in stderr:
                f.write(f"{line}\n")
       
        
        gpu_model = "Unknown"
        try:
            from slurm_monitor.utils.system_info import SystemInfo
            si = SystemInfo()
            gpu_model = si.gpu_info.model
        except LoadError:
            logger.warning("slurm_monitor not available: system info could not be extracted"
            pass

        with open(config.temp_dir / "system_info.yaml", "w") as f:
            data = dict(si)
            
            import torch
            data['software'] = { 'torch': torch.__version__ }
            yaml.dump(data, f)

        report = Report(
            benchmark=name,
            variant=variant,
            start_time=int(start_time.timestamp()),
            end_time=int(end_time.timestamp()),
            # slurm_job_id=0
            device_type=device_type,
            gpu_model=gpu_model,
            gpu_count=gpu_count,
            metrics=config.extract_metrics(stdout + stderr)
        )

        with open(config.temp_dir / "report.yaml", "w") as f:
            yaml.dump(report.model_dump(), f)

        return report
