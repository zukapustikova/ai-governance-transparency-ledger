"""Tests for Shared Transparency Ledger."""

import os
import tempfile

import pytest

from backend.crypto_utils import generate_anonymous_id, verify_anonymous_id
from backend.models import (
    ComplianceReviewCreate,
    ComplianceStatus,
    ComplianceSubmissionCreate,
    ComplianceTemplateType,
    ConcernCategory,
    ConcernCreate,
    ConcernResponseCreate,
    ConcernStatus,
    ResolutionCreate,
    SubmitterRole,
)
from backend.transparency import TransparencyLedger


@pytest.fixture
def temp_ledger():
    """Create a temporary transparency ledger for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name

    ledger = TransparencyLedger(storage_path=temp_path)
    yield ledger

    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


class TestAnonymousIdentity:
    """Tests for anonymous identity generation."""

    def test_generate_anonymous_id(self):
        """Should generate consistent anonymous ID."""
        anon_id = generate_anonymous_id("alice@lab.com", "mysecret123")

        assert anon_id.startswith("anon_")
        assert len(anon_id) == 17  # "anon_" + 12 hex chars

    def test_same_input_same_output(self):
        """Same identity + salt should produce same anonymous ID."""
        id1 = generate_anonymous_id("alice@lab.com", "mysecret123")
        id2 = generate_anonymous_id("alice@lab.com", "mysecret123")

        assert id1 == id2

    def test_different_salt_different_output(self):
        """Different salt should produce different anonymous ID."""
        id1 = generate_anonymous_id("alice@lab.com", "secret1")
        id2 = generate_anonymous_id("alice@lab.com", "secret2")

        assert id1 != id2

    def test_different_identity_different_output(self):
        """Different identity should produce different anonymous ID."""
        id1 = generate_anonymous_id("alice@lab.com", "samesecret")
        id2 = generate_anonymous_id("bob@lab.com", "samesecret")

        assert id1 != id2

    def test_verify_anonymous_id(self):
        """Should verify ownership of anonymous ID."""
        identity = "alice@lab.com"
        salt = "mysecret123"
        anon_id = generate_anonymous_id(identity, salt)

        assert verify_anonymous_id(identity, salt, anon_id) is True
        assert verify_anonymous_id(identity, "wrong_salt", anon_id) is False
        assert verify_anonymous_id("wrong@email.com", salt, anon_id) is False


class TestConcernManagement:
    """Tests for concern creation and retrieval."""

    def test_raise_concern(self, temp_ledger):
        """Should create a concern with all fields."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Safety test skipped",
                description="Observed that CBRN eval was not completed",
                deployment_id="model-v1-prod"
            ),
            submitter_id="anon_abc123",
            submitter_role=SubmitterRole.WHISTLEBLOWER
        )

        assert concern.id is not None
        assert concern.title == "Safety test skipped"
        assert concern.status == ConcernStatus.OPEN
        assert concern.submitter_role == SubmitterRole.WHISTLEBLOWER
        assert concern.hash is not None

    def test_get_concern(self, temp_ledger):
        """Should retrieve a concern by ID."""
        created = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.CAPABILITY_RISK,
                title="Test concern title",
                description="This is a detailed test description for the concern"
            ),
            submitter_id="anon_xyz",
            submitter_role=SubmitterRole.WHISTLEBLOWER
        )

        retrieved = temp_ledger.get_concern(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    def test_get_nonexistent_concern(self, temp_ledger):
        """Should return None for invalid ID."""
        result = temp_ledger.get_concern("nonexistent")
        assert result is None

    def test_list_concerns_filter_by_status(self, temp_ledger):
        """Should filter concerns by status."""
        # Create open concern
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Open concern one",
                description="This is a detailed description for the concern"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        open_concerns = temp_ledger.list_concerns(status=ConcernStatus.OPEN)
        assert len(open_concerns) == 1

        resolved_concerns = temp_ledger.list_concerns(status=ConcernStatus.RESOLVED)
        assert len(resolved_concerns) == 0

    def test_list_concerns_filter_by_deployment(self, temp_ledger):
        """Should filter concerns by deployment ID."""
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.DEPLOYMENT,
                title="Deploy concern one",
                description="This is a detailed description for deploy-a",
                deployment_id="deploy-a"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.DEPLOYMENT,
                title="Deploy concern two",
                description="This is a detailed description for deploy-b",
                deployment_id="deploy-b"
            ),
            "anon_2", SubmitterRole.WHISTLEBLOWER
        )

        deploy_a = temp_ledger.list_concerns(deployment_id="deploy-a")
        assert len(deploy_a) == 1
        assert deploy_a[0].deployment_id == "deploy-a"


