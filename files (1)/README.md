# Support Triage OpenEnv

A customer-support triage reinforcement-learning environment following the [OpenEnv](https://huggingface.co/openenv) specification.

The agent reads support tickets and must:
- classify urgency (`low` / `medium` / `high`)
- route to the correct team
- request clarification when needed
- produce a short, policy-safe resolution response

---

## Tasks

| ID | Description | Correct team | Urgency | Clarification? |
|----|-------------|-------------|---------|----------------|
| `easy` | Password reset, clean ticket | `account_support` | `low` | No |
| `medium` | Double-charge complaint, missing invoice numbers | `billing` | `medium` | Yes |
| `hard` | Enterprise: security breach + billing anomaly + policy violation | `trust_safety` | `high` | No |

---

## Reward breakdown (per step, sum capped at 1.0)

| Criterion | Points |
|-----------|--------|
| Correct team | +0.20 |
| Correct urgency | +0.20 |
| Clarification behaviour matches task | +0.20 |
| Response contains required keywords | +0.20 |
| Response is 10–300 chars | +0.20 |

---

## Local development

### 1. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn app:app --reload --port 7860
```

### 3. Run the validator

```bash
python tests/validate_local.py
```

### 4. Run the agent baseline

```bash
cp .env.example .env   # fill in your values
export $(cat .env | xargs)
python inference.py
```

---

## Docker

```bash
docker build -t support-triage-openenv .
docker run -p 7860:7860 support-triage-openenv
```

---

## Hugging Face Space deployment

1. Create a new **Docker Space** on Hugging Face.
2. Push this repository to the Space.
3. Set the following **Space secrets**:
   - `API_BASE_URL`
   - `MODEL_NAME`
   - `HF_TOKEN`
4. The Space will auto-build and expose the environment at `https://<your-space>.hf.space`.

---

## API reference

### `POST /reset`

```json
{ "task_id": "easy" }
```

Returns `StepResponse` with initial observation.

### `POST /step`

```json
{
  "chosen_team": "account_support",
  "urgency": "low",
  "ask_clarification": false,
  "response_text": "We will reset your password shortly."
}
```

Returns `StepResponse` with reward and done flag.

### `GET /state`

Returns current `TicketState`.

---

## File structure

```
support-triage-openenv/
├── openenv.yaml       # OpenEnv manifest
├── inference.py       # Agent baseline script
├── README.md
├── requirements.txt
├── .env.example
├── models.py          # Pydantic models (Action / Observation / State)
├── graders.py         # Rule-based graders → 0.0–1.0
├── tasks.py           # Task definitions
├── app.py             # FastAPI server
├── environment.py     # Core env logic (reset / step / state)
├── Dockerfile
└── tests/
    └── validate_local.py
```
