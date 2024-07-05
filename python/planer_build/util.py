from os.path import realpath
from pathlib import Path


def win_from_wsl(path):
    """ Convert an absolute path on a WSL system into the corresponding
        Windows path. """

    path = realpath(str(path))

    if not path.startswith('/mnt'):
        raise Exception(f'path is expected to be an absolute path on a WSL'
                        f' installation: {path}')

    parts = path.split('/')

    return Path(f'{parts[2]}:/{"/".join(parts[3:])}')


def wsl_from_win(path):
    """ Convert an absolute path on a Windows system into the corresponding
        WSL path. """

    slashes = path.replace('\\', '/')

    return slashes.replace('C:', '/mnt/c')