class TestResponseManagement:
    """Tests for concern responses."""

    def test_respond_to_concern(self, temp_ledger):
        """Should create response and update status."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern title",
                description="This is a detailed test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        response = temp_ledger.respond_to_concern(
            ConcernResponseCreate(
                concern_id=concern.id,
                response_text="We have addressed this issue completely"
            ),
            responder_id="Anthropic Safety",
            responder_role=SubmitterRole.LAB
        )

        assert response is not None
        assert response.response_text == "We have addressed this issue completely"

        # Status should be updated
        updated = temp_ledger.get_concern(concern.id)
        assert updated.status == ConcernStatus.ADDRESSED

    def test_respond_to_nonexistent_concern(self, temp_ledger):
        """Should return None for invalid concern ID."""
        result = temp_ledger.respond_to_concern(
            ConcernResponseCreate(
                concern_id="fake",
                response_text="Test response text here"
            ),
            "Lab", SubmitterRole.LAB
        )
        assert result is None

    def test_dispute_response(self, temp_ledger):
        """Should mark concern as disputed."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern title",
                description="This is a detailed test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        # Lab responds
        temp_ledger.respond_to_concern(
            ConcernResponseCreate(
                concern_id=concern.id,
                response_text="We have fixed this issue"
            ),
            "Lab", SubmitterRole.LAB
        )

        # Whistleblower disputes
        success = temp_ledger.dispute_response(concern.id, "anon_1")
        assert success is True

        updated = temp_ledger.get_concern(concern.id)
        assert updated.status == ConcernStatus.DISPUTED


