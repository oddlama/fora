import subprocess
import json

class Vault:
    def __init__(self):
        decrypted = subprocess.run(["gpg", "--quiet", "--decrypt", "vault.gpg"], capture_output=True)
