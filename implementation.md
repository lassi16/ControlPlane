# ControlPlane — Implementation Plan & Architecture

> **Current Status: v0.2.0** | Deployed on Render (backend) + Vercel (frontend)
> Last updated: August 2026

---

## 1. What We're Building

A **model-agnostic gateway** that intercepts every LLM request-response pair and evaluates it across three risk dimensions — correctness (performance), data safety (responsibility), and cost — using a two-path architecture:

- **Inline path**: lightweight checks that run before the response reaches the user
- **Async path**: deep claim-level verification that runs in parallel, off the critical path

The system deploys as a **proxy** — applications point their LLM calls at ControlPlane instead of directly at the model API. ControlPlane forwards the request, intercepts the response, runs checks, applies policy, and delivers the result.

---

## 2. Tech Stack — Actual (v0.2.0)

| Layer | Technology | Status | Notes |
|---|---|---|---|
| **Gateway / API** | Python + FastAPI | ✅ Live | Deployed on Render free tier |
| **LLM** | Groq `openai/gpt-oss-20b` | ✅ Live | Free tier, no cost |
| **Database (local)** | SQLite (aiosqlite) | ✅ Live | Zero-config, auto-detected |
| **Database (prod)** | PostgreSQL (asyncpg) | ✅ Live | Render free Postgres |
| **Queue / async** | Background threads (Celery-ready) | ⚠️ Partial | Threads work; Celery needs Redis |
| **Toxicity check** | Keyword heuristics | ⚠️ Partial | Week 2: replace with `toxic-bert` |
| **NLI classification** | Regex heuristics | ⚠️ Partial | Week 2: replace with DeBERTa |
| **Claim extraction** | Groq LLM (free) | ✅ Live | `openai/gpt-oss-20b` |
| **Evidence retrieval** | DuckDuckGo `ddgs` + local KB | ✅ Live | Free, no key needed |
| **Math verification** | Python `sympy` | ✅ Live | Deterministic |
| **Dashboard** | React + Vite + Recharts | ✅ Live | Deployed on Vercel |
| **Deployment** | Render (API) + Vercel (frontend) | ✅ Live | Both free tier |
| **Docker** | docker-compose.yml ready | ⚠️ Ready | Needs Docker Desktop installed |

### Original Plan vs Actual

| Planned | Actual | Reason |
|---|---|---|
| HuggingFace models (local) | Groq API (free) | No GPU; Groq is faster and free |
| Google/Bing Search API | DuckDuckGo `ddgs` | Paid APIs removed; ddgs is free |
| Redis cache | Thread-based fallback | Redis needs Docker; threads work fine |
| PostgreSQL from day 1 | SQLite → PostgreSQL | SQLite for local; Postgres on deploy |
| Kubernetes (prod) | Render + Vercel | Overkill for prototype; free platforms simpler |


## 3. Project Structure

