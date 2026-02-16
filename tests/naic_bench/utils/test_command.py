from naic_bench.utils.command import find_confd

def test_find_confd():
    assert find_confd() is not None
