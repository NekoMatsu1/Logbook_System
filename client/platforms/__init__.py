import sys

def load(simulation=True):
    if sys.platform == 'win32':
        from .windows import Windows
        return Windows(simulation)
    if sys.platform.startswith('linux'):
        from .linux import Linux
        return Linux(simulation)
    raise RuntimeError('Supported platforms: Windows and Linux Mint X11')
