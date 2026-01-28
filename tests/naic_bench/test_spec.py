import pytest
from naic_bench.spec import BenchmarkSpec

def test_load(testdir, tmp_path):
    specfile = testdir / "data" / "conf.d" / "a.yaml"

    specs = BenchmarkSpec.load(config_filename=specfile, data_dir=tmp_path)
    bc = specs["pytorch"]["a"]["fp16"]
    bc.expand_placeholders(CPU_COUNT=128)
    assert bc.arguments["train-loader-workers"] == '32'
