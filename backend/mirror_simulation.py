"""Multi-mirror simulation for demonstrating ledger replication and tamper detection."""

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class MirrorSimulation:
    """
    Simulates 3 independent copies of the transparency ledger.

    In a real deployment, each party (lab, auditor, government) would
    maintain their own copy of the ledger. This simulation demonstrates:
    - Sync mechanism across mirrors
    - Tamper detection through hash comparison
    - What happens when one party tries to modify records

    Data is persisted to disk for durability across restarts.
    """

    PARTIES = ["lab", "auditor", "government"]

    def __init__(self, storage_path: str = "data/mirror_store.json"):
        self.storage_path = Path(storage_path)
        self.mirrors: dict[str, dict] = {
            "lab": {"records": {}, "last_sync": None},
            "auditor": {"records": {}, "last_sync": None},
            "government": {"records": {}, "last_sync": None}
        }
        self._load()

    def _load(self) -> None:
        """Load mirror data from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    content = f.read()
                    if content.strip():
                        data = json.loads(content)
                        for party in self.PARTIES:
                            if party in data:
                                self.mirrors[party]["records"] = data[party].get("records", {})
                                last_sync = data[party].get("last_sync")
                                if last_sync:
                                    self.mirrors[party]["last_sync"] = datetime.fromisoformat(last_sync)
            except json.JSONDecodeError:
                pass

    def _save(self) -> None:
        """Save mirror data to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for party in self.PARTIES:
            data[party] = {
                "records": self.mirrors[party]["records"],
                "last_sync": self.mirrors[party]["last_sync"].isoformat()
                           if self.mirrors[party]["last_sync"] else None
            }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def _compute_mirror_hash(self, party: str) -> str:
        """Compute a hash of all records in a mirror for comparison."""
        records = self.mirrors[party]["records"]
        if not records:
            return "empty_" + "0" * 58

        # Sort by record ID for consistent ordering
        sorted_records = sorted(records.items(), key=lambda x: x[0])
        content = json.dumps(sorted_records, sort_keys=True, separators=(',', ':'), default=str)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def sync_from_source(self, ledger_data: dict) -> dict:
        """
        Sync all mirrors from an authoritative source.

        In reality, this would be a distributed consensus mechanism.
        For demo purposes, we sync from provided ledger data.

        Args:
            ledger_data: Dictionary containing records to sync

        Returns:
            Sync status for all mirrors
        """
        sync_time = datetime.utcnow()
        record_count = len(ledger_data.get("records", {}))

        for party in self.PARTIES:
            # Each party gets a deep copy of the records
            self.mirrors[party]["records"] = copy.deepcopy(ledger_data.get("records", {}))
            self.mirrors[party]["last_sync"] = sync_time

        self._save()

        return {
            "synced_parties": self.PARTIES,
            "record_count": record_count,
            "sync_time": sync_time.isoformat(),
            "all_hashes_match": True
        }

    def get_mirror_status(self, party: str) -> Optional[dict]:
        """Get status of a specific mirror."""
        if party not in self.PARTIES:
            return None

        mirror = self.mirrors[party]
        return {
            "party": party,
            "record_count": len(mirror["records"]),
            "hash": self._compute_mirror_hash(party),
            "last_sync": mirror["last_sync"].isoformat() if mirror["last_sync"] else None
        }

    def get_all_mirror_status(self) -> list[dict]:
        """Get status of all mirrors."""
        return [self.get_mirror_status(party) for party in self.PARTIES]

    def compare_mirrors(self) -> dict:
        """
        Compare all mirrors and detect any divergence.

        Returns:
            Comparison result with consistency status
        """
        hashes = {}
        for party in self.PARTIES:
            hashes[party] = self._compute_mirror_hash(party)

        unique_hashes = set(hashes.values())
        all_consistent = len(unique_hashes) == 1

        # Find which parties diverge if not consistent
        divergent_parties = []
        if not all_consistent:
            # Find the majority hash (or first hash if tied)
            hash_counts = {}
            for h in hashes.values():
                hash_counts[h] = hash_counts.get(h, 0) + 1

            majority_hash = max(hash_counts.keys(), key=lambda h: hash_counts[h])

            for party, h in hashes.items():
                if h != majority_hash:
                    divergent_parties.append(party)

        if all_consistent:
            message = "All mirrors are consistent. No tampering detected."
        else:
            message = f"DIVERGENCE DETECTED! Affected parties: {', '.join(divergent_parties)}"

        return {
            "all_consistent": all_consistent,
            "lab_hash": hashes["lab"],
            "auditor_hash": hashes["auditor"],
            "government_hash": hashes["government"],
            "divergent_parties": divergent_parties,
            "message": message
        }

    def tamper_mirror(self, party: str, record_id: str, new_value: dict) -> dict:
        """
        Simulate tampering with one party's mirror (DEMO ONLY).

        This modifies a record in one party's copy, which will cause
        divergence detection when mirrors are compared.

        Args:
            party: Which party's mirror to tamper with
            record_id: ID of record to modify
            new_value: New value for the record

        Returns:
            Tamper result
        """
        if party not in self.PARTIES:
            return {"success": False, "error": f"Invalid party: {party}"}

        if record_id not in self.mirrors[party]["records"]:
            # If record doesn't exist, add it (simulating injection)
            self.mirrors[party]["records"][record_id] = new_value
            self._save()
            return {
                "success": True,
                "party": party,
                "record_id": record_id,
                "action": "injected",
                "warning": "Record injected into this mirror. Will cause divergence!"
            }
        else:
            # Modify existing record
            old_value = self.mirrors[party]["records"][record_id]
            self.mirrors[party]["records"][record_id] = new_value
            self._save()
            return {
                "success": True,
                "party": party,
                "record_id": record_id,
                "action": "modified",
                "old_value": old_value,
                "warning": "Record modified in this mirror. Will cause divergence!"
            }

    def detect_tampering(self) -> dict:
        """
        Run tamper detection across all mirrors.

        Returns:
            Detection result with recommendations
        """
        comparison = self.compare_mirrors()

        if comparison["all_consistent"]:
            return {
                "tampering_detected": False,
                "affected_parties": [],
                "affected_records": [],
                "recommendation": "All mirrors are in sync. Ledger integrity verified."
            }

        # Find which records differ
        affected_records = []
        divergent_parties = comparison["divergent_parties"]

        # Get records from each mirror and compare
        all_record_ids = set()
        for party in self.PARTIES:
            all_record_ids.update(self.mirrors[party]["records"].keys())

        for record_id in all_record_ids:
            values = {}
            for party in self.PARTIES:
                record = self.mirrors[party]["records"].get(record_id)
                values[party] = json.dumps(record, sort_keys=True, default=str) if record else None

            unique_values = set(values.values())
            if len(unique_values) > 1:
                affected_records.append({
                    "record_id": record_id,
                    "values_by_party": {
                        p: self.mirrors[p]["records"].get(record_id)
                        for p in self.PARTIES
                    }
                })

        return {
            "tampering_detected": True,
            "affected_parties": divergent_parties,
            "affected_records": affected_records,
            "recommendation": f"ALERT: Tampering detected in mirrors held by: {', '.join(divergent_parties)}. "
                             f"Investigate immediately. {len(affected_records)} record(s) affected."
        }

    def reset(self) -> dict:
        """Reset all mirrors to empty state."""
        self.mirrors = {
            "lab": {"records": {}, "last_sync": None},
            "auditor": {"records": {}, "last_sync": None},
            "government": {"records": {}, "last_sync": None}
        }
        self._save()
        return {"message": "All mirrors have been reset"}


# Global instance
mirror_simulation = MirrorSimulation()
