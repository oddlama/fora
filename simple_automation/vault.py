"""
Provides the Vault class for secure variable storage.
"""

import base64
import getpass
import json
import os
import subprocess
import tempfile

from simple_automation.vars import Vars
from simple_automation.exceptions import LogicError, MessageError
from simple_automation.utils import choice_yes

class Vault(Vars):
    """
    A base-class for vaults.

    Parameters
    ----------
    manager : Manager
        The manager to which this vault is registered.
    file : str
        The file which serves as the permanent storage.
    """

    def __init__(self, manager, file: str):
        super().__init__()
        self.manager = manager
        self.file = file

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        """
        Decrypts the given ciphertext. Should be implemented by subclasses.

        Parameters
        ----------
        ciphertext : bytes
            The bytes to decrypt.

        Returns
        -------
        bytes
            The plaintext
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def encrypt_content(self, plaintext: bytes) -> bytes:
        """
        Encrypts the given plaintext. Should be implemented by subclasses.

        Parameters
        ----------
        plaintext : bytes
            The bytes to encrypt.

        Returns
        -------
        bytes
            The ciphertext
        """
        raise NotImplementedError("Must be overwritten by subclass.")

    def decrypt(self):
        """
        Decrypts the vault (using self.decrypt_content) and loads the content into our Vars.
        """
        try:
            with open(self.file, 'rb') as f:
                self.vars = json.loads(self.decrypt_content(base64.decodebytes(f.read())))
        except FileNotFoundError:
            if self.manager.edit_vault is None:
                print(f"[1;33mwarning:[m [1mLoaded nonexistent vault '{self.file}': [mTo create the file, use --edit-vault")

    def encrypt(self) -> bytes:
        """
        Encrypts the currently stored Vars (using self.encrypt_content) and overwrites the vault file.
        """
        content = base64.encodebytes(self.encrypt_content(json.dumps(self.vars).encode('utf-8')))
        with open(self.file, 'wb') as f:
            f.write(content)

    def edit(self):
        """
        Opens an $EDITOR containing the loaded content as a pretty printed json,
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

            while True:
                # Run editor
                p = subprocess.run([editor, tf.name], check=False)
                if p.returncode != 0:
                    raise RuntimeError(f"Aborting vault edit: $EDITOR exited with status {p.returncode}")

                # Seek to beginning of file and load content
                tf.seek(0)
                try:
                    self.vars = json.load(tf)
                    break
                except json.decoder.JSONDecodeError as e:
                    print(f"[1;31merror:[m {str(e)}")
                    if not choice_yes("Invalid json! Reopen editor?"):
                        # Abort without saving.
                        print("Editing aborted. Changes have been discarded.")
                        return

            # Save vault
            self.encrypt()