```
controlplane/
├── gateway/                    # FastAPI gateway (core proxy)
│   ├── main.py                 # App entry point, ASGI server
│   ├── proxy.py                # Forward request to LLM, intercept response
│   ├── routes.py               # API endpoints (/v1/chat/completions, /health, /dashboard)
│   └── middleware.py           # Request/response logging, timing
│
├── precheck/                   # Layer 0 — runs BEFORE LLM call
│   ├── pii_input.py            # Regex PII scan on user prompt
│   ├── injection.py            # Prompt injection detection
│   ├── budget.py               # Session/account spend gate
│   ├── classifier.py           # Multi-label query classifier
│   └── impact.py               # Preliminary impact estimate
│
├── fast_checks/                # Layer 1 — runs AFTER LLM response, INLINE
│   ├── tier1.py                # Deterministic: regex PII, credentials, secrets, schema
│   ├── tier2.py                # ML classifiers: toxicity, safety, topic drift, NER PII
│   ├── anomaly.py              # Statistical anomaly (token count, cost, latency vs baseline)
│   ├── confidence.py           # Hedging language, modal verbs, assertion density
│   └── impact_rescore.py       # Response-time impact re-scoring
│
├── deep_checks/                # Layer 2 — runs ASYNC (Celery tasks)
│   ├── claim_extractor.py      # Extract atomic claims from response
│   ├── evidence_retriever.py   # Search API / KB lookup / deterministic tools
│   ├── evidence_integrity.py   # Scan retrieved evidence for injection / quality
│   ├── nli_classifier.py       # DeBERTa NLI: ENTAILMENT / CONTRADICTION / NEUTRAL
│   ├── math_verifier.py        # Sympy-based math verification
│   ├── code_verifier.py        # Sandboxed code execution
│   ├── coverage.py             # Verification coverage metric
│   └── risk_model.py           # Calibrated risk score: P(unsupported claim)
│
├── policy/                     # Layer 3 — Policy Engine
│   ├── engine.py               # Main policy decision logic
│   ├── performance_policy.py   # Performance risk → action mapping
│   ├── responsibility_policy.py# Responsibility risk → action mapping
│   ├── cost_policy.py          # Cost risk → action mapping
│   └── actions.py              # ALLOW, ANNOTATE, REDACT, BLOCK, ESCALATE, WARN
│
├── responsibility/             # Data safety components
│   ├── pii_detector.py         # 3-layer PII: pattern + NER + semantic similarity
│   ├── data_taxonomy.py        # PII / Credentials / Secrets / Confidential / Regulated
│   ├── lineage.py              # Input→Output data lineage tracking
│   └── redactor.py             # Deterministic redaction (safe transforms only)
│
├── cost/                       # Cost engine
│   ├── tracker.py              # Actual cost calculation (tokens × price + tool + retry)
│   ├── anomaly.py              # Absolute / relative / trend cost anomalies
│   └── baseline.py             # Learned cost baselines per (model, category)
│
├── telemetry/                  # Fleet monitoring + baselines
│   ├── event_store.py          # Log every check result to PostgreSQL
│   ├── baselines.py            # Behavioral baseline + policy target baseline
│   ├── trends.py               # Change-point detection, statistical significance
│   ├── alerts.py               # Alert generation (behavioral anomaly / policy violation)
│   └── dashboard_api.py        # REST endpoints for dashboard frontend
│
├── human_review/               # Human escalation queue
│   ├── queue.py                # Priority-tiered review queue
│   ├── feedback.py             # Reviewer label ingestion + safeguards
│   └── routing.py              # CRITICAL/HIGH/MEDIUM/LOW routing logic
│
├── models/                     # Database models
│   ├── events.py               # Telemetry event schema
│   ├── policies.py             # Policy configuration schema
│   ├── baselines.py            # Baseline data schema
│   └── reviews.py              # Human review queue schema
│
├── config/                     # Configuration
│   ├── settings.py             # App settings (env vars, model paths, API keys)
│   ├── model_pricing.py        # Token pricing per model (GPT-4, Claude, Gemini, etc.)
│   └── default_policies.py     # Default policy rules per impact tier
│
├── dashboard/                  # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── Overview.jsx        # Fleet-level summary
│   │   │   ├── RequestDetail.jsx   # Single request drill-down
│   │   │   ├── CostAnalytics.jsx   # Cost trends + anomalies
│   │   │   ├── HallucinationRate.jsx # Contradiction rate over time
│   │   │   ├── ReviewQueue.jsx     # Human review interface
│   │   │   └── Policies.jsx        # Policy configuration UI
│   │   └── components/
│   │       ├── RiskBadge.jsx
│   │       ├── ClaimCard.jsx
│   │       ├── TrendChart.jsx
│   │       └── MetricCard.jsx
│   └── package.json
│
├── tests/                      # Test suite
│   ├── test_precheck.py
│   ├── test_fast_checks.py
│   ├── test_claim_extraction.py
│   ├── test_nli.py
│   ├── test_policy_engine.py
│   ├── test_pii_detection.py
│   ├── test_cost_tracking.py
│   └── test_end_to_end.py
│
├── docker-compose.yml          # Dev deployment
├── Dockerfile                  # Gateway container
├── requirements.txt
└── README.md
```

---

## 4. Database Schema (Core Tables)

