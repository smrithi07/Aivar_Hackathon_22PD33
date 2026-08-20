# Semantic DLP Gateway

**Aivar Innovations — Agentic AI Task (AI Governance)**
**Problem Statement PS-5.3: Semantic Data Exfiltration Detector**

Live demo: http://semantic-dlp-prod.eba-btbumjmq.ap-south-2.elasticbeanstalk.com/

---

## The Problem

Standard DLP (Data Loss Prevention) tools catch exfiltration by pattern-matching known formats — a credit card number, an email address, a Social Security number. But an AI agent doesn't need to leak data in a recognizable format. If an agent has access to a confidential record, it can paraphrase, summarize, or reconstruct that information piece-by-piece — with zero exact quotes and zero recognizable patterns. No format-matching DLP tool catches this, because the *surface form* is unrecognizable even when the *meaning* is leaked.

**Semantic DLP Gateway** detects this class of leak: it identifies when an AI-generated output semantically carries protected information, even when that information has been reworded, rounded, summarized, or reconstructed without ever directly quoting the source.
# Semantic DLP Gateway

**Aivar Innovations — Agentic AI Task (AI Governance)**
**Problem Statement PS-5.3: Semantic Data Exfiltration Detector**

Live demo: http://semantic-dlp-prod.eba-btbumjmq.ap-south-2.elasticbeanstalk.com/

---

## The Problem

Standard DLP (Data Loss Prevention) tools catch exfiltration by pattern-matching known formats — a credit card number, an email address, a Social Security number. But an AI agent doesn't need to leak data in a recognizable format. If an agent has access to a confidential record, it can paraphrase, summarize, or reconstruct that information piece-by-piece — with zero exact quotes and zero recognizable patterns. No format-matching DLP tool catches this, because the *surface form* is unrecognizable even when the *meaning* is leaked.

**Semantic DLP Gateway** detects this class of leak: it identifies when an AI-generated output semantically carries protected information, even when that information has been reworded, rounded, summarized, or reconstructed without ever directly quoting the source.

---

## Architecture

Every candidate output is scored against a protected vault using three independent signals, which are combined into a single risk-weighted decision:

```
                        ┌─────────────────────────┐
                        │   PROTECTED VAULT        │
                        │ 10 synthetic finance docs │
                        │ across 5 categories        │
                        └───────────┬───────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
         ┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │  SIMILARITY   │ │  FACT MATCHER    │ │   LLM JUDGE       │
         │ Cohere embed  │ │ regex/NER extract │ │ Gemini structured │
         │ + cosine sim  │ │ + fuzzy field match│ │ factual-overlap   │
         └──────┬───────┘ └────────┬──────────┘ └────────┬──────────┘
                │                  │                      │
                └──────────────────┼──────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │    RISK ENGINE        │
                        │ weighted combination  │
                        │ + sensitivity bonus    │
                        └──────────┬────────────┘
                                   ▼
                         ALLOW / REVIEW / BLOCK
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │    AUDIT LOG          │
                        │ persisted, queryable   │
                        │ + live UI history panel│
                        └─────────────────────┘
```

### Why three signals, not one

- **Similarity (Cohere embeddings + cosine similarity)** — a recall-oriented signal. Catches "this is semantically related to something in the vault" even through heavy paraphrasing, but can't tell *which* specific facts leaked or whether the match is coincidental.
- **Fact Matcher (regex/NER + fuzzy matching against known field values)** — a precision-oriented signal. Extracts dollar amounts, dates, percentages, and named entities from the candidate text and checks them against the vault's known ground-truth values (with tolerance for rounding). Catches exact/near-exact leaks reliably, but is blind to spelled-out numbers or heavily reworded facts.
- **LLM Judge (Gemini, structured JSON output)** — a reasoning-oriented signal. Given the candidate text and a shortlist of the most similar vault documents, it judges whether the output contains facts that could only plausibly have come from that document — even when reworded, rounded, or reconstructed through inference. This is the signal that satisfies the problem statement's core requirement: detecting leaks that are paraphrased without any direct quoting.

