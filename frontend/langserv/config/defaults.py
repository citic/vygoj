# Default configuration of the language server. It loads this file, and then config/config.py
# (git-ignored), which only needs the settings of each server that differ from these: at least
# LANG_SERVER_SECRET, and usually ORIGINS. A setting in config.py replaces the whole value of this
# file. Keep this file complete and valid: the code reads every setting from it without fallback
# values. The address and port where the server listens are HOST and PORT in its Makefile
# (0.0.0.0:7070), and the frontend lists them in LANG_SERVERS of frontend/config/config.py

# Secret shared with the frontend, as LANG_SERVER_SECRET in frontend/config/config.py. The frontend
# signs with it the keys that let the users who may open a problem connect for KEY_MAX_AGE seconds.
# Anyone who knows it can use the language server, so it must be set in config.py: the server
# refuses to start without it or with fewer than 32 characters. make config adds the one of the
# frontend to config.py if the frontend is in this computer, or a random one
LANG_SERVER_SECRET = ''
# Addresses of the frontend, as browsers send them in the Origin header of the connections, e.g.
# 'https://vygoj.ucr.ac.cr'. Pages of other sites cannot connect, even with a valid key
ORIGINS = ['http://localhost:8080']
# Docker image of the containers where the language servers run, built by make image
IMAGE = 'vygoj-langserv'
# Command of the language server of each programming language of VygOJ, run in the image. Code
# editors of other languages get no connection
LANGUAGES = {
    # Suggestions of functions of other headers add their #include, without marking them. The
    # headers of the solution are open in the editor, and not on the disk (--use-dirty-headers)
    'C': ['clangd', '--log=error', '--header-insertion-decorators=false', '--use-dirty-headers'],
    'C++': ['clangd', '--log=error', '--header-insertion-decorators=false', '--use-dirty-headers'],
    # pylsp reads the modules of the solution from the disk: the script of the image
    # (image/pylsp-files) writes them in /home/student and runs pylsp
    'Python': ['pylsp-files'],
    # Script of the image (image/jdtls) with the options of Java and Eclipse
    'Java': ['jdtls'],
}
# Options of the language server of each language, sent in the initializationOptions of its
# initialize request in place of the ones of the editor
INITIALIZATION_OPTIONS = {
    # jdtls does not give parameter hints unless they are enabled, and suggests the internal classes
    # of the JDK (e.g. com.sun.tools.jdeprscan.scan.Scan for "new Scan") unless they are filtered
    'Java': {'settings': {'java': {'signatureHelp': {'enabled': True}, 'completion': {
        'filteredTypes': ['com.sun.*', 'sun.*', 'jdk.*', 'java.awt.*', 'org.graalvm.*']}}}},
}
# Limits of each container: memory (without swap), CPUs, and processes and threads
CONTAINER_MEMORY = '512m'
CONTAINER_CPUS = 1
CONTAINER_PIDS = 128
# Code editors connected at the same time in this server, and editors of a user (e.g. two tabs).
# Each connection keeps a thread of gunicorn busy, so MAX_SESSIONS must be lower than THREADS in the
# Makefile (120)
MAX_SESSIONS = 100
MAX_USER_SESSIONS = 3
# Seconds that a key is valid after the frontend signs it, that a connection may wait for a
# message of its editor, e.g. while the student does not type, and that a connection may last
KEY_MAX_AGE = 60
IDLE_TIMEOUT = 15 * 60
MAX_DURATION = 2 * 60 * 60
# Bytes of a message of an editor, even the key. Changes carry the whole solution, which the
# frontend limits to 1 MiB too (MAX_CONTENT_LENGTH)
MAX_MESSAGE_SIZE = 2**20