class TestResolutionManagement:
    """Tests for concern resolution by auditors."""

    def test_resolve_concern(self, temp_ledger):
        """Should mark concern as resolved."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern title",
                description="This is a detailed test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        resolution = temp_ledger.resolve_concern(
            ResolutionCreate(
                concern_id=concern.id,
                resolution_notes="Verified fix is adequate and complete"
            ),
            auditor_id="AI Safety Institute"
        )

        assert resolution is not None
        assert resolution.resolution_notes == "Verified fix is adequate and complete"

        updated = temp_ledger.get_concern(concern.id)
        assert updated.status == ConcernStatus.RESOLVED

    def test_resolve_nonexistent_concern(self, temp_ledger):
        """Should return None for invalid concern ID."""
        result = temp_ledger.resolve_concern(
            ResolutionCreate(
                concern_id="fake",
                resolution_notes="Test resolution notes here"
            ),
            "Auditor"
        )
        assert result is None


class TestDeploymentClearance:
    """Tests for deployment clearance checks."""

    def test_cleared_when_no_concerns(self, temp_ledger):
        """Deployment should be cleared when no concerns exist."""
        clearance = temp_ledger.check_deployment_clearance("new-deploy")

        assert clearance.is_cleared is True
        assert clearance.total_concerns == 0

    def test_blocked_when_open_concerns(self, temp_ledger):
        """Deployment should be blocked when open concerns exist."""
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Blocking concern title",
                description="This concern blocks the deployment from proceeding",
                deployment_id="deploy-x"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        clearance = temp_ledger.check_deployment_clearance("deploy-x")

        assert clearance.is_cleared is False
        assert clearance.open_concerns == 1
        assert "BLOCKED" in clearance.message

    def test_cleared_when_all_resolved(self, temp_ledger):
        """Deployment should be cleared when all concerns are resolved."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Resolvable concern",
                description="This concern can be resolved properly",
                deployment_id="deploy-y"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        temp_ledger.resolve_concern(
            ResolutionCreate(
                concern_id=concern.id,
                resolution_notes="This has been properly fixed and verified"
            ),
            "Auditor"
        )

        clearance = temp_ledger.check_deployment_clearance("deploy-y")

        assert clearance.is_cleared is True
        assert clearance.resolved_concerns == 1

    def test_blocked_when_disputed(self, temp_ledger):
        """Deployment should be blocked when disputed concerns exist."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.CAPABILITY_RISK,
                title="Disputed concern title",
                description="This concern will be disputed by the whistleblower",
                deployment_id="deploy-z"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        # Lab responds
        temp_ledger.respond_to_concern(
            ConcernResponseCreate(
                concern_id=concern.id,
                response_text="We believe this has been fixed"
            ),
            "Lab", SubmitterRole.LAB
        )

        # Whistleblower disputes
        temp_ledger.dispute_response(concern.id, "anon_1")

        clearance = temp_ledger.check_deployment_clearance("deploy-z")

        assert clearance.is_cleared is False


class TestPersistence:
    """Tests for ledger persistence."""

    def test_persistence(self):
        """Concerns should persist across instances."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create ledger and add concern
            ledger1 = TransparencyLedger(storage_path=temp_path)
            concern = ledger1.raise_concern(
                ConcernCreate(
                    category=ConcernCategory.SAFETY_EVAL,
                    title="Persistent concern title",
                    description="This concern should persist across instances"
                ),
                "anon_1", SubmitterRole.WHISTLEBLOWER
            )

            # Load in new instance
            ledger2 = TransparencyLedger(storage_path=temp_path)
            retrieved = ledger2.get_concern(concern.id)

            assert retrieved is not None
            assert retrieved.title == "Persistent concern title"

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_reset(self, temp_ledger):
        """Reset should clear all data."""
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.OTHER,
                title="Test concern title",
                description="This is a detailed test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        assert len(temp_ledger.concerns) == 1

        temp_ledger.reset()

        assert len(temp_ledger.concerns) == 0
        assert len(temp_ledger.responses) == 0
        assert len(temp_ledger.resolutions) == 0


class TestTamperProofing:
    """Tests for hash chain integrity."""

    def test_concerns_have_hashes(self, temp_ledger):
        """Each concern should have a hash."""
        concern = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern title",
                description="This is a detailed test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )

        assert concern.hash is not None
        assert len(concern.hash) == 64  # SHA256 hex

    def test_different_concerns_different_hashes(self, temp_ledger):
        """Different concerns should have different hashes."""
        c1 = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern one",
                description="This is the first test description"
            ),
            "anon_1", SubmitterRole.WHISTLEBLOWER
        )
        c2 = temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Test concern two",
                description="This is the second test description"
            ),
            "anon_2", SubmitterRole.WHISTLEBLOWER
        )

        assert c1.hash != c2.hash


# ============================================================
# Compliance Submission Tests
# ============================================================

