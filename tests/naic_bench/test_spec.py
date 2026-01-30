import pytest
from naic_bench.spec import BenchmarkSpec
from naic_bench.utils import find_confd

def test_load(testdir, tmp_path):
    specfile = testdir / "data" / "conf.d" / "a.yaml"

    specs = BenchmarkSpec.load(config_filename=specfile, data_dir=tmp_path)
    bc = specs["pytorch"]["a"]["fp16"]
    bc.expand_placeholders(CPU_COUNT=128)
    assert bc.arguments["train-loader-workers"] == '32'

@pytest.mark.parametrize("name,metric,expected,teststring",
    [
        ["transformerxl_base","throughput", 140123.0, "Training throughput: 140123 Tok/s"]
    ]
)
def test_metrics(name, metric, expected, teststring, tmp_path):
    benchmarks = BenchmarkSpec.load_all(confd_dir=find_confd(), data_dir=tmp_path)
    config = benchmarks["pytorch"][name]

    for variant, spec in config.items():
        assert spec.extract_metrics([teststring])[metric] == expected
