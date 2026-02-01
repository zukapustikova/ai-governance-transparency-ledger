"""API key authentication and role-based authorization for AI Governance Transparency Ledger."""

import hashlib
import json
import secrets
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException, Depends, Request


class AuthorizedParty:
    """Represents an authorized party in the system."""

    def __init__(
        self,
        party_id: str,
        name: str,
        role: str,
        api_key_hash: str,
        created_at: datetime,
        is_active: bool = True
    ):
        self.party_id = party_id
        self.name = name
        self.role = role
        self.api_key_hash = api_key_hash
        self.created_at = created_at
        self.is_active = is_active

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "party_id": self.party_id,
            "name": self.name,
            "role": self.role,
            "api_key_hash": self.api_key_hash,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthorizedParty":
        """Create from dictionary."""
        return cls(
            party_id=data["party_id"],
            name=data["name"],
            role=data["role"],
            api_key_hash=data["api_key_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            is_active=data.get("is_active", True)
        )


class AuthStore:
    """Manages API keys and authorized parties."""

    VALID_ROLES = {"lab", "auditor", "government"}

    def __init__(self, storage_path: str = "data/auth_store.json"):
        self.storage_path = Path(storage_path)
        self.parties: dict[str, AuthorizedParty] = {}
        self._load()

    def _load(self) -> None:
        """Load parties from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    content = f.read()
                    if content.strip():  # Only parse if file has content
                        data = json.loads(content)
                        for party_data in data.get("parties", []):
                            party = AuthorizedParty.from_dict(party_data)
                            self.parties[party.party_id] = party
            except json.JSONDecodeError:
                # File exists but is empty or invalid - start fresh
                pass

    def _save(self) -> None:
        """Save parties to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "parties": [p.to_dict() for p in self.parties.values()]
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """Hash an API key for secure storage."""
        return hashlib.sha256(api_key.encode('utf-8')).hexdigest()

    @staticmethod
    def _generate_party_id() -> str:
        """Generate a unique party ID."""
        return f"party_{secrets.token_hex(8)}"

    @staticmethod
    def _generate_api_key() -> str:
        """Generate a secure API key."""
        return f"afr_{secrets.token_urlsafe(32)}"

    def register_party(self, name: str, role: str) -> tuple[str, str]:
        """
        Register a new authorized party.

        Args:
            name: Display name of the party
            role: Role (lab, auditor, or government)

        Returns:
            Tuple of (party_id, api_key) - api_key is only returned once!

        Raises:
            ValueError: If role is invalid
        """
        if role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of: {self.VALID_ROLES}")

        party_id = self._generate_party_id()
        api_key = self._generate_api_key()
        api_key_hash = self._hash_api_key(api_key)

        party = AuthorizedParty(
            party_id=party_id,
            name=name,
            role=role,
            api_key_hash=api_key_hash,
            created_at=datetime.utcnow(),
            is_active=True
        )

        self.parties[party_id] = party
        self._save()

        return party_id, api_key

    def verify_api_key(self, api_key: str) -> Optional[AuthorizedParty]:
        """
        Verify an API key and return the associated party.

        Args:
            api_key: The API key to verify

        Returns:
            AuthorizedParty if valid, None otherwise
        """
        api_key_hash = self._hash_api_key(api_key)

        for party in self.parties.values():
            if party.api_key_hash == api_key_hash and party.is_active:
                return party

        return None

    def revoke_party(self, party_id: str) -> bool:
        """
        Revoke access for a party.

        Args:
            party_id: The party ID to revoke

        Returns:
            True if revoked, False if party not found
        """
        if party_id not in self.parties:
            return False

        self.parties[party_id].is_active = False
        self._save()
        return True

    def list_parties(self) -> list[AuthorizedParty]:
        """
        List all registered parties.

        Returns:
            List of all parties (active and inactive)
        """
        return list(self.parties.values())

    def get_party(self, party_id: str) -> Optional[AuthorizedParty]:
        """Get a party by ID."""
        return self.parties.get(party_id)

    def rotate_api_key(self, party_id: str) -> Optional[str]:
        """
        Rotate the API key for a party.

        Generates a new API key and invalidates the old one.

        Args:
            party_id: The party ID to rotate the key for

        Returns:
            The new API key if successful, None if party not found or inactive
        """
        party = self.parties.get(party_id)
        if not party or not party.is_active:
            return None

        # Generate new key
        new_api_key = self._generate_api_key()
        new_api_key_hash = self._hash_api_key(new_api_key)

        # Update the party's key hash
        party.api_key_hash = new_api_key_hash
        self._save()

        return new_api_key

    def reset(self) -> None:
        """Reset the auth store (for testing/demo)."""
        self.parties = {}
        self._save()


# Global auth store instance
auth_store = AuthStore()


class RateLimiter:
    """Simple in-memory rate limiter for registration endpoint."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[datetime]] = defaultdict(list)

    def _cleanup_old_requests(self, key: str) -> None:
        """Remove requests outside the current window."""
        now = datetime.utcnow()
        cutoff = now.timestamp() - self.window_seconds
        self._requests[key] = [
            req for req in self._requests[key]
            if req.timestamp() > cutoff
        ]

    def is_allowed(self, key: str) -> bool:
        """
        Check if a request is allowed for the given key.

        Args:
            key: Identifier for rate limiting (e.g., IP address)

        Returns:
            True if allowed, False if rate limited
        """
        self._cleanup_old_requests(key)
        return len(self._requests[key]) < self.max_requests

    def record_request(self, key: str) -> None:
        """Record a request for the given key."""
        self._requests[key].append(datetime.utcnow())

    def get_remaining(self, key: str) -> int:
        """Get remaining requests in current window."""
        self._cleanup_old_requests(key)
        return max(0, self.max_requests - len(self._requests[key]))

    def reset(self) -> None:
        """Reset all rate limit tracking (for testing/demo)."""
        self._requests.clear()


# Global rate limiter for registration: 5 requests per minute per IP
registration_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


# FastAPI dependencies

async def check_registration_rate_limit(request: Request) -> None:
    """
    FastAPI dependency to check rate limit for registration.

    Raises HTTPException 429 if rate limit exceeded.
    """
    # Use client IP as rate limit key
    client_ip = request.client.host if request.client else "unknown"

    if not registration_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 5 registrations per minute. Please try again later."
        )

    # Record this request
    registration_rate_limiter.record_request(client_ip)


async def get_current_party(x_api_key: str = Header(None)) -> AuthorizedParty:
    """
    FastAPI dependency to get the current authenticated party.

    Raises HTTPException 401 if no valid API key provided.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )

    party = auth_store.verify_api_key(x_api_key)
    if not party:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key."
        )

    return party