No single signal is trusted alone. A number matching by coincidence, a vaguely-similar topic, or an over-eager LLM guess are all cross-checked against the other two before a decision is made — this is what keeps the false-positive rate low while still catching genuinely obfuscated leaks.

### Risk scoring

```
combined_score = 0.30 × similarity_score
                + 0.30 × fact_match_score
                + 0.40 × llm_leak_score
                + 0.10 (bonus, if any matched field is tagged "high" sensitivity)
```

The LLM judge signal is weighted highest because it's the only one that reasons about actual semantic fact-derivation — the PS's explicit ask — rather than surface-level pattern matching.

**Decision thresholds:** `< 0.4` → ALLOW · `0.4–0.7` → REVIEW · `≥ 0.7` → BLOCK

These thresholds and weights are principled defaults chosen through manual reasoning and testing, not statistically calibrated against a large labeled dataset — see Known Limitations.

---

## The Protected Vault

Ten synthetic (entirely fictional) finance documents, generated via Gemini, spanning five categories — chosen to give the project a finance/fintech framing consistent with real regulatory concerns (SOX, GLBA-style data sensitivity):

| Category | Example fields |
|---|---|
| Employee Compensation | salary, bonus, department, manager, joining date |
| Customer Financial Records | income, credit limit, outstanding balance, risk score |
| Corporate Transactions | transaction amount, client, transaction type, approver |
| Internal Financial Reports | revenue, expenses, profit, growth forecast |
| Confidential Deal Information | acquisition price, valuation, expected synergy, announcement date |

Each field is tagged with a sensitivity level (`high` / `medium` / `low`) at ingestion — e.g., salary and valuation are `high`, department and approver are `low`. This tagging feeds directly into the risk engine's scoring bonus, and every detected match propagates its source `doc_id` and `category` into the audit log — satisfying the bonus **data lineage** requirement: every vault document acts as a tagged source, and any output that semantically matches one carries that tag through to the audit trail.

---

## Tech Stack

| Component | Technology |
|---|---|
| API framework | Flask |
| Embeddings | Cohere (`embed-v4.0`) |
| Similarity search | Cosine similarity (numpy) |
| Fact extraction | Regex + `rapidfuzz` fuzzy string matching |
| LLM reasoning | Google Gemini (`gemini-3.5-flash-lite`) |
| Vault generation | Gemini, structured JSON output |
| Audit logging | Persistent local log, queryable by decision, surfaced live in the UI |
| Deployment | AWS Elastic Beanstalk (single-instance, Python/AL2023 platform) |
| Frontend | Server-rendered HTML + vanilla JS (no build step); includes a live "Recent decisions" panel reading directly from the audit log |

---

## API

### `POST /score`
Core detection endpoint.

**Request:**
```json
{ "text": "An employee named Cassian earns roughly one hundred fifteen thousand dollars a year in the Quantum Logistics team." }
```

**Response:**
```json
{
  "decision": "BLOCK",
  "overall_risk_score": 0.7438,
  "top_match": {
    "doc_id": "employee_compensation_001",
    "category": "employee_compensation",
    "entity_name": "Cassian Vane",
    "similarity_score": 0.7262,
    "fact_match_score": 0.1,
    "llm_leak_score": 0.99,
    "matched_fields": ["salary", "department", "joining_date"]
  },
  "all_scores": [ ... ]
}
```

### `GET /vault`
Lists vault documents by metadata only (`doc_id`, `category`, `entity_name`) — never exposes field values, since that would defeat the purpose of a protected vault.

### `GET /audit`
Returns the persisted audit log. Supports `?limit=20&decision=BLOCK` query params.

