"""FastAPI REST API for AI Flight Recorder."""

from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware

from backend.audit_log import AuditLog
from backend.auth import auth_store, get_current_party, AuthorizedParty, check_registration_rate_limit, registration_rate_limiter
from backend.merkle_tree import MerkleTree, ProofStep
from backend.models import (
    Event,
    EventCreate,
    EventType,
    KeyRotationResponse,
    LogStatus,
    MerkleProofStep,
    PartyInfo,
    PartyRegistrationRequest,
    PartyRegistrationResponse,
    PartyRole,
    ProofResponse,
    TamperRequest,
    VerificationResult,
    ZKCommitment,
    ZKCommitmentRequest,
    ZKProof,
    ZKProofRequest,
    ZKVerifyRequest,
    ZKVerifyResponse,
)
from backend.zk_proofs import ZKCommitmentStore

# Initialize FastAPI app
app = FastAPI(
    title="AI Governance Transparency Ledger",
    description="Shared transparency ledger for frontier AI compliance verification",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize audit log
audit_log = AuditLog(storage_path="data/audit_log.json")


def get_event_count_by_type(event_type: EventType) -> int:
    """Get count of events by type for ZK commitments."""
    return len([e for e in audit_log.events if e.event_type == event_type])


# Initialize ZK commitment store with callback to get event counts
zk_store = ZKCommitmentStore(
    storage_path="data/zk_store.json",
    get_event_count=get_event_count_by_type
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "ai-flight-recorder"}


@app.post("/events", response_model=Event)
async def create_event(event: EventCreate):
    """
    Add a new event to the audit log.

    The event is automatically assigned a timestamp and hash
    that chains to the previous event.
    """
    return audit_log.add_event(event)


@app.get("/events", response_model=list[Event])
async def get_events(
    limit: Optional[int] = Query(None, ge=1, le=1000),
    event_type: Optional[EventType] = None
):
    """
    Retrieve events from the audit log.

    Events are returned in reverse chronological order (most recent first).
    """
    return audit_log.get_events(limit=limit, event_type=event_type)


@app.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: int):
    """Get a specific event by ID."""
    event = audit_log.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/status", response_model=LogStatus)
async def get_status():
    """Get current status of the audit log."""
    events = audit_log.events
    verification = audit_log.verify_chain()

    # Build Merkle tree for root hash
    merkle_root = None
    if events:
        tree = MerkleTree([e.hash for e in events])
        merkle_root = tree.get_root()

    return LogStatus(
        total_events=len(events),
        latest_hash=audit_log.get_latest_hash(),
        merkle_root=merkle_root,
        is_chain_valid=verification.is_valid,
        last_event_time=events[-1].timestamp if events else None
    )


@app.get("/verify", response_model=VerificationResult)
async def verify_chain():
    """
    Verify the integrity of the entire hash chain.

    Returns detailed verification results including
    the location of any detected tampering.
    """
    return audit_log.verify_chain()


@app.get("/proof/{event_id}", response_model=ProofResponse)
async def get_merkle_proof(event_id: int):
    """
    Generate a Merkle proof for a specific event.

    This proof can be used to verify that an event is part
    of the log without revealing all other events.
    """
    event = audit_log.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build Merkle tree
    events = audit_log.events
    if not events:
        raise HTTPException(status_code=400, detail="No events in log")

    tree = MerkleTree([e.hash for e in events])
    proof = tree.get_proof(event_id)
    merkle_root = tree.get_root()

    # Verify the proof
    is_valid = MerkleTree.verify_proof(event.hash, proof, merkle_root)

    return ProofResponse(
        event_id=event_id,
        event_hash=event.hash,
        merkle_root=merkle_root,
        proof=[MerkleProofStep(hash=p.hash, position=p.position) for p in proof],
        is_valid=is_valid
    )


@app.post("/proof/verify")
async def verify_merkle_proof(
    event_hash: str,
    merkle_root: str,
    proof: list[MerkleProofStep]
):
    """
    Verify a Merkle proof.

    Allows external verification that an event is part of the log.
    """
    proof_steps = [ProofStep(hash=p.hash, position=p.position) for p in proof]
    is_valid = MerkleTree.verify_proof(event_hash, proof_steps, merkle_root)

    return {"is_valid": is_valid}


