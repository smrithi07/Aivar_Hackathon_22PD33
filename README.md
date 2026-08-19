# Semantic DLP Gateway

Semantic DLP Gateway is a Flask-based data-loss prevention service for detecting
whether generated text reveals facts from a protected finance vault.

The gateway combines three signals:

- Cohere embeddings and NumPy cosine similarity for semantic matching
- RapidFuzz and typed field extraction for exact and approximate fact matching
- Gemini judgment for paraphrased or reconstructed protected facts

The final risk score is calculated per vault document and classified as:

- `ALLOW`: below the review threshold
- `REVIEW`: requires human review
- `BLOCK`: above the block threshold

## Demo

The current Elastic Beanstalk deployment is available at:

<http://semantic-dlp-prod.eba-btbumjmq.ap-south-2.elasticbeanstalk.com>

The browser UI is served from `/`. The service also exposes JSON API endpoints.

## Architecture

```text
Client / browser
				|
				v
Flask API and UI
				|
				v
Risk engine
	|          |             |
	v          v             v
Cohere     RapidFuzz     Gemini
similarity fact match    LLM judge
				|
				v
Vault JSON, embedding cache, audit JSONL
```

For each `/score` request, the risk engine:

1. Embeds the candidate text with Cohere.
2. Scores it against cached vault embeddings.
3. Extracts and compares numbers, percentages, dates, and text fields.
4. Sends the top similarity matches to Gemini for factual-leakage judgment.
5. Combines similarity, fact-match, and LLM scores.
6. Adds a bonus when high-sensitivity fields match.
7. Returns the highest-risk document and decision.

## Project Structure

```text
app/
	api/routes.py                 Flask routes
	audit/logger.py               JSONL audit logging
	config.py                     Environment configuration
	embeddings/                   Cohere embedding and similarity logic
	fact_matcher/                 Typed fact extraction and fuzzy matching
	llm_judge/                    Gemini factual-leakage judgment
	risk_engine/                  Weighted risk scoring
	templates/index.html          Browser dashboard
	vault/                        Vault schema, generator, and data
scripts/
	build_vault.py                Generate synthetic vault documents
	normalize_vault.py            Normalize generated currency fields
tests/                          Manual and evaluation scripts
run.py                          Flask application entry point
Procfile                        Elastic Beanstalk Gunicorn command
```

## Requirements

- Python 3.9+ locally; Elastic Beanstalk is configured for Python 3.11
- Cohere API key
- Google Gemini API key
- Internet access from the application for both model APIs

Installed runtime dependencies are pinned in [requirements.txt](requirements.txt).

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the project root. Do not commit it:

```env
COHERE_API_KEY=your_cohere_api_key
GEMINI_API_KEY=your_gemini_api_key
RISK_THRESHOLD_REVIEW=0.4
RISK_THRESHOLD_BLOCK=0.7
```

Start the development server:

```bash
python run.py
```

Open <http://127.0.0.1:5001>.

For a production-style local run:

```bash
gunicorn --bind 0.0.0.0:5001 run:app
```

## Vault Workflow

The repository includes a generated vault under `app/vault/data/`. To generate
or extend it using Gemini:

```bash
python scripts/build_vault.py
```

The generator creates two synthetic documents per schema category by default.
It resumes from an existing vault and skips document IDs already present.

Normalize generated currency values before running the service:

```bash
python scripts/normalize_vault.py
```

The embedding cache is created automatically at:

```text
app/vault/data/vault_embeddings.json
```

The first score request with missing embeddings calls Cohere to build the cache.
Pre-generating the cache is recommended before deployment or demonstrations.

## API

### Health check

```bash
curl http://127.0.0.1:5001/health
```

Response:

```json
{"status": "ok", "service": "semantic-dlp-gateway"}
```

### List protected vault metadata

```bash
curl http://127.0.0.1:5001/vault
```

This returns document IDs, categories, and entity names only. Protected field
values are not exposed.

### Score candidate text

```bash
curl -X POST http://127.0.0.1:5001/score \
	-H 'Content-Type: application/json' \
	-d '{"text":"The acquisition is expected to close at a valuation of 4.2 million."}'
```

The response includes:

```json
{
	"text": "...",
	"decision": "REVIEW",
	"overall_risk_score": 0.58,
	"top_match": {
		"doc_id": "confidential_deal_information_001",
		"category": "confidential_deal_information",
		"entity_name": "Example Entity",
		"similarity_score": 0.81,
		"fact_match_score": 0.5,
		"llm_leak_score": 0.7,
		"matched_fields": ["valuation"],
		"risk_score": 0.58
	},
	"all_scores": []
}
```

`all_scores` contains the five highest-risk documents. The example values above
are illustrative; actual values depend on the vault and model responses.

### Read audit events

```bash
curl 'http://127.0.0.1:5001/audit?limit=20&decision=BLOCK'
```

Supported decisions are `ALLOW`, `REVIEW`, and `BLOCK`.


```

These scripts call Cohere and Gemini and may be subject to API quotas and cost.

## Deploying to AWS Elastic Beanstalk

The project is configured for Elastic Beanstalk with:

- Application: `semantic-dlp-gateway`
- Environment: `semantic-dlp-prod`
- Region: `ap-south-2`
- Platform: Python 3.11 on 64-bit Amazon Linux 2023
- Start command: `gunicorn run:app`

Install and configure the EB CLI, then initialize the project if needed:

```bash
eb init semantic-dlp-gateway --platform "Python 3.11" --region ap-south-2
eb use semantic-dlp-prod
```

Set secrets and thresholds as Elastic Beanstalk environment properties. Do not
place API keys in source control or in the README:

```bash
eb setenv \
  COHERE_API_KEY=your_cohere_api_key \
  GEMINI_API_KEY=your_gemini_api_key \
```

Deploy the current branch:

```bash
eb deploy semantic-dlp-prod
eb status semantic-dlp-prod
eb open
```

After deployment, verify the service:

```bash
curl http://your-environment-url/health
```

## Deployment Notes

The current version uses local JSON files for the vault, embedding cache, and
audit log. These files are available inside the Elastic Beanstalk instance, but
the instance filesystem should be treated as ephemeral. A production-grade
multi-instance deployment should move:

- `vault.json` and `vault_embeddings.json` to private Amazon S3
- audit events to DynamoDB or another durable store
- API secrets to AWS Secrets Manager or Systems Manager Parameter Store
- application logs to CloudWatch Logs

The `/vault` and `/audit` endpoints are currently debug/demo endpoints. Add
authentication, authorization, request limits, and HTTPS before exposing them
to untrusted users.

## Configuration Reference

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `COHERE_API_KEY` | Yes | None | Cohere embeddings |
| `GEMINI_API_KEY` | Yes | None | Gemini vault generation and judgment |
| `RISK_THRESHOLD_REVIEW` | No | `0.4` | Minimum score for `REVIEW` |
| `RISK_THRESHOLD_BLOCK` | No | `0.7` | Minimum score for `BLOCK` |
| `AUDIT_LOG_PATH` | No | `app/audit/data/audit_log.jsonl` | Audit JSONL location |