**Response:**
```json
{
  "count": 4,
  "events": [
    {
      "timestamp": "2026-08-20T09:44:29.211871+00:00",
      "source": "api",
      "decision": "BLOCK",
      "overall_risk_score": 0.8578,
      "text": "...",
      "top_match": {
        "doc_id": "employee_compensation_001",
        "category": "employee_compensation",
        "entity_name": "Cassian Vane",
        "similarity_score": 0.5926,
        "fact_match_score": 0.6,
        "llm_leak_score": 1.0,
        "matched_fields": ["bonus", "salary"]
      }
    }
  ]
}
```

This same endpoint powers the "Recent decisions" panel on the live UI, which renders the last 10 events (decision, entity, matched fields, risk score, time-since) directly from this response.

### `GET /health`
Basic health check for deployment monitoring.

---

## Testing & Validation

### Required success criteria (per PS-5.3)

A 20-case evaluation suite (10 normal outputs, 5 paraphrased vault leaks, 5 borderline cases) was generated and run against all four of the problem statement's stated success criteria:

| Criterion | Result |
|---|---|
| Similarity ranks paraphrased content higher than unrelated outputs | **PASS** — min(paraphrased similarity) = 0.738 vs. max(normal similarity) = 0.398 |
| Factual overlap detector identifies ≥4/5 paraphrased cases | **PASS** — 5/5 detected |
| False positive rate on normal outputs below 20% | **PASS** — 0/10 flagged (0%) |
| Detection works despite obfuscation without direct quoting | **PASS** — validated via the same paraphrased test set, all generated without direct quotation |

### Adversarial stress testing

Beyond the required suite, six hand-crafted adversarial cases were run to test specific evasion strategies not covered by the generated test set:

| Attack pattern | Result |
|---|---|
| Inferential/Q&A reconstruction ("based on what's typical for someone with Cassian's tenure...") | **Caught** (BLOCK) |
| Numeric coincidence in an unrelated context (same salary figure, describing a car) | **Correctly not flagged** (ALLOW) — proves the system doesn't false-positive on coincidental numbers |
| Low-sensitivity-only reveal (department, manager, join date — no dollar figures) | **Caught** (REVIEW) — correctly routed to human review rather than a binary guess |
| Unit-conversion obfuscation (monthly figure requiring ×12 math to match) | **Caught** (REVIEW) — via the LLM judge's reasoning, not the regex fact-matcher |
| Name + all figures simultaneously generalized | **Inconsistent** — oscillates between REVIEW/BLOCK across repeated runs; see Known Limitations |
| Cross-category mixed leak (transaction + compensation facts in one output) | **Caught** (REVIEW), but only one of the two source documents is surfaced in the top-level match |

---

## Known Limitations

Documented honestly rather than hidden:

1. **Simultaneous name + figure generalization.** When an output omits the entity's name *and* rounds every number ("an analyst in the logistics division... just north of a hundred grand"), detection is unreliable — verdicts vary between REVIEW and BLOCK across repeated runs on the same input, rather than consistently flagging. This appears to stem from LLM judge non-determinism at the decision boundary on a genuinely ambiguous case, rather than a deterministic miss — the system does not offer a reliable silent-bypass path even here, but consistency at this boundary is a fair target for future work.
2. **Single top-match surfacing.** The current design returns one top-matching document per evaluation. An output that mixes leaked facts from two different vault categories in a single sentence is still correctly flagged, but only the highest-scoring source document is detailed in the response — the second leak isn't separately decomposed.
3. **Regex-based fact extraction cannot parse spelled-out numbers** ("one hundred fifteen thousand dollars") on its own — this gap is intentionally covered by the LLM judge signal instead, which reasons about phrasing rather than pattern-matching digits.
4. **Audit log persistence is tied to the deployed instance's local disk.** Functionally reliable for this single-instance demo deployment, but a production system would need this in durable external storage (e.g. DynamoDB) to survive instance replacement and support multi-worker concurrency safely — noted as a next step, not attempted under hackathon time constraints.
5. **Scope boundary.** This system detects output-side semantic leakage. It assumes vault access itself is already governed upstream (identity/access control, encryption, authorization) — those concerns belong to other units in this problem set (e.g., PS-2 Tool Permission Enforcer, PS-6/7 Compliance & Audit) and are out of scope here by design.

