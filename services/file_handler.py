import time
from pathlib import Path


def remove_file(path: str):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def remove_file_after(path: str, ttl_sec: int):
    """Sleep for ttl_sec then delete the file. Intended for BackgroundTasks."""
    if ttl_sec > 0:
        time.sleep(ttl_sec)
    remove_file(path)
