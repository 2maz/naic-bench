from rich import print as print
from pathlib import Path
import subprocess
import logging
import yaml
import platform
import site
from slurm_monitor.utils.system_info import SystemInfo

from naic_bench.utils import Command
from naic_bench.spec import (
        VirtualEnv,
        Report,
        BenchmarkSpec
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class BenchmarkRunner:
    benchmark_specs: dict[str, any]

    def __init__(self, *,
            data_dir: Path | str,
            benchmarks_dir: Path | str,
            confd_dir: Path | str
            ):
        self.data_dir = Path(data_dir)
        self.benchmarks_dir = Path(benchmarks_dir)
        self.confd_dir = Path(confd_dir)

        self.benchmark_specs = {}

        self.load_all()

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

        python_path = f"{python_path}:{':'.join(site.getsitepackages())}"
        venv = VirtualEnv(name=venv_name, python_path=python_path)

        if not Path(venv_name).exists():
            logger.info(f"BenchmarkRunner[{benchmark_name}]: preparing venv: {venv_name}")
            subprocess.run(["python3", "-m", "venv", venv_name],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

            requirements_txt = workdir / "requirements.txt"
            if requirements_txt.exists():
                subprocess.run(f". {venv_name}/bin/activate; PYTHONPATH={venv.python_path} pip install -r {requirements_txt}", shell=True)
        else:
            logger.info(f"BenchmarkRunner[{benchmark_name}]: venv: {venv_name} already exists")
        return venv

    def load_all(self):
        self.benchmark_specs = BenchmarkSpec.load_all(confd_dir=self.confd_dir, data_dir=self.data_dir)

    def execute(self,
            framework: str,
            name: str,
            variant: str,
            device_type: str = "cpu",
            gpu_count: int = 1,
            timeout_in_s: int = 1200):
        config = self.benchmark_specs[framework][name][variant]
        config.expand_placeholders(GPU_COUNT=gpu_count)

        clone_target_path = config.git_target_dir(self.benchmarks_dir)
        workdir = clone_target_path / config.base_dir

        cmd = config.get_command(device_type=device_type, gpu_count=gpu_count)
        logger.info(f"Execute: {cmd} in {workdir}")

        venv = self.prepare_venv(benchmark_name=name, workdir=workdir)

        logger.info(f"BenchmarkRunner.execute [{name}|{variant=}]: . {venv.name}/bin/activate; cd {workdir}; PYTHONPATH={venv.python_path} {cmd}")
        result = Command.run_with_progress(
                    [f". {venv.name}/bin/activate; cd {workdir}; PYTHONPATH={venv.python_path} {cmd}"],
                    shell=True
                 )

        with open(config.temp_dir / "stdout.log", "w") as f:
            for line in result.stdout:
                f.write(f"{line}\n")

        with open(config.temp_dir / "stderr.log", "w") as f:
            for line in result.stderr:
                f.write(f"{line}\n")

        si = SystemInfo()

        with open(config.temp_dir / "system_info.yaml", "w") as f:
            data = dict(si)

            try:
                import torch
                data['software'] = { 'torch': torch.__version__ }
            except ImportError:
                logger.warning("BenchmarkRunner: failed to check torch version")

            yaml.dump(data, f)

        report = Report(
            benchmark=name,
            variant=variant,
            start_time=int(result.start_time.timestamp()),
            end_time=int(result.end_time.timestamp()),
            # slurm_job_id=0
            device_type=device_type,
            gpu_model=si.gpu_info.model,
            gpu_count=gpu_count,
            metrics=config.extract_metrics(result.stdout + result.stderr)
        )

        with open(config.temp_dir / "report.yaml", "w") as f:
            yaml.dump(report.model_dump(), f)

        return report
