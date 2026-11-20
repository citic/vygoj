""" Language server of VygOJ: the code editor of the problem page connects here with a WebSocket,
and talks the Language Server Protocol (LSP) with a language server (e.g. clangd) that runs in a
container without network for that editor, to get suggestions and parameter hints """
import collections
import contextlib
import json
import os
import secrets
import subprocess
import threading

import flask
import flask_sock
from itsdangerous import BadSignature, URLSafeTimedSerializer
from simple_websocket import ConnectionClosed

# Web application ---------------------------------------------------------------------------------

app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = flask.Flask(__name__)
sock = flask_sock.Sock(app)

# Load the default configuration, and replace it with the settings of this server, if any. Every
# setting is defined in defaults.py, so the code needs no fallback values
app.config.from_pyfile(os.path.join(app_path, 'config/defaults.py'))
config_file = os.path.join(app_path, 'config/config.py')
app.config.from_pyfile(config_file, silent=True)
config = app.config
# The WebSocket keeps a whole message in memory before the code receives it, so it closes the
# connections that send longer messages while they arrive, even before their key
config['SOCK_SERVER_OPTIONS'] = {'max_message_size': config['MAX_MESSAGE_SIZE']}

# Anyone who knows the secret can sign keys and use the language server, so it must be hard to guess
MIN_SECRET_LENGTH = 32
if not isinstance(config['LANG_SERVER_SECRET'], str) or len(
        config['LANG_SERVER_SECRET']) < MIN_SECRET_LENGTH:
    raise RuntimeError(f'LANG_SERVER_SECRET in {config_file} must be the random string of at least '
        f'{MIN_SECRET_LENGTH} characters of the frontend, generate one with: '
        "python3 -c 'import secrets; print(secrets.token_hex(32))'")
# Keys signed by the frontend (lang_server_key() in problem_controller.py) with the same secret
keys = URLSafeTimedSerializer(config['LANG_SERVER_SECRET'], salt='lang-srv')

# Sessions -----------------------------------------------------------------------------------------

# Seconds that an editor may take to send its key. A connection without key keeps a thread busy
KEY_TIMEOUT = 3
# Code editors connected, by user. The server runs in one process (WORKERS in the Makefile), so its
# threads count every session here, and the lock makes checking and counting one step
sessions = collections.Counter()
sessions_lock = threading.Lock()

def open_session(ws) -> tuple[str, str] | None:
    """ Count the session of the editor and return its language and user, or None if it may not
    connect: a page of another site, a missing or expired key, or too many sessions """
    if flask.request.headers.get('Origin') not in config['ORIGINS']:
        return None
    try:
        key = keys.loads(ws.receive(timeout=KEY_TIMEOUT) or '', max_age=config['KEY_MAX_AGE'])
    except (BadSignature, ConnectionClosed, TypeError):
        return None
    language = key.get('language') if isinstance(key, dict) else None
    if language not in config['LANGUAGES']:
        return None
    user = str(key.get('user'))
    with sessions_lock:
        if (sessions.total() >= config['MAX_SESSIONS']
                or sessions[user] >= config['MAX_USER_SESSIONS']):
            return None
        sessions[user] += 1
    return language, user

# Containers --------------------------------------------------------------------------------------

# Label of the containers of this server, e.g. to remove leaked ones
LABEL = 'vygoj=lang-srv'
# Seconds that a container may take to stop, and that docker kill may take
DOCKER_TIMEOUT = 10

def start_container(language: str) -> subprocess.Popen:
    """ Start the language server of the language in a new container, and return the docker run
    process, whose stdin and stdout are the ones of the server. The container has no network,
    capabilities, nor writable files but /tmp, runs as nobody, and stops by itself at the end of
    MAX_DURATION or when its stdin closes """
    name = f'lang-srv-{secrets.token_hex(8)}'
    command = ['docker', 'run', '--rm', '--interactive', '--name', name, '--label', LABEL,
        '--network', 'none', '--read-only', '--tmpfs', '/tmp:size=64m',
        '--user', '65534:65534', '--env', 'HOME=/tmp', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges',
        '--memory', config['CONTAINER_MEMORY'], '--memory-swap', config['CONTAINER_MEMORY'],
        '--cpus', str(config['CONTAINER_CPUS']), '--pids-limit', str(config['CONTAINER_PIDS']),
        config['IMAGE'], 'timeout', str(config['MAX_DURATION']), *config['LANGUAGES'][language]]
    # pylint: disable-next=consider-using-with # the session closes it when the editor leaves
    return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL)

