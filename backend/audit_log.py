"""Audit log engine with hash chain for tamper-proof logging."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.crypto_utils import hash_with_previous, verify_chain_hash
from backend.models import Event, EventCreate, EventType, VerificationResult


class AuditLog:
    """
    Tamper-proof audit log using hash chains.

    Each event's hash incorporates the previous event's hash,
    creating a chain where any modification is detectable.
    """

    def __init__(self, storage_path: str = "data/audit_log.json"):
        """
        Initialize the audit log.

        Args:
            storage_path: Path to JSON file for persistent storage
        """
        self.storage_path = Path(storage_path)
        self.events: list[Event] = []
        self._load()

    def _load(self) -> None:
        """Load events from storage file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.events = [
                        Event(
                            id=e['id'],
                            event_type=EventType(e['event_type']),
                            description=e['description'],
                            metadata=e['metadata'],
                            timestamp=datetime.fromisoformat(e['timestamp']),
                            previous_hash=e.get('previous_hash'),
                            hash=e['hash']
                        )
                        for e in data
                    ]
            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted file - start fresh
                self.events = []

    def _save(self) -> None:
        """Persist events to storage file."""
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            {
                'id': e.id,
                'event_type': e.event_type.value,
                'description': e.description,
                'metadata': e.metadata,
                'timestamp': e.timestamp.isoformat(),
                'previous_hash': e.previous_hash,
                'hash': e.hash
            }
            for e in self.events
        ]

        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_event(self, event_create: EventCreate) -> Event:
        """
        Add a new event to the log.

        The event is automatically assigned an ID, timestamp,
        and hash that chains to the previous event.

        Args:
            event_create: Event data to log

        Returns:
            Complete Event record with hash
        """
        # Determine chain values
        event_id = len(self.events)
        previous_hash = self.events[-1].hash if self.events else None
        timestamp = datetime.utcnow()

        # Create data dict for hashing
        event_data = {
            'id': event_id,
            'event_type': event_create.event_type.value,
            'description': event_create.description,
            'metadata': event_create.metadata,
            'timestamp': timestamp.isoformat()
        }

        # Compute chain hash
        event_hash = hash_with_previous(event_data, previous_hash)

        # Create complete event
        event = Event(
            id=event_id,
            event_type=event_create.event_type,
            description=event_create.description,
            metadata=event_create.metadata,
            timestamp=timestamp,
            previous_hash=previous_hash,
            hash=event_hash
        )

        self.events.append(event)
        self._save()

        return event

    def get_events(
        self,
        limit: Optional[int] = None,
        event_type: Optional[EventType] = None
    ) -> list[Event]:
        """
        Retrieve events from the log.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type

        Returns:
            List of events (most recent first)
        """
        events = self.events.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Return in reverse chronological order
        events = list(reversed(events))

        if limit:
            events = events[:limit]

        return events

    def get_event(self, event_id: int) -> Optional[Event]:
        """
        Get a specific event by ID.

        Args:
            event_id: Event ID to retrieve

        Returns:
            Event if found, None otherwise
        """
        if 0 <= event_id < len(self.events):
            return self.events[event_id]
        return None

    def verify_chain(self) -> VerificationResult:
        """
        Verify the integrity of the entire hash chain.

        Returns:
            VerificationResult indicating if chain is valid
        """
        if not self.events:
            return VerificationResult(
                is_valid=True,
                checked_events=0
            )

        for i, event in enumerate(self.events):
            # Get expected previous hash
            expected_previous = self.events[i - 1].hash if i > 0 else None

            # Check previous hash reference
            if event.previous_hash != expected_previous:
                return VerificationResult(
                    is_valid=False,
                    checked_events=i + 1,
                    first_invalid_index=i,
                    error_message=f"Event {i}: Previous hash mismatch"
                )

            # Recompute hash and verify
            event_data = {
                'id': event.id,
                'event_type': event.event_type.value,
                'description': event.description,
                'metadata': event.metadata,
                'timestamp': event.timestamp.isoformat()
            }

            if not verify_chain_hash(event_data, event.previous_hash, event.hash):
                return VerificationResult(
                    is_valid=False,
                    checked_events=i + 1,
                    first_invalid_index=i,
                    error_message=f"Event {i}: Hash verification failed (data tampered)"
                )

        return VerificationResult(
            is_valid=True,
            checked_events=len(self.events)
        )

    def get_latest_hash(self) -> Optional[str]:
        """Get the hash of the most recent event."""
        return self.events[-1].hash if self.events else None

    def reset(self) -> None:
        """Clear all events (for demo purposes)."""
        self.events = []
        if self.storage_path.exists():
            os.remove(self.storage_path)

    def tamper_event(self, event_id: int, new_description: Optional[str] = None,
                     new_metadata: Optional[dict] = None) -> bool:
        """
        Simulate tampering with an event (for demo purposes).

        This directly modifies an event WITHOUT updating its hash,
        which will cause chain verification to fail.

        Args:
            event_id: ID of event to tamper with
            new_description: New description to set
            new_metadata: New metadata to set

        Returns:
            True if tampering was performed, False if event not found
        """
        if event_id < 0 or event_id >= len(self.events):
            return False

        event = self.events[event_id]

        # Create new event with modified data but SAME hash (simulating tampering)
        self.events[event_id] = Event(
            id=event.id,
            event_type=event.event_type,
            description=new_description if new_description else event.description,
            metadata=new_metadata if new_metadata else event.metadata,
            timestamp=event.timestamp,
            previous_hash=event.previous_hash,
            hash=event.hash  # Keep original hash - this is the tampering!
        )

        self._save()
        return True
