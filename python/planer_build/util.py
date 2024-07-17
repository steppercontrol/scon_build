from os.path import realpath

from mk_build import PathInput

wsl_drive = 'Z'


def win_from_wsl(path: PathInput) -> str:
    """ Convert an absolute path on a WSL system into the corresponding
        Windows path. """

    path = realpath(str(path))

    if path.startswith('/mnt'):
        parts = path.split('/')

        return f'{parts[2]}:/{"/".join(parts[3:])}'
    else:
        return '/'.join([f'{wsl_drive}:', path])


def wsl_from_win(path: PathInput) -> str:
    """ Convert an absolute path on a Windows system into the corresponding
        WSL path. """

    slashes = str(path).replace('\\', '/')

    return slashes.replace('C:', '/mnt/c')
