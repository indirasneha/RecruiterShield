"""Evaluate the API's hybrid decisions on fixed validation/held-out/challenge sets."""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support  # noqa: E402
from app.ml.model import LABELS  # noqa: E402
from app.services.analyzer import analyze_message  # noqa: E402


def read_csv(filename: str) -> list[dict[str, str]]:
    with (ROOT / "data" / filename).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def multiclass(actual: list[str], predicted: list[str]) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, labels=LABELS, average="macro", zero_division=0)
    return {
        "examples": len(actual),
        "accuracy": accuracy_score(actual, predicted),
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": f1,
        "labels_order": list(LABELS),
        "confusion_matrix_rows_actual_columns_predicted": confusion_matrix(actual, predicted, labels=LABELS).tolist(),
    }


def binary(actual: list[bool], predicted: list[bool]) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, average="binary", zero_division=0)
    false_positives = sum((not truth) and guess for truth, guess in zip(actual, predicted))
    false_negatives = sum(truth and (not guess) for truth, guess in zip(actual, predicted))
    negatives = sum(not truth for truth in actual)
    positives = sum(actual)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positives": false_positives,
        "false_positive_rate": false_positives / negatives if negatives else 0,
        "false_negatives": false_negatives,
        "false_negative_rate": false_negatives / positives if positives else 0,
        "confusion_matrix_rows_actual_negative_positive_columns_predicted_negative_positive": confusion_matrix(actual, predicted, labels=[False, True]).tolist(),
    }


def run() -> dict:
    heldout = read_csv("test.csv")
    challenge = read_csv("adversarial_challenge.csv")
    validation = read_csv("validation.csv")
    heldout_predictions = [analyze_message(row["text"]) for row in heldout]
    challenge_predictions = [analyze_message(row["text"]) for row in challenge]
    validation_predictions = [analyze_message(row["text"]) for row in validation]
    challenge_is_attack = [row["truth"] == "FRAUDULENT" for row in challenge]
    challenge_is_risky = [pred.risk_level.value != "LOW" for pred in challenge_predictions]
    legitimate_high = sum(row["truth"] == "LEGITIMATE" and pred.risk_level.value == "HIGH" for row, pred in zip(challenge, challenge_predictions))
    report = {
        "engine_indicators": sorted({prediction.analysis_type for prediction in heldout_predictions + challenge_predictions}),
        "original_heldout": {
            "three_class": multiclass([row["label"] for row in heldout], [pred.risk_level.value for pred in heldout_predictions]),
            "binary_risk_screen": binary([row["label"] != "LOW" for row in heldout], [pred.risk_level.value != "LOW" for pred in heldout_predictions]),
        },
        "adversarial_challenge": {
            "examples": len(challenge),
            "legitimate_examples": sum(row["truth"] == "LEGITIMATE" for row in challenge),
            "fraudulent_examples": sum(row["truth"] == "FRAUDULENT" for row in challenge),
            "risk_level_three_class": multiclass([row["risk_label"] for row in challenge], [pred.risk_level.value for pred in challenge_predictions]),
            "legitimate_vs_fraud_binary": binary(challenge_is_attack, challenge_is_risky),
            "legitimate_high_risk_false_positives": legitimate_high,
        },
        "separate_validation": multiclass([row["risk_label"] for row in validation], [pred.risk_level.value for pred in validation_predictions]),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", choices=("before", "after"), required=True)
    args = parser.parse_args()
    report = run()
    output = ROOT / "data" / f"phase3_{args.tag}.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
