""" Give the config/config.py of the frontend and of the language server the secrets that they
need to start, with random values, without changing the settings that they already have. Run by
make config: python3 common/make_config.py frontend langserv writes both files, and each layer
writes its own. Both share the same LANG_SERVER_SECRET: a layer copies the one of the other if it
has it, so they match in any order. A language server in another computer needs a copy of the
secret of the frontend by hand """
import ast
import os
import secrets
import sys

# Folder of the repository, the parent of common/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Configuration file of each layer and the secrets it needs. The servers refuse to start without
# them, so a new installation has the minimal security without editing files
LAYERS = {
    'frontend': ('frontend/config/config.py', ('SECRET_KEY', 'LANG_SERVER_SECRET')),
    'langserv': ('frontend/langserv/config/config.py', ('LANG_SERVER_SECRET',)),
}

# Secret that the frontend and the language server must have equal, so the language server accepts
# the keys that the frontend signs
SHARED_SECRET = 'LANG_SERVER_SECRET'

# Value of a setting that config.py computes (e.g. from an environment variable), which this script
# cannot read. It counts as set, so it is never replaced
COMPUTED = object()

HEADER = ('# Settings of this server that differ from config/defaults.py, which explains each\n'
    '# one. Keep this file private: it has secrets\n')


class ConfigError(Exception):
    """ A configuration file cannot be read or written, or the secrets of the layers differ """


def read_settings(path: str) -> dict:
    """ Answer the settings that the config.py in path assigns, with their literal values or
    COMPUTED. The file is parsed, not run, so reading it has no side effects. A missing file has no
    settings """
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as file:
            tree = ast.parse(file.read(), path)
    except (OSError, SyntaxError, ValueError) as error:
        raise ConfigError(f'cannot read {path}: {error}') from error
    settings = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    settings[target.id] = literal_value(node.value)
    return settings


def literal_value(node):
    """ Answer the value of the expression node if it is a literal, or COMPUTED """
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return COMPUTED


def choose_shared_secret(settings: dict) -> str | None:
    """ Answer the LANG_SERVER_SECRET for the layers that lack it: the one of another layer, or a
    new random one. Answer None if another layer computes it, because its value is unknown here,
    and a random one would differ. Fail if the layers have different ones, because the language
    server would refuse every editor """
    values = {value[SHARED_SECRET] for value in settings.values() if SHARED_SECRET in value}
    computed = COMPUTED in values
    values.discard(COMPUTED)
    if len(values) > 1:
        files = ' and '.join(path for path, _ in LAYERS.values())
        raise ConfigError(f'{SHARED_SECRET} differs in {files}, make them equal')
    if values:
        return values.pop()
    return None if computed else secrets.token_hex(32)


def add_settings(path: str, new_settings: dict):
    """ Append the settings to the config.py in path, creating it if it does not exist. Only its
    owner may read it, because it has secrets """
    exists = os.path.exists(path)
    lines = [] if exists else [HEADER]
    if exists and not file_ends_with_newline(path):
        lines.append('\n')
    lines.append('# Random secrets added by make config\n')
    lines += [f'{name} = {value!r}\n' for name, value in new_settings.items()]
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, 'a', encoding='utf-8') as file:
            file.writelines(lines)
        os.chmod(path, 0o600)
    except OSError as error:
        raise ConfigError(f'cannot write {path}: {error}') from error


def file_ends_with_newline(path: str) -> bool:
    """ Answer whether the file in path is empty or ends with a new line """
    with open(path, 'rb') as file:
        file.seek(0, os.SEEK_END)
        if file.tell() == 0:
            return True
        file.seek(-1, os.SEEK_END)
        return file.read(1) == b'\n'


def configure(layers: list):
    """ Add the missing secrets to the configuration files of the layers. The files of the other
    layers are read too, for their shared secret """
    settings = {layer: read_settings(os.path.join(ROOT, path))
        for layer, (path, _) in LAYERS.items()}
    shared_secret = choose_shared_secret(settings)
    for layer in layers:
        relative_path, names = LAYERS[layer]
        missing = {name: shared_secret if name == SHARED_SECRET else secrets.token_hex(32)
            for name in names if name not in settings[layer]}
        if SHARED_SECRET in missing and shared_secret is None:
            raise ConfigError(f'{SHARED_SECRET} is computed in the config.py of another layer, '
                f'write the same value in {relative_path}')
        if missing:
            add_settings(os.path.join(ROOT, relative_path), missing)
            print(f'{relative_path}: added {", ".join(missing)}')


def main() -> int:
    """ Configure the layers named in the arguments, and answer the exit status """
    layers = sys.argv[1:]
    unknown = [layer for layer in layers if layer not in LAYERS]
    if not layers or unknown:
        print(f'usage: {sys.argv[0]} {"|".join(LAYERS)}...', file=sys.stderr)
        return 2
    try:
        configure(layers)
    except ConfigError as error:
        print(f'make config: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