```sql
-- Every request-response pair processed
CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    request_id      VARCHAR(64) NOT NULL,
    application_id  VARCHAR(64),
    model_id        VARCHAR(64),
    user_query      TEXT,
    llm_response    TEXT,
    query_labels    JSONB,          -- {"factual": 0.82, "analytical": 0.61, ...}
    impact_preliminary VARCHAR(16), -- low / medium / high / critical
    impact_rescored VARCHAR(16),    -- post-response re-score

    -- Fast check results
    tier1_pii       JSONB,
    tier2_toxicity  FLOAT,
    tier2_safety    FLOAT,
    tier2_anomaly   JSONB,

    -- Deep check results (populated async)
    claims          JSONB,          -- [{text, status, evidence_quality, nli_score}, ...]
    verification_coverage FLOAT,
    contradiction_rate    FLOAT,
    risk_score      FLOAT,          -- P(unsupported claim)
    detector_confidence FLOAT,

    -- Cost
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    actual_cost     DECIMAL(10, 6),
    expected_cost   DECIMAL(10, 6),

    -- Policy decision
    policy_action   VARCHAR(16),    -- allow / annotate / redact / block / escalate
    action_details  JSONB,

    -- Status
    deep_check_status VARCHAR(16) DEFAULT 'pending' -- pending / running / complete / skipped
);

-- Baselines per (model, category, app)
CREATE TABLE baselines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        VARCHAR(64),
    query_category  VARCHAR(64),
    application_id  VARCHAR(64),
    metric_name     VARCHAR(64),    -- token_count / cost / latency / hallucination_rate / ...
    baseline_type   VARCHAR(16),    -- behavioral / policy_target
    p50             FLOAT,
    p95             FLOAT,
    p99             FLOAT,
    sample_count    INTEGER,
    last_updated    TIMESTAMPTZ,
    UNIQUE(model_id, query_category, application_id, metric_name, baseline_type)
);

-- Human review queue
CREATE TABLE reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    priority        VARCHAR(16),    -- critical / high / medium / low
    status          VARCHAR(16) DEFAULT 'pending', -- pending / in_review / resolved
    assigned_to     VARCHAR(64),
    reviewer_label  VARCHAR(16),    -- correct / incorrect / uncertain
    reviewer_notes  TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

-- Policy configuration per application
CREATE TABLE policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  VARCHAR(64) NOT NULL,
    risk_dimension  VARCHAR(16),    -- performance / responsibility / cost
    impact_tier     VARCHAR(16),    -- low / medium / high / critical
    action_rules    JSONB,          -- {threshold: 0.7, action: "block", ...}
    data_policy     JSONB,          -- {classification, allowed_destinations, regulatory_scope}
    fairness_config JSONB,          -- {protected_attributes, acceptable_disparity}
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## 5. API Contract

### Main Proxy Endpoint (OpenAI-compatible)

```
POST /v1/chat/completions
```

Applications send their normal OpenAI-format request. ControlPlane forwards it, intercepts the response, runs checks, applies policy, and returns the result with optional annotations.

**Request** — standard OpenAI chat completions format:
```json
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Who invented the telephone?"}],
  "controlplane": {
    "application_id": "app_123",
    "data_classification": "internal",
    "impact_override": null
  }
}
```

**Response** — standard format + ControlPlane metadata:
```json
{
  "choices": [{"message": {"content": "Alexander Graham Bell..."}}],
  "controlplane": {
    "request_id": "req_abc",
    "policy_action": "allow",
    "impact": "medium",
    "fast_checks": {
      "pii_detected": false,
      "toxicity": 0.02,
      "safety": 0.01
    },
    "deep_check_status": "pending",
    "annotations": []
  }
}
```

### Dashboard API Endpoints

```
GET  /api/dashboard/overview           # Fleet-level summary metrics
GET  /api/dashboard/events             # Paginated event log
GET  /api/dashboard/events/:id         # Single event detail (with claims)
GET  /api/dashboard/metrics/hallucination  # Hallucination rate over time
GET  /api/dashboard/metrics/cost       # Cost trends
GET  /api/dashboard/metrics/pii        # PII incident rate
GET  /api/dashboard/baselines          # Current baselines
GET  /api/dashboard/alerts             # Active alerts
GET  /api/reviews                      # Human review queue
POST /api/reviews/:id/resolve          # Submit reviewer decision
GET  /api/policies/:app_id            # Get policy config
PUT  /api/policies/:app_id            # Update policy config
```

---

## 6. Implementation Phases

---

### Phase 1 — Gateway Proxy + Pre-Check
**Goal**: ControlPlane intercepts requests, forwards to LLM, returns response. Pre-check scans input.

#### 1.1 Gateway Proxy (`gateway/proxy.py`)
```python
# Core logic:
# 1. Receive OpenAI-format request
# 2. Run pre-checks on input
# 3. Forward to actual LLM API (OpenAI / Anthropic / etc.)
# 4. Return response with controlplane metadata attached
```
- Accept `POST /v1/chat/completions`
- Parse the `model` field → look up target API base URL from config
- Forward request using `httpx.AsyncClient`
- Attach `request_id`, timing metadata
- Support streaming (SSE passthrough) — collect full response for checks, stream to user simultaneously

#### 1.2 Pre-Check: Input PII Scan (`precheck/pii_input.py`)
- Regex patterns for: email, phone, credit card, national ID formats, API key patterns (`sk-`, `AKIA`, `ghp_`, etc.)
- Return: list of detected items with type and position
- Action: log warning (don't block — the user chose to include it)

#### 1.3 Pre-Check: Prompt Injection Detection (`precheck/injection.py`)
- Pattern matching for common injection phrases: "ignore previous instructions", "you are now", "system:", role-override patterns
- Small classifier (distilbert-based) for more sophisticated attempts
- Return: injection_probability score

#### 1.4 Pre-Check: Budget Gate (`precheck/budget.py`)
- Redis-backed session/account spend tracker
- Check: `current_session_spend + estimated_request_cost < budget_limit`
- If over budget → return 429 with explanation

#### 1.5 Pre-Check: Query Classifier (`precheck/classifier.py`)
- Multi-label classifier (fine-tuned distilbert or zero-shot with `bart-large-mnli`)
- Labels: `factual`, `analytical`, `mathematical`, `code`, `creative`, `current_info`
- Output: probability vector, not single label
- Threshold per label: 0.5 for activation

#### 1.6 Pre-Check: Impact Estimate (`precheck/impact.py`)
- Rule-based + classifier:
  - Application domain (from config: `medical` → HIGH, `entertainment` → LOW)
  - Query labels (`medical` keywords → HIGH, `creative` → LOW)
- Output: `{low, medium, high, critical}` — preliminary, will be re-scored after response

#### 1.7 Database + Event Logging
- Set up PostgreSQL with schema from Section 4
- Log every request as an event row at entry
- Redis for session state

**Deliverable**: A working proxy that forwards requests to any OpenAI-compatible API, scans inputs, classifies queries, and logs everything.

---

### Phase 2 — Fast Checks (Inline, Post-Response)
**Goal**: Before delivering the response, run lightweight checks. This is the inline path.

#### 2.1 Tier 1: Deterministic Patterns (`fast_checks/tier1.py`)
- Same regex engine as pre-check, but scanning the **response** text
- Credentials: API keys, tokens, private key headers (`-----BEGIN`)
- PII: email, phone, national ID, credit card
- Schema validation: if response is JSON, validate against expected schema
- Loop detection: repeated sequences > N tokens
- Return: list of detections with type, position, severity

#### 2.2 Tier 2: Toxicity + Safety (`fast_checks/tier2.py`)
- Model: `unitary/toxic-bert` or `facebook/roberta-hate-speech-dynabench` (local, ~300MB)
- Input: response text
- Output: toxicity_score [0,1], safety categories
- Threshold: configurable per application policy

#### 2.3 Tier 2: NER-based PII (`fast_checks/tier2.py`)
- Model: `dslim/bert-base-NER` or `Jean-Baptiste/roberta-large-ner-english` (local)
- Catches: person names, addresses, organization names in prose
- This is the Layer 2 PII that regex misses
- Output: detected entities with type, position, confidence
- Acknowledged false-negative rate: ~5–15%

#### 2.4 Tier 2: Topic Drift (`fast_checks/tier2.py`)
- Sentence-transformers embedding of query vs response
- Cosine similarity below threshold → flag (response may be off-topic)
- Model: `all-MiniLM-L6-v2` (local, 80MB, fast)
- Note: this detects drift, NOT correctness — explicitly labeled as such

#### 2.5 Statistical Anomaly (`fast_checks/anomaly.py`)
- Compare current response metrics against stored baselines:
  - `output_tokens` vs baseline `P95` for this `(model, category)`
  - `actual_cost` vs baseline `P95`
  - `response_latency` vs baseline `P95`
- If no baseline exists yet (cold start): skip, don't false-alarm

#### 2.6 Confidence Signals (`fast_checks/confidence.py`)
- Rule-based + regex:
  - Hedging phrases: "I think", "I'm not sure", "it's possible that"
  - Strong assertions: "definitely", "certainly", "the answer is"
  - Modal verbs: "might", "could", "should"
- Output: `confidence_score` [0,1] — how confident the model *sounds*
- This is NOT correctness — it's one input to the risk model

#### 2.7 Impact Re-Score (`fast_checks/impact_rescore.py`)
- Scan response content for high-impact domain signals:
  - Medical: medication names, dosage, symptoms, drug interactions (keyword list + NER)
  - Financial: specific investment advice, account numbers
  - Legal: legal citations, rights advisories
- If detected: upgrade impact to HIGH or CRITICAL regardless of preliminary estimate
- Can only increase impact, never decrease
- Output: `impact_rescored` ∈ `{low, medium, high, critical}`

#### 2.8 Policy Decision (Inline)
- Using Tier 1 + Tier 2 results + rescored impact:
  - Credential/secret in response → REDACT (automatic)
  - Toxicity above threshold → BLOCK or ANNOTATE per policy
  - PII in response + data policy violation → REDACT or BLOCK
- If no immediate risk → ALLOW and continue to async path

**Deliverable**: Responses pass through fast checks before delivery. PII/credentials are auto-redacted. Toxic content is caught. Impact is re-scored against response content.

---

### Phase 3 — Deep Verification (Async)
**Goal**: Claim-level factual verification, running in parallel via Celery workers.

#### 3.1 Async Task Dispatch
- After inline checks, if Tier 3 is triggered (by risk signal OR sampling policy):
  - Enqueue Celery task: `deep_verify(event_id)`
- Sampling policy:
  - `impact = critical/high` → always enqueue
  - `impact = medium` → 25% random sample
  - `impact = low` → 5% random sample
  - Tier 2 risk signal present → always enqueue regardless of impact

#### 3.2 Claim Extraction (`deep_checks/claim_extractor.py`)
- Model: `google/flan-t5-small` or `google/flan-t5-base` (local)
- Prompt format:
  ```
  Extract all factual claims from the following text as a numbered list.
  Each claim should be one atomic statement.

  Text: "{response_text}"

  Claims:
  ```
- Parse output into list of claim strings
- Classify each claim: `factual_assertion`, `numerical`, `causal`, `recommendation`, `opinion`
- Opinion/style claims → `NOT_VERIFIABLE` immediately
- Return: list of `{text, type, status: "pending"}`

#### 3.3 Tool-Aware Evidence Retrieval (`deep_checks/evidence_retriever.py`)
- Route each claim to the appropriate verifier based on type:

  ```python
  if claim.type == "numerical" or claim.type == "mathematical":
      return math_verifier.verify(claim)          # sympy
  elif claim.type == "code":
      return code_verifier.verify(claim)           # sandbox
  elif claim.type == "factual_assertion":
      return search_evidence(claim)                # search API
  elif claim.type == "opinion":
      return ClaimResult(status="NOT_VERIFIABLE")
  ```

- **Search evidence** (`evidence_retriever.py`):
  - Call Google Search API (or Bing) with claim text as query
  - Take top 3–5 results
  - Extract relevant snippets (first 500 chars per result)
  - Return: list of `{source_url, snippet, title}`

#### 3.4 Evidence Integrity Scan (`deep_checks/evidence_integrity.py`)
- Before using retrieved evidence for NLI, scan it:
  - Prompt injection patterns in evidence text
  - Source allowlist check (is this domain trusted?)
  - Content-type anomaly (is evidence mostly instructions/code rather than factual prose?)
- If evidence fails integrity → discard it; claim status → `NOT_VERIFIABLE`
- Log the adversarial attempt

#### 3.5 Evidence Quality Scoring
- Per evidence snippet:
  - `source_authority`: known-good (Wikipedia, official sites) = 0.9; news = 0.7; unknown = 0.4
  - `freshness`: if query is about current info, discount evidence older than 6 months
  - `specificity`: embedding similarity between claim and evidence snippet
- `evidence_quality = weighted_avg(authority, freshness, specificity)`

#### 3.6 NLI Classification (`deep_checks/nli_classifier.py`)
- Model: `microsoft/deberta-v3-base-mnli-fever-anli` (local, ~400MB)
- Input format:
  ```
  premise: "{evidence_snippet}"
  hypothesis: "{claim_text}"
  ```
- Output: `{ENTAILMENT, CONTRADICTION, NEUTRAL}` + confidence score
- Run against top evidence snippet (highest quality score)
- Map to claim status:
  - `ENTAILMENT` → `SUPPORTED`
  - `CONTRADICTION` → `CONTRADICTED`
  - `NEUTRAL` → `UNKNOWN`

#### 3.7 Math Verification (`deep_checks/math_verifier.py`)
- Parse mathematical expression from claim using regex + sympy
- Evaluate symbolically
- Compare model's stated answer with computed answer
- Exact match → `SUPPORTED`; mismatch → `CONTRADICTED`
- Parse failure → `NOT_VERIFIABLE`

#### 3.8 Code Verification (`deep_checks/code_verifier.py`)
- Extract code blocks from response
- Run in sandboxed Docker container with timeout (5s)
- Check: does it run without error? Does output match expected?
- Syntax error → `CONTRADICTED` (if model claimed it would work)
- Runs successfully → `SUPPORTED`

#### 3.9 Verification Coverage (`deep_checks/coverage.py`)
```python
total_claims = len(all_claims)
verified = len([c for c in claims if c.status in ("SUPPORTED", "CONTRADICTED", "UNKNOWN")])
coverage = verified / total_claims if total_claims > 0 else 0
contradiction_rate = len([c for c in claims if c.status == "CONTRADICTED"]) / total_claims
```

#### 3.10 Calibrated Risk Model (`deep_checks/risk_model.py`)
- Initially: rule-based scoring (pre-training data):
  ```python
  risk_score = (
      0.4 * contradiction_rate +
      0.3 * (1 - groundedness_score) +
      0.2 * (1 - verification_coverage) +
      0.1 * (1 - confidence_calibration)
  )
  ```
- Later: trained logistic regression / gradient boost on labeled data
- Output: `P(material unsupported claim)` + `detector_confidence`

#### 3.11 Retroactive Action
- After deep verification completes, update the event record in DB
- If CONTRADICTED claim found on HIGH/CRITICAL impact:
  - Add to human review queue
  - Log alert for operator dashboard
  - If application has configured retroactive notification → send webhook
- Update fleet-level metrics (hallucination count, contradiction rate)

**Deliverable**: Celery workers perform full claim-level verification. Each claim gets a status. Fleet metrics update in real-time.

---

### Phase 4 — Policy Engine + Responsibility Engine
**Goal**: Risk-specific policy decisions, PII data lineage, deterministic redaction.

#### 4.1 Policy Engine (`policy/engine.py`)
```python
def evaluate(event, fast_results, deep_results, policy_config):
    perf_action  = performance_policy(deep_results, policy_config)
    resp_action  = responsibility_policy(fast_results, policy_config)
    cost_action  = cost_policy(event.actual_cost, baselines, policy_config)

    # Most severe action wins for inline path
    # Each action logged independently
    return resolve_actions(perf_action, resp_action, cost_action)
