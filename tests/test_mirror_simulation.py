"""Tests for multi-mirror simulation system."""

import os
import tempfile

import pytest

from backend.mirror_simulation import MirrorSimulation


@pytest.fixture
def mirror_sim():
    """Create a fresh mirror simulation for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    sim = MirrorSimulation(storage_path=temp_path)
    yield sim

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestMirrorSimulation:
    """Tests for MirrorSimulation class."""

    def test_sync_creates_identical_mirrors(self, mirror_sim):
        """Sync creates identical copies in all mirrors."""
        ledger_data = {
            "records": {
                "concern_1": {"title": "Test concern", "description": "A test"},
                "submission_1": {"title": "Test submission", "data": "Some data"}
            }
        }

        result = mirror_sim.sync_from_source(ledger_data)

        assert result["record_count"] == 2
        assert result["all_hashes_match"] is True

        # All mirrors should have same content
        for party in ["lab", "auditor", "government"]:
            status = mirror_sim.get_mirror_status(party)
            assert status["record_count"] == 2

    def test_compare_identical_mirrors(self, mirror_sim):
        """Identical mirrors show as consistent."""
        ledger_data = {"records": {"test_1": {"data": "test"}}}
        mirror_sim.sync_from_source(ledger_data)

        result = mirror_sim.compare_mirrors()

        assert result["all_consistent"] is True
        assert result["lab_hash"] == result["auditor_hash"]
        assert result["auditor_hash"] == result["government_hash"]
        assert len(result["divergent_parties"]) == 0

    def test_tamper_changes_only_targeted_mirror(self, mirror_sim):
        """Tampering only affects one party's mirror."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        # Tamper with lab's copy
        result = mirror_sim.tamper_mirror("lab", "test_1", {"data": "tampered"})

        assert result["success"] is True
        assert result["action"] == "modified"

        # Lab should have different content
        assert mirror_sim.mirrors["lab"]["records"]["test_1"]["data"] == "tampered"
        assert mirror_sim.mirrors["auditor"]["records"]["test_1"]["data"] == "original"
        assert mirror_sim.mirrors["government"]["records"]["test_1"]["data"] == "original"

    def test_detection_finds_divergence(self, mirror_sim):
        """Tamper detection identifies divergent mirrors."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        # Tamper with lab's copy
        mirror_sim.tamper_mirror("lab", "test_1", {"data": "tampered"})

        # Detect tampering
        result = mirror_sim.detect_tampering()

        assert result["tampering_detected"] is True
        assert "lab" in result["affected_parties"]
        assert len(result["affected_records"]) == 1
        assert result["affected_records"][0]["record_id"] == "test_1"

    def test_consistent_mirrors_pass_detection(self, mirror_sim):
        """Consistent mirrors pass tamper detection."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        result = mirror_sim.detect_tampering()

        assert result["tampering_detected"] is False
        assert len(result["affected_parties"]) == 0
        assert len(result["affected_records"]) == 0

    def test_empty_mirrors_are_consistent(self, mirror_sim):
        """Empty mirrors are considered consistent."""
        result = mirror_sim.compare_mirrors()

        assert result["all_consistent"] is True

    def test_inject_new_record(self, mirror_sim):
        """Injecting a new record into one mirror causes divergence."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        # Inject new record into lab's copy
        result = mirror_sim.tamper_mirror("lab", "injected_1", {"data": "malicious"})

        assert result["success"] is True
        assert result["action"] == "injected"

        # Detect the injection
        detection = mirror_sim.detect_tampering()
        assert detection["tampering_detected"] is True
        assert "lab" in detection["affected_parties"]

    def test_reset_clears_all_mirrors(self, mirror_sim):
        """Reset clears all mirror data."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        mirror_sim.reset()

        for party in ["lab", "auditor", "government"]:
            status = mirror_sim.get_mirror_status(party)
            assert status["record_count"] == 0

    def test_invalid_party(self, mirror_sim):
        """Invalid party returns None for status."""
        status = mirror_sim.get_mirror_status("invalid_party")
        assert status is None

    def test_tamper_invalid_party(self, mirror_sim):
        """Tampering with invalid party returns error."""
        result = mirror_sim.tamper_mirror("invalid_party", "test_1", {"data": "test"})
        assert result["success"] is False
        assert "error" in result

    def test_multiple_tampers(self, mirror_sim):
        """Multiple tampers are detected correctly."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        # Tamper with multiple parties
        mirror_sim.tamper_mirror("lab", "test_1", {"data": "tampered_lab"})
        mirror_sim.tamper_mirror("auditor", "test_1", {"data": "tampered_auditor"})

        # All three parties now have different data
        detection = mirror_sim.detect_tampering()
        assert detection["tampering_detected"] is True
        # Note: detection identifies divergent parties based on majority hash

    def test_get_all_mirror_status(self, mirror_sim):
        """Get status of all mirrors."""
        ledger_data = {"records": {"test_1": {"data": "original"}}}
        mirror_sim.sync_from_source(ledger_data)

        statuses = mirror_sim.get_all_mirror_status()
        assert len(statuses) == 3
        parties = [s["party"] for s in statuses]
        assert "lab" in parties
        assert "auditor" in parties
        assert "government" in parties


class TestMirrorPersistence:
    """Tests for mirror simulation persistence."""

    def test_data_persists_across_instances(self):
        """Mirror data persists to disk and loads on new instance."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create and sync first instance
            sim1 = MirrorSimulation(storage_path=temp_path)
            ledger_data = {"records": {"test_1": {"data": "persistent"}}}
            sim1.sync_from_source(ledger_data)

            # Create second instance from same file
            sim2 = MirrorSimulation(storage_path=temp_path)

            # Data should be loaded
            for party in ["lab", "auditor", "government"]:
                assert sim2.mirrors[party]["records"]["test_1"]["data"] == "persistent"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_tamper_persists(self):
        """Tampered data persists across instances."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            sim1 = MirrorSimulation(storage_path=temp_path)
            ledger_data = {"records": {"test_1": {"data": "original"}}}
            sim1.sync_from_source(ledger_data)
            sim1.tamper_mirror("lab", "test_1", {"data": "tampered"})

            # Load in new instance
            sim2 = MirrorSimulation(storage_path=temp_path)

            # Tamper should persist
            assert sim2.mirrors["lab"]["records"]["test_1"]["data"] == "tampered"
            assert sim2.mirrors["auditor"]["records"]["test_1"]["data"] == "original"

            # Detection should still work
            result = sim2.detect_tampering()
            assert result["tampering_detected"] is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
