"""Pydantic models for AI Flight Recorder."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of AI governance events that can be logged."""

    TRAINING_STARTED = "training_started"
    TRAINING_COMPLETED = "training_completed"
    SAFETY_EVAL_RUN = "safety_eval_run"
    SAFETY_EVAL_PASSED = "safety_eval_passed"
    SAFETY_EVAL_FAILED = "safety_eval_failed"
    MODEL_DEPLOYED = "model_deployed"
    INCIDENT_REPORTED = "incident_reported"


class EventCreate(BaseModel):
    """Schema for creating a new event."""

    event_type: EventType
    description: str = Field(..., min_length=1, max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    """Complete event record with hash chain data."""

    id: int
    event_type: EventType
    description: str
    metadata: dict[str, Any]
    timestamp: datetime
    previous_hash: Optional[str] = None
    hash: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VerificationResult(BaseModel):
    """Result of chain verification."""

    is_valid: bool
    checked_events: int
    first_invalid_index: Optional[int] = None
    error_message: Optional[str] = None


class LogStatus(BaseModel):
    """Current status of the audit log."""

    total_events: int
    latest_hash: Optional[str] = None
    merkle_root: Optional[str] = None
    is_chain_valid: bool
    last_event_time: Optional[datetime] = None


class MerkleProofStep(BaseModel):
    """Single step in a Merkle proof."""

    hash: str
    position: str  # "left" or "right"


class ProofResponse(BaseModel):
    """Merkle proof for an event."""

    event_id: int
    event_hash: str
    merkle_root: str
    proof: list[MerkleProofStep]
    is_valid: bool


class TamperRequest(BaseModel):
    """Request to simulate tampering (demo only)."""

    event_id: int
    new_description: Optional[str] = None
    new_metadata: Optional[dict[str, Any]] = None


# Zero-Knowledge Proof Models

class ZKCommitment(BaseModel):
    """A cryptographic commitment to an event count."""

    id: str
    commitment_hash: str
    event_type: EventType
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ZKCommitmentRequest(BaseModel):
    """Request to create a new ZK commitment."""

    event_type: EventType


class ZKProofRequest(BaseModel):
    """Request to generate a ZK proof."""

    commitment_id: str
    threshold: int = Field(..., ge=0)


class ZKProof(BaseModel):
    """Zero-knowledge proof that count >= threshold."""

    commitment_id: str
    threshold: int
    excess_commitment: str
    proof_data: dict[str, Any]
    is_valid: bool
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ZKVerifyRequest(BaseModel):
    """Request to verify a ZK proof."""

    commitment_hash: str
    threshold: int
    excess_commitment: str
    proof_data: dict[str, Any]


class ZKVerifyResponse(BaseModel):
    """Response from ZK proof verification."""

    is_valid: bool
    message: str


# Shared Transparency / Whistleblower Models

class SubmitterRole(str, Enum):
    """Role of the entity submitting to the shared ledger."""

    LAB = "lab"  # Frontier lab (public identity)
    WHISTLEBLOWER = "whistleblower"  # Anonymous submitter
    AUDITOR = "auditor"  # Independent auditor (public identity)


class ConcernStatus(str, Enum):
    """Status of a concern in the resolution workflow."""

    OPEN = "open"  # Newly raised, not yet addressed
    ADDRESSED = "addressed"  # Lab has responded
    DISPUTED = "disputed"  # Whistleblower disputes lab's response
    RESOLVED = "resolved"  # Auditor has verified resolution


class ConcernCategory(str, Enum):
    """Categories of safety/governance concerns."""

    SAFETY_EVAL = "safety_eval"  # Safety evaluation issues
    TRAINING_DATA = "training_data"  # Training data concerns
    CAPABILITY_RISK = "capability_risk"  # Dangerous capability concerns
    DEPLOYMENT = "deployment"  # Deployment process issues
    DOCUMENTATION = "documentation"  # Missing/incorrect documentation
    PROCESS = "process"  # Process/governance violations
    OTHER = "other"


class ConcernCreate(BaseModel):
    """Request to create a new concern."""

    category: ConcernCategory
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    evidence_hash: Optional[str] = None  # Hash of supporting evidence
    deployment_id: Optional[str] = None  # Link to specific deployment
    model_id: Optional[str] = None  # Link to specific model


class Concern(BaseModel):
    """A concern raised in the shared transparency ledger."""

    id: str
    category: ConcernCategory
    title: str
    description: str
    submitter_id: str  # Anonymous ID for whistleblowers, org name for labs
    submitter_role: SubmitterRole
    status: ConcernStatus
    evidence_hash: Optional[str] = None
    deployment_id: Optional[str] = None
    model_id: Optional[str] = None
    timestamp: datetime
    hash: str  # For tamper-proof chain

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConcernResponseCreate(BaseModel):
    """Request to respond to a concern."""

    concern_id: str
    response_text: str = Field(..., min_length=10, max_length=5000)
    evidence_hash: Optional[str] = None  # Hash of evidence supporting response


class ConcernResponse(BaseModel):
    """A response to a concern (from lab or auditor)."""

    id: str
    concern_id: str
    response_text: str
    responder_id: str
    responder_role: SubmitterRole
    evidence_hash: Optional[str] = None
    timestamp: datetime
    hash: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ResolutionCreate(BaseModel):
    """Request to mark a concern as resolved."""

    concern_id: str
    resolution_notes: str = Field(..., min_length=10, max_length=2000)


class Resolution(BaseModel):
    """Final resolution of a concern by auditor."""

    id: str
    concern_id: str
    resolution_notes: str
    auditor_id: str
    timestamp: datetime
    hash: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DeploymentClearance(BaseModel):
    """Clearance status for a deployment."""

    deployment_id: str
    total_concerns: int
    open_concerns: int
    addressed_concerns: int
    resolved_concerns: int
    is_cleared: bool  # True only if all concerns are resolved
    message: str


class AnonymousIdRequest(BaseModel):
    """Request to generate an anonymous ID."""

    identity: str = Field(..., min_length=1)  # e.g., email
    salt: str = Field(..., min_length=8)  # Secret salt


class AnonymousIdResponse(BaseModel):
    """Response with generated anonymous ID."""

    anonymous_id: str
    message: str


# === Compliance Submission Models ===

class ComplianceTemplateType(str, Enum):
    """Types of compliance templates labs must submit."""

    SAFETY_EVALUATION = "safety_evaluation"  # Pre-deployment safety eval results
    TRAINING_DATA = "training_data"  # Training data documentation
    CAPABILITY_ASSESSMENT = "capability_assessment"  # Dangerous capability assessment
    RED_TEAM_REPORT = "red_team_report"  # Red team testing results
    HUMAN_OVERSIGHT = "human_oversight"  # Human oversight attestation
    INCIDENT_REPORT = "incident_report"  # Post-deployment incident reports


class ComplianceStatus(str, Enum):
    """Status of a compliance submission."""

    SUBMITTED = "submitted"  # Lab has submitted, awaiting review
    UNDER_REVIEW = "under_review"  # Auditor is reviewing
    VERIFIED = "verified"  # Auditor has verified
    REJECTED = "rejected"  # Auditor has rejected, needs resubmission


class ComplianceSubmissionCreate(BaseModel):
    """Request to submit a compliance document."""

    template_type: ComplianceTemplateType
    deployment_id: str = Field(..., min_length=1)
    model_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=5, max_length=200)
    summary: str = Field(..., min_length=10, max_length=2000)
    evidence_hash: str = Field(..., min_length=64, max_length=64)  # Required SHA-256 hash
    metadata: dict[str, Any] = Field(default_factory=dict)  # Template-specific fields


