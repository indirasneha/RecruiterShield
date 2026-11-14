"""Before/after evaluation for the fixed Phase 6 corpora; never trains or tunes."""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app, _request_times, _request_times_lock  # noqa: E402
from app.ml.model import LABELS, default_model_path  # noqa: E402
from app.services.analyzer import _load_model, _risk_from_hybrid, analyze_message  # noqa: E402
from app.services.signals import detect_signals, is_benign_recruitment_context  # noqa: E402

DATASETS = {
    "original_heldout": (ROOT / "data" / "test.csv", "label", None),
    "phase3_challenge": (ROOT / "data" / "adversarial_challenge.csv", "risk_label", "truth"),
    "redteam": (ROOT / "data" / "redteam" / "messages.csv", "true_label", "category"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def metrics(actual: list[str], predicted: list[str], records: list[dict[str, str]], group_key: str | None) -> dict:
    precision, recall, f1, support = precision_recall_fscore_support(actual, predicted, labels=LABELS, zero_division=0)
    macro = precision_recall_fscore_support(actual, predicted, labels=LABELS, average="macro", zero_division=0)
    actual_positive = [value != "LOW" for value in actual]
    predicted_positive = [value != "LOW" for value in predicted]
    tn = sum(not a and not p for a, p in zip(actual_positive, predicted_positive))
    fp = sum(not a and p for a, p in zip(actual_positive, predicted_positive))
    fn = sum(a and not p for a, p in zip(actual_positive, predicted_positive))
    tp = sum(a and p for a, p in zip(actual_positive, predicted_positive))
    high_downgraded = sum(a == "HIGH" and p != "HIGH" for a, p in zip(actual, predicted))
    legitimate_high = sum(a == "LOW" and p == "HIGH" for a, p in zip(actual, predicted))
    details = {
        label: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]), "support": int(support[i])}
        for i, label in enumerate(LABELS)
    }
    result = {
        "examples": len(actual),
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_precision": float(macro[0]),
        "macro_recall": float(macro[1]),
        "macro_f1": float(macro[2]),
        "per_class": details,
        "labels_order": list(LABELS),
        "confusion_matrix_rows_actual_columns_predicted": confusion_matrix(actual, predicted, labels=LABELS).tolist(),
        "binary_risk_screen": {
            "positive_definition": "MEDIUM or HIGH; negative is LOW",
            "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
            "false_negative_rate": fn / (fn + tp) if fn + tp else 0.0,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "high_label_downgraded_to_low_or_medium": high_downgraded,
        "LOW_label_incorrectly_classified_HIGH": legitimate_high,
    }
    if group_key:
        fraud_mask = [
            (record.get(group_key, "") == "FRAUDULENT")
            if group_key == "truth" else
            (record.get("category", "") in {"identity_harvesting", "indirect_financial_scam"})
            for record in records
        ]
        result["fraudulent_message_downgrades"] = sum(is_fraud and pred != "HIGH" for is_fraud, pred in zip(fraud_mask, predicted))
        result["legitimate_message_classified_HIGH"] = sum(record.get(group_key) == "LEGITIMATE" and pred == "HIGH" for record, pred in zip(records, predicted)) if group_key == "truth" else None
    return result


def aggregation_reason(message: str, predicted: str, signals) -> tuple[str, str]:
    active = [signal for signal in signals if signal.severity > 0]
    benign = is_benign_recruitment_context(message)
    if any(signal.severity == 2 and signal.category != "Identity document request" for signal in active):
        return "HIGH", "direct severity-2 money/financial/credential signal takes precedence"
    if any(signal.category == "Identity document request" for signal in active):
        if len(active) >= 2:
            return "HIGH", "identity request plus another active contextual signal"
        return "MEDIUM", "single identity-document request is capped at MEDIUM"
    if len(active) >= 2:
        return "HIGH", "two or more active caution signals"
    if active:
        return "MEDIUM", "one active caution signal"
    if benign or any(signal.severity == 0 for signal in signals):
        return "LOW", "broad benign-context or severity-zero override suppresses model-only risk"
    if predicted in {"MEDIUM", "HIGH"}:
        return "MEDIUM", "unsupported model HIGH is softened to MEDIUM"
    return "LOW", "no active signal and model predicted LOW"


def evaluate(tag: str) -> dict:
    model = _load_model(str(default_model_path()))
    if model is None:
        raise RuntimeError("Trained model is unavailable; refusing to report fallback output as classifier evaluation.")
    client = TestClient(app)
    output: dict = {
        "tag": tag,
        "training_or_threshold_tuning_performed": False,
        "model_artifact": str(default_model_path().relative_to(ROOT)),
        "label_order": list(LABELS),
        "datasets": {},
        "redteam_high_downgrade_traces": [],
    }
    for dataset_name, (path, label_key, group_key) in DATASETS.items():
        records = read_csv(path)
        actual = [record[label_key] for record in records]
        texts = [record["text"] for record in records]
        classifier_predictions = [str(label) for label in model.predict(texts)]
        api_results = []
        for text in texts:
            with _request_times_lock:
                _request_times.clear()
            response = client.post("/api/analyze/message", json={"text": text})
            if response.status_code != 200:
                raise RuntimeError(f"API failed with status {response.status_code} for {dataset_name}.")
            api_results.append(response.json())
        api_predictions = [result["risk_level"] for result in api_results]
        output["datasets"][dataset_name] = {
            "source": str(path.relative_to(ROOT)),
            "classifier_only": metrics(actual, classifier_predictions, records, group_key),
            "complete_api_pipeline": metrics(actual, api_predictions, records, group_key),
            "analysis_type_values": sorted({item["analysis_type"] for item in api_results}),
        }

        if dataset_name == "redteam" and tag == "before":
            for record, ml_prediction, result in zip(records, classifier_predictions, api_results):
                if record[label_key] != "HIGH" or result["risk_level"] == "HIGH":
                    continue
                signals = detect_signals(record["text"])
                context_only = _risk_from_hybrid("LOW", signals, is_benign_recruitment_context(record["text"]))
                rule_result, reason = aggregation_reason(record["text"], ml_prediction, signals)
                output["redteam_high_downgrade_traces"].append({
                    "id": record["id"],
                    "pattern": record["pattern"],
                    "message": record["text"],
                    "expected_label": record[label_key],
                    "ml_prediction": ml_prediction,
                    "contextual_signals": [
                        {"category": signal.category, "severity": signal.severity, "evidence": signal.evidence, "explanation": signal.explanation}
                        for signal in signals
                    ],
                    "benign_context_detected": is_benign_recruitment_context(record["text"]),
                    "context_only_risk_before_combination": context_only.value,
                    "hybrid_risk_after_aggregation": result["risk_level"],
                    "aggregation_rule": reason,
                    "why_different_from_expected": (
                        f"Expected {record[label_key]}, but ML predicted {ml_prediction} and contextual aggregation returned {result['risk_level']}. "
                        f"Rule path: {reason}."
                    ),
                })

    if tag == "before" and len(output["redteam_high_downgrade_traces"]) != 38:
        raise RuntimeError(f"Expected 38 HIGH downgrades from the Phase 6A baseline; found {len(output['redteam_high_downgrade_traces'])}.")
    output_path = ROOT / "data" / "redteam" / f"phase6_{tag}.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", choices=("before", "after"), required=True)
    args = parser.parse_args()
    report = evaluate(args.tag)
    for dataset, stats in report["datasets"].items():
        print(f"{dataset}: API accuracy={stats['complete_api_pipeline']['accuracy']:.3f}; "
              f"macro-F1={stats['complete_api_pipeline']['macro_f1']:.3f}; "
              f"FNR={stats['complete_api_pipeline']['binary_risk_screen']['false_negative_rate']:.3f}; "
              f"HIGH downgraded={stats['complete_api_pipeline']['high_label_downgraded_to_low_or_medium']}")
        print("  API confusion matrix:", stats["complete_api_pipeline"]["confusion_matrix_rows_actual_columns_predicted"])
    print(f"Report: data/redteam/phase6_{args.tag}.json")


if __name__ == "__main__":
    main()
