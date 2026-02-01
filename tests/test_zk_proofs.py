"""Tests for Zero-Knowledge proof module."""

import os
import tempfile

import pytest

from backend.models import EventType
from backend.zk_proofs import ZKCommitmentStore


@pytest.fixture
def temp_zk_store():
    """Create a temporary ZK store for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    # Create store with a mock event count function
    event_counts = {EventType.SAFETY_EVAL_RUN: 5}

    def get_count(event_type):
        return event_counts.get(event_type, 0)

    store = ZKCommitmentStore(storage_path=temp_path, get_event_count=get_count)
    store._event_counts = event_counts  # Store reference for test manipulation
    yield store

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def configurable_zk_store():
    """Create a ZK store with configurable event count."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    counts = {"value": 10}

    def get_count(event_type):
        return counts["value"]

    store = ZKCommitmentStore(storage_path=temp_path, get_event_count=get_count)
    store._counts = counts  # For test manipulation
    yield store

    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestCommitmentCreation:
    """Tests for commitment creation."""

    def test_create_commitment(self, temp_zk_store):
        """Should create a commitment with required fields."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)

        assert commitment.id is not None
        assert len(commitment.id) == 16  # 8 bytes hex = 16 chars
        assert commitment.commitment_hash is not None
        assert len(commitment.commitment_hash) == 64  # SHA256 hex
        assert commitment.event_type == EventType.SAFETY_EVAL_RUN
        assert commitment.timestamp is not None

    def test_commitment_hides_count(self, temp_zk_store):
        """Commitment hash should not reveal the count in plaintext."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)

        # Hash should be valid SHA256 hex (64 chars)
        assert len(commitment.commitment_hash) == 64
        assert all(c in '0123456789abcdef' for c in commitment.commitment_hash)

        # The count is hidden - you cannot extract "count=5" from the hash
        # (Note: individual hex digits 0-9, a-f will appear, that's fine)
        # The key property: hash(5||blinding1) != hash(5||blinding2)
        # This is tested in test_different_commitments_same_count

    def test_different_commitments_same_count(self, temp_zk_store):
        """Two commitments to the same count should differ (random blinding)."""
        c1 = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        c2 = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)

        # Same event type, same count, but different hashes due to blinding
        assert c1.commitment_hash != c2.commitment_hash
        assert c1.id != c2.id

    def test_get_commitment(self, temp_zk_store):
        """Should retrieve a commitment by ID."""
        created = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        retrieved = temp_zk_store.get_commitment(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.commitment_hash == created.commitment_hash

    def test_get_nonexistent_commitment(self, temp_zk_store):
        """Should return None for invalid ID."""
        result = temp_zk_store.get_commitment("nonexistent")
        assert result is None


class TestProofGeneration:
    """Tests for ZK proof generation."""

    def test_valid_proof_when_count_meets_threshold(self, temp_zk_store):
        """Should generate valid proof when count >= threshold."""
        # Count is 5
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=3)

        assert proof is not None
        assert proof.is_valid is True
        assert proof.threshold == 3
        assert proof.excess_commitment != ""
        assert "verification_hash" in proof.proof_data
        assert "threshold_blinding" in proof.proof_data

    def test_valid_proof_when_count_equals_threshold(self, temp_zk_store):
        """Should generate valid proof when count == threshold."""
        # Count is 5
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=5)

        assert proof.is_valid is True
        assert proof.threshold == 5

    def test_invalid_proof_when_count_below_threshold(self, temp_zk_store):
        """Should generate invalid proof when count < threshold."""
        # Count is 5
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=10)

        assert proof.is_valid is False
        assert "error" in proof.proof_data
        assert proof.excess_commitment == ""

    def test_proof_for_nonexistent_commitment(self, temp_zk_store):
        """Should return None for invalid commitment ID."""
        proof = temp_zk_store.generate_proof("nonexistent", threshold=1)
        assert proof is None


