from naic_bench.utils import Command

class Nvidia:
    @classmethod
    def device_uuids(cls):
        result = Command.run(["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader"])
        return result.splitlines()
