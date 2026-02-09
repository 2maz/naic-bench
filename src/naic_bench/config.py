from typing import ClassVar
import tempfile
from pathlib import Path

class Config:
    output_base_dir: ClassVar[Path] = Path(tempfile.gettempdir()) / "naic-bench"