class TestComplianceSubmission:
    """Tests for compliance submission management."""

    def test_submit_compliance(self, temp_ledger):
        """Should create a compliance submission with all fields."""
        submission = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id="model-v1-prod",
                model_id="model-v1",
                title="Pre-deployment Safety Evaluation",
                summary="Comprehensive safety evaluation covering all benchmarks.",
                evidence_hash="a" * 64,
                metadata={"test_cases": 15000, "score": 0.98}
            ),
            lab_id="Anthropic"
        )

        assert submission.id is not None
        assert submission.template_type == ComplianceTemplateType.SAFETY_EVALUATION
        assert submission.status == ComplianceStatus.SUBMITTED
        assert submission.evidence_hash == "a" * 64
        assert submission.lab_id == "Anthropic"
        assert submission.hash is not None

    def test_get_compliance_submission(self, temp_ledger):
        """Should retrieve a submission by ID."""
        created = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.RED_TEAM_REPORT,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Red Team Testing Results",
                summary="Results from external red team evaluation.",
                evidence_hash="b" * 64
            ),
            lab_id="TestLab"
        )

        retrieved = temp_ledger.get_compliance_submission(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == created.title

    def test_get_nonexistent_submission(self, temp_ledger):
        """Should return None for invalid ID."""
        result = temp_ledger.get_compliance_submission("nonexistent")
        assert result is None

    def test_list_submissions_filter_by_deployment(self, temp_ledger):
        """Should filter submissions by deployment ID."""
        temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id="deploy-a",
                model_id="model-a",
                title="Safety Eval A",
                summary="Safety evaluation for deployment A.",
                evidence_hash="a" * 64
            ),
            lab_id="Lab1"
        )
        temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id="deploy-b",
                model_id="model-b",
                title="Safety Eval B",
                summary="Safety evaluation for deployment B.",
                evidence_hash="b" * 64
            ),
            lab_id="Lab2"
        )

        deploy_a = temp_ledger.list_compliance_submissions(deployment_id="deploy-a")
        assert len(deploy_a) == 1
        assert deploy_a[0].deployment_id == "deploy-a"

    def test_list_submissions_filter_by_template_type(self, temp_ledger):
        """Should filter submissions by template type."""
        temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Safety Eval",
                summary="Safety evaluation submission.",
                evidence_hash="a" * 64
            ),
            lab_id="Lab1"
        )
        temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.RED_TEAM_REPORT,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Red Team",
                summary="Red team report submission.",
                evidence_hash="b" * 64
            ),
            lab_id="Lab1"
        )

        safety_evals = temp_ledger.list_compliance_submissions(
            template_type=ComplianceTemplateType.SAFETY_EVALUATION
        )
        assert len(safety_evals) == 1
        assert safety_evals[0].template_type == ComplianceTemplateType.SAFETY_EVALUATION


class TestComplianceReview:
    """Tests for compliance review by auditors."""

    def test_verify_submission(self, temp_ledger):
        """Should verify a submission and update status."""
        submission = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.CAPABILITY_ASSESSMENT,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Capability Assessment",
                summary="Assessment of dangerous capabilities.",
                evidence_hash="c" * 64
            ),
            lab_id="TestLab"
        )

        reviewed = temp_ledger.review_compliance(
            ComplianceReviewCreate(
                submission_id=submission.id,
                status=ComplianceStatus.VERIFIED,
                notes="Evidence verified. All requirements met.",
                evidence_verified=True
            ),
            auditor_id="AI Safety Institute"
        )

        assert reviewed is not None
        assert reviewed.status == ComplianceStatus.VERIFIED
        assert reviewed.reviewed_by == "AI Safety Institute"
        assert reviewed.review_notes == "Evidence verified. All requirements met."

    def test_reject_submission(self, temp_ledger):
        """Should reject a submission that doesn't meet requirements."""
        submission = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.TRAINING_DATA,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Training Data Documentation",
                summary="Documentation of training data sources.",
                evidence_hash="d" * 64
            ),
            lab_id="TestLab"
        )

        reviewed = temp_ledger.review_compliance(
            ComplianceReviewCreate(
                submission_id=submission.id,
                status=ComplianceStatus.REJECTED,
                notes="Evidence hash did not match provided documentation.",
                evidence_verified=False
            ),
            auditor_id="AI Safety Institute"
        )

        assert reviewed.status == ComplianceStatus.REJECTED

    def test_review_nonexistent_submission(self, temp_ledger):
        """Should return None for invalid submission ID."""
        result = temp_ledger.review_compliance(
            ComplianceReviewCreate(
                submission_id="fake",
                status=ComplianceStatus.VERIFIED,
                notes="This should fail.",
                evidence_verified=True
            ),
            auditor_id="Auditor"
        )
        assert result is None

    def test_invalid_review_status(self, temp_ledger):
        """Should reject invalid review status."""
        submission = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.HUMAN_OVERSIGHT,
                deployment_id="deploy-1",
                model_id="model-1",
                title="Human Oversight Attestation",
                summary="Attestation of human oversight procedures.",
                evidence_hash="e" * 64
            ),
            lab_id="TestLab"
        )

        with pytest.raises(ValueError):
            temp_ledger.review_compliance(
                ComplianceReviewCreate(
                    submission_id=submission.id,
                    status=ComplianceStatus.SUBMITTED,  # Invalid for review
                    notes="Invalid status.",
                    evidence_verified=True
                ),
                auditor_id="Auditor"
            )