class ComplianceSubmission(BaseModel):
    """A compliance submission in the ledger."""

    id: str
    template_type: ComplianceTemplateType
    deployment_id: str
    model_id: str
    lab_id: str
    title: str
    summary: str
    evidence_hash: str
    metadata: dict[str, Any]
    status: ComplianceStatus
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    hash: str  # For tamper-proof chain

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ComplianceReviewCreate(BaseModel):
    """Request to review a compliance submission (auditor only)."""

    submission_id: str
    status: ComplianceStatus = Field(..., description="Must be VERIFIED or REJECTED")
    notes: str = Field(..., min_length=10, max_length=2000)
    evidence_verified: bool = Field(..., description="Did evidence hash match actual evidence?")


class DeploymentComplianceStatus(BaseModel):
    """Full compliance status for a deployment."""

    deployment_id: str
    model_id: str
    required_templates: list[ComplianceTemplateType]
    submitted_templates: list[ComplianceTemplateType]
    verified_templates: list[ComplianceTemplateType]
    missing_templates: list[ComplianceTemplateType]
    rejected_templates: list[ComplianceTemplateType]

    # Concern status (from existing system)
    open_concerns: int
    unresolved_concerns: int
    resolved_concerns: int

    # Overall gate status
    compliance_complete: bool  # All required templates verified
    concerns_resolved: bool  # All concerns resolved
    is_cleared: bool  # Both compliance complete AND concerns resolved
    message: str


# === Role Authentication Models ===

class PartyRole(str, Enum):
    """Valid roles for authorized parties."""

    LAB = "lab"
    AUDITOR = "auditor"
    GOVERNMENT = "government"


class PartyRegistrationRequest(BaseModel):
    """Request to register a new authorized party."""

    name: str = Field(..., min_length=1, max_length=100)
    role: PartyRole


class PartyRegistrationResponse(BaseModel):
    """Response from party registration with API key (shown only once)."""

    party_id: str
    name: str
    role: PartyRole
    api_key: str = Field(..., description="API key - save this! It will not be shown again.")


class PartyInfo(BaseModel):
    """Public information about an authorized party."""

    id: str
    name: str
    role: PartyRole
    created_at: datetime
    is_active: bool

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class KeyRotationResponse(BaseModel):
    """Response from API key rotation."""

    party_id: str
    new_api_key: str = Field(..., description="New API key - save this! It will not be shown again.")
    message: str = "API key rotated successfully. Old key is now invalid."


# === Multi-Mirror Simulation Models ===

# Note: MirrorParty reuses PartyRole values - they represent the same entities
MirrorParty = PartyRole


class MirrorStatus(BaseModel):
    """Status of a single mirror copy."""

    party: MirrorParty
    record_count: int
    hash: str
    last_sync: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class MirrorComparisonResult(BaseModel):
    """Result of comparing all mirrors."""

    all_consistent: bool
    lab_hash: str
    auditor_hash: str
    government_hash: str
    divergent_parties: list[MirrorParty]
    message: str


class TamperDetectionResult(BaseModel):
    """Result of tamper detection across mirrors."""

    tampering_detected: bool
    affected_parties: list[MirrorParty]
    affected_records: list[dict]
    recommendation: str


class MirrorTamperRequest(BaseModel):
    """Request to tamper with a mirror (demo only)."""

    party: MirrorParty
    record_id: str
    new_value: dict


class MirrorSyncRequest(BaseModel):
    """Request to sync mirrors from ledger data."""

    include_concerns: bool = True
    include_submissions: bool = True