def stop_container(process: subprocess.Popen):
    """ Close the stdin of the language server, which makes docker remove its container when the
    language server exits, or kill the container if it does not exit in time """
    try:
        process.stdin.close()
        process.wait(timeout=DOCKER_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        name = process.args[process.args.index('--name') + 1]
        subprocess.run(['docker', 'kill', name], capture_output=True, timeout=DOCKER_TIMEOUT,
            check=False)

# Protocol ----------------------------------------------------------------------------------------

# Methods of the protocol that editors may send. Others, e.g. renaming files or running commands
# of the server, are dropped
CLIENT_METHODS = {'initialize', 'initialized', 'textDocument/didOpen', 'textDocument/didChange',
    'textDocument/completion', 'textDocument/signatureHelp'}
# Folder of the solution files in the containers
ROOT = 'file:///home/student'
# Bytes of a message of a language server, e.g. thousands of suggestions after "std::"
MAX_SERVER_MESSAGE_SIZE = 16 * 2**20
# Errors of a broken connection, a dead language server, or a malformed message, e.g. JSON nested
# too deep or a method that is not a string. They end the session
SESSION_ERRORS = (ConnectionClosed, OSError, ValueError, TypeError, RecursionError)

def write_message(process: subprocess.Popen, lock: threading.Lock, message: dict):
    """ Send the message to the language server, after the header with its length that LSP needs """
    body = json.dumps(message).encode()
    with lock:
        process.stdin.write(b'Content-Length: %d\r\n\r\n%s' % (len(body), body))
        process.stdin.flush()

def read_message(process: subprocess.Popen) -> dict | None:
    """ Return the next message of the language server, or None when it exits or sends a message
    too long, which would fill the memory of this server """
    length = 0
    while line := process.stdout.readline(1024).strip():
        name, _, value = line.partition(b':')
        if name.lower() == b'content-length':
            length = int(value)
    if not 0 < length <= MAX_SERVER_MESSAGE_SIZE:
        return None
    body = process.stdout.read(length)
    return json.loads(body) if body else None

def answer_server(process: subprocess.Popen, lock: threading.Lock, ws):
    """ Send the editor the answers of the language server to its requests, until either side
    closes. This server answers the requests of the language server itself (e.g. its settings),
    and drops its notifications (e.g. diagnostics: the backend reports the errors of the code) """
    try:
        while (message := read_message(process)) is not None:
            if 'method' not in message:
                ws.send(json.dumps(message))
            elif 'id' in message:
                params = message.get('params')
                items = params.get('items') if isinstance(params, dict) else None
                result = [None] * len(items) if isinstance(items, list) else None
                write_message(process, lock, {'jsonrpc': '2.0', 'id': message['id'],
                    'result': result})
    except SESSION_ERRORS:
        pass
    finally:
        # The editor may have closed the connection already
        with contextlib.suppress(ConnectionClosed):
            ws.close()

def relay(ws, process: subprocess.Popen, language: str):
    """ Pass the allowed messages of the editor to the language server, and its answers back,
    until the editor leaves or stays without messages IDLE_TIMEOUT """
    lock = threading.Lock()
    threading.Thread(target=answer_server, args=(process, lock, ws), daemon=True).start()
    with contextlib.suppress(*SESSION_ERRORS):
        while (data := ws.receive(timeout=config['IDLE_TIMEOUT'])) is not None:
            message = json.loads(data)
            if not isinstance(message, dict) or message.get('method') not in CLIENT_METHODS:
                continue
            # The editor may not choose the folder nor the options of the language server
            if message['method'] == 'initialize':
                params = message.get('params')
                message['params'] = {'processId': None, 'rootUri': ROOT,
                    'capabilities': params.get('capabilities') if isinstance(params, dict) else {},
                    'initializationOptions': config['INITIALIZATION_OPTIONS'].get(language)}
            write_message(process, lock, message)
    # The end of its input does not stop every language server (jdtls keeps running)
    with contextlib.suppress(OSError):
        write_message(process, lock, {'jsonrpc': '2.0', 'method': 'exit'})

# Routes ------------------------------------------------------------------------------------------

@sock.route('/')
def lang_server(ws):
    """ An editor connected: its first message is the key from the frontend, and the next ones are
    messages for its language server in a container of its own """
    session = open_session(ws)
    if not session:
        return
    language, user = session
    try:
        process = start_container(language)
        try:
            relay(ws, process, language)
        finally:
            stop_container(process)
    finally:
        with sessions_lock:
            sessions[user] -= 1
