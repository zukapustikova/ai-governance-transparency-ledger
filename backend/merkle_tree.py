"""Merkle tree implementation for selective disclosure proofs."""

from dataclasses import dataclass
from typing import Optional

from backend.crypto_utils import combine_hashes


@dataclass
class MerkleNode:
    """Node in a Merkle tree."""
    hash: str
    left: Optional['MerkleNode'] = None
    right: Optional['MerkleNode'] = None
    is_leaf: bool = False
    leaf_index: Optional[int] = None


@dataclass
class ProofStep:
    """Single step in a Merkle proof."""
    hash: str
    position: str  # "left" or "right"


class MerkleTree:
    """
    Merkle tree for efficient verification and selective disclosure.

    Allows proving that a specific event is part of the log
    without revealing all events.
    """

    def __init__(self, hashes: list[str]):
        """
        Build Merkle tree from list of hashes.

        Args:
            hashes: List of leaf hashes (event hashes)
        """
        self.leaf_count = len(hashes)
        self.root: Optional[MerkleNode] = None
        self.leaves: list[MerkleNode] = []

        if hashes:
            self._build_tree(hashes)

    def _build_tree(self, hashes: list[str]) -> None:
        """Build the tree from leaf hashes."""
        # Create leaf nodes
        self.leaves = [
            MerkleNode(hash=h, is_leaf=True, leaf_index=i)
            for i, h in enumerate(hashes)
        ]

        # Build tree bottom-up
        current_level = self.leaves

        while len(current_level) > 1:
            next_level = []

            for i in range(0, len(current_level), 2):
                left = current_level[i]

                # If odd number, duplicate last node
                if i + 1 < len(current_level):
                    right = current_level[i + 1]
                else:
                    right = left  # Duplicate for odd case

                parent_hash = combine_hashes(left.hash, right.hash)
                parent = MerkleNode(
                    hash=parent_hash,
                    left=left,
                    right=right
                )
                next_level.append(parent)

            current_level = next_level

        self.root = current_level[0] if current_level else None

    def get_root(self) -> Optional[str]:
        """Get the Merkle root hash."""
        return self.root.hash if self.root else None

    def get_proof(self, leaf_index: int) -> list[ProofStep]:
        """
        Generate proof for a specific leaf.

        Args:
            leaf_index: Index of the leaf to prove

        Returns:
            List of ProofSteps to verify inclusion
        """
        if leaf_index < 0 or leaf_index >= self.leaf_count:
            return []

        proof = []
        current_index = leaf_index
        current_level = self.leaves

        while len(current_level) > 1:
            # Determine sibling
            is_left = current_index % 2 == 0
            sibling_index = current_index + 1 if is_left else current_index - 1

            # Handle edge case for odd number of nodes
            if sibling_index < len(current_level):
                sibling = current_level[sibling_index]
                proof.append(ProofStep(
                    hash=sibling.hash,
                    position="right" if is_left else "left"
                ))
            else:
                # No sibling (odd case, node duplicated)
                proof.append(ProofStep(
                    hash=current_level[current_index].hash,
                    position="right"
                ))

            # Move up to next level
            current_index = current_index // 2
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                parent_hash = combine_hashes(left.hash, right.hash)
                next_level.append(MerkleNode(hash=parent_hash))
            current_level = next_level

        return proof

    @staticmethod
    def verify_proof(
        leaf_hash: str,
        proof: list[ProofStep],
        expected_root: str
    ) -> bool:
        """
        Verify a Merkle proof.

        Args:
            leaf_hash: Hash of the leaf being verified
            proof: Proof steps from get_proof()
            expected_root: Expected Merkle root

        Returns:
            True if proof is valid
        """
        current_hash = leaf_hash

        for step in proof:
            if step.position == "left":
                current_hash = combine_hashes(step.hash, current_hash)
            else:
                current_hash = combine_hashes(current_hash, step.hash)

        return current_hash == expected_root


def build_merkle_tree(event_hashes: list[str]) -> MerkleTree:
    """
    Convenience function to build a Merkle tree.

    Args:
        event_hashes: List of event hashes

    Returns:
        MerkleTree instance
    """
    return MerkleTree(event_hashes)


def generate_proof(tree: MerkleTree, event_index: int) -> tuple[list[ProofStep], str]:
    """
    Generate a Merkle proof for an event.

    Args:
        tree: MerkleTree instance
        event_index: Index of event to prove

    Returns:
        Tuple of (proof steps, merkle root)
    """
    return tree.get_proof(event_index), tree.get_root() or ""


def verify_merkle_proof(
    event_hash: str,
    proof: list[ProofStep],
    merkle_root: str
) -> bool:
    """
    Verify that an event is included in the tree.

    Args:
        event_hash: Hash of the event
        proof: Merkle proof steps
        merkle_root: Expected root hash

    Returns:
        True if event is verified as part of the tree
    """
    return MerkleTree.verify_proof(event_hash, proof, merkle_root)
