# Handoff: Nice-to-Have Improvements Implementation

**Date:** 2026-02-01
**Session:** Implementation of four suggested improvements from previous session

---

## Summary

Implemented all four suggested improvements from the previous handoff:
1. Rate limiting on `/auth/register`
2. Persistent mirror storage
3. Integration tests with TestClient
4. API key rotation mechanism

---

## Features Implemented

### 1. Rate Limiting on `/auth/register`

**Goal:** Prevent abuse by limiting registration requests.

**Changes:**
- `backend/auth.py`: Added `RateLimiter` class with configurable limits
- `backend/api.py`: Added `check_registration_rate_limit` dependency

**How it works:**
- 5 registrations per minute per IP address
- Returns 429 Too Many Requests when exceeded
- Rate limiter resets with `/demo/auth-reset`

**Configuration:**
```python
registration_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
```

---

### 2. Persistent Mirror Storage

**Goal:** Mirror data survives server restarts.

**Changes:**
- `backend/mirror_simulation.py`: Added `_load()` and `_save()` methods
- Storage path: `data/mirror_store.json`

**Fixed issue:** JSON serialization of datetime objects in mirror hashes (added `default=str` to `json.dumps`)

---

### 3. Integration Tests with TestClient

**Goal:** End-to-end API testing using FastAPI's TestClient.

**New file:** `tests/test_integration.py`

**Tests added (11 total):**
| Test Class | Tests |
|------------|-------|
| TestAuthFlow | 5 tests (register, rate limiting, invalid key, revoke, rotate) |
| TestTransparencyFlow | 1 test (raise, respond, resolve concern) |
| TestMirrorFlow | 1 test (sync, tamper, detect) |
| TestComplianceFlow | 1 test (submit, review) |
| TestRoleBasedAccess | 3 tests (lab submit, auditor blocked, auditor review) |

**Dependency fix:** Updated `fastapi>=0.115.0` for httpx/starlette compatibility.

---

### 4. API Key Rotation

**Goal:** Allow parties to rotate their API key without re-registering.

**Changes:**
- `backend/auth.py`: Added `rotate_api_key()` method to `AuthStore`
- `backend/api.py`: Added `POST /auth/rotate-key` endpoint
- `backend/models.py`: Added `KeyRotationResponse` model

**Endpoint:** `POST /auth/rotate-key`
- Requires valid API key in `X-API-Key` header
- Returns new API key (shown only once)
- Old key is immediately invalidated

**Example:**
```bash
curl -X POST http://localhost:8000/auth/rotate-key \
  -H "X-API-Key: afr_old_key_here"
```

---

## Files Changed

### New Files
| File | Purpose |
|------|---------|
| `tests/test_integration.py` | 11 integration tests |

### Modified Files
| File | Changes |
|------|---------|
| `backend/auth.py` | RateLimiter class, rotate_api_key method |
| `backend/api.py` | Rate limit dependency, rotation endpoint, imports |
| `backend/mirror_simulation.py` | Persistence (_load/_save), JSON serialization fix |
| `backend/models.py` | KeyRotationResponse model |
| `requirements.txt` | Updated fastapi>=0.115.0 |
| `tests/test_auth.py` | 10 new tests (5 rate limiter, 5 rotation) |
| `tests/test_mirror_simulation.py` | 2 persistence tests |

---

## Test Results

```
153 passed, 19 warnings in 0.69s
```

**New tests added:** 23
- `test_auth.py`: +10 tests (rate limiter: 5, rotation: 5)
- `test_mirror_simulation.py`: +2 tests (persistence)
- `test_integration.py`: +11 tests (new file)

---

## API Changes

### New Endpoint
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/rotate-key` | POST | Rotate API key (requires auth) |

### Modified Endpoint
| Endpoint | Change |
|----------|--------|
| `/auth/register` | Now rate limited (5/min/IP) |
| `/demo/auth-reset` | Also resets rate limiter |

---

## Known Limitations

1. **Rate limiter is in-memory** - Resets on server restart. For production with multiple instances, use Redis-based rate limiting.

2. **Mirror storage is single-file** - All parties' mirrors stored in one JSON file. In production, each party would have separate persistent storage.

---

## How to Test

1. **Test rate limiting:**
   ```bash
   # Register 5 times (should succeed)
   for i in {1..5}; do
     curl -X POST http://localhost:8000/auth/register \
       -H "Content-Type: application/json" \
       -d '{"name": "Test '$i'", "role": "lab"}'
   done

   # 6th should fail with 429
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"name": "Test 6", "role": "lab"}'
   ```

2. **Test key rotation:**
   ```bash
   # Register and get key
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"name": "Test Lab", "role": "lab"}'

   # Rotate using the returned key
   curl -X POST http://localhost:8000/auth/rotate-key \
     -H "X-API-Key: YOUR_API_KEY"
   ```

3. **Test mirror persistence:**
   ```bash
   # Sync mirrors, then restart server
   curl -X POST http://localhost:8000/demo/mirror/sync
   # Restart server
   curl http://localhost:8000/demo/mirror/status
   # Data should still be present
   ```

4. **Run all tests:**
   ```bash
   python -m pytest -v
   ```

---

## Next Steps (If Continuing)

1. Add Redis-based rate limiting for multi-instance deployments
2. Add API key expiration dates
3. Add audit logging for key rotation events
4. Update pydantic models to use `ConfigDict` instead of deprecated `Config` class (removes warnings)