class TestDeploymentComplianceStatus:
    """Tests for unified deployment compliance status (the deployment gate)."""

    def test_cleared_when_all_requirements_met(self, temp_ledger):
        """Deployment should be cleared when all templates verified and no concerns."""
        deployment_id = "deploy-cleared"
        model_id = "model-cleared"

        # Submit and verify all required templates
        for template_type in [
            ComplianceTemplateType.SAFETY_EVALUATION,
            ComplianceTemplateType.CAPABILITY_ASSESSMENT,
            ComplianceTemplateType.RED_TEAM_REPORT
        ]:
            sub = temp_ledger.submit_compliance(
                ComplianceSubmissionCreate(
                    template_type=template_type,
                    deployment_id=deployment_id,
                    model_id=model_id,
                    title=f"{template_type.value} submission",
                    summary=f"Submission for {template_type.value}.",
                    evidence_hash="a" * 64
                ),
                lab_id="TestLab"
            )
            temp_ledger.review_compliance(
                ComplianceReviewCreate(
                    submission_id=sub.id,
                    status=ComplianceStatus.VERIFIED,
                    notes="Verified and approved.",
                    evidence_verified=True
                ),
                auditor_id="Auditor"
            )

        status = temp_ledger.get_deployment_compliance_status(deployment_id, model_id)

        assert status.is_cleared is True
        assert status.compliance_complete is True
        assert status.concerns_resolved is True
        assert len(status.missing_templates) == 0
        assert "CLEARED" in status.message

    def test_blocked_when_missing_templates(self, temp_ledger):
        """Deployment should be blocked when required templates are missing."""
        deployment_id = "deploy-missing"
        model_id = "model-missing"

        # Only submit safety evaluation (missing capability_assessment and red_team_report)
        sub = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id=deployment_id,
                model_id=model_id,
                title="Safety Evaluation",
                summary="Safety evaluation submission.",
                evidence_hash="a" * 64
            ),
            lab_id="TestLab"
        )
        temp_ledger.review_compliance(
            ComplianceReviewCreate(
                submission_id=sub.id,
                status=ComplianceStatus.VERIFIED,
                notes="Verified and approved.",
                evidence_verified=True
            ),
            auditor_id="Auditor"
        )

        status = temp_ledger.get_deployment_compliance_status(deployment_id, model_id)

        assert status.is_cleared is False
        assert status.compliance_complete is False
        assert len(status.missing_templates) == 2
        assert ComplianceTemplateType.CAPABILITY_ASSESSMENT in status.missing_templates
        assert ComplianceTemplateType.RED_TEAM_REPORT in status.missing_templates
        assert "BLOCKED" in status.message
        assert "Missing" in status.message

    def test_blocked_when_unresolved_concerns(self, temp_ledger):
        """Deployment should be blocked when concerns are unresolved."""
        deployment_id = "deploy-concerns"
        model_id = "model-concerns"

        # Submit and verify all required templates
        for template_type in [
            ComplianceTemplateType.SAFETY_EVALUATION,
            ComplianceTemplateType.CAPABILITY_ASSESSMENT,
            ComplianceTemplateType.RED_TEAM_REPORT
        ]:
            sub = temp_ledger.submit_compliance(
                ComplianceSubmissionCreate(
                    template_type=template_type,
                    deployment_id=deployment_id,
                    model_id=model_id,
                    title=f"{template_type.value} submission",
                    summary=f"Submission for {template_type.value}.",
                    evidence_hash="a" * 64
                ),
                lab_id="TestLab"
            )
            temp_ledger.review_compliance(
                ComplianceReviewCreate(
                    submission_id=sub.id,
                    status=ComplianceStatus.VERIFIED,
                    notes="Verified and approved.",
                    evidence_verified=True
                ),
                auditor_id="Auditor"
            )

        # Add an unresolved concern
        temp_ledger.raise_concern(
            ConcernCreate(
                category=ConcernCategory.SAFETY_EVAL,
                title="Safety concern blocking deployment",
                description="This concern blocks the deployment from proceeding.",
                deployment_id=deployment_id
            ),
            submitter_id="anon_1",
            submitter_role=SubmitterRole.WHISTLEBLOWER
        )

        status = temp_ledger.get_deployment_compliance_status(deployment_id, model_id)

        assert status.is_cleared is False
        assert status.compliance_complete is True
        assert status.concerns_resolved is False
        assert status.unresolved_concerns == 1
        assert "BLOCKED" in status.message
        assert "concern" in status.message.lower()

    def test_blocked_when_rejected_templates(self, temp_ledger):
        """Deployment should be blocked when templates are rejected."""
        deployment_id = "deploy-rejected"
        model_id = "model-rejected"

        # Submit safety evaluation but get it rejected
        sub = temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id=deployment_id,
                model_id=model_id,
                title="Safety Evaluation",
                summary="Safety evaluation submission.",
                evidence_hash="a" * 64
            ),
            lab_id="TestLab"
        )
        temp_ledger.review_compliance(
            ComplianceReviewCreate(
                submission_id=sub.id,
                status=ComplianceStatus.REJECTED,
                notes="Evidence did not match hash.",
                evidence_verified=False
            ),
            auditor_id="Auditor"
        )

        status = temp_ledger.get_deployment_compliance_status(deployment_id, model_id)

        assert status.is_cleared is False
        assert status.compliance_complete is False
        assert len(status.rejected_templates) == 1
        assert "BLOCKED" in status.message
        assert "Rejected" in status.message


