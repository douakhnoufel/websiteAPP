from pathlib import Path

def remove_file(path: str):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass
