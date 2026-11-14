"""Score the frozen red-team corpus with the current classifier and API pipeline."""

import csv
import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from fastapi.testclient import TestClient
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app, _request_times, _request_times_lock  # noqa: E402
from app.ml.model import LABELS, default_model_path  # noqa: E402
from app.services.analyzer import _load_model  # noqa: E402

DATASET = ROOT / "data" / "redteam" / "messages.csv"
RESULTS = ROOT / "data" / "redteam" / "results.json"
SOURCE_DATASETS = (
    ROOT / "data" / "train.csv",
    ROOT / "data" / "test.csv",
    ROOT / "data" / "validation.csv",
    ROOT / "data" / "adversarial_challenge.csv",
)
EXPECTED_CATEGORY_COUNTS = {
    "identity_harvesting": 25,
    "indirect_financial_scam": 25,
    "legitimate_suspicious": 25,
    "ambiguous": 25,
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def near_duplicate(left: str, right: str) -> bool:
    if left == right:
        return True
    if 2 * min(len(left), len(right)) / max(1, len(left) + len(right)) < 0.82:
        return False
    left_words, right_words = set(left.split()), set(right.split())
    if left_words and right_words and len(left_words & right_words) / len(left_words | right_words) < 0.62:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.82


def validate_dataset(rows: list[dict[str, str]]) -> None:
    if len(rows) != 100:
        raise ValueError(f"Red-team corpus must contain exactly 100 records; found {len(rows)}.")
    counts = Counter(row["category"] for row in rows)
    if counts != EXPECTED_CATEGORY_COUNTS:
        raise ValueError(f"Expected 25 records per category; got {dict(counts)}.")
    if any(row["true_label"] not in LABELS for row in rows):
        raise ValueError("Every record must have a LOW, MEDIUM, or HIGH true_label.")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Red-team example IDs must be unique.")
    texts = [normalized(row["text"]) for row in rows]
    if len(set(texts)) != len(texts):
        raise ValueError("Red-team messages contain exact duplicates.")
    for index, left in enumerate(texts):
        for right in texts[index + 1:]:
            if near_duplicate(left, right):
                raise ValueError("Red-team messages contain a near-duplicate pair (similarity >= .82).")


def validate_independent_of_existing(rows: list[dict[str, str]]) -> None:
    corpus = [normalized(row["text"]) for row in rows]
    for path in SOURCE_DATASETS:
        for old_row in read_rows(path):
            old_text = normalized(old_row.get("text", ""))
            if old_text and any(near_duplicate(old_text, text) for text in corpus):
                raise ValueError(f"Red-team example duplicates or closely paraphrases an existing record in {path.name}.")


def class_metrics(actual: list[str], predicted: list[str]) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(
        actual, predicted, labels=LABELS, zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        actual, predicted, labels=LABELS, average="macro", zero_division=0,
    )
    per_class = {
        label: {
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1": float(f1[index]),
            "support": int(support[index]),
        }
        for index, label in enumerate(LABELS)
    }
    return {
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "labels_order": list(LABELS),
        "per_class": per_class,
        "confusion_matrix_rows_actual_columns_predicted": confusion_matrix(actual, predicted, labels=LABELS).tolist(),
    }


def binary_risk_metrics(actual: list[str], predicted: list[str]) -> dict:
    actual_positive = [label != "LOW" for label in actual]
    predicted_positive = [label != "LOW" for label in predicted]
    tp = sum(a and p for a, p in zip(actual_positive, predicted_positive))
    fp = sum((not a) and p for a, p in zip(actual_positive, predicted_positive))
    fn = sum(a and (not p) for a, p in zip(actual_positive, predicted_positive))
    tn = sum((not a) and (not p) for a, p in zip(actual_positive, predicted_positive))
    return {
        "positive_definition": "MEDIUM or HIGH risk; negative definition: LOW",
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_negative_rate": fn / (fn + tp) if fn + tp else 0.0,
        "false_positives": fp,
        "false_negatives": fn,
        "confusion_matrix_rows_actual_negative_positive_columns_predicted_negative_positive": [[tn, fp], [fn, tp]],
    }


def pattern_counts(rows: list[dict[str, str]], predictions: list[str], predicate) -> list[dict[str, object]]:
    counts: Counter[str] = Counter(
        row["pattern"] for row, predicted in zip(rows, predictions) if predicate(row, predicted)
    )
    return [{"pattern": pattern, "count": count} for pattern, count in counts.most_common()]


def evaluate() -> dict:
    rows = read_rows(DATASET)
    validate_dataset(rows)
    validate_independent_of_existing(rows)
    model = _load_model(str(default_model_path()))
    if model is None:
        raise RuntimeError("The trained classifier artifact is missing or could not be loaded; refusing to label fallback output as ML evaluation.")

    texts = [row["text"] for row in rows]
    model_predictions = [str(label) for label in model.predict(texts)]
    client = TestClient(app)
    api_results = []
    for row in rows:
        # This evaluation isolates detector decisions from the process-local
        # abuse throttle; the API endpoint, schema validation, and response
        # serialization still run for each example.
        with _request_times_lock:
            _request_times.clear()
        response = client.post("/api/analyze/message", json={"text": row["text"]})
        if response.status_code != 200:
            raise RuntimeError(f"API returned {response.status_code} for {row['id']}; cannot complete evaluation.")
        result = response.json()
        if result.get("analysis_type") != "ai_hybrid":
            raise RuntimeError(f"API used {result.get('analysis_type')} on {row['id']}; expected the trained hybrid pipeline.")
        api_results.append(result)

    actual = [row["true_label"] for row in rows]
    api_predictions = [result["risk_level"] for result in api_results]
    missed_scam = lambda row, prediction: row["category"] in {"identity_harvesting", "indirect_financial_scam"} and prediction == "LOW"
    high_risk_undercall = lambda row, prediction: row["true_label"] == "HIGH" and prediction != "HIGH"
    false_alarm = lambda row, prediction: row["category"] == "legitimate_suspicious" and prediction != "LOW"

    examples = []
    for row, model_prediction, result in zip(rows, model_predictions, api_results):
        findings = result.get("findings", [])
        examples.append({
            "id": row["id"],
            "category": row["category"],
            "pattern": row["pattern"],
            "text": row["text"],
            "expected_label": row["true_label"],
            "expected_reason": row["expected_reason"],
            "classifier_prediction": model_prediction,
            "classifier_correct": model_prediction == row["true_label"],
            "api_prediction": result["risk_level"],
            "api_correct": result["risk_level"] == row["true_label"],
            "api_analysis_type": result["analysis_type"],
            "api_findings": [
                {"category": finding["category"], "explanation": finding["explanation"], "evidence": finding["evidence"]}
                for finding in findings
            ],
            "api_explanation": (
                "; ".join(finding["explanation"] for finding in findings)
                if findings else "No explicit contextual finding was returned; review the expected scenario rationale and verify independently."
            ),
        })

    category_evaluation = {}
    for category in EXPECTED_CATEGORY_COUNTS:
        indices = [index for index, row in enumerate(rows) if row["category"] == category]
        category_evaluation[category] = {
            "examples": len(indices),
            "api_predictions": dict(Counter(api_predictions[index] for index in indices)),
            "api_correct": sum(api_predictions[index] == actual[index] for index in indices),
            "classifier_predictions": dict(Counter(model_predictions[index] for index in indices)),
            "classifier_correct": sum(model_predictions[index] == actual[index] for index in indices),
        }

    result = {
        "dataset": "backend/data/redteam/messages.csv",
        "dataset_size": len(rows),
        "dataset_category_counts": dict(Counter(row["category"] for row in rows)),
        "true_label_counts": dict(Counter(actual)),
        "training_or_tuning_performed": False,
        "original_datasets_modified": False,
        "model_artifact": str(default_model_path().relative_to(ROOT)),
        "analysis_type_observed": sorted({item["api_analysis_type"] for item in examples}),
        "label_order": list(LABELS),
        "classifier_only": {
            "three_class": class_metrics(actual, model_predictions),
            "binary_risk_screen": binary_risk_metrics(actual, model_predictions),
        },
        "complete_api_pipeline": {
            "three_class": class_metrics(actual, api_predictions),
            "binary_risk_screen": binary_risk_metrics(actual, api_predictions),
        },
        "category_breakdown": category_evaluation,
        "missed_scam_patterns": {
            "classifier_only": pattern_counts(rows, model_predictions, missed_scam),
            "complete_api_pipeline": pattern_counts(rows, api_predictions, missed_scam),
        },
        "high_risk_scam_undercall_patterns": {
            "definition": "HIGH ground-truth examples predicted MEDIUM or LOW; these are class downgrades, not necessarily LOW-risk-screen false negatives.",
            "classifier_only": pattern_counts(rows, model_predictions, high_risk_undercall),
            "complete_api_pipeline": pattern_counts(rows, api_predictions, high_risk_undercall),
        },
        "legitimate_false_alarm_patterns": {
            "classifier_only": pattern_counts(rows, model_predictions, false_alarm),
            "complete_api_pipeline": pattern_counts(rows, api_predictions, false_alarm),
        },
        "examples": examples,
        "limitations": [
            "All messages and labels are synthetic; these scores are not estimates of real-world performance.",
            "The four scenario categories are balanced, but true risk labels are not class-balanced by design.",
            "API decisions share the same saved classifier artifact as the classifier-only evaluation; only the contextual decision layer differs.",
            "The local request throttle is cleared between TestClient requests so the report measures detection rather than per-client abuse controls.",
        ],
    }
    RESULTS.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    result = evaluate()
    for pipeline in ("classifier_only", "complete_api_pipeline"):
        metrics = result[pipeline]
        print(f"{pipeline}: macro_f1={metrics['three_class']['macro_f1']:.3f}; "
              f"FPR={metrics['binary_risk_screen']['false_positive_rate']:.3f}; "
              f"FNR={metrics['binary_risk_screen']['false_negative_rate']:.3f}")
        print("  confusion matrix:", metrics["three_class"]["confusion_matrix_rows_actual_columns_predicted"])
    print(f"Results saved: {RESULTS}")


if __name__ == "__main__":
    main()
