from simple_automation.vars import Vars
from simple_automation.exceptions import LogicError

import getpass
import json
import os
import subprocess
import tempfile

class Vault(Vars):
    """
    A base-class for vaults.
    """

    def __init__(self, manager, file):
        """
        Initializes the vault.
        """
        super().__init__()
        self.manager = manager
        self.file = file

    def encrypt_content(self, plaintext: bytes) -> bytes:
        """
        Encrypts the given plaintext. Should be implemented by subclasses.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        """
        Decrypts the given ciphertext. Should be implemented by subclasses.
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def decrypt(self):
        """
        Decrypts the vault (using self.decrypt_content) and loads the content into our Vars.
        """
        try:
            with open(self.file, 'rb') as f:
                self.vars = json.loads(self.decrypt_content(f.read()))
        except FileNotFoundError:
            print(f"[1;33mwarning:[m [1mLoaded nonexistent vault '{self.file}': [mTo create the file, use --edit-vault")
            pass

    def encrypt(self) -> bytes:
        """
        Encrypts the currently stored Vars (using self.encrypt_content) and overwrites the vault file.
        """
        content = self.encrypt_content(json.dumps(self.vars).encode('utf-8'))
        with open(self.file, 'wb') as f:
            f.write(content)

    def edit(self):
        """
        Opens an $EDITOR containing the loaded content as a pretty printent json,
        and updates the internal representation as well as the original vault file,
        if the content changed after the editor exists.
        """
        editor = os.environ.get('EDITOR')
        if editor is None:
            raise RuntimeError("Cannot edit vault: $EDITOR is not set!")

        with tempfile.NamedTemporaryFile(suffix=".tmp") as tf:
            # Set up temporary file
            tf.write(json.dumps(self.vars, sort_keys=True, indent=4).encode('utf-8'))
            tf.flush()

            # Run editor
            p = subprocess.run([editor, tf.name])
            if p.returncode != 0:
                raise RuntimeError(f"Aborting vault edit: $EDITOR exited with status {p.returncode}")

            # Seek to beginning of file and load content
            tf.seek(0)
            self.vars = json.load(tf)

            # Save vault
            self.encrypt()

class SymmetricVault(Vault):
    def __init__(self, manager, file, keyfile=None, key=None):
        """
        Initializes the vault from the given file and key/keyfile.
        The key may be given as str or bytes. If the key is given a a str,
        it will automatically be converted to bytes (without encoding) before usage.
        """
        super().__init__(manager, file)

        # Get key from keyfile / ask for pass
        if key is None:
            if keyfile is None:
                # Ask for key
                self.key = getpass.getpass(f"Password for vault '{self.file}': ")
            else:
                with open(keyfile, 'rb') as f:
                    self.key = f.read()

        # Change key to bytes, if it's a str
        if type(self.key) == str:
            # Latin1 is a str <-> bytes no-op (see https://stackoverflow.com/questions/42795042/how-to-cast-a-string-to-bytes-without-encoding)
            self.key = self.key.encode('latin1')

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        return b''

    def encrypt_content(self, plaintext: bytes) -> bytes:
        return b''


class GpgVault(Vault):
    def __init__(self, manager, file, recipient):
        """
        Initializes the gpg encrypted vault from the given file and recipient.
        The recipient is only needed for encryption (when editing), and reflects
        the gpg parameter '--recipient'. If you don't plan on using the editing
        feature, the recipient may be set to None.
        """
        super().__init__(manager, file)
        self.recipient = recipient

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        return subprocess.run(["gpg", "--quiet", "--decrypt"], input=ciphertext, capture_output=True, check=True).stdout

    def encrypt_content(self, plaintext: bytes) -> bytes:
        if self.recipient is None:
            raise LogicError("GpgVault encryption requires a recipient")
        return subprocess.run(["gpg", "--quiet", "--encrypt", "--recipient", self.recipient], input=plaintext, capture_output=True, check=True).stdout