---

## Running Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your COHERE_API_KEY and GEMINI_API_KEY
python scripts/build_vault.py   # one-time: generates the protected vault
python run.py
```

Visit `http://localhost:5000/`.

## Deployment

Deployed on AWS Elastic Beanstalk, single-instance mode (Python on Amazon Linux 2023 platform), with environment variables set via `eb setenv`. See the live demo link at the top of this document.

---

## Production Readiness Checklist

- [x] Deployed to a cloud environment (AWS Elastic Beanstalk), not localhost
- [x] Exposes a usable, documented API
- [x] Persists state (vault, embeddings cache, audit log)
- [x] Structured error handling and input validation on all endpoints
- [x] Health check endpoint (`/health`)
- [x] Connects to real LLM providers (Cohere for embeddings, Gemini for reasoning) — no mocked responses
- [x] Logging on every request (application logs + persistent audit trail, surfaced live in-app)
- [x] Retry/backoff logic for transient upstream API failures (confirmed recovering from real rate-limit and timeout errors during testing)
---

## Architecture

Every candidate output is scored against a protected vault using three independent signals, which are combined into a single risk-weighted decision:

```
                        ┌─────────────────────────┐
                        │   PROTECTED VAULT        │
                        │ 10 synthetic finance docs │
                        │ across 5 categories        │
                        └───────────┬───────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
         ┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐
         │  SIMILARITY   │ │  FACT MATCHER    │ │   LLM JUDGE       │
         │ Cohere embed  │ │ regex/NER extract │ │ Gemini structured │
         │ + cosine sim  │ │ + fuzzy field match│ │ factual-overlap   │
         └──────┬───────┘ └────────┬──────────┘ └────────┬──────────┘
                │                  │                      │
                └──────────────────┼──────────────────────┘
                                   ▼
                        ┌─────────────────────┐
                        │    RISK ENGINE        │
                        │ weighted combination  │
                        │ + sensitivity bonus    │
                        └──────────┬────────────┘
                                   ▼
                         ALLOW / REVIEW / BLOCK
                                   │
                                   ▼
                        ┌─────────────────────┐
                        │    AUDIT LOG          │
                        │ persisted, queryable   │
                        └─────────────────────┘
```

### Why three signals, not one

- **Similarity (Cohere embeddings + cosine similarity)** — a recall-oriented signal. Catches "this is semantically related to something in the vault" even through heavy paraphrasing, but can't tell *which* specific facts leaked or whether the match is coincidental.
- **Fact Matcher (regex/NER + fuzzy matching against known field values)** — a precision-oriented signal. Extracts dollar amounts, dates, percentages, and named entities from the candidate text and checks them against the vault's known ground-truth values (with tolerance for rounding). Catches exact/near-exact leaks reliably, but is blind to spelled-out numbers or heavily reworded facts.
- **LLM Judge (Gemini, structured JSON output)** — a reasoning-oriented signal. Given the candidate text and a shortlist of the most similar vault documents, it judges whether the output contains facts that could only plausibly have come from that document — even when reworded, rounded, or reconstructed through inference. This is the signal that satisfies the problem statement's core requirement: detecting leaks that are paraphrased without any direct quoting.

No single signal is trusted alone. A number matching by coincidence, a vaguely-similar topic, or an over-eager LLM guess are all cross-checked against the other two before a decision is made — this is what keeps the false-positive rate low while still catching genuinely obfuscated leaks.

### Risk scoring

