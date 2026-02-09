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
        ["transformerxl_base","throughput", 140123.0, [
                "Training throughput: 140123 Tok/s"
            ]
        ],
        ["ssd", "throughput", 646.242, [
                "Creating index...",
                "Done (t=0.48s)",
                "DLL 2026-02-09 15:50:00.948517 - () avg_img/sec : 646.2415546927269 images/s med_img/sec : 646.3537480022912 images/s min_img/sec : 642.838741874282 images/s max_img/sec : 649.0996051242621 images/s",
                "Done benchmarking. Total images: 57000  total time: 88.202      Average images/sec: 646.242     Median images/sec: 646.354",
                "Training performance = 646.353759765625 FPS",
                "DLL 2026-02-09 15:50:01.338979 - (0,) time : 159.1902894973755",
                "saving model...",
                "DLL 2026-02-09 15:50:01.454263 - (0, 0) model path : /tmp/ssd_fp32/models/epoch_0.pt",
                "DLL 2026-02-09 15:50:01.454558 - () total time : 159.1902894973755",
                "DLL 2026-02-09 15:50:01.454575 - ()",
            ]
        ]
    ]
)
def test_metrics(name, metric, expected, teststring, tmp_path):
    benchmarks = BenchmarkSpec.load_all(confd_dir=find_confd(), data_dir=tmp_path)
    config = benchmarks["pytorch"][name]

    for variant, spec in config.items():
        assert spec.extract_metrics(teststring)[metric] == expected