```

#### 4.2 Action Resolution
```python
ACTION_SEVERITY = {
    "allow": 0, "annotate": 1, "warn": 2, "redact": 3, "block": 4, "escalate": 5
}

def resolve_actions(*actions):
    # Most severe wins — but each is logged independently
    return max(actions, key=lambda a: ACTION_SEVERITY[a.action])
```

#### 4.3 Impact-Aware Risk
```python
effective_risk = risk_score * detector_confidence * impact_weight_map[impact_rescored]
# impact_weight_map: low=0.3, medium=0.6, high=1.0, critical=1.0

# Thresholds (configurable per application):
if effective_risk > 0.5:   action = "block"
elif effective_risk > 0.3: action = "verify"  # trigger sync deep check if not done
elif effective_risk > 0.15: action = "annotate"
else:                       action = "allow"
```

#### 4.4 Three-Layer PII Detection (`responsibility/pii_detector.py`)
```python
def detect_pii(text, input_text=None):
    # Layer 1: Pattern matching (deterministic)
    pattern_hits = regex_scan(text)  # email, phone, credit card, API keys

    # Layer 2: NER (model-based, inline)
    ner_hits = ner_scan(text)  # names, addresses, orgs

    # Layer 3: Semantic similarity (async only)
    if input_text:
        leakage_hits = semantic_leakage_scan(input_text, text)

    return combine_results(pattern_hits, ner_hits, leakage_hits)