```
combined_score = 0.30 × similarity_score
                + 0.30 × fact_match_score
                + 0.40 × llm_leak_score
                + 0.10 (bonus, if any matched field is tagged "high" sensitivity)
```

The LLM judge signal is weighted highest because it's the only one that reasons about actual semantic fact-derivation — the PS's explicit ask — rather than surface-level pattern matching.

**Decision thresholds:** `< 0.4` → ALLOW · `0.4–0.7` → REVIEW · `≥ 0.7` → BLOCK

---

## The Protected Vault

Ten synthetic (entirely fictional) finance documents, generated via Gemini, spanning five categories — chosen to give the project a finance/fintech framing consistent with real regulatory concerns (SOX, GLBA-style data sensitivity):

| Category | Example fields |
|---|---|
| Employee Compensation | salary, bonus, department, manager, joining date |
| Customer Financial Records | income, credit limit, outstanding balance, risk score |
| Corporate Transactions | transaction amount, client, transaction type, approver |
| Internal Financial Reports | revenue, expenses, profit, growth forecast |
| Confidential Deal Information | acquisition price, valuation, expected synergy, announcement date |

Each field is tagged with a sensitivity level (`high` / `medium` / `low`) at ingestion — e.g., salary and valuation are `high`, department and approver are `low`. This tagging feeds directly into the risk engine's scoring bonus, and every detected match propagates its source `doc_id` and `category` into the audit log — satisfying the bonus **data lineage** requirement: every vault document acts as a tagged source, and any output that semantically matches one carries that tag through to the audit trail.

---

## Tech Stack

| Component | Technology |
|---|---|
| API framework | Flask |
| Embeddings | Cohere (`embed-v4.0`) |
| Similarity search | Cosine similarity (numpy) |
| Fact extraction | Regex + `rapidfuzz` fuzzy string matching |
| LLM reasoning | Google Gemini (`gemini-3.5-flash-lite`) |
| Vault generation | Gemini, structured JSON output |
| Audit logging | Persistent local log, queryable by decision |
| Deployment | AWS Elastic Beanstalk (single-instance, Python/AL2023 platform) |
| Frontend | Server-rendered HTML + vanilla JS (no build step) |

---

## API

### `POST /score`
Core detection endpoint.

**Request:**
```json
{ "text": "An employee named Cassian earns roughly one hundred fifteen thousand dollars a year in the Quantum Logistics team." }
```

**Response:**
```json
{
  "decision": "BLOCK",
  "overall_risk_score": 0.7438,
  "top_match": {
    "doc_id": "employee_compensation_001",
    "category": "employee_compensation",
    "entity_name": "Cassian Vane",
    "similarity_score": 0.7262,
    "fact_match_score": 0.1,
    "llm_leak_score": 0.99,
    "matched_fields": ["salary", "department", "joining_date"]
  },
  "all_scores": [ ... ]
}
```

### `GET /vault`
Lists vault documents by metadata only (`doc_id`, `category`, `entity_name`) — never exposes field values, since that would defeat the purpose of a protected vault.

### `GET /audit`
Returns the persisted audit log. Supports `?decision=BLOCK` filtering.

### `GET /health`
Basic health check for deployment monitoring.

---


---

## Known Limitations


1. **Scope boundary.** This system detects output-side semantic leakage. It assumes vault access itself is already governed upstream (identity/access control, encryption, authorization) — those concerns belong to other units in this problem set (e.g., PS-2 Tool Permission Enforcer, PS-6/7 Compliance & Audit) and are out of scope here by design.

---

## Running Locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your COHERE_API_KEY and GEMINI_API_KEY
python scripts/build_vault.py   # one-time: generates the protected vault
python run.py
```

Visit `http://localhost:5001/`.

## Deployment

Deployed on AWS Elastic Beanstalk, single-instance mode (Python on Amazon Linux 2023 platform), with environment variables set via `eb setenv`. See the live demo link at the top of this document.

---

