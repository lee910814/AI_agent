"""BYOK 암호화 유틸리티 테스트."""

import pytest

from app.core.encryption import decrypt_api_key, encrypt_api_key


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        """암호화 후 복호화하면 원본이 복원된다."""
        original = "sk-test-api-key-1234567890"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    def test_encrypted_is_different_from_original(self):
        """암호화 결과는 원본과 달라야 한다."""
        original = "sk-test-api-key"
        encrypted = encrypt_api_key(original)
        assert encrypted != original

    def test_different_plaintexts_produce_different_ciphertexts(self):
        """서로 다른 평문은 서로 다른 암호문을 생성한다."""
        enc1 = encrypt_api_key("key-one")
        enc2 = encrypt_api_key("key-two")
        assert enc1 != enc2

    def test_decrypt_invalid_ciphertext_raises(self):
        """잘못된 암호문 복호화 시 ValueError가 발생한다."""
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_api_key("invalid-ciphertext-data")

    def test_empty_key_encrypt_decrypt(self):
        """빈 문자열도 암/복호화된다."""
        encrypted = encrypt_api_key("")
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == ""

    def test_unicode_key_roundtrip(self):
        """유니코드 키도 라운드트립 성공."""
        original = "sk-테스트-키-🔑"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original