```

#### 4.5 Data Lineage (`responsibility/lineage.py`)
- At pre-check: classify input sensitivity, store in session context
- At fast-check: scan output for reproduced sensitive tokens
- Compare: did classified-sensitive input appear in output?
- If yes + policy forbids it → REDACT or BLOCK

#### 4.6 Redactor (`responsibility/redactor.py`)
- **Deterministic only** — no semantic rewriting:
  ```python
  def redact(text, detections):
      for det in detections:
          if det.type in ("email", "phone", "credit_card", "api_key", "ssn"):
              text = text.replace(det.value, f"[{det.type.upper()}_REDACTED]")
          elif det.type in ("person_name", "address"):  # NER-based
              text = text.replace(det.value, f"[PII_REDACTED]")
      return text
  ```

#### 4.7 Cost Tracking (`cost/tracker.py`)
```python
def calculate_cost(model_id, input_tokens, output_tokens, tool_calls=0, retries=0):
    pricing = MODEL_PRICING[model_id]
    return (
        input_tokens * pricing["input_per_token"] +
        output_tokens * pricing["output_per_token"] +
        tool_calls * pricing.get("tool_call", 0) +
        retries * pricing.get("retry_overhead", 0)
    )
```

**Deliverable**: Policy engine makes risk-specific decisions. PII is detected across three layers. Sensitive data is traced from input to output. Redaction is automatic and deterministic.

---

### Phase 5 — Fleet Monitoring + Dashboard
**Goal**: Telemetry aggregation, baselines, trend detection, operator dashboard.

#### 5.1 Telemetry Aggregation (`telemetry/baselines.py`)
- Cron job (every hour): aggregate events per `(model_id, query_category, application_id)`
- Compute: P50, P95, P99 for token count, cost, latency
- Compute: rolling hallucination rate, contradiction rate, PII incident rate
- Store in `baselines` table

#### 5.2 Two Baselines
```python
class BaselineEngine:
    def get_behavioral_baseline(self, model_id, category, metric):
        # Learned from traffic — "what normally happens"
        return db.query(baselines).filter(type="behavioral", ...)

    def get_policy_target(self, app_id, metric):
        # Set by operator — "what should happen"
        return db.query(baselines).filter(type="policy_target", ...)

    def check_anomaly(self, current_value, model_id, category, metric):
        behavioral = self.get_behavioral_baseline(model_id, category, metric)
        policy = self.get_policy_target(app_id, metric)

        alerts = []
        if current_value > behavioral.p95:
            alerts.append(Alert(type="BEHAVIORAL_ANOMALY", ...))
        if current_value > policy.target:
            alerts.append(Alert(type="POLICY_VIOLATION", ...))
        return alerts
