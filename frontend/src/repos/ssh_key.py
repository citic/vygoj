""" SSH key of each user, which the frontend uses to push their repos to the remotes that they
choose (e.g. a repo of the user in GitHub):

    user/<username>/ssh/id_ed25519        # private key, readable only by the user of the server
    user/<username>/ssh/id_ed25519.pub    # public key, which the user adds to their remote
    user/<username>/ssh/known_hosts       # keys of the hosts of their remotes

Each user has their own key, so a remote that trusts it trusts only that user: another user who
sets that remote as their origin cannot push to it. The key has no passphrase, because the
frontend uses it without the user. Deleting the user deletes their folder, and the key with it """

import os
import shlex
import subprocess

from repos.git_repo import user_folder

# Seconds that ssh-keygen may take to make a key, and that ssh may take to connect to a host
KEYGEN_TIMEOUT = 10
CONNECT_TIMEOUT = 15
# Comment of the public keys, which hosts show in their lists of keys
KEY_COMMENT = 'VygOJ'

class UserKey:
    """ The SSH key pair of a user """

    def __init__(self, username: str):
        """ Find the files of the key from the username of the user """
        self.folder = os.path.join(user_folder(username), 'ssh')
        self.private = os.path.join(self.folder, 'id_ed25519')
        self.known_hosts = os.path.join(self.folder, 'known_hosts')

    def public_key(self) -> str:
        """ Return the public key, as a line of authorized_keys. The key is made the first time """
        if not os.path.isfile(self.private):
            self.create()
        with open(f'{self.private}.pub', encoding='utf-8') as file:
            return file.read().strip()

    def create(self):
        """ Make a new ed25519 key pair without passphrase. Raise OSError if ssh-keygen fails """
        os.makedirs(self.folder, mode=0o700, exist_ok=True)
        try:
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', KEY_COMMENT,
                '-f', self.private], stdin=subprocess.DEVNULL, capture_output=True,
                timeout=KEYGEN_TIMEOUT, check=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise OSError('ssh-keygen failed') from error

    def ssh_command(self) -> str:
        """ Return the command for GIT_SSH_COMMAND that connects with this key only: no agent,
        config, nor keys of the user of the server, and no questions. A host is trusted the first
        time, and its key is kept in the known_hosts of the user. git runs the command with the
        shell, so the paths are quoted """
        return shlex.join(['ssh', '-F', '/dev/null', '-i', self.private,
            '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'UserKnownHostsFile={self.known_hosts}',
            '-o', f'ConnectTimeout={CONNECT_TIMEOUT}'])
