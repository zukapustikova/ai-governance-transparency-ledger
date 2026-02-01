"""Tests for Merkle tree implementation."""

import pytest

from backend.crypto_utils import hash_data
from backend.merkle_tree import (
    MerkleTree,
    ProofStep,
    build_merkle_tree,
    generate_proof,
    verify_merkle_proof,
)


class TestMerkleTreeConstruction:
    """Tests for Merkle tree building."""

    def test_empty_tree(self):
        """Empty tree should have no root."""
        tree = MerkleTree([])
        assert tree.get_root() is None

    def test_single_leaf(self):
        """Single leaf tree should have leaf as root."""
        h = hash_data({"event": "single"})
        tree = MerkleTree([h])

        # Root should be hash of single leaf combined with itself
        assert tree.get_root() is not None
        assert tree.leaf_count == 1

    def test_two_leaves(self):
        """Two leaf tree should combine properly."""
        h1 = hash_data({"event": "one"})
        h2 = hash_data({"event": "two"})
        tree = MerkleTree([h1, h2])

        assert tree.get_root() is not None
        assert tree.leaf_count == 2

    def test_power_of_two_leaves(self):
        """Power of 2 leaves should build balanced tree."""
        hashes = [hash_data({"event": i}) for i in range(8)]
        tree = MerkleTree(hashes)

        assert tree.get_root() is not None
        assert tree.leaf_count == 8

    def test_odd_number_leaves(self):
        """Odd number of leaves should be handled."""
        hashes = [hash_data({"event": i}) for i in range(5)]
        tree = MerkleTree(hashes)

        assert tree.get_root() is not None
        assert tree.leaf_count == 5

    def test_deterministic_root(self):
        """Same leaves should produce same root."""
        hashes = [hash_data({"event": i}) for i in range(4)]

        tree1 = MerkleTree(hashes)
        tree2 = MerkleTree(hashes)

        assert tree1.get_root() == tree2.get_root()

    def test_different_leaves_different_root(self):
        """Different leaves should produce different root."""
        hashes1 = [hash_data({"event": i}) for i in range(4)]
        hashes2 = [hash_data({"event": i + 100}) for i in range(4)]

        tree1 = MerkleTree(hashes1)
        tree2 = MerkleTree(hashes2)

        assert tree1.get_root() != tree2.get_root()


class TestMerkleProof:
    """Tests for Merkle proof generation and verification."""

    def test_proof_single_leaf(self):
        """Proof for single leaf tree."""
        h = hash_data({"event": "only"})
        tree = MerkleTree([h])

        proof = tree.get_proof(0)
        root = tree.get_root()

        # Should verify
        assert MerkleTree.verify_proof(h, proof, root) is True

    def test_proof_two_leaves(self):
        """Proof for two leaf tree."""
        h1 = hash_data({"event": "first"})
        h2 = hash_data({"event": "second"})
        tree = MerkleTree([h1, h2])

        # Proof for first leaf
        proof1 = tree.get_proof(0)
        assert MerkleTree.verify_proof(h1, proof1, tree.get_root()) is True

        # Proof for second leaf
        proof2 = tree.get_proof(1)
        assert MerkleTree.verify_proof(h2, proof2, tree.get_root()) is True

    def test_proof_larger_tree(self):
        """Proof for larger tree."""
        hashes = [hash_data({"event": i}) for i in range(8)]
        tree = MerkleTree(hashes)

        # Verify all leaves
        for i, h in enumerate(hashes):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(h, proof, tree.get_root()) is True

    def test_proof_odd_tree(self):
        """Proof for odd-sized tree."""
        hashes = [hash_data({"event": i}) for i in range(7)]
        tree = MerkleTree(hashes)

        for i, h in enumerate(hashes):
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(h, proof, tree.get_root()) is True

    def test_invalid_proof_wrong_hash(self):
        """Proof should fail with wrong leaf hash."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)
        wrong_hash = hash_data({"event": "wrong"})

        assert MerkleTree.verify_proof(wrong_hash, proof, tree.get_root()) is False

    def test_invalid_proof_wrong_root(self):
        """Proof should fail with wrong root."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)
        wrong_root = hash_data({"event": "wrong_root"})

        assert MerkleTree.verify_proof(hashes[0], proof, wrong_root) is False

    def test_invalid_proof_modified(self):
        """Proof should fail if modified."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = MerkleTree(hashes)

        proof = tree.get_proof(0)

        # Modify proof
        if proof:
            modified_proof = [ProofStep(hash="wrong", position=proof[0].position)] + proof[1:]
            assert MerkleTree.verify_proof(hashes[0], modified_proof, tree.get_root()) is False

    def test_invalid_index(self):
        """Should return empty proof for invalid index."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = MerkleTree(hashes)

        assert tree.get_proof(-1) == []
        assert tree.get_proof(4) == []
        assert tree.get_proof(100) == []


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_build_merkle_tree(self):
        """build_merkle_tree should work correctly."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = build_merkle_tree(hashes)

        assert tree.get_root() is not None
        assert tree.leaf_count == 4

    def test_generate_proof(self):
        """generate_proof should return proof and root."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = build_merkle_tree(hashes)

        proof, root = generate_proof(tree, 2)

        assert len(proof) > 0
        assert root == tree.get_root()

    def test_verify_merkle_proof_function(self):
        """verify_merkle_proof function should work."""
        hashes = [hash_data({"event": i}) for i in range(4)]
        tree = build_merkle_tree(hashes)

        proof, root = generate_proof(tree, 1)

        assert verify_merkle_proof(hashes[1], proof, root) is True
        assert verify_merkle_proof(hashes[0], proof, root) is False


class TestEdgeCases:
    """Edge case tests."""

    def test_large_tree(self):
        """Should handle large trees."""
        hashes = [hash_data({"event": i}) for i in range(1000)]
        tree = MerkleTree(hashes)

        assert tree.get_root() is not None

        # Spot check some proofs
        for i in [0, 499, 999]:
            proof = tree.get_proof(i)
            assert MerkleTree.verify_proof(hashes[i], proof, tree.get_root()) is True

    def test_proof_length(self):
        """Proof length should be log2(n)."""
        for n in [2, 4, 8, 16, 32]:
            hashes = [hash_data({"event": i}) for i in range(n)]
            tree = MerkleTree(hashes)
            proof = tree.get_proof(0)

            # Proof length should be approximately log2(n)
            import math
            expected_length = math.ceil(math.log2(n))
            assert len(proof) == expected_length
