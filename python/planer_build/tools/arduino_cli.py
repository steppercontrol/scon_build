from dataclasses import asdict
from operator import itemgetter

from mk_build import CompletedProcess, environ, run
import mk_build.config as config_
import planer_build.configure as planer_config_
from ..util import win_from_wsl

config = config_.get()
planer_config = planer_config_.get()


def compile(
    ino_path,
    build_path,
    libraries
) -> CompletedProcess[bytes]:
    common = _build_args(board=True, port=True, verbose=True)

    arduino_cli = _arduino_cli()

    if arduino_cli.endswith('.exe'):
        ino_path = win_from_wsl(ino_path)
        libraries = win_from_wsl(libraries)
        build_path = win_from_wsl(build_path)

    return run([
        arduino_cli, 'compile', ino_path,
        '--optimize-for-debug',
        '--build-path', build_path,
        '--warnings', 'all',
        '--libraries', libraries
    ] + common)


def core_install(core: str) -> CompletedProcess[bytes]:
    return run([_arduino_cli(), 'core', 'install', core])


def upload(path: str) -> CompletedProcess[bytes]:
    common = _build_args(board=True, port=True, verbose=True)

    return run([_arduino_cli(), 'upload', '--input-file', path] + common)


def monitor() -> CompletedProcess[bytes]:
    common = _build_args(board=True, port=True)

    return run([_arduino_cli(), 'monitor', '-q', '-c', 'baudrate=115200']
               + common)


def _build_args(board=False, port=False, verbose=False) -> list[str]:
    args = []

    if board:
        args += ['-b', _arduino_fqbn()]

    if port:
        args += ['-p', planer_config.arduino.port]

    if verbose and config.verbose > 0:
        args.append('-v')

    return args


def _arduino_cli() -> str:
    return environ('ARDUINO_CLI', 'arduino-cli')


def _arduino_fqbn() -> str:
    core, board = itemgetter('core', 'board')(asdict(planer_config.arduino))

    return f'{core}:{board}'
