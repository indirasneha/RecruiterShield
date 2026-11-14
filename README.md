# RecruiterShield

RecruiterShield helps students assess recruitment messages for identity harvesting and recruitment fraud. Built for AI-FEST 2026 at Mahindra University by **VALIANT ALCHEMIST**.

The message endpoint combines a word and character n-gram TF-IDF classifier with explainable context checks for identity documents, financial details, candidate fees, credentials, artificial urgency, coercion, secrecy, and unusual selection claims. It returns LOW/MEDIUM/HIGH categories with message evidence and actions. It never returns an uncalibrated probability or claims to verify a recruiter. If the trained model is missing or cannot load, the endpoint returns `analysis_type: "baseline_fallback"` and says so in the disclaimer.

## Project structure

```text
frontend/                 Next.js, TypeScript, Tailwind CSS dashboard
  app/                    Responsive dashboard and styles
  lib/api.ts              Typed API client
backend/
  app/main.py             FastAPI app, health and analysis routes, CORS
  app/api/schemas.py      Pydantic request and response models
  app/services/analyzer.py Hybrid decision, evidence and explicit fallback
  app/services/document_analysis.py In-memory PDF extraction and page-aware findings
  app/services/signals.py  Contextual request and coercion indicators
  app/ml/model.py          Word/character TF-IDF and balanced logistic regression
  scripts/generate_synthetic_data.py  Synthetic, family-disjoint split generator
  scripts/train_model.py              Train and held-out evaluation
  scripts/prepare_phase3_eval_sets.py Independent validation/challenge corpus
  scripts/evaluate_phase3.py           Before/after hybrid evaluation
  data/train.csv, test.csv            Stratified synthetic data (120 / 60)
  data/validation.csv                  Separate 30-message rule-validation set
  data/adversarial_challenge.csv       60-message frozen challenge set
  data/evaluation.json                 Classifier-only held-out metrics
  data/phase3_before.json, phase3_after.json  Hybrid before/after metrics
  tests/test_api.py                     API and detection tests
```

## Requirements

- Node.js 20.9 or newer and npm
- Python 3.10 or newer

## Run the backend (Windows PowerShell)

```powershell
cd D:\RecruiterShield\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again. Alternatively, use `.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` without activation.

Health check: `http://127.0.0.1:8000/api/health`. Interactive API docs: `http://127.0.0.1:8000/docs`.

## Run the frontend (second PowerShell window)

```powershell
cd D:\RecruiterShield\frontend
npm.cmd install
Copy-Item .env.example .env.local
npm.cmd run dev
```

Open `http://localhost:3000`. The frontend API URL defaults to `http://localhost:8000`; configure `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` to change it. Backend `CORS_ORIGINS` accepts a comma-separated list and defaults to `http://localhost:3000`.

## Train and evaluate the message model

After installing backend requirements, run from `backend`:

```powershell
python scripts\generate_synthetic_data.py
python scripts\train_model.py
```

The generator creates 180 entirely synthetic messages: 60 for each risk label. It keeps all five paraphrases of a scenario family in the same split; eight scenario families per label go to training and four are held out. It rejects exact duplicates, shared families, and cross-split text pairs with a `SequenceMatcher` similarity of 0.82 or greater. The resulting splits contain 120 training and 60 held-out messages with equal per-class counts. Training uses only `data/train.csv`; metrics are calculated once against `data/test.csv` and written to `data/evaluation.json`. The fitted pipeline is saved to `app/ml/artifacts/recruitment_classifier.joblib`. The fixed model seed, deterministic family allocation, and pinned scikit-learn/joblib versions make the training run reproducible.

## Phase 3 adversarial evaluation

The rule/model pipeline was evaluated before and after the contextual changes with the same saved classifier and the same original 60-message `test.csv`. That held-out set was not used to train or select the changes. A separate 33-message validation set (11 per class) was used for rule checks. The 60-message challenge set is separate from training, held-out and validation data; it has 30 legitimate messages and 30 fraudulent messages, including ordinary deadlines, resume/interview requests, post-offer secure documents/payroll, direct credential/payment requests, and multi-signal attacks. The generated before/after measurements are in `data/phase3_before.json` and `data/phase3_after.json`.

### Original held-out set: hybrid API decisions

| Metric | Before | After |
|---|---:|---:|
| Three-class accuracy | 0.817 | 0.733 |
| Macro precision | 0.819 | 0.762 |
| Macro recall | 0.817 | 0.733 |
| Macro F1 | 0.816 | 0.737 |
| Risk-screen false positives (LOW predicted MEDIUM/HIGH) | 4 / 20 (20%) | 3 / 20 (15%) |
| Risk-screen false negatives (MEDIUM/HIGH predicted LOW) | 2 / 40 (5%) | 5 / 40 (12.5%) |

After-change confusion matrix (rows actual, columns predicted; order LOW, MEDIUM, HIGH):

