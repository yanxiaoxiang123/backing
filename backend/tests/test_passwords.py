"""密码哈希测试：PBKDF2-HMAC-SHA256、每用户盐、恒定时间校验。"""

from app.passwords import hash_password, verify_password


class TestHashPassword:
    def test_hash_uses_pbkdf2_format(self):
        stored = hash_password("correct-horse-battery-staple")
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        assert algorithm == "pbkdf2_sha256"
        assert int(iterations) >= 100_000
        assert len(bytes.fromhex(salt_hex)) == 16
        assert len(bytes.fromhex(digest_hex)) == 32

    def test_hash_is_salted_per_call(self):
        first = hash_password("same-password")
        second = hash_password("same-password")
        assert first != second

    def test_hash_never_contains_the_plaintext(self):
        stored = hash_password("hunter2-very-secret")
        assert "hunter2" not in stored


class TestVerifyPassword:
    def test_accepts_matching_password(self):
        stored = hash_password("s3cret-pass")
        assert verify_password("s3cret-pass", stored) is True

    def test_rejects_wrong_password(self):
        stored = hash_password("s3cret-pass")
        assert verify_password("s3cret-pas", stored) is False

    def test_accepts_unicode_password(self):
        stored = hash_password("量化研究-密码")
        assert verify_password("量化研究-密码", stored) is True

    def test_rejects_empty_and_malformed_hashes(self):
        assert verify_password("anything", "") is False
        assert verify_password("anything", None) is False
        assert verify_password("anything", "not-a-hash") is False
        assert verify_password("anything", "bcrypt$1$abcd$ef") is False
        assert verify_password("anything", "pbkdf2_sha256$not-int$abcd$ef") is False
