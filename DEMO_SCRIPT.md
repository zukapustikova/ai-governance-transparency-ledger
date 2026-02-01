# AI Governance Transparency Ledger - Demo Guide

## Quick Setup

### Prerequisites
- Python 3.11+
- pip

### Installation
```bash
# Clone the repository
git clone <repo-url>
cd ai-flight-recorder

# Install dependencies
pip install -r requirements.txt
```

### Running the App

**Option 1: Two terminals (recommended)**

Terminal 1 - Start the API backend:
```bash
cd /path/to/ai-flight-recorder
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Terminal 2 - Start the frontend:
```bash
cd /path/to/ai-flight-recorder
python -m streamlit run frontend/app.py --server.port 8501
```

**Option 2: Single command**
```bash
python run.py
```

Open browser to: **http://localhost:8501**

---

## Demo Flow (5 minutes)

### Step 1: Load Demo Data (30 seconds)

1. Open http://localhost:8501
2. On the **Overview** page, click **"Load demo data"**
3. You should see "Demo data loaded and mirrors synced!"

This populates:
- 2 safety concerns (1 whistleblower, 1 lab-reported)
- 3 compliance submissions (safety eval, capability assessment, red team report)
- All concerns resolved, all submissions verified

---

### Step 2: Check Deployment Gate (1 minute)

1. Click **"Gate"** in the navigation bar
2. The form shows pre-filled values:
   - Deployment ID: `gpt-safe-v2.1-prod`
   - Model ID: `gpt-safe-v2.1`
3. Click **"Check Status"**

**Expected Result:**
- ✅ **CLEARED FOR DEPLOYMENT** - All requirements met, no blocking concerns

**What this demonstrates:**
- All 3 required compliance templates are verified (Safety Evaluation, Capability Assessment, Red Team Report)
- 0 open concerns, 2 resolved concerns
- The deployment gate blocks releases until all requirements are met

---

### Step 3: View Compliance Submissions (1 minute)

1. Click **"Compliance"** in the navigation
2. Select **"Auditor (review submissions)"**
3. Scroll down to see **"All Submissions"**

You'll see:
- ✅ Safety Evaluation Report - VERIFIED
- ✅ Dangerous Capability Assessment - VERIFIED
- ✅ Red Team Testing Report - VERIFIED

**What this demonstrates:**
- Labs submit compliance documentation with evidence hashes
- Auditors review and verify/reject submissions
- Cryptographic evidence hashes ensure document integrity

---

### Step 4: View Concerns (1 minute)

1. Click **"Concerns"** in the navigation
2. Click the **"View All Concerns"** tab

You'll see:
- RESOLVED: "Safety evaluation skipped for bioweapon capability" (whistleblower)
- RESOLVED: "Model card incomplete for deployment" (lab self-reported)

**What this demonstrates:**
- Anonymous whistleblower submissions (using client-side hashing)
- Labs can self-report concerns
- Auditors resolve concerns after lab responses
- Unresolved concerns block deployment

---

### Step 5: Multi-Party Mirrors (1.5 minutes)

1. Click **"Mirrors"** in the navigation
2. You'll see 3 mirrors: Lab, Auditor, Government
3. All should show **"Consistent"** with matching hashes

**Simulate Tampering:**
1. Expand **"Demo: Simulate Tampering"**
2. Select Target Party: `lab`
3. Enter Record ID: `concern_1`
4. Enter New Title: `Nothing happened`
5. Click **"Tamper Record"**
6. Click **"Detect Tampering"** button at the top

**Expected Result:**
- ⚠️ Tampering detected!
- Lab mirror shows **"DIVERGENT"**

**What this demonstrates:**
- Ledger is replicated across multiple parties
- No single party can tamper undetected
- Hash comparison reveals any modifications

---

## Key Features Summary

| Feature | Description |
|---------|-------------|
| **Deployment Gate** | Blocks releases until all compliance requirements met |
| **Compliance Templates** | Required documentation (safety eval, capability assessment, red team) |
| **Anonymous Concerns** | Whistleblowers submit using client-side hashed IDs |
| **Multi-Party Mirrors** | Lab, auditor, government each hold copies |
| **Tamper Detection** | Hash comparison detects any unauthorized changes |

---

## Troubleshooting

**"Cannot connect to API"**
- Make sure the backend is running on port 8000
- Check: `curl http://localhost:8000/health`

**Gate shows BLOCKED**
- Click "Load demo data" on the Overview page first

**Mirrors show empty**
- Demo data loading auto-syncs mirrors
- Or click "Sync All Mirrors" on the Mirrors page

---

## API Endpoints

- Health check: `GET http://localhost:8000/health`
- API documentation: `http://localhost:8000/docs`
- Deployment status: `GET http://localhost:8000/compliance/status/{deployment_id}?model_id={model_id}`