```

#### 5.3 Statistical Significance (`telemetry/trends.py`)
- Minimum sample thresholds before alerts fire:
  - Rate-change alerts: N ≥ 1,000
  - Change-point detection: N ≥ 500
  - Per-category baseline: N ≥ 200
- Below threshold: show "insufficient data" in dashboard, not false rates
- Use scipy for significance testing:
  ```python
  from scipy.stats import proportions_ztest
  stat, pvalue = proportions_ztest([count_new, count_old], [n_new, n_old])
  if pvalue < 0.001 and n_new >= MIN_SAMPLE:
      fire_alert(...)
  ```

#### 5.4 Human Review Queue (`human_review/queue.py`)
```python
def enqueue_review(event, risk_score, detector_confidence, impact):
    priority = calculate_priority(risk_score, detector_confidence, impact)
    # CRITICAL: risk > 0.8, confidence > 0.8, impact = critical
    # HIGH:     risk > 0.6, confidence > 0.7, impact >= high
    # MEDIUM:   risk > 0.4, sampled 10%
    # LOW:      log only

    if priority in ("critical", "high"):
        Review.create(event_id=event.id, priority=priority, status="pending")
```

#### 5.5 Dashboard Frontend (`dashboard/`)
- **Overview page**: fleet-level cards showing today's request count, hallucination rate, PII incidents, cost, active alerts
- **Hallucination drilldown**: line chart of contradiction rate over time, per model, with behavioral baseline and policy target overlaid
- **Cost analytics**: cost per request trend, cost anomaly events, model routing efficiency
- **Request detail**: single event view showing query, response, claims extracted, claim statuses, evidence used, policy decision taken
- **Review queue**: list of pending reviews, sorted by priority, with accept/reject/uncertain buttons
- **Policy config**: edit thresholds, impact overrides, data classification per application

**Deliverable**: Operator dashboard showing fleet health, drill-down into individual events, trend charts with statistical significance, and a working human review interface.

---

## 7. Verification Plan

### Three Demo Flows (for presentation)

**Demo 1 — Hallucination Caught**
```
Query:    "Who invented the telephone?"
LLM:      "Thomas Edison invented the telephone in 1876."
→ Claim extracted: "Edison invented the telephone"
→ Evidence: Wikipedia says Bell invented the telephone
→ NLI: CONTRADICTION (confidence: 0.96)
→ Coverage: 1/1 = 100%
→ Risk: P(unsupported) = 0.94
→ Policy: ANNOTATE (medium-impact contradiction)
→ Dashboard: contradiction event logged, rate updated
```

**Demo 2 — Impact Re-Score in Action**
```
Query:    "What herbs help with stress?" (preliminary: LOW)
LLM:      "Don't combine St. John's Wort with SSRIs — serotonin syndrome risk"
→ Response contains medication names + clinical warning
→ Impact re-scored: LOW → HIGH
→ Tier 3 triggered at 100% (high impact)
→ Claim verified against clinical reference → SUPPORTED
→ Policy: ANNOTATE (medical disclaimer added)
```

**Demo 3 — Data Leakage Prevented**
```
User input:  contains API key "sk-abc123..."
LLM:         reproduces the key in explanation
→ Tier 1: credential pattern matched in output
→ Lineage: sensitive input token reproduced in output
→ Policy: REDACT automatically
→ Response delivered with "[API_KEY_REDACTED]"
→ Dashboard: leakage incident logged
```

### Automated Tests
```bash
pytest tests/ -v                    # Unit tests for each component
pytest tests/test_end_to_end.py     # Full pipeline integration tests
```

### Manual Verification
- Send 50 crafted queries (mix of correct, hallucinated, PII-laden, toxic)
- Verify each gets correct policy action
- Check dashboard reflects all events correctly
- Verify async deep checks complete and update event records

---

## 8. Build Order — Actual Progress

### Completed ✅

```
Phase 1 — Gateway Proxy
  ✔ FastAPI proxy forwards to Groq free-tier LLM
  ✔ OpenAI-compatible API contract
  ✔ Pre-check: PII scan, injection detection, query classifier, impact estimate
  ✔ PostgreSQL + SQLite dual persistence (auto-detected)
  ✔ Event logging with full metadata

