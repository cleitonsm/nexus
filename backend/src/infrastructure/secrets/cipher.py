from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SecretDecryptionError(ValueError):
    pass


class FernetSecretCipher:
    def __init__(self, master_key: str) -> None:
        if not master_key.strip():
            raise ValueError("NEXUS_SECRETS_KEY must not be empty.")
        digest = hashlib.sha256(master_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        token = self._fernet.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken as exc:
            raise SecretDecryptionError("Unable to decrypt stored secret.") from exc
        return decrypted.decode("utf-8")
