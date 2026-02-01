"""Tests for role-based authentication system."""

import os
import tempfile

import pytest

from backend.auth import AuthStore, RateLimiter


@pytest.fixture
def temp_auth_store():
    """Create a temporary auth store for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    store = AuthStore(storage_path=temp_path)
    yield store

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestAuthStore:
    """Tests for AuthStore class."""

    def test_register_party_returns_id_and_key(self, temp_auth_store):
        """Registration returns party_id and api_key."""
        party_id, api_key = temp_auth_store.register_party("Test Lab", "lab")

        assert party_id.startswith("party_")
        assert api_key.startswith("afr_")
        assert len(party_id) == 22  # party_ + 16 hex chars
        assert len(api_key) > 30

    def test_register_party_invalid_role(self, temp_auth_store):
        """Registration with invalid role raises error."""
        with pytest.raises(ValueError, match="Invalid role"):
            temp_auth_store.register_party("Test Lab", "invalid_role")

    def test_verify_valid_api_key(self, temp_auth_store):
        """Valid API key returns party."""
        party_id, api_key = temp_auth_store.register_party("Test Lab", "lab")
        party = temp_auth_store.verify_api_key(api_key)

        assert party is not None
        assert party.party_id == party_id
        assert party.name == "Test Lab"
        assert party.role == "lab"

    def test_verify_invalid_api_key(self, temp_auth_store):
        """Invalid API key returns None."""
        party = temp_auth_store.verify_api_key("invalid_key")
        assert party is None

    def test_revoke_party(self, temp_auth_store):
        """Revoked party's API key no longer works."""
        party_id, api_key = temp_auth_store.register_party("Test Lab", "lab")
        assert temp_auth_store.verify_api_key(api_key) is not None

        result = temp_auth_store.revoke_party(party_id)
        assert result is True

        # API key should no longer work
        assert temp_auth_store.verify_api_key(api_key) is None

    def test_revoke_nonexistent_party(self, temp_auth_store):
        """Revoking nonexistent party returns False."""
        result = temp_auth_store.revoke_party("nonexistent_id")
        assert result is False

    def test_list_parties(self, temp_auth_store):
        """List parties returns all registered parties."""
        temp_auth_store.register_party("Lab 1", "lab")
        temp_auth_store.register_party("Auditor 1", "auditor")

        parties = temp_auth_store.list_parties()
        assert len(parties) == 2
        names = [p.name for p in parties]
        assert "Lab 1" in names
        assert "Auditor 1" in names

    def test_get_party(self, temp_auth_store):
        """Get party by ID."""
        party_id, _ = temp_auth_store.register_party("Test Lab", "lab")
        party = temp_auth_store.get_party(party_id)

        assert party is not None
        assert party.name == "Test Lab"

    def test_persistence(self, temp_auth_store):
        """Auth store persists data to file."""
        party_id, api_key = temp_auth_store.register_party("Test Lab", "lab")

        # Create new store from same path
        store2 = AuthStore(storage_path=temp_auth_store.storage_path)

        party = store2.verify_api_key(api_key)
        assert party is not None
        assert party.name == "Test Lab"

    def test_all_roles_valid(self, temp_auth_store):
        """All valid roles can be registered."""
        for role in ["lab", "auditor", "government"]:
            party_id, api_key = temp_auth_store.register_party(f"Test {role}", role)
            party = temp_auth_store.verify_api_key(api_key)
            assert party.role == role


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_within_limit(self):
        """Requests within limit are allowed."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        for _ in range(3):
            assert limiter.is_allowed("test_ip")
            limiter.record_request("test_ip")

    def test_blocks_over_limit(self):
        """Requests over limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)

        for _ in range(3):
            assert limiter.is_allowed("test_ip")
            limiter.record_request("test_ip")

        # 4th request should be blocked
        assert not limiter.is_allowed("test_ip")

    def test_different_keys_independent(self):
        """Different keys have independent limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        for _ in range(2):
            limiter.record_request("ip1")

        # ip1 is at limit
        assert not limiter.is_allowed("ip1")

        # ip2 is still allowed
        assert limiter.is_allowed("ip2")

    def test_get_remaining(self):
        """Get remaining returns correct count."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        assert limiter.get_remaining("test_ip") == 5

        limiter.record_request("test_ip")
        assert limiter.get_remaining("test_ip") == 4

        limiter.record_request("test_ip")
        limiter.record_request("test_ip")
        assert limiter.get_remaining("test_ip") == 2

    def test_reset_clears_all(self):
        """Reset clears all rate limit tracking."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        for _ in range(2):
            limiter.record_request("test_ip")

        assert not limiter.is_allowed("test_ip")

        limiter.reset()
        assert limiter.is_allowed("test_ip")


class TestKeyRotation:
    """Tests for API key rotation."""

    def test_rotate_generates_new_key(self, temp_auth_store):
        """Rotation generates a new API key."""
        party_id, old_key = temp_auth_store.register_party("Test Lab", "lab")

        new_key = temp_auth_store.rotate_api_key(party_id)

        assert new_key is not None
        assert new_key != old_key
        assert new_key.startswith("afr_")

    def test_old_key_invalid_after_rotation(self, temp_auth_store):
        """Old API key no longer works after rotation."""
        party_id, old_key = temp_auth_store.register_party("Test Lab", "lab")

        new_key = temp_auth_store.rotate_api_key(party_id)

        # Old key should not work
        assert temp_auth_store.verify_api_key(old_key) is None

        # New key should work
        party = temp_auth_store.verify_api_key(new_key)
        assert party is not None
        assert party.party_id == party_id

    def test_rotate_nonexistent_party(self, temp_auth_store):
        """Rotating for nonexistent party returns None."""
        result = temp_auth_store.rotate_api_key("nonexistent_id")
        assert result is None

    def test_rotate_revoked_party(self, temp_auth_store):
        """Cannot rotate key for revoked party."""
        party_id, _ = temp_auth_store.register_party("Test Lab", "lab")
        temp_auth_store.revoke_party(party_id)

        result = temp_auth_store.rotate_api_key(party_id)
        assert result is None

    def test_rotation_persists(self, temp_auth_store):
        """Rotated key persists to storage."""
        party_id, old_key = temp_auth_store.register_party("Test Lab", "lab")
        new_key = temp_auth_store.rotate_api_key(party_id)

        # Create new store from same path
        store2 = AuthStore(storage_path=temp_auth_store.storage_path)

        # Old key should not work
        assert store2.verify_api_key(old_key) is None

        # New key should work
        party = store2.verify_api_key(new_key)
        assert party is not None
