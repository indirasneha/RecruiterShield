"""Reproducible text model: word and character TF-IDF with balanced logistic regression."""

from pathlib import Path

LABELS = ("LOW", "MEDIUM", "HIGH")


def build_pipeline():
    # Import only for model training so the API can use its explicit fallback
    # when the classifier dependency or saved artifact is unavailable.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=50_000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True, max_features=60_000)),
    ])
    classifier = LogisticRegression(class_weight="balanced", max_iter=2_000, random_state=2026)
    return Pipeline([("features", features), ("classifier", classifier)])


def default_model_path() -> Path:
    return Path(__file__).resolve().parent / "artifacts" / "recruitment_classifier.joblib"
