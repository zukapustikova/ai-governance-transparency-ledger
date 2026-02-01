"""Tests for audit log engine."""

import os
import tempfile
from pathlib import Path

import pytest

from backend.audit_log import AuditLog
from backend.models import EventCreate, EventType


@pytest.fixture
def temp_log():
    """Create a temporary audit log for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    log = AuditLog(storage_path=temp_path)
    yield log

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestAuditLogBasics:
    """Basic audit log operations."""

    def test_empty_log(self, temp_log):
        """New log should be empty."""
        assert len(temp_log.events) == 0
        assert temp_log.get_latest_hash() is None

    def test_add_event(self, temp_log):
        """Should be able to add an event."""
        event = temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Started training model v1"
        ))

        assert event.id == 0
        assert event.event_type == EventType.TRAINING_STARTED
        assert event.hash is not None
        assert event.previous_hash is None  # First event

    def test_add_multiple_events(self, temp_log):
        """Multiple events should chain correctly."""
        e1 = temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Started training"
        ))
        e2 = temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_COMPLETED,
            description="Completed training"
        ))

        assert e2.previous_hash == e1.hash
        assert e2.hash != e1.hash

    def test_get_event(self, temp_log):
        """Should retrieve specific event by ID."""
        created = temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Running safety eval"
        ))

        retrieved = temp_log.get_event(0)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.hash == created.hash

    def test_get_nonexistent_event(self, temp_log):
        """Should return None for invalid ID."""
        assert temp_log.get_event(999) is None
        assert temp_log.get_event(-1) is None


class TestEventFiltering:
    """Event retrieval and filtering."""

    def test_get_events_order(self, temp_log):
        """Events should be returned in reverse chronological order."""
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="First"
        ))
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_COMPLETED,
            description="Second"
        ))

        events = temp_log.get_events()
        assert events[0].description == "Second"
        assert events[1].description == "First"

    def test_get_events_limit(self, temp_log):
        """Should respect limit parameter."""
        for i in range(5):
            temp_log.add_event(EventCreate(
                event_type=EventType.SAFETY_EVAL_RUN,
                description=f"Event {i}"
            ))

        events = temp_log.get_events(limit=3)
        assert len(events) == 3

    def test_get_events_by_type(self, temp_log):
        """Should filter by event type."""
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Training"
        ))
        temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Safety"
        ))
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_COMPLETED,
            description="Training done"
        ))

        safety_events = temp_log.get_events(event_type=EventType.SAFETY_EVAL_RUN)
        assert len(safety_events) == 1
        assert safety_events[0].description == "Safety"


class TestChainVerification:
    """Hash chain verification tests."""

    def test_verify_empty_chain(self, temp_log):
        """Empty chain should be valid."""
        result = temp_log.verify_chain()
        assert result.is_valid is True
        assert result.checked_events == 0

    def test_verify_valid_chain(self, temp_log):
        """Unmodified chain should verify."""
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Training started"
        ))
        temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Running eval"
        ))
        temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_PASSED,
            description="Eval passed"
        ))

        result = temp_log.verify_chain()
        assert result.is_valid is True
        assert result.checked_events == 3

    def test_detect_tampering(self, temp_log):
        """Should detect when event data is tampered."""
        temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Original description"
        ))

        # Tamper with the event
        temp_log.tamper_event(0, new_description="Tampered description")

        result = temp_log.verify_chain()
        assert result.is_valid is False
        assert result.first_invalid_index == 0
        assert "tampered" in result.error_message.lower()

    def test_detect_middle_tampering(self, temp_log):
        """Should detect tampering in middle of chain."""
        for i in range(5):
            temp_log.add_event(EventCreate(
                event_type=EventType.SAFETY_EVAL_RUN,
                description=f"Event {i}"
            ))

        # Tamper with middle event
        temp_log.tamper_event(2, new_description="Tampered")

        result = temp_log.verify_chain()
        assert result.is_valid is False
        assert result.first_invalid_index == 2


class TestPersistence:
    """Storage and persistence tests."""

    def test_persistence(self):
        """Events should persist across instances."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create and add event
            log1 = AuditLog(storage_path=temp_path)
            log1.add_event(EventCreate(
                event_type=EventType.MODEL_DEPLOYED,
                description="Deployed to prod"
            ))

            # Load in new instance
            log2 = AuditLog(storage_path=temp_path)
            assert len(log2.events) == 1
            assert log2.events[0].description == "Deployed to prod"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_reset(self, temp_log):
        """Reset should clear all events."""
        temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Test"
        ))
        assert len(temp_log.events) == 1

        temp_log.reset()
        assert len(temp_log.events) == 0


class TestMetadata:
    """Event metadata handling."""

    def test_event_with_metadata(self, temp_log):
        """Should store and retrieve metadata."""
        metadata = {
            "model_version": "1.0",
            "dataset_size": 10000,
            "hyperparams": {"lr": 0.001, "epochs": 10}
        }

        event = temp_log.add_event(EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Training with metadata",
            metadata=metadata
        ))

        assert event.metadata == metadata

    def test_metadata_in_hash(self, temp_log):
        """Metadata changes should affect hash."""
        e1 = temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Same description",
            metadata={"score": 0.95}
        ))

        temp_log.reset()

        e2 = temp_log.add_event(EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Same description",
            metadata={"score": 0.85}
        ))

        # Different metadata = different hash
        assert e1.hash != e2.hash
