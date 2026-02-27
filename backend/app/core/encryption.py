"""
Credential encryption service using Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet
import base64
import hashlib
from app.config import settings


class CredentialEncryption:
    """
    Handles encryption and decryption of AWS credentials.
    Uses Fernet symmetric encryption with a key derived from SECRET_KEY.
    """

    def __init__(self):
        """Initialize encryption with key derived from SECRET_KEY."""
        # Derive a Fernet key from the SECRET_KEY
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return ""

        encrypted = self.fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted_text: Encrypted string to decrypt

        Returns:
            Decrypted plaintext string
        """
        if not encrypted_text:
            return ""

        decrypted = self.fernet.decrypt(encrypted_text.encode())
        return decrypted.decode()


# Global instance
credential_encryption = CredentialEncryption()
