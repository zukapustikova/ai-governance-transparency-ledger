"""Cryptographic utilities for tamper-proof audit logging."""

import hashlib
import json
from typing import Any, Optional


def hash_data(data: dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of data with consistent key ordering.

    Args:
        data: Dictionary to hash

    Returns:
        Hexadecimal hash string
    """
    # Sort keys recursively for consistent hashing
    serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def hash_with_previous(data: dict[str, Any], previous_hash: Optional[str] = None) -> str:
    """
    Chain events together by including previous hash in computation.

    Args:
        data: Current event data to hash
        previous_hash: Hash of previous event (None for genesis)

    Returns:
        Hexadecimal hash string incorporating the chain
    """
    # Create a combined structure that includes the previous hash
    chain_data = {
        "previous_hash": previous_hash or "0" * 64,  # Genesis uses zeros
        "data": data
    }
    return hash_data(chain_data)


def verify_hash(data: dict[str, Any], expected_hash: str) -> bool:
    """
    Verify that data produces expected hash.

    Args:
        data: Data to verify
        expected_hash: Expected hash value

    Returns:
        True if hash matches, False otherwise
    """
    computed = hash_data(data)
    return computed == expected_hash


def verify_chain_hash(
    data: dict[str, Any],
    previous_hash: Optional[str],
    expected_hash: str
) -> bool:
    """
    Verify that data with previous hash produces expected chain hash.

    Args:
        data: Current event data
        previous_hash: Hash of previous event
        expected_hash: Expected hash value

    Returns:
        True if chain hash matches, False otherwise
    """
    computed = hash_with_previous(data, previous_hash)
    return computed == expected_hash


def combine_hashes(left: str, right: str) -> str:
    """
    Combine two hashes for Merkle tree construction.

    Args:
        left: Left child hash
        right: Right child hash

    Returns:
        Parent hash combining both children
    """
    combined = left + right
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def generate_anonymous_id(identity: str, salt: str) -> str:
    """
    Generate an anonymous but consistent ID for a whistleblower.

    The same identity + salt always produces the same anonymous ID,
    allowing consistent pseudonymous participation without revealing identity.

    Args:
        identity: The real identity (e.g., email)
        salt: A secret salt known only to the whistleblower

    Returns:
        Anonymous ID (first 16 chars of hash for readability)
    """
    combined = f"{identity}||{salt}"
    full_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    return f"anon_{full_hash[:12]}"


def verify_anonymous_id(identity: str, salt: str, anonymous_id: str) -> bool:
    """
    Verify that an identity/salt pair matches an anonymous ID.

    This allows a whistleblower to prove ownership of their anonymous ID
    to a trusted party (like an auditor) if needed.

    Args:
        identity: The claimed real identity
        salt: The secret salt
        anonymous_id: The anonymous ID to verify

    Returns:
        True if the identity/salt produces this anonymous ID
    """
    computed = generate_anonymous_id(identity, salt)
    return computed == anonymous_id