Phase 2 — Fast Checks
  ✔ Tier 1: regex credential/PII detection in response
  ✔ Tier 2: keyword toxicity (heuristic), topic drift
  ✔ Impact re-scorer (medical/financial keywords)
  ✔ Confidence signal extraction
  ✔ Policy engine: Most-Severe-Wins (allow/annotate/redact/block)

Phase 3 — Deep Verification
  ✔ Claim extraction via Groq (async background thread)
  ✔ Evidence retrieval: DuckDuckGo + local knowledge base
  ✔ NLI heuristic classifier (regex-based)
  ✔ Risk score model
  ✔ Retroactive alerts (contradicted claims → review queue)

Phase 5 — Dashboard
  ✔ Overview: fleet KPIs, time series, donut chart
  ✔ Event Log: searchable, filterable, paginated
  ✔ Event Detail: claims, evidence, risk summary
  ✔ Hallucination Monitor: contradiction rate chart
  ✔ Cost Analytics: spend by model
  ✔ Data Safety: PII incident view
  ✔ Review Queue: human reviewer interface
  ✔ Live Demo: interactive chat playground

Deployment
  ✔ Render (backend) — https://controlplane-api.onrender.com
  ✔ Vercel (frontend) — https://controlplane-dashboard.vercel.app
  ✔ GitHub — https://github.com/lassi16/ControlPlane
```

### Week 2 (Next) ⏳

```
  □ Swap keyword toxicity → unitary/toxic-bert
  □ Swap regex NLI → cross-encoder/nli-deberta-v3-small
  □ API key authentication (per-tenant)
  □ Redis + Celery (true async workers)
  □ Rate limiting
```

### Week 3–4 (Planned) 🔮

```
  □ Nginx reverse proxy + SSL certificate
  □ Prometheus + Grafana metrics
  □ Statistical significance on baselines
  □ Webhook retroactive notifications
  □ Policy configuration UI
```

---

*ControlPlane v0.2.0 — AIC 2026 | lassi16/ControlPlane*
