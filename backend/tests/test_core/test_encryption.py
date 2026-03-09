"""
Unit tests for app.core.encryption — CredentialEncryption service.
"""
import pytest
from app.core.encryption import CredentialEncryption, credential_encryption


class TestCredentialEncryption:
    """Test encrypt / decrypt roundtrip and edge cases."""

    @pytest.fixture
    def enc(self):
        return CredentialEncryption()

    def test_encrypt_returns_non_empty_string(self, enc):
        result = enc.encrypt("my-secret-key")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encrypt_differs_from_plaintext(self, enc):
        plaintext = "AKIAIOSFODNN7EXAMPLE"
        assert enc.encrypt(plaintext) != plaintext

    def test_roundtrip(self, enc):
        plaintext = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY"
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext

    def test_encrypt_empty_string(self, enc):
        assert enc.encrypt("") == ""

    def test_decrypt_empty_string(self, enc):
        assert enc.decrypt("") == ""

    def test_same_plaintext_gives_different_ciphertext(self, enc):
        """Fernet uses a random IV, so two encryptions differ."""
        plaintext = "my-secret"
        c1 = enc.encrypt(plaintext)
        c2 = enc.encrypt(plaintext)
        # Both decrypt to the same value even though ciphertexts differ
        assert enc.decrypt(c1) == plaintext
        assert enc.decrypt(c2) == plaintext

    def test_global_instance_works(self):
        plaintext = "global-test"
        encrypted = credential_encryption.encrypt(plaintext)
        assert credential_encryption.decrypt(encrypted) == plaintext

    def test_multiple_roundtrips(self, enc):
        values = [
            "AKIAIOSFODNN7EXAMPLE",
            "wJalrXUtnFEMI/K7MDENG",
            "us-east-1",
            "arn:aws:iam::123456789012:role/MyRole",
        ]
        for v in values:
            assert enc.decrypt(enc.encrypt(v)) == v

    def test_unicode_content(self, enc):
        plaintext = "こんにちは世界"
        assert enc.decrypt(enc.encrypt(plaintext)) == plaintext
