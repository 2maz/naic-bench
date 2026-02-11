import re
from naic_bench.utils.command import ( ExecutionResult, Command, find_confd ) # noqa

def canonized_name(name: str):
    return re.sub(r"[/:]",'-', name)
