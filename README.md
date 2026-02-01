# AI Flight Recorder

A tamper-proof audit logging system for AI governance using hash chains and Merkle trees.

## Overview

AI Flight Recorder provides cryptographic guarantees that AI governance events cannot be modified without detection. Like an aircraft's black box, it creates an immutable record of important events in an AI system's lifecycle.

### Key Features

- **Hash Chain Integrity**: Each event is cryptographically linked to the previous event
- **Tamper Detection**: Any modification to historical events is immediately detectable
- **Merkle Proofs**: Prove specific events exist without revealing the entire log
- **Zero-Knowledge Proofs**: Prove compliance thresholds without revealing exact counts
- **REST API**: Full-featured API for integration with existing systems
- **Interactive UI**: Streamlit dashboard for visualization and demonstration

## Quick Start

### Prerequisites

- Python 3.9+
- pip

### Installation

```bash
# Clone the repository
cd ai-flight-recorder

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

```bash
# Start both backend and frontend
python run.py
```

Or run services separately:

```bash
# Terminal 1: Start API server
uvicorn backend.api:app --reload --port 8000

# Terminal 2: Start Streamlit UI
streamlit run frontend/app.py --server.port 8501
```

### Access Points

- **Frontend**: http://localhost:8501
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                    │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────┐ ┌──────┐│
│  │Log Event│ │ Timeline │ │ Verify │ │Proofs │ │ Demo ││
│  └─────────┘ └──────────┘ └────────┘ └───────┘ └──────┘│
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                      │
│  ┌──────────────────────────────────────────────────┐  │
│  │ REST API: /events, /verify, /proof, /status      │  │
│  └──────────────────────────────────────────────────┘  │
│                            │                            │
│  ┌────────────┐    ┌───────────────┐    ┌───────────┐  │
│  │ Audit Log  │    │  Merkle Tree  │    │  Crypto   │  │
│  │ (Hash Chain)│    │   (Proofs)    │    │  Utils    │  │
│  └────────────┘    └───────────────┘    └───────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  JSON Storage   │
                  │ (audit_log.json)│
                  └─────────────────┘
```

## How It Works

### Hash Chain

Each event contains:
- Event data (type, description, metadata, timestamp)
- Hash of the previous event
- Its own hash (computed from data + previous hash)

```
Event 0          Event 1          Event 2
┌──────────┐     ┌──────────┐     ┌──────────┐
│ data     │     │ data     │     │ data     │
│ prev: 0  │────▶│ prev: H0 │────▶│ prev: H1 │
│ hash: H0 │     │ hash: H1 │     │ hash: H2 │
└──────────┘     └──────────┘     └──────────┘
```

If anyone modifies Event 1's data, its hash changes, breaking the chain.

### Merkle Tree

Events are organized into a Merkle tree for efficient proofs:

```
              Root Hash
             /         \
        Hash01          Hash23
       /     \         /     \
    Hash0   Hash1   Hash2   Hash3
      │       │       │       │
   Event0  Event1  Event2  Event3
```

To prove Event2 exists, you only need: Hash3, Hash01, and the root.

### Zero-Knowledge Proofs

ZK proofs enable privacy-preserving compliance verification:

```
Organization                          Auditor
     │                                   │
     │  1. Commit to count               │
     │     C = SHA256(count || blinding) │
     │                                   │
     │  2. Generate proof for threshold  │
     │     Prove: count >= N             │
     │                                   │
     │  3. Share proof ─────────────────>│
     │                                   │
     │                    4. Verify proof│
     │                       (learns only│
     │                        count >= N)│
```

**Use case**: Prove "we ran at least 5 safety evaluations" without revealing if you ran 5, 10, or 100.

## API Reference

### Events

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/events` | Log a new event |
| GET | `/events` | List all events |
| GET | `/events/{id}` | Get specific event |

### Verification

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/verify` | Verify chain integrity |
| GET | `/status` | Get log status |
| GET | `/proof/{id}` | Generate Merkle proof |
| POST | `/proof/verify` | Verify a Merkle proof |

### Demo

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/demo/reset` | Clear all events |
| POST | `/demo/populate` | Add sample events |
| POST | `/demo/tamper` | Simulate tampering |

### Zero-Knowledge Proofs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/zk/commitment` | Create commitment to event count |
| GET | `/zk/commitment/{id}` | Retrieve a commitment |
| POST | `/zk/prove` | Generate ZK proof for threshold |
| POST | `/zk/verify` | Verify a ZK proof |

## Event Types

| Type | Description |
|------|-------------|
| `training_started` | Model training initiated |
| `training_completed` | Model training finished |
| `safety_eval_run` | Safety evaluation executed |
| `safety_eval_passed` | Safety checks passed |
| `safety_eval_failed` | Safety checks failed |
| `model_deployed` | Model deployed to environment |
| `incident_reported` | Safety incident logged |

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_crypto.py -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

## Project Structure

```
ai-flight-recorder/
├── backend/
│   ├── __init__.py
│   ├── api.py           # FastAPI REST endpoints
│   ├── audit_log.py     # Hash chain implementation
│   ├── crypto_utils.py  # Cryptographic utilities
│   ├── merkle_tree.py   # Merkle tree & proofs
│   ├── models.py        # Pydantic data models
│   └── zk_proofs.py     # Zero-knowledge proofs
├── frontend/
│   └── app.py           # Streamlit dashboard
├── data/
│   ├── audit_log.json   # Persistent storage
│   └── zk_store.json    # ZK commitments storage
├── tests/
│   ├── test_audit_log.py
│   ├── test_crypto.py
│   ├── test_merkle.py
│   └── test_zk_proofs.py
├── requirements.txt
├── run.py               # Application launcher
└── README.md
```

## Security Considerations

- **Storage**: The JSON file should be protected with appropriate filesystem permissions
- **Production**: Consider using a database with write-ahead logging
- **Backup**: Regularly backup the audit log to prevent data loss
- **Access Control**: Implement authentication for the API in production

## License

MIT License