# Demo endpoints for demonstration purposes

@app.post("/demo/tamper")
async def demo_tamper(request: TamperRequest):
    """
    Simulate tampering with an event (DEMO ONLY).

    This modifies event data without updating the hash,
    which will cause chain verification to fail.
    """
    success = audit_log.tamper_event(
        event_id=request.event_id,
        new_description=request.new_description,
        new_metadata=request.new_metadata
    )

    if not success:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "message": f"Event {request.event_id} has been tampered with",
        "warning": "Chain verification will now fail!"
    }


@app.post("/demo/reset")
async def demo_reset():
    """
    Reset the audit log (DEMO ONLY).

    Clears all events for a fresh demonstration.
    """
    audit_log.reset()
    return {"message": "Audit log has been reset"}


@app.post("/demo/populate")
async def demo_populate():
    """
    Populate the log with sample events (DEMO ONLY).

    Creates a realistic sequence of AI governance events.
    """
    sample_events = [
        EventCreate(
            event_type=EventType.TRAINING_STARTED,
            description="Initiated training run for GPT-Safe v2.1",
            metadata={
                "model_id": "gpt-safe-v2.1",
                "dataset": "curated-safety-v3",
                "compute_hours": 1000
            }
        ),
        EventCreate(
            event_type=EventType.TRAINING_COMPLETED,
            description="Training completed successfully",
            metadata={
                "model_id": "gpt-safe-v2.1",
                "final_loss": 0.023,
                "training_time_hours": 847
            }
        ),
        EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Running comprehensive safety evaluation suite",
            metadata={
                "eval_suite": "safety-benchmark-v4",
                "test_cases": 15000
            }
        ),
        EventCreate(
            event_type=EventType.SAFETY_EVAL_PASSED,
            description="All safety evaluations passed",
            metadata={
                "harmlessness_score": 0.98,
                "helpfulness_score": 0.94,
                "honesty_score": 0.96
            }
        ),
        EventCreate(
            event_type=EventType.MODEL_DEPLOYED,
            description="Model deployed to production (10% rollout)",
            metadata={
                "environment": "production",
                "rollout_percentage": 10,
                "region": "us-west-2"
            }
        ),
        EventCreate(
            event_type=EventType.MODEL_DEPLOYED,
            description="Model deployed to production (100% rollout)",
            metadata={
                "environment": "production",
                "rollout_percentage": 100,
                "region": "global"
            }
        ),
        EventCreate(
            event_type=EventType.INCIDENT_REPORTED,
            description="Minor incident: Model gave incorrect citation",
            metadata={
                "severity": "low",
                "category": "accuracy",
                "affected_users": 3
            }
        ),
        EventCreate(
            event_type=EventType.SAFETY_EVAL_RUN,
            description="Post-incident safety re-evaluation",
            metadata={
                "eval_suite": "safety-benchmark-v4",
                "focus": "accuracy",
                "triggered_by": "incident-001"
            }
        ),
    ]

    created_events = []
    for event in sample_events:
        created = audit_log.add_event(event)
        created_events.append(created)

    return {
        "message": f"Created {len(created_events)} sample events",
        "event_ids": [e.id for e in created_events]
    }


# Zero-Knowledge Proof Endpoints

@app.post("/zk/commitment", response_model=ZKCommitment)
async def create_zk_commitment(request: ZKCommitmentRequest):
    """
    Create a cryptographic commitment to the current event count.

    This commitment hides the actual count but can later be used
    to prove that the count meets certain thresholds without
    revealing the exact number.

    Use case: "Commit to how many safety evaluations we've run,
    so we can later prove we ran at least N without revealing the exact count."
    """
    return zk_store.create_commitment(request.event_type)


