import re
import unicodedata
from pathlib import PurePosixPath


def sanitize_filename(filename: str) -> str:
    filename = unicodedata.normalize("NFKD", filename)
    filename = PurePosixPath(filename).name
    filename = filename.replace("..", "")
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    filename = filename.replace(" ", "_")
    filename = re.sub(r"_+", "_", filename)
    filename = filename.strip("._")
    if not filename:
        filename = "unnamed"
    return filename


def safe_output_filename(original_filename: str, extension: str = ".jpg") -> str:
    stem = PurePosixPath(sanitize_filename(original_filename)).stem
    if not stem:
        stem = "output"
    return stem + extension
