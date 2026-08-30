# ControlPlane

ControlPlane is an AI governance infrastructure layer — a model-agnostic gateway proxy that intercepts every LLM request and response to provide continuous visibility and control. It acts as an independent auditing system that evaluates AI interactions across three primary dimensions: correctness, data safety, and cost.

## The Problem

Organizations embedding LLMs into their products face three compounding failure modes:
1.  **Hallucinations:** LLMs state false information with perfect confidence. Rule-based filters cannot catch semantic falsehoods.
2.  **Data Leakage:** Sensitive information (PII, credentials) provided in prompts can be silently reproduced by the LLM and sent to unintended destinations.
3.  **Cost Unpredictability:** Token usage drifts silently, causing unexpected budget spikes.

## Architecture & Approach

ControlPlane solves this without adding latency to the user experience. It utilizes **two distinct processing paths**:

### 1. Fast Inline Path (< 10ms)
A deterministic, rule-based pipeline that runs before the response reaches the user. It never calls another LLM, ensuring zero added latency.
*   **Input PII Scanner:** Detects emails, phones, API keys, etc., entering the system via regex patterns.
*   **Output PII & Credential Scanner:** Detects sensitive data in the LLM's response.
*   **Data Lineage Tracker:** Compares input PII against output text to catch leakage.
*   **Auto-Redactor:** Automatically strips sensitive data from the output before delivery.

### 2. Async Deep Verification (Background)
A heavy, LLM-powered verification pipeline that runs entirely off the critical path. The user receives their response instantly, while deep checks happen in the background and retroactively update the dashboard.
*   **Claim Extraction:** Decomposes responses into verifiable atomic claims.
*   **Tool-Aware Evidence Retrieval:** Routes claims to the appropriate verifier (e.g., Knowledge Base, Web Search, or Sympy for deterministic math verification).
*   **NLI Entailment Classifier:** Evaluates if the evidence supports, contradicts, or is unknown regarding the claim.
*   **Risk Scoring:** Aggregates findings to update the event's audit log.

## Features

*   **Model-Agnostic:** Works with any OpenAI-compatible API endpoint.
*   **Zero-Latency Promise:** Inline checks are purely deterministic; heavy checks are asynchronous.
*   **Data Leakage Prevention:** Tracks PII lineage from prompt to output and auto-redacts leaks.
*   **Cost Monitoring & Anomaly Detection:** Tracks per-request costs, calculates P50/P90 baselines, and alerts on anomalies (>3x P90).
*   **Fleet Trend Detection:** Compares rolling 1-hour metrics against 24-hour baselines to detect spikes in hallucination rates, cost, or PII incidents.
*   **Actionable Policy Engine:** Executes decisions (`ALLOW`, `ANNOTATE`, `REDACT`, `BLOCK`, `ESCALATE`) based on multi-dimensional scoring (Responsibility, Lineage, Performance, Cost).
*   **Comprehensive Operator Dashboard:** Real-time visibility into the fleet, complete event audit trails, cost analytics, and human review queues.

## Setup & Running Locally

### Prerequisites
*   Python 3.10+
*   Node.js v18+

### 1. Backend Setup
```bash
# Navigate to the backend directory
cd controlplane

# Create a virtual environment and install dependencies
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Start the gateway server
python -m uvicorn gateway.main:app --reload --port 8000
```
*The backend runs on `http://localhost:8000`.*

### 2. Frontend Setup
```bash
# Navigate to the dashboard directory
cd controlplane/dashboard

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```
*The dashboard runs on `http://localhost:5173`.*

## Project Structure

```text
controlplane/
├── dashboard/             # React/Vite operator dashboard frontend
├── data/                  # Local SQLite database (events.db)
├── deep_checks/           # Async LLM-powered verification (claims, NLI, math)
├── fast_checks/           # Deterministic inline scanners (PII, injection)
├── gateway/               # FastAPI routing and request handling
├── human_review/          # Human-in-the-loop review queue logic
├── policy/                # Policy engine (Allow, Annotate, Redact, Block, Escalate)
├── responsibility/        # Data lineage tracking and auto-redaction
└── telemetry/             # Cost baselines, trend detection, and event storage
```

## Integration

To route your application traffic through ControlPlane, simply change the base URL of your LLM client.

**Before:**
```python
client = OpenAI(api_key="your-api-key")
```

**After:**
```python
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="your-api-key"
)
```
No other code changes are required.