@app.get("/zk/commitment/{commitment_id}", response_model=ZKCommitment)
async def get_zk_commitment(commitment_id: str):
    """
    Retrieve a ZK commitment by ID.

    Returns the public commitment data (not the secret count or blinding factor).
    """
    commitment = zk_store.get_commitment(commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return commitment


@app.post("/zk/prove", response_model=ZKProof)
async def generate_zk_proof(request: ZKProofRequest):
    """
    Generate a zero-knowledge proof that count >= threshold.

    This proof demonstrates that the committed count meets the threshold
    WITHOUT revealing the actual count. A valid proof means:
    - The organization ran AT LEAST `threshold` events of that type
    - The exact count remains private

    Use case: "Prove we ran at least 5 safety evaluations without
    revealing whether we ran 5, 10, or 100."
    """
    proof = zk_store.generate_proof(request.commitment_id, request.threshold)
    if proof is None:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return proof


@app.post("/zk/verify", response_model=ZKVerifyResponse)
async def verify_zk_proof(request: ZKVerifyRequest):
    """
    Verify a zero-knowledge proof without learning the actual count.

    This endpoint can be used by third-party auditors to verify
    that an organization met compliance thresholds without the
    organization revealing sensitive operational data.

    Returns whether the proof is valid and a verification message.
    """
    is_valid, message = ZKCommitmentStore.verify_proof(
        commitment_hash=request.commitment_hash,
        threshold=request.threshold,
        excess_commitment=request.excess_commitment,
        proof_data=request.proof_data
    )
    return ZKVerifyResponse(is_valid=is_valid, message=message)


@app.post("/demo/zk-reset")
async def demo_zk_reset():
    """
    Reset the ZK commitment store (DEMO ONLY).

    Clears all commitments for a fresh demonstration.
    """
    zk_store.reset()
    return {"message": "ZK commitment store has been reset"}


# ============================================================
# Role Authentication Endpoints
# ============================================================

@app.post("/auth/register", response_model=PartyRegistrationResponse)
async def register_party(
    request: PartyRegistrationRequest,
    _: None = Depends(check_registration_rate_limit)
):
    """
    Register a new authorized party and receive an API key.

    IMPORTANT: The API key is returned only once! Store it securely.

    NOTE: This endpoint is unprotected for demo purposes. In production,
    party registration should require admin authentication or be handled
    through a separate secure process.

    Rate limited to 5 registrations per minute per IP address.

    Roles:
    - lab: Can submit compliance documentation and respond to concerns
    - auditor: Can review submissions and resolve concerns
    - government: Can view all data for oversight
    """
    try:
        party_id, api_key = auth_store.register_party(request.name, request.role.value)
        return PartyRegistrationResponse(
            party_id=party_id,
            name=request.name,
            role=request.role,
            api_key=api_key
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/auth/parties", response_model=list[PartyInfo])
async def list_parties():
    """
    List all registered parties.

    Returns public information about all parties (active and inactive).
    API keys are never exposed.
    """
    parties = auth_store.list_parties()
    return [
        PartyInfo(
            id=p.party_id,
            name=p.name,
            role=PartyRole(p.role),
            created_at=p.created_at,
            is_active=p.is_active
        )
        for p in parties
    ]


@app.delete("/auth/parties/{party_id}")
async def revoke_party(party_id: str):
    """
    Revoke access for a party.

    The party's API key will no longer be valid.
    """
    success = auth_store.revoke_party(party_id)
    if not success:
        raise HTTPException(status_code=404, detail="Party not found")
    return {"message": f"Party {party_id} has been revoked"}


@app.post("/auth/rotate-key", response_model=KeyRotationResponse)
async def rotate_api_key(party: AuthorizedParty = Depends(get_current_party)):
    """
    Rotate API key for the currently authenticated party.

    Generates a new API key and invalidates the old one.
    Requires a valid API key in the X-API-Key header.

    IMPORTANT: The new API key is returned only once! Store it securely.
    """
    new_api_key = auth_store.rotate_api_key(party.party_id)
    if not new_api_key:
        raise HTTPException(
            status_code=400,
            detail="Unable to rotate API key. Party may be inactive."
        )

    return KeyRotationResponse(
        party_id=party.party_id,
        new_api_key=new_api_key
    )


@app.get("/auth/me", response_model=PartyInfo)
async def get_current_party_info(party: AuthorizedParty = Depends(get_current_party)):
    """
    Get information about the currently authenticated party.

    Requires a valid API key in the X-API-Key header.
    """
    return PartyInfo(
        id=party.party_id,
        name=party.name,
        role=PartyRole(party.role),
        created_at=party.created_at,
        is_active=party.is_active
    )


@app.post("/demo/auth-reset")
async def demo_auth_reset():
    """
    Reset the auth store (DEMO ONLY).

    Clears all registered parties for a fresh demonstration.
    Also resets the registration rate limiter.
    """
    auth_store.reset()
    registration_rate_limiter.reset()
    return {"message": "Auth store and rate limiter have been reset"}


# ============================================================
# Shared Transparency Ledger Endpoints
# ============================================================

from backend.crypto_utils import generate_anonymous_id
from backend.models import (
    AnonymousIdRequest,
    AnonymousIdResponse,
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
from backend.transparency import TransparencyLedger

# Initialize transparency ledger
transparency_ledger = TransparencyLedger(storage_path="data/transparency_ledger.json")


@app.post("/transparency/anonymous-id", response_model=AnonymousIdResponse, deprecated=True)
async def create_anonymous_id(request: AnonymousIdRequest):
    """
    Generate an anonymous ID for a whistleblower.

    DEPRECATED: For maximum privacy, use client-side ID generation instead.
    This endpoint sends your identity to the server, which reduces privacy.
    The frontend now includes JavaScript-based local generation using Web Crypto API.

    The whistleblower provides their identity and a secret salt.
    The same identity+salt always produces the same anonymous ID,
    allowing consistent pseudonymous participation.

    IMPORTANT: The salt must be kept secret by the whistleblower.
    """
    anonymous_id = generate_anonymous_id(request.identity, request.salt)
    return AnonymousIdResponse(
        anonymous_id=anonymous_id,
        message="WARNING: For better privacy, use client-side ID generation in the web UI. "
                "This server-side endpoint receives your identity. "
                "Keep your salt secret - you'll need it to prove ownership of this ID."
    )


@app.post("/transparency/concerns", response_model=Concern)
async def raise_concern(
    concern: ConcernCreate,
    submitter_id: str,
    role: SubmitterRole
):
    """
    Raise a new concern in the shared transparency ledger.

    All concerns are visible to everyone (labs, whistleblowers, auditors).
    Whistleblowers use their anonymous ID as submitter_id.
    Labs and auditors use their organization name.
    """
    return transparency_ledger.raise_concern(concern, submitter_id, role)


@app.get("/transparency/concerns", response_model=list[Concern])
async def list_concerns(
    deployment_id: Optional[str] = None,
    status: Optional[ConcernStatus] = None,
    category: Optional[ConcernCategory] = None
):
    """
    List all concerns in the transparency ledger.

    Optional filters by deployment, status, or category.
    Everyone can see all concerns.
    """
    return transparency_ledger.list_concerns(
        deployment_id=deployment_id,
        status=status,
        category=category
    )


@app.get("/transparency/concerns/{concern_id}", response_model=Concern)
async def get_concern(concern_id: str):
    """Get a specific concern by ID."""
    concern = transparency_ledger.get_concern(concern_id)
    if concern is None:
        raise HTTPException(status_code=404, detail="Concern not found")
    return concern


@app.post("/transparency/responses", response_model=ConcernResponse)
async def respond_to_concern(
    response: ConcernResponseCreate,
    responder_id: str,
    role: SubmitterRole,
    x_api_key: Optional[str] = Header(None)
):
    """
    Respond to a concern.

    Labs typically respond to explain/address concerns.
    Whistleblowers can respond to dispute or add information.
    Auditors can respond to ask for clarification.

    If X-API-Key header is provided, the request is authenticated and
    the caller must have the 'lab' role to respond as a lab.
    """
    # If API key provided and role is lab, verify lab role
    if x_api_key and role == SubmitterRole.LAB:
        party = auth_store.verify_api_key(x_api_key)
        if not party:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        if party.role != "lab":
            raise HTTPException(status_code=403, detail="Access denied. Lab role required.")

    result = transparency_ledger.respond_to_concern(response, responder_id, role)
    if result is None:
        raise HTTPException(status_code=404, detail="Concern not found")
    return result


@app.get("/transparency/concerns/{concern_id}/responses", response_model=list[ConcernResponse])
async def get_concern_responses(concern_id: str):
    """Get all responses to a specific concern."""
    return transparency_ledger.get_responses(concern_id)


@app.post("/transparency/concerns/{concern_id}/dispute")
async def dispute_concern(concern_id: str, disputer_id: str):
    """
    Mark a concern as disputed.

    Used when a whistleblower disagrees with the lab's response.
    This prevents the concern from being considered "addressed".
    """
    success = transparency_ledger.dispute_response(concern_id, disputer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Concern not found")
    return {"message": "Concern marked as disputed"}


@app.post("/transparency/resolutions", response_model=Resolution)
async def resolve_concern(
    resolution: ResolutionCreate,
    auditor_id: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Mark a concern as resolved (AUDITOR ONLY).

    Only auditors can mark concerns as fully resolved.
    This clears the concern for deployment purposes.

    If X-API-Key header is provided, the request is authenticated and
    the caller must have the 'auditor' role.
    """
    # If API key provided, verify role
    if x_api_key:
        party = auth_store.verify_api_key(x_api_key)
        if not party:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        if party.role != "auditor":
            raise HTTPException(status_code=403, detail="Access denied. Auditor role required.")

    result = transparency_ledger.resolve_concern(resolution, auditor_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Concern not found")
    return result


@app.get("/transparency/clearance/{deployment_id}", response_model=DeploymentClearance)
async def check_deployment_clearance(deployment_id: str):
    """
    Check if a deployment is cleared for release.

    A deployment is cleared only when ALL concerns linked to it
    have been resolved by an auditor.
    """
    return transparency_ledger.check_deployment_clearance(deployment_id)


@app.get("/transparency/stats")
async def get_transparency_stats():
    """Get statistics about the transparency ledger."""
    return transparency_ledger.get_stats()


@app.post("/demo/transparency-reset")
async def demo_transparency_reset():
    """
    Reset the transparency ledger (DEMO ONLY).

    Clears all concerns, responses, and resolutions.
    """
    transparency_ledger.reset()
    return {"message": "Transparency ledger has been reset"}


@app.post("/demo/transparency-populate")
async def demo_transparency_populate():
    """
    Populate the transparency ledger with sample data (DEMO ONLY).

    Creates a realistic scenario with concerns, responses, and resolutions.
    """
    # Create sample concerns
    concerns_created = []

    # Whistleblower concern
    c1 = transparency_ledger.raise_concern(
        ConcernCreate(
            category=ConcernCategory.SAFETY_EVAL,
            title="Safety evaluation skipped for bioweapon capability",
            description="The CBRN safety evaluation was marked as passed but I observed "
                        "that the full test suite was not run. Only 20% of test cases "
                        "were executed before the team lead marked it complete.",
            deployment_id="gpt-safe-v2.1-prod",
            model_id="gpt-safe-v2.1"
        ),
        submitter_id="anon_7f3a2b1c9d8e",
        submitter_role=SubmitterRole.WHISTLEBLOWER
    )
    concerns_created.append(c1.id)

    # Lab self-reported concern
    c2 = transparency_ledger.raise_concern(
        ConcernCreate(
            category=ConcernCategory.DOCUMENTATION,
            title="Model card incomplete for deployment",
            description="We identified that the model card is missing capability "
                        "descriptions for code generation. Updating before full rollout.",
            deployment_id="gpt-safe-v2.1-prod",
            model_id="gpt-safe-v2.1"
        ),
        submitter_id="Anthropic Safety Team",
        submitter_role=SubmitterRole.LAB
    )
    concerns_created.append(c2.id)

    # Add response from lab to whistleblower concern
    transparency_ledger.respond_to_concern(
        ConcernResponseCreate(
            concern_id=c1.id,
            response_text="We have reviewed the logs and confirm that the CBRN evaluation "
                          "was interrupted due to infrastructure issues. We have now "
                          "completed the full evaluation suite. See evidence hash for logs.",
            evidence_hash="a1b2c3d4e5f6789..."
        ),
        responder_id="Anthropic Safety Team",
        responder_role=SubmitterRole.LAB
    )

    # Resolve the whistleblower concern (after lab addressed it)
    transparency_ledger.resolve_concern(
        ResolutionCreate(
            concern_id=c1.id,
            resolution_notes="Verified lab's response. Full CBRN evaluation suite has now been "
                             "completed and logs confirm all test cases passed. Concern resolved."
        ),
        auditor_id="AI Safety Institute"
    )

    # Resolve the documentation concern
    transparency_ledger.resolve_concern(
        ResolutionCreate(
            concern_id=c2.id,
            resolution_notes="Verified that model card has been updated with complete "
                             "capability documentation. Meets requirements."
        ),
        auditor_id="AI Safety Institute"
    )

    return {
        "message": "Transparency ledger populated with sample data",
        "concerns_created": concerns_created,
        "scenario": "Two concerns raised and resolved (whistleblower + lab self-reported)"
    }


# ============================================================
# Compliance Submission Endpoints
# ============================================================

@app.post("/compliance/submissions", response_model=ComplianceSubmission)
async def submit_compliance(
    submission: ComplianceSubmissionCreate,
    lab_id: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Submit a compliance document (LAB ONLY).

    Labs submit compliance documentation for each required template type.
    Each submission must include an evidence hash - a SHA-256 hash of the
    actual evidence document. Auditors can later verify the evidence matches.

    If X-API-Key header is provided, the request is authenticated and
    the caller must have the 'lab' role.

    Template types:
    - safety_evaluation: Pre-deployment safety evaluation results
    - training_data: Training data documentation
    - capability_assessment: Dangerous capability assessment
    - red_team_report: Red team testing results
    - human_oversight: Human oversight attestation
    - incident_report: Post-deployment incident reports
    """
    # If API key provided, verify lab role
    if x_api_key:
        party = auth_store.verify_api_key(x_api_key)
        if not party:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        if party.role != "lab":
            raise HTTPException(status_code=403, detail="Access denied. Lab role required.")

    return transparency_ledger.submit_compliance(submission, lab_id)


@app.get("/compliance/submissions", response_model=list[ComplianceSubmission])
async def list_compliance_submissions(
    deployment_id: Optional[str] = None,
    lab_id: Optional[str] = None,
    template_type: Optional[ComplianceTemplateType] = None,
    status: Optional[ComplianceStatus] = None
):
    """
    List compliance submissions with optional filters.

    All parties (labs, auditors, government) can view all submissions.
    """
    return transparency_ledger.list_compliance_submissions(
        deployment_id=deployment_id,
        lab_id=lab_id,
        template_type=template_type,
        status=status
    )


@app.get("/compliance/submissions/{submission_id}", response_model=ComplianceSubmission)
async def get_compliance_submission(submission_id: str):
    """Get a specific compliance submission by ID."""
    submission = transparency_ledger.get_compliance_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


@app.post("/compliance/review", response_model=ComplianceSubmission)
async def review_compliance(
    review: ComplianceReviewCreate,
    auditor_id: str,
    x_api_key: Optional[str] = Header(None)
):
    """
    Review a compliance submission (AUDITOR ONLY).

    Auditors review submissions and either verify or reject them.
    The auditor must indicate whether the evidence hash was verified
    against the actual evidence document.

    If X-API-Key header is provided, the request is authenticated and
    the caller must have the 'auditor' role.

    Status must be either 'verified' or 'rejected'.
    """
    # If API key provided, verify auditor role
    if x_api_key:
        party = auth_store.verify_api_key(x_api_key)
        if not party:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        if party.role != "auditor":
            raise HTTPException(status_code=403, detail="Access denied. Auditor role required.")

    try:
        result = transparency_ledger.review_compliance(review, auditor_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Submission not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/compliance/status/{deployment_id}", response_model=DeploymentComplianceStatus)
async def get_deployment_compliance_status(
    deployment_id: str,
    model_id: str
):
    """
    Get full compliance status for a deployment - THE DEPLOYMENT GATE.

    This is the unified check that verifies:
    1. All required compliance templates are submitted and verified
    2. All concerns are resolved

    A deployment is only CLEARED when BOTH conditions are met.

    Default required templates:
    - safety_evaluation
    - capability_assessment
    - red_team_report
    """
    return transparency_ledger.get_deployment_compliance_status(deployment_id, model_id)


@app.get("/compliance/templates")
async def get_template_types():
    """
    Get list of all compliance template types.

    Returns the available template types and which are required by default.
    """
    from backend.transparency import DEFAULT_REQUIRED_TEMPLATES

    return {
        "all_templates": [t.value for t in ComplianceTemplateType],
        "default_required": [t.value for t in DEFAULT_REQUIRED_TEMPLATES],
        "descriptions": {
            "safety_evaluation": "Pre-deployment safety evaluation results",
            "training_data": "Training data documentation and provenance",
            "capability_assessment": "Assessment of dangerous capabilities",
            "red_team_report": "Red team testing results",
            "human_oversight": "Human oversight attestation",
            "incident_report": "Post-deployment incident reports"
        }
    }


@app.post("/demo/compliance-populate")
async def demo_compliance_populate():
    """
    Populate with sample compliance data (DEMO ONLY).

    Creates a realistic scenario with compliance submissions and reviews.
    """
    from backend.models import ComplianceSubmissionCreate, ComplianceTemplateType

    submissions_created = []

    # Submit safety evaluation (verified)
    s1 = transparency_ledger.submit_compliance(
        ComplianceSubmissionCreate(
            template_type=ComplianceTemplateType.SAFETY_EVALUATION,
            deployment_id="gpt-safe-v2.1-prod",
            model_id="gpt-safe-v2.1",
            title="Pre-deployment Safety Evaluation Report",
            summary="Comprehensive safety evaluation covering harmlessness, "
                    "helpfulness, and honesty benchmarks. All tests passed "
                    "with scores above required thresholds.",
            evidence_hash="a" * 64,
            metadata={
                "eval_suite": "safety-benchmark-v4",
                "harmlessness_score": 0.98,
                "helpfulness_score": 0.94,
                "honesty_score": 0.96,
                "test_cases": 15000
            }
        ),
        lab_id="Anthropic"
    )
    submissions_created.append(s1.id)

    # Verify the safety evaluation
    transparency_ledger.review_compliance(
        ComplianceReviewCreate(
            submission_id=s1.id,
            status=ComplianceStatus.VERIFIED,
            notes="Evidence verified. Safety evaluation meets all requirements.",
            evidence_verified=True
        ),
        auditor_id="AI Safety Institute"
    )

    # Submit capability assessment
    s2 = transparency_ledger.submit_compliance(
        ComplianceSubmissionCreate(
            template_type=ComplianceTemplateType.CAPABILITY_ASSESSMENT,
            deployment_id="gpt-safe-v2.1-prod",
            model_id="gpt-safe-v2.1",
            title="Dangerous Capability Assessment",
            summary="Assessment of CBRN, cyber, and persuasion capabilities. "
                    "Model shows minimal dangerous capabilities with appropriate "
                    "refusal behaviors for harmful requests.",
            evidence_hash="b" * 64,
            metadata={
                "cbrn_risk": "minimal",
                "cyber_risk": "minimal",
                "persuasion_risk": "low",
                "refusal_rate": 0.99
            }
        ),
        lab_id="Anthropic"
    )
    submissions_created.append(s2.id)

    # Verify the capability assessment
    transparency_ledger.review_compliance(
        ComplianceReviewCreate(
            submission_id=s2.id,
            status=ComplianceStatus.VERIFIED,
            notes="Capability assessment verified. Risk levels acceptable.",
            evidence_verified=True
        ),
        auditor_id="AI Safety Institute"
    )

    # Submit red team report
    s3 = transparency_ledger.submit_compliance(
        ComplianceSubmissionCreate(
            template_type=ComplianceTemplateType.RED_TEAM_REPORT,
            deployment_id="gpt-safe-v2.1-prod",
            model_id="gpt-safe-v2.1",
            title="Red Team Testing Report",
            summary="Comprehensive red team testing conducted by external security "
                    "researchers. No critical vulnerabilities found. Minor issues "
                    "identified and mitigated before deployment.",
            evidence_hash="c" * 64,
            metadata={
                "testers": 12,
                "test_hours": 500,
                "critical_findings": 0,
                "medium_findings": 2,
                "findings_mitigated": True
            }
        ),
        lab_id="Anthropic"
    )
    submissions_created.append(s3.id)

    # Verify the red team report
    transparency_ledger.review_compliance(
        ComplianceReviewCreate(
            submission_id=s3.id,
            status=ComplianceStatus.VERIFIED,
            notes="Red team report verified. All findings addressed appropriately.",
            evidence_verified=True
        ),
        auditor_id="AI Safety Institute"
    )

    return {
        "message": "Compliance submissions populated with sample data",
        "submissions_created": submissions_created,
        "scenario": "All required templates (safety eval, capability assessment, red team report) verified"
    }


# ============================================================
# Multi-Mirror Simulation Demo Endpoints
# ============================================================

from backend.mirror_simulation import mirror_simulation
from backend.models import (
    MirrorComparisonResult,
    MirrorParty,
    MirrorStatus,
    MirrorSyncRequest,
    MirrorTamperRequest,
    TamperDetectionResult,
)


@app.post("/demo/mirror/sync")
async def sync_mirrors(request: MirrorSyncRequest = None):
    """
    Sync all mirrors from the authoritative transparency ledger.

    This simulates the initial distribution of ledger data to all
    parties (lab, auditor, government). In a real system, this would
    be a distributed consensus mechanism.
    """
    # Build ledger data from transparency ledger
    records = {}

    if request is None or request.include_concerns:
        concerns = transparency_ledger.list_concerns()
        for c in concerns:
            records[f"concern_{c.id}"] = c.model_dump()

    if request is None or request.include_submissions:
        submissions = transparency_ledger.list_compliance_submissions()
        for s in submissions:
            records[f"submission_{s.id}"] = s.model_dump()

    ledger_data = {"records": records}
    result = mirror_simulation.sync_from_source(ledger_data)

    return {
        "message": "All mirrors synced from transparency ledger",
        "parties": result["synced_parties"],
        "record_count": result["record_count"],
        "sync_time": result["sync_time"]
    }


@app.get("/demo/mirror/status", response_model=list[MirrorStatus])
async def get_mirror_status():
    """
    Get status of all 3 mirrors.

    Shows record count, content hash, and last sync time for each party.
    """
    statuses = mirror_simulation.get_all_mirror_status()
    return [
        MirrorStatus(
            party=MirrorParty(s["party"]),
            record_count=s["record_count"],
            hash=s["hash"],
            last_sync=s["last_sync"]
        )
        for s in statuses
    ]


@app.get("/demo/mirror/compare", response_model=MirrorComparisonResult)
async def compare_mirrors():
    """
    Compare all mirrors and detect any divergence.

    If all mirrors have the same hash, the ledger is consistent.
    If hashes differ, tampering or sync issues are detected.
    """
    result = mirror_simulation.compare_mirrors()
    return MirrorComparisonResult(
        all_consistent=result["all_consistent"],
        lab_hash=result["lab_hash"],
        auditor_hash=result["auditor_hash"],
        government_hash=result["government_hash"],
        divergent_parties=[MirrorParty(p) for p in result["divergent_parties"]],
        message=result["message"]
    )


@app.post("/demo/mirror/tamper")
async def tamper_mirror(request: MirrorTamperRequest):
    """
    Tamper with one party's mirror copy (DEMO ONLY).

    This simulates a malicious actor modifying records in one
    party's copy of the ledger. After tampering, the compare
    endpoint will detect the divergence.
    """
    result = mirror_simulation.tamper_mirror(
        party=request.party.value,
        record_id=request.record_id,
        new_value=request.new_value
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Tamper failed"))

    return result


@app.get("/demo/mirror/detect", response_model=TamperDetectionResult)
async def detect_tampering():
    """
    Run tamper detection across all mirrors.

    Compares all mirrors and identifies:
    - Which parties have divergent data
    - Which specific records differ
    - Recommendations for remediation
    """
    result = mirror_simulation.detect_tampering()
    return TamperDetectionResult(
        tampering_detected=result["tampering_detected"],
        affected_parties=[MirrorParty(p) for p in result["affected_parties"]],
        affected_records=result["affected_records"],
        recommendation=result["recommendation"]
    )


@app.post("/demo/mirror/reset")
async def reset_mirrors():
    """
    Reset all mirrors to empty state (DEMO ONLY).

    Clears all mirror data for a fresh demonstration.
    """
    result = mirror_simulation.reset()
    return result