class TestCompliancePersistence:
    """Tests for compliance submission persistence."""

    def test_compliance_persistence(self):
        """Compliance submissions should persist across instances."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            # Create ledger and add submission
            ledger1 = TransparencyLedger(storage_path=temp_path)
            submission = ledger1.submit_compliance(
                ComplianceSubmissionCreate(
                    template_type=ComplianceTemplateType.INCIDENT_REPORT,
                    deployment_id="deploy-persist",
                    model_id="model-persist",
                    title="Persistent Incident Report",
                    summary="This submission should persist across instances.",
                    evidence_hash="f" * 64
                ),
                lab_id="TestLab"
            )

            # Load in new instance
            ledger2 = TransparencyLedger(storage_path=temp_path)
            retrieved = ledger2.get_compliance_submission(submission.id)

            assert retrieved is not None
            assert retrieved.title == "Persistent Incident Report"

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_reset_clears_compliance(self, temp_ledger):
        """Reset should clear compliance submissions."""
        temp_ledger.submit_compliance(
            ComplianceSubmissionCreate(
                template_type=ComplianceTemplateType.SAFETY_EVALUATION,
                deployment_id="deploy-reset",
                model_id="model-reset",
                title="To be deleted",
                summary="This will be cleared on reset.",
                evidence_hash="g" * 64
            ),
            lab_id="TestLab"
        )

        assert len(temp_ledger.compliance_submissions) == 1

        temp_ledger.reset()

        assert len(temp_ledger.compliance_submissions) == 0
