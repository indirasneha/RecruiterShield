from collections import Counter

from scripts.evaluate_redteam import (
    DATASET,
    EXPECTED_CATEGORY_COUNTS,
    SOURCE_DATASETS,
    read_rows,
    validate_dataset,
    validate_independent_of_existing,
)


def test_redteam_dataset_has_all_four_balanced_synthetic_categories():
    rows = read_rows(DATASET)
    validate_dataset(rows)
    assert len(rows) == 100
    assert Counter(row["category"] for row in rows) == EXPECTED_CATEGORY_COUNTS
    assert Counter(row["true_label"] for row in rows) == Counter({"HIGH": 45, "MEDIUM": 30, "LOW": 25})
    assert all(row["text"].strip() and row["expected_reason"].strip() for row in rows)


def test_redteam_corpus_is_exactly_independent_of_existing_splits_and_challenge():
    rows = read_rows(DATASET)
    validate_independent_of_existing(rows)
    redteam_text = {" ".join(row["text"].casefold().split()) for row in rows}
    for path in SOURCE_DATASETS:
        old_text = {" ".join(row.get("text", "").casefold().split()) for row in read_rows(path)}
        assert redteam_text.isdisjoint(old_text), path.name


def test_risk_labels_match_the_intended_redteam_scenario_groups():
    rows = read_rows(DATASET)
    assert all(row["true_label"] == "HIGH" for row in rows if row["category"] == "indirect_financial_scam")
    assert [row["true_label"] for row in rows if row["category"] == "identity_harvesting"].count("MEDIUM") == 5
    assert all(row["true_label"] == "LOW" for row in rows if row["category"] == "legitimate_suspicious")
    assert all(row["true_label"] == "MEDIUM" for row in rows if row["category"] == "ambiguous")
