"""Integration tests for API endpoints using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from backend.api import app, transparency_ledger
from backend.auth import auth_store, registration_rate_limiter
from backend.mirror_simulation import mirror_simulation


@pytest.fixture(autouse=True)
def reset_state():
    """Reset all stores before each test."""
    auth_store.reset()
    registration_rate_limiter.reset()
    mirror_simulation.reset()
    transparency_ledger.reset()
    yield
    auth_store.reset()
    registration_rate_limiter.reset()
    mirror_simulation.reset()
    transparency_ledger.reset()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestAuthFlow:
    """Integration tests for authentication flow."""

    def test_register_and_authenticate(self, client):
        """Full registration and authentication flow."""
        # Register a new party
        response = client.post(
            "/auth/register",
            json={"name": "Test Lab", "role": "lab"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Lab"
        assert data["role"] == "lab"
        assert "api_key" in data
        api_key = data["api_key"]

        # Use the API key to get current party info
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Lab"
        assert data["role"] == "lab"

    def test_rate_limiting_on_register(self, client):
        """Rate limiting blocks excessive registrations."""
        # Make 5 successful registrations
        for i in range(5):
            response = client.post(
                "/auth/register",
                json={"name": f"Party {i}", "role": "lab"}
            )
            assert response.status_code == 200

        # 6th should be rate limited
        response = client.post(
            "/auth/register",
            json={"name": "Party 6", "role": "lab"}
        )
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]

    def test_invalid_api_key(self, client):
        """Invalid API key returns 401."""
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": "invalid_key"}
        )
        assert response.status_code == 401

    def test_revoke_party(self, client):
        """Revoked party cannot authenticate."""
        # Register
        response = client.post(
            "/auth/register",
            json={"name": "Test Lab", "role": "lab"}
        )
        data = response.json()
        party_id = data["party_id"]
        api_key = data["api_key"]

        # Revoke
        response = client.delete(f"/auth/parties/{party_id}")
        assert response.status_code == 200

        # API key should no longer work
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 401

    def test_rotate_api_key(self, client):
        """API key rotation generates new key and invalidates old."""
        # Register
        response = client.post(
            "/auth/register",
            json={"name": "Test Lab", "role": "lab"}
        )
        data = response.json()
        party_id = data["party_id"]
        old_api_key = data["api_key"]

        # Rotate using old key
        response = client.post(
            "/auth/rotate-key",
            headers={"X-API-Key": old_api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["party_id"] == party_id
        new_api_key = data["new_api_key"]
        assert new_api_key != old_api_key

        # Old key should not work
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": old_api_key}
        )
        assert response.status_code == 401

        # New key should work
        response = client.get(
            "/auth/me",
            headers={"X-API-Key": new_api_key}
        )
        assert response.status_code == 200
        assert response.json()["id"] == party_id


class TestTransparencyFlow:
    """Integration tests for transparency ledger flow."""

    def test_raise_and_respond_to_concern(self, client):
        """Full concern lifecycle: raise, respond, resolve."""
        # Raise a concern
        response = client.post(
            "/transparency/concerns",
            params={"submitter_id": "anon_abc123", "role": "whistleblower"},
            json={
                "category": "safety_eval",
                "title": "Test Concern",
                "description": "A test concern description",
                "deployment_id": "test-deploy-1"
            }
        )
        assert response.status_code == 200
        concern = response.json()
        concern_id = concern["id"]

        # Lab responds
        response = client.post(
            "/transparency/responses",
            params={"responder_id": "Test Lab", "role": "lab"},
            json={
                "concern_id": concern_id,
                "response_text": "We have addressed this concern"
            }
        )
        assert response.status_code == 200

        # Auditor resolves
        response = client.post(
            "/transparency/resolutions",
            params={"auditor_id": "AI Safety Institute"},
            json={
                "concern_id": concern_id,
                "resolution_notes": "Verified that concern was addressed"
            }
        )
        assert response.status_code == 200

        # Check concern is resolved
        response = client.get(f"/transparency/concerns/{concern_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"


class TestMirrorFlow:
    """Integration tests for mirror simulation flow."""

    def test_sync_and_detect_tampering(self, client):
        """Full mirror sync and tamper detection flow."""
        # First populate transparency ledger
        response = client.post("/demo/transparency-populate")
        assert response.status_code == 200

        # Sync mirrors
        response = client.post("/demo/mirror/sync")
        assert response.status_code == 200
        assert response.json()["record_count"] > 0

        # Check all consistent
        response = client.get("/demo/mirror/compare")
        assert response.status_code == 200
        assert response.json()["all_consistent"] is True

        # Tamper with one mirror
        response = client.post(
            "/demo/mirror/tamper",
            json={
                "party": "lab",
                "record_id": "fake_record",
                "new_value": {"data": "malicious"}
            }
        )
        assert response.status_code == 200

        # Detect tampering
        response = client.get("/demo/mirror/detect")
        assert response.status_code == 200
        data = response.json()
        assert data["tampering_detected"] is True
        assert "lab" in data["affected_parties"]


class TestComplianceFlow:
    """Integration tests for compliance submission flow."""

    def test_submit_and_review_compliance(self, client):
        """Full compliance submission and review flow."""
        # Submit compliance document
        response = client.post(
            "/compliance/submissions",
            params={"lab_id": "Test Lab"},
            json={
                "template_type": "safety_evaluation",
                "deployment_id": "test-deploy-1",
                "model_id": "test-model-1",
                "title": "Safety Evaluation Report",
                "summary": "All tests passed",
                "evidence_hash": "a" * 64
            }
        )
        assert response.status_code == 200
        submission = response.json()
        submission_id = submission["id"]
        assert submission["status"] == "submitted"

        # Review and verify
        response = client.post(
            "/compliance/review",
            params={"auditor_id": "AI Safety Institute"},
            json={
                "submission_id": submission_id,
                "status": "verified",
                "notes": "Evidence verified",
                "evidence_verified": True
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "verified"


class TestRoleBasedAccess:
    """Integration tests for role-based access control."""

    def test_lab_can_submit_compliance(self, client):
        """Lab role can submit compliance with API key."""
        # Register as lab
        response = client.post(
            "/auth/register",
            json={"name": "Test Lab", "role": "lab"}
        )
        api_key = response.json()["api_key"]

        # Submit with API key
        response = client.post(
            "/compliance/submissions",
            params={"lab_id": "Test Lab"},
            headers={"X-API-Key": api_key},
            json={
                "template_type": "safety_evaluation",
                "deployment_id": "test-deploy-1",
                "model_id": "test-model-1",
                "title": "Safety Report",
                "summary": "All tests passed successfully",
                "evidence_hash": "a" * 64
            }
        )
        assert response.status_code == 200

    def test_auditor_cannot_submit_compliance(self, client):
        """Auditor role cannot submit compliance."""
        # Register as auditor
        response = client.post(
            "/auth/register",
            json={"name": "Test Auditor", "role": "auditor"}
        )
        api_key = response.json()["api_key"]

        # Try to submit (should fail)
        response = client.post(
            "/compliance/submissions",
            params={"lab_id": "Test Auditor"},
            headers={"X-API-Key": api_key},
            json={
                "template_type": "safety_evaluation",
                "deployment_id": "test-deploy-1",
                "model_id": "test-model-1",
                "title": "Safety Report",
                "summary": "All tests passed successfully",
                "evidence_hash": "a" * 64
            }
        )
        assert response.status_code == 403

    def test_auditor_can_review_compliance(self, client):
        """Auditor role can review compliance."""
        # Submit as lab (no auth)
        response = client.post(
            "/compliance/submissions",
            params={"lab_id": "Test Lab"},
            json={
                "template_type": "safety_evaluation",
                "deployment_id": "test-deploy-1",
                "model_id": "test-model-1",
                "title": "Safety Report",
                "summary": "All tests passed successfully",
                "evidence_hash": "a" * 64
            }
        )
        submission_id = response.json()["id"]

        # Register as auditor
        response = client.post(
            "/auth/register",
            json={"name": "Test Auditor", "role": "auditor"}
        )
        api_key = response.json()["api_key"]

        # Review with API key
        response = client.post(
            "/compliance/review",
            params={"auditor_id": "Test Auditor"},
            headers={"X-API-Key": api_key},
            json={
                "submission_id": submission_id,
                "status": "verified",
                "notes": "Evidence verified and approved",
                "evidence_verified": True
            }
        )
        assert response.status_code == 200