class SymmetricVault(Vault):
    """
    A SymmetricVault is a Vault which saves its context symmetrically encrypted.
    Content is encrypted with a salted key (+scrypt) using AES-256-GCM.

    Initializes the vault from the given file and key/keyfile.
    If neither key nor keyfile is provided, the key will be read via getpass().
    The key may be given as str or bytes. If the key is given a a str,
    it will automatically be converted to bytes (without encoding) before usage.

    Parameters
    ----------
    manager : Manager
        The manager to which this vault is registered.
    file : str
        The file which serves as the permanent storage.
    keyfile : str, optional
        A file which contains the decryption key. Defaults to None.
    key : str, optional
        The decryption key. Defaults to None.
    """
    def __init__(self, manager, file: str, keyfile=None, key=None):
        super().__init__(manager, file)
        self.keyfile = keyfile
        self.key = key

    def get_key(self):
        """
        Loads the decryption key.
        """
        # Get key from keyfile / ask for pass
        if self.key is None:
            if self.keyfile is None:
                # Ask for key
                self.key = getpass.getpass(f"Password for vault '{self.file}': ")
            else:
                with open(self.keyfile, 'rb') as f:
                    self.key = f.read()

        # Change key to bytes, if it's a str
        if isinstance(self.key, str):
            # Latin1 is a str <-> bytes no-op (see https://stackoverflow.com/questions/42795042/how-to-cast-a-string-to-bytes-without-encoding)
            self.key = self.key.encode('latin1')

    def kdf(self, salt):
        """
        Derives the actual aeskey from a given salt and the saved key.
        """
        # pylint: disable=C0415
        from Crypto.Protocol.KDF import scrypt
        return scrypt(self.key, salt, key_len=32, N=2**17, r=8, p=1)

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        """
        Decrypts the given ciphertext.

        Parameters
        ----------
        ciphertext : bytes
            The bytes to decrypt.

        Returns
        -------
        bytes
            The plaintext
        """
        self.get_key()
        # pylint: disable=C0415
        from Crypto.Cipher import AES

        # Split ciphertext into raw input parts
        salt = ciphertext[:32]
        nonce = ciphertext[32:48]
        aes_ciphertext = ciphertext[48:-16]
        tag = ciphertext[-16:]

        # Derive aeskey and decrypt ciphertext
        aeskey = self.kdf(salt)
        cipher = AES.new(aeskey, AES.MODE_GCM, nonce=nonce)
        plaintext = cipher.decrypt(aes_ciphertext)

        # Verify encrypted file was not tampered with
        try:
            cipher.verify(tag)
        except ValueError as e:
            # If we get a ValueError, there was an error when decrypting so delete the file we created
            raise MessageError(f"Refusing decrypted data from '{self.file}', because content verification failed! Your file might have been tampered with!") from e

        return plaintext

    def encrypt_content(self, plaintext: bytes) -> bytes:
        """
        Encrypts the given plaintext.

        Parameters
        ----------
        plaintext : bytes
            The bytes to encrypt.

        Returns
        -------
        bytes
            The ciphertext
        """
        # pylint: disable=C0415
        from Crypto.Cipher import AES
        from Crypto.Random import get_random_bytes
        salt = get_random_bytes(32)

        # Derive aeskey and encrypt plaintext
        aeskey = self.kdf(salt)
        cipher = AES.new(aeskey, AES.MODE_GCM)
        aes_ciphertext = cipher.encrypt(plaintext)
        tag = cipher.digest()

        # Return salt, nonce, AES ciphertext and verification tag
        return salt + cipher.nonce + aes_ciphertext + tag

class GpgVault(Vault):
    """
    A GpgVault is a Vault which saves its context encrypted with gpg.
    This can be convenient if you e.g. use a YubiKey or similar hardware
    to store your encryption keys.

    Initializes the gpg encrypted vault from the given file and recipient.

    Parameters
    ----------
    manager : Manager
        The manager to which this vault is registered.
    file : str
        The file which serves as the permanent storage.
    recipient: str
        Only needed for encryption (when editing). Reflects the gpg
        command line parameter '--recipient'. If you don't plan on using
        the editing feature, the recipient may be set to None.
    """
    def __init__(self, manager, file: str, recipient: str):
        super().__init__(manager, file)
        self.recipient = recipient

    def decrypt_content(self, ciphertext: bytes) -> bytes:
        """
        Decrypts the given ciphertext.

        Parameters
        ----------
        ciphertext : bytes
            The bytes to decrypt.

        Returns
        -------
        bytes
            The plaintext
        """
        print(f"Decrypting gpg vault '{self.file}'")
        return subprocess.run(["gpg", "--quiet", "--decrypt"], input=ciphertext, capture_output=True, check=True).stdout

    def encrypt_content(self, plaintext: bytes) -> bytes:
        """
        Encrypts the given plaintext.

        Parameters
        ----------
        plaintext : bytes
            The bytes to encrypt.

        Returns
        -------
        bytes
            The ciphertext
        """
        if self.recipient is None:
            raise LogicError("GpgVault encryption requires a recipient")
        return subprocess.run(["gpg", "--quiet", "--encrypt", "--recipient", self.recipient], input=plaintext, capture_output=True, check=True).stdout
