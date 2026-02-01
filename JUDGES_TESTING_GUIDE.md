# AI Governance Transparency Ledger
## Judges Testing Guide

---

## Quick Start

### Live Demo URL
**https://ai-governance-transparency-ledger-5lfyre3cwf6dtfpikclmma.streamlit.app**

### Deployment Architecture

| Component | Platform | URL |
|-----------|----------|-----|
| **Frontend** | Streamlit | https://ai-governance-transparency-ledger-5lfyre3cwf6dtfpikclmma.streamlit.app |
| **Backend API** | Render | https://ai-governance-transparency-ledger.onrender.com |

> **Note:** The Render backend uses a free tier and may experience cold starts (30-60 seconds) on first request. Please allow time for the API to wake up.

---

## Test 1: Submit Compliance Record

**Purpose:** Verify that compliance records can be submitted and stored.

### Steps:
1. Click **"Compliance Dashboard"** in the sidebar
2. Click **"Submit New Compliance"**
3. Enter the following:
   - Lab ID: `test_lab`
   - Framework: Select `EU AI Act`
   - Description: `Test compliance submission`
   - Evidence Hash: `abc123def456789...` (any 64-character hex string)
4. Click **"Submit"**

### Expected Result:
- Success message appears
- Record is added to the compliance list
- Record shows timestamp and unique ID

### Pass Criteria:
✓ Record successfully stored
✓ Evidence hash displayed (not the actual evidence)
✓ Timestamp automatically added

---

## Test 2: Verify Chain Integrity

**Purpose:** Demonstrate tamper-proof hash chain verification.

### Steps:
1. Click **"Audit Log"** in the sidebar
2. Review the list of records (should include your Test 1 submission)
3. Click **"Verify Chain Integrity"**
4. Note the verification result

### Expected Result:
- All records shown with their hash values
- Verification shows "Chain Valid" with green indicator
- Each record links to previous record via hash

### Pass Criteria:
✓ Chain verification completes
✓ All hashes are displayed
✓ Integrity status clearly shown

---

## Test 3: Tamper Detection

**Purpose:** Prove that any modification to historical records is detected.

### Steps:
1. While still in the Audit Log, click **"Simulate Tampering"** (or use Demo Controls if available)
2. Click **"Verify Chain Integrity"** again
3. Observe the failure message

### Expected Result:
- Verification shows "Chain Invalid" with red indicator
- System identifies the exact record that was modified
- Error message explains what was detected

### Pass Criteria:
✓ Tampering is detected
✓ Specific tampered record is identified
✓ System does not allow the modification to go unnoticed

---

## Test 4: Anonymous Whistleblower Submission

**Purpose:** Verify client-side identity protection.

### Steps:
1. Click **"Raise Concerns"** in the sidebar
2. In the "Your Identity" field, enter: `Judge Test User`
3. In the "Secret Passphrase" field, enter: `hackathon2024`
4. Click **"Generate Anonymous ID"**
5. Note that the anonymous ID is generated in your browser
6. Enter a concern: `Test concern for verification purposes`
7. Click **"Submit Concern"**

### Expected Result:
- Anonymous ID is generated locally (shown in browser)
- Your real identity (`Judge Test User`) is never sent to server
- Concern is recorded with only the anonymous hash
- Confirmation message appears

### Pass Criteria:
✓ Anonymous ID generated client-side
✓ Real identity never transmitted
✓ Concern successfully recorded

---

## Test 5: Deployment Gate Check

**Purpose:** Verify that deployment is blocked until compliance is met.

### Steps:
1. Click **"Deployment Gate"** in the sidebar
2. Review the current gate status
3. Note any blocking conditions (unresolved concerns, missing compliance)
4. Try to clear the gate (if controls available)

### Expected Result:
- Gate shows current compliance status for all frameworks
- Unresolved concerns block deployment (red indicator)
- Clear explanation of what is blocking/allowing deployment

### Pass Criteria:
✓ Gate status clearly displayed
✓ Blocking conditions enumerated
✓ Cannot bypass gate with unresolved issues

---

## API Testing (Advanced)

For direct API verification, the backend is hosted at:

**Base URL:** `https://ai-governance-transparency-ledger.onrender.com`

### Example Endpoints:
- `GET /health` - API health check
- `GET /api/compliance` - List all compliance records
- `GET /api/audit/verify` - Verify chain integrity
- `POST /api/concerns` - Submit anonymous concern

### Testing with curl:
```bash
# Health check
curl https://ai-governance-transparency-ledger.onrender.com/health

# Verify chain integrity
curl https://ai-governance-transparency-ledger.onrender.com/api/audit/verify
```

---

## Summary Checklist

| Test | Feature | Status |
|------|---------|--------|
| 1 | Compliance Submission | ☐ Pass / ☐ Fail |
| 2 | Chain Verification | ☐ Pass / ☐ Fail |
| 3 | Tamper Detection | ☐ Pass / ☐ Fail |
| 4 | Anonymous Whistleblower | ☐ Pass / ☐ Fail |
| 5 | Deployment Gate | ☐ Pass / ☐ Fail |

---

## Links

- **Live Application:** https://ai-governance-transparency-ledger-5lfyre3cwf6dtfpikclmma.streamlit.app
- **Backend API:** https://ai-governance-transparency-ledger.onrender.com
- **GitHub Repository:** https://github.com/zukapustikova/ai-governance-transparency-ledger

---

*AI Governance Transparency Ledger - Hackathon Submission*
