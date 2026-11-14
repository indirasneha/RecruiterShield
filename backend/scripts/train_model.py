"""Fit on train.csv once, score the untouched held-out test.csv, and persist artifacts."""

import csv
import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import joblib
import sklearn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.ml.model import LABELS, build_pipeline, default_model_path  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    train = read_csv(ROOT / "data" / "train.csv")
    test = read_csv(ROOT / "data" / "test.csv")
    if not train or not test:
        raise SystemExit("Training or held-out data is empty. Run generate_synthetic_data.py first.")
    train_families = {row["family"] for row in train}
    test_families = {row["family"] for row in test}
    if train_families & test_families:
        raise SystemExit("A scenario family appears in both splits; refusing to evaluate leaked data.")
    train_texts = {" ".join(row["text"].casefold().split()) for row in train}
    test_texts = {" ".join(row["text"].casefold().split()) for row in test}
    if train_texts & test_texts:
        raise SystemExit("An exact message duplicate crosses the split boundary.")
    near_duplicate = next((
        (left["family"], right["family"])
        for left in train for right in test
        if SequenceMatcher(None, " ".join(left["text"].casefold().split()),
                           " ".join(right["text"].casefold().split())).ratio() >= 0.82
    ), None)
    if near_duplicate:
        raise SystemExit(f"Near-duplicate scenario crosses split boundary (similarity >= .82): {near_duplicate}")
    if set(row["label"] for row in train) != set(LABELS) or set(row["label"] for row in test) != set(LABELS):
        raise SystemExit("Each split must include all three risk labels.")

    model = build_pipeline()
    model.fit([row["text"] for row in train], [row["label"] for row in train])
    actual = [row["label"] for row in test]
    predicted = model.predict([row["text"] for row in test]).tolist()
    precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, labels=LABELS, average="macro", zero_division=0)
    matrix = confusion_matrix(actual, predicted, labels=LABELS)

    # For attack screening, LOW is the non-risk class; MEDIUM/HIGH are risk-positive.
    binary_actual = [label != "LOW" for label in actual]
    binary_predicted = [label != "LOW" for label in predicted]
    false_positives = sum(not expected and found for expected, found in zip(binary_actual, binary_predicted))
    false_negatives = sum(expected and not found for expected, found in zip(binary_actual, binary_predicted))
    report = {
        "model": "word+character TF-IDF / balanced LogisticRegression",
        "sklearn_version": sklearn.__version__,
        "train_size": len(train),
        "heldout_size": len(test),
        "train_class_counts": dict(Counter(row["label"] for row in train)),
        "heldout_class_counts": dict(Counter(row["label"] for row in test)),
        "heldout_accuracy": accuracy_score(actual, predicted),
        "heldout_macro_precision": precision,
        "heldout_macro_recall": recall,
        "heldout_macro_f1": f1,
        "confusion_matrix_labels_order": list(LABELS),
        "confusion_matrix_rows_actual_columns_predicted": matrix.tolist(),
        "classification_report": classification_report(actual, predicted, labels=LABELS, output_dict=True, zero_division=0),
        "binary_risk_screening": {
            "positive_definition": "MEDIUM or HIGH",
            "negative_definition": "LOW",
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        },
        "split_method": "Deterministic scenario-family split: 8 of 12 families per class for training, 4 held out; exact duplicates, shared families, and text pairs with SequenceMatcher similarity >= .82 are rejected across splits.",
        "probabilities_used_for_decision": False,
    }
    model_path = default_model_path()
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path, compress=3)
    metrics_path = ROOT / "data" / "evaluation.json"
    metrics_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Model saved: {model_path}")
    print(f"Evaluation saved: {metrics_path}")
    print(json.dumps({key: report[key] for key in (
        "train_size", "heldout_size", "train_class_counts", "heldout_class_counts",
        "heldout_accuracy", "heldout_macro_precision", "heldout_macro_recall", "heldout_macro_f1",
        "confusion_matrix_labels_order", "confusion_matrix_rows_actual_columns_predicted", "binary_risk_screening",
    )}, indent=2))


if __name__ == "__main__":
    main()
