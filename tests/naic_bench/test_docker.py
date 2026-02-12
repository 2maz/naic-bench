import pytest
from naic_bench.docker import Docker

@pytest.mark.parametrize("device_type",[
    "nvidia",
    "nvidia-volta",
    "rocm",
    "habana",
    ]
)
def test_dockerfile(device_type):
    dockerfile = Docker.dockerfile(device_type)
    assert dockerfile.exists()
