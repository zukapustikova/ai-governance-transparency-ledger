"""Shared Transparency Ledger for Whistleblower-Aware Governance."""

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from .crypto_utils import generate_anonymous_id, hash_data
from .models import (
    ComplianceReviewCreate,
    ComplianceStatus,
    ComplianceSubmission,
    ComplianceSubmissionCreate,
    ComplianceTemplateType,
    Concern,
    ConcernCategory,
    ConcernCreate,
    ConcernResponse,
    ConcernResponseCreate,
    ConcernStatus,
    DeploymentClearance,
    DeploymentComplianceStatus,
    Resolution,
    ResolutionCreate,
    SubmitterRole,
)

# Default required templates for deployment clearance
DEFAULT_REQUIRED_TEMPLATES = [
    ComplianceTemplateType.SAFETY_EVALUATION,
    ComplianceTemplateType.CAPABILITY_ASSESSMENT,
    ComplianceTemplateType.RED_TEAM_REPORT,
]


class TransparencyLedger:
    """
    Shared Transparency Ledger where labs, whistleblowers, and auditors
    can all submit and view concerns.

    Key properties:
    - All submissions visible to everyone
    - Whistleblower identities protected via anonymous IDs
    - Tamper-proof through hash chain
    - Deployment blocked until all concerns resolved
    """

    def __init__(self, storage_path: str = "data/transparency_ledger.json"):
        self.storage_path = Path(storage_path)
        self.concerns: dict[str, dict] = {}
        self.responses: dict[str, dict] = {}
        self.resolutions: dict[str, dict] = {}
        self.compliance_submissions: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load ledger from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.concerns = data.get("concerns", {})
                        self.responses = data.get("responses", {})
                        self.resolutions = data.get("resolutions", {})
                        self.compliance_submissions = data.get("compliance_submissions", {})
            except (json.JSONDecodeError, IOError):
                # If file is empty or corrupted, start fresh
                pass

    def _save(self) -> None:
        """Persist ledger to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump({
                "concerns": self.concerns,
                "responses": self.responses,
                "resolutions": self.resolutions,
                "compliance_submissions": self.compliance_submissions
            }, f, indent=2, default=str)

    def _generate_id(self) -> str:
        """Generate a unique ID for entries."""
        return secrets.token_hex(8)

    def _compute_hash(self, data: dict) -> str:
        """Compute hash for tamper-proofing."""
        return hash_data(data)

    # === Concern Management ===

    def raise_concern(
        self,
        concern: ConcernCreate,
        submitter_id: str,
        submitter_role: SubmitterRole
    ) -> Concern:
        """
        Raise a new concern in the shared ledger.

        Args:
            concern: The concern details
            submitter_id: Anonymous ID (whistleblower) or org name (lab/auditor)
            submitter_role: Role of the submitter

        Returns:
            The created concern record
        """
        concern_id = self._generate_id()
        timestamp = datetime.utcnow()

        concern_data = {
            "id": concern_id,
            "category": concern.category.value,
            "title": concern.title,
            "description": concern.description,
            "submitter_id": submitter_id,
            "submitter_role": submitter_role.value,
            "status": ConcernStatus.OPEN.value,
            "evidence_hash": concern.evidence_hash,
            "deployment_id": concern.deployment_id,
            "model_id": concern.model_id,
            "timestamp": timestamp.isoformat(),
        }

        concern_data["hash"] = self._compute_hash(concern_data)
        self.concerns[concern_id] = concern_data
        self._save()

        return Concern(
            id=concern_id,
            category=concern.category,
            title=concern.title,
            description=concern.description,
            submitter_id=submitter_id,
            submitter_role=submitter_role,
            status=ConcernStatus.OPEN,
            evidence_hash=concern.evidence_hash,
            deployment_id=concern.deployment_id,
            model_id=concern.model_id,
            timestamp=timestamp,
            hash=concern_data["hash"]
        )

    def get_concern(self, concern_id: str) -> Optional[Concern]:
        """Get a specific concern by ID."""
        if concern_id not in self.concerns:
            return None

        data = self.concerns[concern_id]
        return Concern(
            id=data["id"],
            category=ConcernCategory(data["category"]),
            title=data["title"],
            description=data["description"],
            submitter_id=data["submitter_id"],
            submitter_role=SubmitterRole(data["submitter_role"]),
            status=ConcernStatus(data["status"]),
            evidence_hash=data.get("evidence_hash"),
            deployment_id=data.get("deployment_id"),
            model_id=data.get("model_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            hash=data["hash"]
        )

    def list_concerns(
        self,
        deployment_id: Optional[str] = None,
        status: Optional[ConcernStatus] = None,
        category: Optional[ConcernCategory] = None
    ) -> list[Concern]:
        """List concerns with optional filters."""
        results = []
        for data in self.concerns.values():
            # Apply filters
            if deployment_id and data.get("deployment_id") != deployment_id:
                continue
            if status and data["status"] != status.value:
                continue
            if category and data["category"] != category.value:
                continue

            results.append(Concern(
                id=data["id"],
                category=ConcernCategory(data["category"]),
                title=data["title"],
                description=data["description"],
                submitter_id=data["submitter_id"],
                submitter_role=SubmitterRole(data["submitter_role"]),
                status=ConcernStatus(data["status"]),
                evidence_hash=data.get("evidence_hash"),
                deployment_id=data.get("deployment_id"),
                model_id=data.get("model_id"),
                timestamp=datetime.fromisoformat(data["timestamp"]),
                hash=data["hash"]
            ))

        # Sort by timestamp (newest first)
        results.sort(key=lambda c: c.timestamp, reverse=True)
        return results

    # === Response Management ===

    def respond_to_concern(
        self,
        response: ConcernResponseCreate,
        responder_id: str,
        responder_role: SubmitterRole
    ) -> Optional[ConcernResponse]:
        """
        Respond to a concern. Updates concern status to ADDRESSED.

        Args:
            response: The response details
            responder_id: ID of responder
            responder_role: Role of responder

        Returns:
            The created response record, or None if concern not found
        """
        if response.concern_id not in self.concerns:
            return None

        response_id = self._generate_id()
        timestamp = datetime.utcnow()

        response_data = {
            "id": response_id,
            "concern_id": response.concern_id,
            "response_text": response.response_text,
            "responder_id": responder_id,
            "responder_role": responder_role.value,
            "evidence_hash": response.evidence_hash,
            "timestamp": timestamp.isoformat(),
        }

        response_data["hash"] = self._compute_hash(response_data)
        self.responses[response_id] = response_data

        # Update concern status to ADDRESSED (unless already resolved)
        concern = self.concerns[response.concern_id]
        if concern["status"] != ConcernStatus.RESOLVED.value:
            concern["status"] = ConcernStatus.ADDRESSED.value

        self._save()

        return ConcernResponse(
            id=response_id,
            concern_id=response.concern_id,
            response_text=response.response_text,
            responder_id=responder_id,
            responder_role=responder_role,
            evidence_hash=response.evidence_hash,
            timestamp=timestamp,
            hash=response_data["hash"]
        )

    def dispute_response(self, concern_id: str, disputer_id: str) -> bool:
        """
        Mark a concern as disputed (whistleblower disagrees with lab's response).

        Returns:
            True if successful, False if concern not found
        """
        if concern_id not in self.concerns:
            return False

        self.concerns[concern_id]["status"] = ConcernStatus.DISPUTED.value
        self._save()
        return True

    def get_responses(self, concern_id: str) -> list[ConcernResponse]:
        """Get all responses to a specific concern."""
        results = []
        for data in self.responses.values():
            if data["concern_id"] == concern_id:
                results.append(ConcernResponse(
                    id=data["id"],
                    concern_id=data["concern_id"],
                    response_text=data["response_text"],
                    responder_id=data["responder_id"],
                    responder_role=SubmitterRole(data["responder_role"]),
                    evidence_hash=data.get("evidence_hash"),
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    hash=data["hash"]
                ))

        results.sort(key=lambda r: r.timestamp)
        return results

    # === Resolution Management ===

    def resolve_concern(
        self,
        resolution: ResolutionCreate,
        auditor_id: str
    ) -> Optional[Resolution]:
        """
        Mark a concern as resolved (auditor only).

        Args:
            resolution: Resolution details
            auditor_id: ID of the auditor

        Returns:
            The resolution record, or None if concern not found
        """
        if resolution.concern_id not in self.concerns:
            return None

        resolution_id = self._generate_id()
        timestamp = datetime.utcnow()

        resolution_data = {
            "id": resolution_id,
            "concern_id": resolution.concern_id,
            "resolution_notes": resolution.resolution_notes,
            "auditor_id": auditor_id,
            "timestamp": timestamp.isoformat(),
        }

        resolution_data["hash"] = self._compute_hash(resolution_data)
        self.resolutions[resolution_id] = resolution_data

        # Update concern status to RESOLVED
        self.concerns[resolution.concern_id]["status"] = ConcernStatus.RESOLVED.value
        self._save()

        return Resolution(
            id=resolution_id,
            concern_id=resolution.concern_id,
            resolution_notes=resolution.resolution_notes,
            auditor_id=auditor_id,
            timestamp=timestamp,
            hash=resolution_data["hash"]
        )

    # === Compliance Submission Management ===

    def submit_compliance(
        self,
        submission: ComplianceSubmissionCreate,
        lab_id: str
    ) -> ComplianceSubmission:
        """
        Submit a compliance document to the ledger.

        Args:
            submission: The compliance submission details
            lab_id: ID of the lab submitting

        Returns:
            The created compliance submission record
        """
        submission_id = self._generate_id()
        timestamp = datetime.utcnow()

        submission_data = {
            "id": submission_id,
            "template_type": submission.template_type.value,
            "deployment_id": submission.deployment_id,
            "model_id": submission.model_id,
            "lab_id": lab_id,
            "title": submission.title,
            "summary": submission.summary,
            "evidence_hash": submission.evidence_hash,
            "metadata": submission.metadata,
            "status": ComplianceStatus.SUBMITTED.value,
            "submitted_at": timestamp.isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
        }

        submission_data["hash"] = self._compute_hash(submission_data)
        self.compliance_submissions[submission_id] = submission_data
        self._save()

        return ComplianceSubmission(
            id=submission_id,
            template_type=submission.template_type,
            deployment_id=submission.deployment_id,
            model_id=submission.model_id,
            lab_id=lab_id,
            title=submission.title,
            summary=submission.summary,
            evidence_hash=submission.evidence_hash,
            metadata=submission.metadata,
            status=ComplianceStatus.SUBMITTED,
            submitted_at=timestamp,
            hash=submission_data["hash"]
        )

    def get_compliance_submission(self, submission_id: str) -> Optional[ComplianceSubmission]:
        """Get a specific compliance submission by ID."""
        if submission_id not in self.compliance_submissions:
            return None

        data = self.compliance_submissions[submission_id]
        return ComplianceSubmission(
            id=data["id"],
            template_type=ComplianceTemplateType(data["template_type"]),
            deployment_id=data["deployment_id"],
            model_id=data["model_id"],
            lab_id=data["lab_id"],
            title=data["title"],
            summary=data["summary"],
            evidence_hash=data["evidence_hash"],
            metadata=data.get("metadata", {}),
            status=ComplianceStatus(data["status"]),
            submitted_at=datetime.fromisoformat(data["submitted_at"]),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
            reviewed_by=data.get("reviewed_by"),
            review_notes=data.get("review_notes"),
            hash=data["hash"]
        )

    def list_compliance_submissions(
        self,
        deployment_id: Optional[str] = None,
        lab_id: Optional[str] = None,
        template_type: Optional[ComplianceTemplateType] = None,
        status: Optional[ComplianceStatus] = None
    ) -> list[ComplianceSubmission]:
        """List compliance submissions with optional filters."""
        results = []
        for data in self.compliance_submissions.values():
            # Apply filters
            if deployment_id and data["deployment_id"] != deployment_id:
                continue
            if lab_id and data["lab_id"] != lab_id:
                continue
            if template_type and data["template_type"] != template_type.value:
                continue
            if status and data["status"] != status.value:
                continue

            results.append(ComplianceSubmission(
                id=data["id"],
                template_type=ComplianceTemplateType(data["template_type"]),
                deployment_id=data["deployment_id"],
                model_id=data["model_id"],
                lab_id=data["lab_id"],
                title=data["title"],
                summary=data["summary"],
                evidence_hash=data["evidence_hash"],
                metadata=data.get("metadata", {}),
                status=ComplianceStatus(data["status"]),
                submitted_at=datetime.fromisoformat(data["submitted_at"]),
                reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
                reviewed_by=data.get("reviewed_by"),
                review_notes=data.get("review_notes"),
                hash=data["hash"]
            ))

        # Sort by submission time (newest first)
        results.sort(key=lambda s: s.submitted_at, reverse=True)
        return results

    def review_compliance(
        self,
        review: ComplianceReviewCreate,
        auditor_id: str
    ) -> Optional[ComplianceSubmission]:
        """
        Review a compliance submission (auditor only).

        Args:
            review: The review details
            auditor_id: ID of the auditor

        Returns:
            The updated submission record, or None if not found
        """
        if review.submission_id not in self.compliance_submissions:
            return None

        if review.status not in [ComplianceStatus.VERIFIED, ComplianceStatus.REJECTED]:
            raise ValueError("Review status must be VERIFIED or REJECTED")

        data = self.compliance_submissions[review.submission_id]
        timestamp = datetime.utcnow()

        data["status"] = review.status.value
        data["reviewed_at"] = timestamp.isoformat()
        data["reviewed_by"] = auditor_id
        data["review_notes"] = review.notes
        data["evidence_verified"] = review.evidence_verified

        # Recompute hash
        data["hash"] = self._compute_hash(data)
        self._save()

        return self.get_compliance_submission(review.submission_id)

    # === Deployment Clearance ===

    def check_deployment_clearance(self, deployment_id: str) -> DeploymentClearance:
        """
        Check if a deployment is cleared (all concerns resolved).

        Args:
            deployment_id: The deployment to check

        Returns:
            Clearance status with concern breakdown
        """
        concerns = self.list_concerns(deployment_id=deployment_id)

        open_count = sum(1 for c in concerns if c.status == ConcernStatus.OPEN)
        addressed_count = sum(1 for c in concerns if c.status == ConcernStatus.ADDRESSED)
        disputed_count = sum(1 for c in concerns if c.status == ConcernStatus.DISPUTED)
        resolved_count = sum(1 for c in concerns if c.status == ConcernStatus.RESOLVED)

        unresolved = open_count + addressed_count + disputed_count
        is_cleared = unresolved == 0

        if is_cleared:
            message = f"Deployment cleared. {resolved_count} concern(s) resolved."
        else:
            message = f"Deployment BLOCKED. {unresolved} unresolved concern(s): {open_count} open, {addressed_count} addressed, {disputed_count} disputed."

        return DeploymentClearance(
            deployment_id=deployment_id,
            total_concerns=len(concerns),
            open_concerns=open_count,
            addressed_concerns=addressed_count + disputed_count,
            resolved_concerns=resolved_count,
            is_cleared=is_cleared,
            message=message
        )

    def get_deployment_compliance_status(
        self,
        deployment_id: str,
        model_id: str,
        required_templates: Optional[list[ComplianceTemplateType]] = None
    ) -> DeploymentComplianceStatus:
        """
        Get full compliance status for a deployment - checks BOTH compliance submissions
        AND concerns. This is the unified deployment gate.

        Args:
            deployment_id: The deployment to check
            model_id: The model being deployed
            required_templates: Templates required for clearance (defaults to standard set)

        Returns:
            Full compliance status with both compliance and concern details
        """
        if required_templates is None:
            required_templates = DEFAULT_REQUIRED_TEMPLATES

        # Get compliance submissions for this deployment
        submissions = self.list_compliance_submissions(deployment_id=deployment_id)

        submitted_templates = []
        verified_templates = []
        rejected_templates = []

        for sub in submissions:
            submitted_templates.append(sub.template_type)
            if sub.status == ComplianceStatus.VERIFIED:
                verified_templates.append(sub.template_type)
            elif sub.status == ComplianceStatus.REJECTED:
                rejected_templates.append(sub.template_type)

        # Find missing templates
        missing_templates = [t for t in required_templates if t not in verified_templates]

        # Get concern status
        concerns = self.list_concerns(deployment_id=deployment_id)
        open_count = sum(1 for c in concerns if c.status == ConcernStatus.OPEN)
        addressed_count = sum(1 for c in concerns if c.status == ConcernStatus.ADDRESSED)
        disputed_count = sum(1 for c in concerns if c.status == ConcernStatus.DISPUTED)
        resolved_count = sum(1 for c in concerns if c.status == ConcernStatus.RESOLVED)
        unresolved_concerns = open_count + addressed_count + disputed_count

        # Compute clearance
        compliance_complete = len(missing_templates) == 0 and len(rejected_templates) == 0
        concerns_resolved = unresolved_concerns == 0
        is_cleared = compliance_complete and concerns_resolved

        # Build message
        messages = []
        if is_cleared:
            messages.append("CLEARED for deployment.")
        else:
            messages.append("BLOCKED.")
            if missing_templates:
                missing_names = [t.value for t in missing_templates]
                messages.append(f"Missing templates: {', '.join(missing_names)}.")
            if rejected_templates:
                rejected_names = [t.value for t in rejected_templates]
                messages.append(f"Rejected templates need resubmission: {', '.join(rejected_names)}.")
            if unresolved_concerns > 0:
                messages.append(f"Unresolved concerns: {unresolved_concerns} ({open_count} open, {addressed_count} addressed, {disputed_count} disputed).")

        return DeploymentComplianceStatus(
            deployment_id=deployment_id,
            model_id=model_id,
            required_templates=required_templates,
            submitted_templates=list(set(submitted_templates)),
            verified_templates=list(set(verified_templates)),
            missing_templates=missing_templates,
            rejected_templates=list(set(rejected_templates)),
            open_concerns=open_count,
            unresolved_concerns=unresolved_concerns,
            resolved_concerns=resolved_count,
            compliance_complete=compliance_complete,
            concerns_resolved=concerns_resolved,
            is_cleared=is_cleared,
            message=" ".join(messages)
        )

    # === Statistics ===

    def get_stats(self) -> dict:
        """Get overall ledger statistics."""
        all_concerns = list(self.concerns.values())
        all_submissions = list(self.compliance_submissions.values())

        return {
            "total_concerns": len(all_concerns),
            "concerns_by_status": {
                "open": sum(1 for c in all_concerns if c["status"] == ConcernStatus.OPEN.value),
                "addressed": sum(1 for c in all_concerns if c["status"] == ConcernStatus.ADDRESSED.value),
                "disputed": sum(1 for c in all_concerns if c["status"] == ConcernStatus.DISPUTED.value),
                "resolved": sum(1 for c in all_concerns if c["status"] == ConcernStatus.RESOLVED.value),
            },
            "concerns_by_role": {
                "lab": sum(1 for c in all_concerns if c["submitter_role"] == SubmitterRole.LAB.value),
                "whistleblower": sum(1 for c in all_concerns if c["submitter_role"] == SubmitterRole.WHISTLEBLOWER.value),
                "auditor": sum(1 for c in all_concerns if c["submitter_role"] == SubmitterRole.AUDITOR.value),
            },
            "total_responses": len(self.responses),
            "total_resolutions": len(self.resolutions),
            "total_compliance_submissions": len(all_submissions),
            "compliance_by_status": {
                "submitted": sum(1 for s in all_submissions if s["status"] == ComplianceStatus.SUBMITTED.value),
                "under_review": sum(1 for s in all_submissions if s["status"] == ComplianceStatus.UNDER_REVIEW.value),
                "verified": sum(1 for s in all_submissions if s["status"] == ComplianceStatus.VERIFIED.value),
                "rejected": sum(1 for s in all_submissions if s["status"] == ComplianceStatus.REJECTED.value),
            },
            "compliance_by_template": {
                t.value: sum(1 for s in all_submissions if s["template_type"] == t.value)
                for t in ComplianceTemplateType
            },
        }

    def reset(self) -> None:
        """Clear all data (demo purposes only)."""
        self.concerns = {}
        self.responses = {}
        self.resolutions = {}
        self.compliance_submissions = {}
        self._save()
