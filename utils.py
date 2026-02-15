import sys, os


def base_path():
    """Return the project root directory (works for both dev and .exe)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