```text
             predicted
actual       LOW  MEDIUM  HIGH
LOW           17      3     0
MEDIUM         5     14     1
HIGH            0      7    13
```

The updated logic reduces held-out false positives by one, but also lowers exact three-class accuracy and misses three more risk-labeled messages in the binary screen. This is a real tradeoff, not an improvement on every metric.

### Independent adversarial challenge

Legitimate vs fraudulent is measured as binary screening, where MEDIUM/HIGH are risk-positive. The challenge risk labels also support a separate three-class confusion matrix.

| Metric | Before | After |
|---|---:|---:|
| Three-class accuracy | 0.767 | 0.817 |
| Macro precision | 0.779 | 0.814 |
| Macro recall | 0.822 | 0.789 |
| Macro F1 | 0.772 | 0.792 |
| Binary precision | 0.707 | 0.900 |
| Binary recall | 0.967 | 0.900 |
| Binary F1 | 0.817 | 0.900 |
| Legitimate false positives | 12 / 30 (40%) | 3 / 30 (10%) |
| Fraudulent false negatives | 1 / 30 (3.3%) | 3 / 30 (10%) |
| Legitimate messages labeled HIGH | 8 | 1 |

After-change challenge confusion matrix (rows actual, columns predicted; order LOW, MEDIUM, HIGH):

```text
             predicted
actual       LOW  MEDIUM  HIGH
LOW           27      2     1
MEDIUM         3     12     0
HIGH            0      5    10
```

The separate validation set scored 30/30 after the rules were adjusted. That is a small rule-check set and is not a generalization estimate. All measurements use synthetic text; neither set establishes real-world detection accuracy. The original held-out test remains unchanged and is not used for tuning.

## Tests and build

With the backend virtual environment active:

```powershell
cd D:\RecruiterShield\backend
python -m pytest -q
```

Frontend production build:

```powershell
cd D:\RecruiterShield\frontend
npm.cmd run build
```

Run frontend lint checks with `npm.cmd run lint` from `frontend`.

The API rejects blank messages, unexpected JSON fields, malformed JSON, and messages longer than 12,000 characters. The message request body is capped at 64 KiB and document uploads at 5 MiB; analysis endpoints have a process-local limit of 60 requests per minute per client address. This throttle is a local safeguard only: production deployments need shared rate limiting and request size/time limits at their trusted reverse proxy or gateway. The frontend and API do not persist submitted message text or log it. Input and results remain in request/browser memory for the active tab; the page clears them when it is refreshed or closed. Error responses do not include submitted input, and evidence redacts common identity numbers, long numeric identifiers, and email addresses. The `analysis_type` value is `ai_hybrid` when the trained classifier was loaded and used, and `baseline_fallback` otherwise.

## Privacy and limitations

- Do not paste passwords, one-time codes, or full identity document numbers. Remove personal contact details where practical.
- The engine can miss scams and flag harmless wording; LOW does not mean safe. Ordinary resume requests and interview scheduling are not high-risk signals by themselves.
- The classifier learns only from the included synthetic corpus, which cannot represent the full language and tactics used by real recruiters or scammers. Context rules are transparent heuristics and can miss paraphrases.
- No recruiter or company is represented as verified. Verify opportunities through independently located official company contact channels.
- Suspicious URLs are treated as plain text and are never visited by the service.
- PDF offer-letter analysis accepts raw `application/pdf` request bodies at `POST /api/analyze/document`. The service streams at most 5 MB into bounded memory, extracts text with pypdf, then passes that text through the same hybrid engine used for messages. It does not write the PDF or extracted text to disk, and it does not return the filename or full extracted text. Responses include page count, extraction status, and page numbers for matched evidence where available.
- PDFs must be text-based, unencrypted, readable, and no more than 100 pages. Scanned/image-only pages are rejected with an explanation because this release does not include OCR. PDFs over 80,000 extracted characters are rejected. Links are not opened; known shorteners and messaging links are flagged for independent review. Document claims and links are not authenticated.
- PDFs are parsed in memory with pypdf 7.1.0, limited to two concurrent parser jobs per worker, and are not saved as temporary files. These limits reduce resource use but do not provide process isolation; run document parsing behind a resource-limited worker/container for public production workloads.
- Synthetic PDF API fixtures cover legitimate offers, fee demands, identity and financial detail requests, OTP/password requests, ambiguous/inconsistent offers, empty/scanned, corrupt, encrypted, oversized, and unsupported uploads. Run them with the complete backend suite above.
- External LLM analysis is not part of this phase.

## PDF analysis demonstration

Start the backend and frontend using the commands above, open `http://localhost:3000`, then choose **Upload PDF** and select a text-based synthetic offer letter. A safe internship offer should produce a LOW review; a document requesting a registration fee, identity documents with bank details, or an OTP/password should show the corresponding findings and recommended actions. The result includes extraction metadata and page references when the evidence maps to a page. Try an image-only PDF to see the explicit unsupported-document message. No PDF is saved by the API.
