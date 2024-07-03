def wsl_from_win(path):
    """ Convert an absolute path on a Windows system into the corresponding
        WSL path. """

    slashes = path.replace('\\', '/')

    return slashes.replace('C:', '/mnt/c')
