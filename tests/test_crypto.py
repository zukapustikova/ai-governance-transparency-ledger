"""Tests for crypto utilities."""

import pytest
from backend.crypto_utils import (
    hash_data,
    hash_with_previous,
    verify_hash,
    verify_chain_hash,
    combine_hashes,
)


class TestHashData:
    """Tests for hash_data function."""

    def test_consistent_hashing(self):
        """Same data should produce same hash."""
        data = {"name": "test", "value": 42}
        hash1 = hash_data(data)
        hash2 = hash_data(data)
        assert hash1 == hash2

    def test_different_data_different_hash(self):
        """Different data should produce different hashes."""
        data1 = {"name": "test1"}
        data2 = {"name": "test2"}
        assert hash_data(data1) != hash_data(data2)

    def test_key_order_independence(self):
        """Key order should not affect hash."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        assert hash_data(data1) == hash_data(data2)

    def test_hash_format(self):
        """Hash should be 64-character hex string."""
        data = {"test": True}
        h = hash_data(data)
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)

    def test_nested_dict_consistency(self):
        """Nested dicts should hash consistently."""
        data1 = {"outer": {"inner": {"deep": 1}}}
        data2 = {"outer": {"inner": {"deep": 1}}}
        assert hash_data(data1) == hash_data(data2)


class TestHashWithPrevious:
    """Tests for hash_with_previous function."""

    def test_genesis_block(self):
        """Genesis block should use zero hash."""
        data = {"event": "genesis"}
        h1 = hash_with_previous(data, None)
        h2 = hash_with_previous(data, None)
        assert h1 == h2

    def test_chain_dependency(self):
        """Hash should change with different previous hash."""
        data = {"event": "test"}
        h1 = hash_with_previous(data, "abc123")
        h2 = hash_with_previous(data, "def456")
        assert h1 != h2

    def test_data_dependency(self):
        """Hash should change with different data."""
        prev = "abc123"
        h1 = hash_with_previous({"event": "a"}, prev)
        h2 = hash_with_previous({"event": "b"}, prev)
        assert h1 != h2


class TestVerifyHash:
    """Tests for verify_hash function."""

    def test_valid_hash(self):
        """Should return True for matching hash."""
        data = {"test": "data"}
        h = hash_data(data)
        assert verify_hash(data, h) is True

    def test_invalid_hash(self):
        """Should return False for non-matching hash."""
        data = {"test": "data"}
        assert verify_hash(data, "wrong_hash") is False

    def test_tampered_data(self):
        """Should detect data tampering."""
        original = {"value": 100}
        h = hash_data(original)
        tampered = {"value": 101}
        assert verify_hash(tampered, h) is False


class TestVerifyChainHash:
    """Tests for verify_chain_hash function."""

    def test_valid_chain(self):
        """Should verify valid chain hash."""
        data = {"event": "test"}
        prev = "prev_hash"
        h = hash_with_previous(data, prev)
        assert verify_chain_hash(data, prev, h) is True

    def test_invalid_chain(self):
        """Should detect invalid chain hash."""
        data = {"event": "test"}
        prev = "prev_hash"
        assert verify_chain_hash(data, prev, "wrong") is False

    def test_tampered_previous(self):
        """Should detect tampering with previous hash reference."""
        data = {"event": "test"}
        h = hash_with_previous(data, "original_prev")
        assert verify_chain_hash(data, "tampered_prev", h) is False


class TestCombineHashes:
    """Tests for combine_hashes function."""

    def test_deterministic(self):
        """Combining same hashes should give same result."""
        left = "a" * 64
        right = "b" * 64
        h1 = combine_hashes(left, right)
        h2 = combine_hashes(left, right)
        assert h1 == h2

    def test_order_matters(self):
        """Order of hashes should matter."""
        left = "a" * 64
        right = "b" * 64
        h1 = combine_hashes(left, right)
        h2 = combine_hashes(right, left)
        assert h1 != h2

    def test_output_format(self):
        """Output should be valid SHA-256 hash."""
        h = combine_hashes("a" * 64, "b" * 64)
        assert len(h) == 64
        assert all(c in '0123456789abcdef' for c in h)
