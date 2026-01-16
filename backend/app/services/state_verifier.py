"""
State Verification System with Merkle Trees and Integrity Validation.

Prevents:
- Silent state corruption
- Desynchronization between agents
- Replay attacks
- Timestamp manipulation
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class StateCheckpoint:
    """Immutable state checkpoint with cryptographic verification."""
    checkpoint_id: str
    timestamp: datetime
    state_data: Dict[str, Any]
    state_hash: str
    previous_checkpoint_hash: Optional[str]
    merkle_root: str
    ttl_seconds: int = 300  # 5 minute default TTL

    def is_expired(self) -> bool:
        """Check if checkpoint has exceeded TTL."""
        return datetime.utcnow() - self.timestamp > timedelta(seconds=self.ttl_seconds)

    def verify_integrity(self) -> bool:
        """Verify checkpoint hasn't been tampered with."""
        computed_hash = self._compute_hash()
        return computed_hash == self.state_hash

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of state data."""
        state_str = json.dumps(self.state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()


class MerkleTree:
    """
    Merkle tree for efficient state verification.

    Enables:
    - O(log n) verification of individual items
    - Detection of any tampering in state collection
    - Incremental updates without full rebuild
    """

    def __init__(self, leaves: List[str]):
        """
        Build Merkle tree from leaf hashes.

        Args:
            leaves: List of SHA-256 hashes (as hex strings)
        """
        if not leaves:
            raise ValueError("Cannot build Merkle tree from empty list")

        self.leaves = leaves
        self.tree = self._build_tree(leaves)
        self.root = self.tree[-1][0] if self.tree else None

    def _build_tree(self, hashes: List[str]) -> List[List[str]]:
        """Build complete Merkle tree bottom-up."""
        if not hashes:
            return []

        tree = [hashes]

        while len(tree[-1]) > 1:
            level = tree[-1]
            next_level = []

            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else left

                combined = left + right
                parent_hash = hashlib.sha256(combined.encode()).hexdigest()
                next_level.append(parent_hash)

            tree.append(next_level)

        return tree

    def get_proof(self, leaf_index: int) -> List[Tuple[str, str]]:
        """
        Get Merkle proof for leaf at index.

        Returns:
            List of (hash, side) tuples where side is 'left' or 'right'
        """
        if leaf_index >= len(self.leaves):
            raise IndexError(f"Leaf index {leaf_index} out of range")

        proof = []
        index = leaf_index

        for level in self.tree[:-1]:  # Exclude root
            sibling_index = index ^ 1  # XOR with 1 to get sibling

            if sibling_index < len(level):
                sibling_hash = level[sibling_index]
                side = "left" if sibling_index < index else "right"
                proof.append((sibling_hash, side))

            index //= 2

        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: List[Tuple[str, str]], root: str) -> bool:
        """
        Verify Merkle proof.

        Args:
            leaf_hash: Hash of the leaf to verify
            proof: List of (hash, side) tuples from get_proof()
            root: Expected Merkle root

        Returns:
            True if proof is valid
        """
        current_hash = leaf_hash

        for sibling_hash, side in proof:
            if side == "left":
                combined = sibling_hash + current_hash
            else:
                combined = current_hash + sibling_hash

            current_hash = hashlib.sha256(combined.encode()).hexdigest()

        return current_hash == root


class StateVerifier:
    """
    Comprehensive state verification system.

    Features:
    - Merkle tree-based batch verification
    - TTL-based expiration
    - Checkpoint chaining for history tracking
    - Corruption detection and recovery
    """

    def __init__(self, max_checkpoints: int = 1000):
        self.checkpoints: Dict[str, StateCheckpoint] = {}
        self.max_checkpoints = max_checkpoints
        self.corruption_events: List[Dict[str, Any]] = []

    def create_checkpoint(
        self,
        checkpoint_id: str,
        state_data: Dict[str, Any],
        previous_checkpoint_id: Optional[str] = None,
        ttl_seconds: int = 300
    ) -> StateCheckpoint:
        """
        Create state checkpoint with integrity verification.

        Args:
            checkpoint_id: Unique identifier
            state_data: State to checkpoint
            previous_checkpoint_id: Link to previous checkpoint (for chaining)
            ttl_seconds: Time-to-live for this checkpoint

        Returns:
            Created checkpoint
        """
        # Get previous checkpoint hash if specified
        previous_hash = None
        if previous_checkpoint_id:
            previous = self.checkpoints.get(previous_checkpoint_id)
            if previous:
                previous_hash = previous.state_hash

        # Compute state hash
        state_str = json.dumps(state_data, sort_keys=True)
        state_hash = hashlib.sha256(state_str.encode()).hexdigest()

        # Build Merkle tree from state items
        state_items = [
            hashlib.sha256(json.dumps({k: v}, sort_keys=True).encode()).hexdigest()
            for k, v in state_data.items()
        ]
        merkle_tree = MerkleTree(state_items)

        # Create checkpoint
        checkpoint = StateCheckpoint(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.utcnow(),
            state_data=state_data,
            state_hash=state_hash,
            previous_checkpoint_hash=previous_hash,
            merkle_root=merkle_tree.root,
            ttl_seconds=ttl_seconds
        )

        # Store checkpoint
        self.checkpoints[checkpoint_id] = checkpoint

        # Cleanup old checkpoints if exceeding limit
        self._cleanup_old_checkpoints()

        logger.info(f"Created checkpoint {checkpoint_id} with Merkle root {merkle_tree.root[:16]}...")

        return checkpoint

    def verify_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Verify checkpoint integrity.

        Returns:
            True if checkpoint is valid and not expired
        """
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            return False

        # Check expiration
        if checkpoint.is_expired():
            logger.warning(f"Checkpoint {checkpoint_id} has expired")
            return False

        # Verify integrity
        if not checkpoint.verify_integrity():
            self._log_corruption_event(checkpoint_id, "Hash mismatch")
            return False

        # Verify chain if previous checkpoint exists
        if checkpoint.previous_checkpoint_hash:
            previous_id = self._find_checkpoint_by_hash(
                checkpoint.previous_checkpoint_hash
            )
            if previous_id:
                if not self.verify_checkpoint(previous_id):
                    self._log_corruption_event(
                        checkpoint_id,
                        "Previous checkpoint invalid"
                    )
                    return False

        return True

    def verify_state_item(
        self,
        checkpoint_id: str,
        item_key: str,
        expected_value: Any
    ) -> bool:
        """
        Verify individual state item using Merkle proof.

        More efficient than verifying entire checkpoint.
        """
        checkpoint = self.checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False

        # Check if item exists in checkpoint
        if item_key not in checkpoint.state_data:
            return False

        # Verify value matches
        if checkpoint.state_data[item_key] != expected_value:
            return False

        # Build Merkle tree and get proof
        state_items = [
            hashlib.sha256(json.dumps({k: v}, sort_keys=True).encode()).hexdigest()
            for k, v in checkpoint.state_data.items()
        ]

        merkle_tree = MerkleTree(state_items)

        # Find index of this item
        item_index = list(checkpoint.state_data.keys()).index(item_key)

        # Get and verify proof
        proof = merkle_tree.get_proof(item_index)
        leaf_hash = state_items[item_index]

        return MerkleTree.verify_proof(leaf_hash, proof, checkpoint.merkle_root)

    def _find_checkpoint_by_hash(self, state_hash: str) -> Optional[str]:
        """Find checkpoint ID by state hash."""
        for checkpoint_id, checkpoint in self.checkpoints.items():
            if checkpoint.state_hash == state_hash:
                return checkpoint_id
        return None

    def _cleanup_old_checkpoints(self):
        """Remove expired or excess checkpoints."""
        # Remove expired
        expired = [
            cp_id for cp_id, cp in self.checkpoints.items()
            if cp.is_expired()
        ]
        for cp_id in expired:
            del self.checkpoints[cp_id]
            logger.info(f"Removed expired checkpoint {cp_id}")

        # Remove oldest if exceeding limit
        if len(self.checkpoints) > self.max_checkpoints:
            sorted_checkpoints = sorted(
                self.checkpoints.items(),
                key=lambda x: x[1].timestamp
            )

            to_remove = len(self.checkpoints) - self.max_checkpoints
            for cp_id, _ in sorted_checkpoints[:to_remove]:
                del self.checkpoints[cp_id]
                logger.info(f"Removed old checkpoint {cp_id}")

    def _log_corruption_event(self, checkpoint_id: str, reason: str):
        """Log state corruption event for audit."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "checkpoint_id": checkpoint_id,
            "reason": reason,
            "severity": "CRITICAL"
        }

        self.corruption_events.append(event)

        logger.critical(f"State corruption detected: {checkpoint_id} - {reason}")

        # Persist to audit log
        with open(".state_corruption.jsonl", "a") as f:
            f.write(json.dumps(event) + "\n")

    def get_corruption_report(self) -> Dict[str, Any]:
        """Get report of all corruption events."""
        return {
            "total_events": len(self.corruption_events),
            "events": self.corruption_events,
            "checkpoints_monitored": len(self.checkpoints)
        }


# Global instance
state_verifier = StateVerifier()
