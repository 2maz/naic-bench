from naic_bench.utils import Command
import re

from slurm_monitor.utils.system_info import SystemInfo
from slurm_monitor.devices.gpu import GPUInfo

class Nvidia:
    @classmethod
    def device_uuids(cls):
        result = Command.run(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"])
        return result.splitlines()

    @classmethod
    def device_architecture(cls) -> str:
        """
        Get device architecture if this is available
        """
        result = Command.run(["nvidia-smi", "-q"])
        for line in result.splitlines():
            m = re.search(r"Product Architecture\s+:\s+(.*)", line)
            if m:
                return m.groups()[0].lower()

        return None



class GPU:
    @classmethod
    def get_device_type(cls) -> tuple[str,str]:
        si = SystemInfo()

        if si.gpu_info.framework == GPUInfo.Framework.CUDA:
            architecture = Nvidia.device_architecture()
            return 'nvidia', architecture

        else:
            return si.gpu_info.framework.value, None