class TestProofVerification:
    """Tests for ZK proof verification."""

    def test_verify_valid_proof(self, temp_zk_store):
        """Should verify a valid proof."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=3)

        is_valid, message = ZKCommitmentStore.verify_proof(
            commitment_hash=commitment.commitment_hash,
            threshold=proof.threshold,
            excess_commitment=proof.excess_commitment,
            proof_data=proof.proof_data
        )

        assert is_valid is True
        assert "count >= 3" in message

    def test_verify_invalid_proof(self, temp_zk_store):
        """Should reject an invalid proof."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=100)

        is_valid, message = ZKCommitmentStore.verify_proof(
            commitment_hash=commitment.commitment_hash,
            threshold=proof.threshold,
            excess_commitment=proof.excess_commitment,
            proof_data=proof.proof_data
        )

        assert is_valid is False
        assert "error" in message.lower() or "failed" in message.lower()

    def test_verify_tampered_proof(self, temp_zk_store):
        """Should reject a proof with tampered data."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=3)

        # Tamper with the verification hash
        tampered_proof_data = proof.proof_data.copy()
        tampered_proof_data["verification_hash"] = "0" * 64

        is_valid, message = ZKCommitmentStore.verify_proof(
            commitment_hash=commitment.commitment_hash,
            threshold=proof.threshold,
            excess_commitment=proof.excess_commitment,
            proof_data=tampered_proof_data
        )

        assert is_valid is False
        assert "mismatch" in message.lower() or "invalid" in message.lower()

    def test_verify_wrong_threshold(self, temp_zk_store):
        """Should reject proof verified with wrong threshold."""
        commitment = temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = temp_zk_store.generate_proof(commitment.id, threshold=3)

        # Try to verify with a different threshold
        is_valid, message = ZKCommitmentStore.verify_proof(
            commitment_hash=commitment.commitment_hash,
            threshold=4,  # Different from proof's threshold
            excess_commitment=proof.excess_commitment,
            proof_data=proof.proof_data
        )

        assert is_valid is False


class TestZKProperty:
    """Tests demonstrating the Zero-Knowledge property."""

    def test_zk_property_count_hidden(self, configurable_zk_store):
        """Two orgs with different counts, same threshold proof - indistinguishable."""
        store = configurable_zk_store

        # Org A has 10 events
        store._counts["value"] = 10
        commitment_a = store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof_a = store.generate_proof(commitment_a.id, threshold=5)

        # Org B has 50 events
        store._counts["value"] = 50
        commitment_b = store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof_b = store.generate_proof(commitment_b.id, threshold=5)

        # Both proofs are valid
        assert proof_a.is_valid is True
        assert proof_b.is_valid is True

        # Both have the same threshold
        assert proof_a.threshold == proof_b.threshold == 5

        # But the proofs don't reveal the actual counts
        # An observer cannot tell if count is 10 or 50
        # They only know count >= 5

        # The proof data structures are similar but values differ
        assert set(proof_a.proof_data.keys()) == set(proof_b.proof_data.keys())

        # Verify both proofs work
        valid_a, _ = ZKCommitmentStore.verify_proof(
            commitment_a.commitment_hash, 5, proof_a.excess_commitment, proof_a.proof_data
        )
        valid_b, _ = ZKCommitmentStore.verify_proof(
            commitment_b.commitment_hash, 5, proof_b.excess_commitment, proof_b.proof_data
        )
        assert valid_a is True
        assert valid_b is True

    def test_proof_does_not_reveal_excess(self, configurable_zk_store):
        """Proof for count=10, threshold=5 should not reveal that excess=5 in plaintext."""
        store = configurable_zk_store
        store._counts["value"] = 10

        commitment = store.create_commitment(EventType.SAFETY_EVAL_RUN)
        proof = store.generate_proof(commitment.id, threshold=5)

        # The excess_commitment is a SHA256 hash (64 hex chars)
        assert len(proof.excess_commitment) == 64
        assert all(c in '0123456789abcdef' for c in proof.excess_commitment)

        # The proof data values are all hashes (64 chars each)
        for key, value in proof.proof_data.items():
            if isinstance(value, str) and key != "error":
                assert len(value) == 64, f"{key} should be a hash"

        # The ZK property: a verifier cannot determine if excess=5 or excess=45
        # This is tested more thoroughly in test_zk_property_count_hidden


class TestPersistence:
    """Tests for ZK store persistence."""

    def test_persistence(self):
        """Commitments should persist across instances."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create store and add commitment
            store1 = ZKCommitmentStore(
                storage_path=temp_path,
                get_event_count=lambda _: 5
            )
            commitment = store1.create_commitment(EventType.SAFETY_EVAL_RUN)

            # Load in new instance
            store2 = ZKCommitmentStore(
                storage_path=temp_path,
                get_event_count=lambda _: 5
            )

            retrieved = store2.get_commitment(commitment.id)
            assert retrieved is not None
            assert retrieved.commitment_hash == commitment.commitment_hash

            # Should also be able to generate proofs
            proof = store2.generate_proof(commitment.id, threshold=3)
            assert proof is not None
            assert proof.is_valid is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_reset(self, temp_zk_store):
        """Reset should clear all commitments."""
        temp_zk_store.create_commitment(EventType.SAFETY_EVAL_RUN)
        assert len(temp_zk_store.commitments) == 1

        temp_zk_store.reset()
        assert len(temp_zk_store.commitments) == 0
