"""
Phase 4 tests — Module B supervised query classification.

Coverage required by the Phase 4 brief:
1. English queries.
2. Hindi queries.
3. All five pilot crops.
4. Ambiguous queries.
5. Unsupported queries.
6. Low-confidence fallback (abstain instead of guess).
7. API validation.
8. Model loading and prediction.
9. Existing knowledge-base safety restrictions remaining intact.

Plus two regression guards this project specifically needs:
- Devanagari text must survive preprocessing (a bug that silently shredded
  Hindi matras existed once; see `preprocessing.normalize_text`).
- Train/test splits must not share query text, and every label must appear in
  every split (otherwise an evaluation can silently skip a class).

Where a test asserts a *behaviour* (abstain, refuse, never map an unsupported
crop onto a pilot crop) it is a hard safety assertion. Where it asserts a
*label* for a specific phrasing it is a regression test against the committed
model artifact — a failure there means the model changed, and the expectation
should be re-derived, not silently relaxed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.classification import labels as L
from app.classification.model import (
    DEFAULT_ARTIFACT_PATH,
    ModelNotLoadedError,
    QueryClassifier,
)
from app.classification.preprocessing import (
    LANGUAGE_ENGLISH,
    LANGUAGE_HINGLISH,
    LANGUAGE_HINDI,
    detect_language,
    normalize_text,
)
from app.classification.schemas import MAX_QUERY_LENGTH, ClassifyRequest
from app.classification.service import (
    ClassifierUnavailableError,
    classify_query,
    get_classifier,
    reset_classifier_cache,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# 8. Model loading and prediction
# --------------------------------------------------------------------------


def test_committed_model_artifact_exists():
    """The runtime artifact must be committed, otherwise the API is dead on import."""
    assert DEFAULT_ARTIFACT_PATH.exists(), (
        f"Missing model artifact at {DEFAULT_ARTIFACT_PATH}. "
        f"Run 'python ml/classification/train_classifier.py'."
    )


def test_model_loads_and_is_fitted():
    classifier = QueryClassifier.load()
    assert classifier.is_fitted()
    assert classifier.model_version.startswith("clf-")
    assert set(classifier.heads) == set(L.TARGETS)


def test_model_artifact_label_space_matches_code():
    """A stale artifact trained on a different taxonomy must be rejected, not used."""
    classifier = QueryClassifier.load()
    payload_space = classifier.training_metadata.get("label_spaces")
    for target in L.TARGETS:
        head_classes = set(classifier.heads[target].named_steps["clf"].classes_)
        declared = set(
            {"crop": L.CROP_CLASSES, "task": L.TASK_CLASSES, "safety_topic": L.SAFETY_CLASSES}[
                target
            ]
        )
        assert head_classes <= declared, f"{target} head predicts undeclared labels"
        if payload_space:  # only present in newer artifacts
            assert set(payload_space[target]) == declared


def test_predict_all_returns_three_targets_with_confidence():
    classifier = QueryClassifier.load()
    predictions = classifier.predict_all("How do I control stem borer in paddy?")
    assert set(predictions) == set(L.TARGETS)
    for target, prediction in predictions.items():
        assert prediction.target == target
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.status


def test_loading_a_missing_artifact_raises_a_clear_error(tmp_path: Path):
    with pytest.raises(ModelNotLoadedError):
        QueryClassifier.load(tmp_path / "does_not_exist.joblib")


def test_loading_a_corrupt_artifact_raises_a_clear_error(tmp_path: Path):
    corrupt = tmp_path / "corrupt.joblib"
    corrupt.write_bytes(b"this is not a joblib artifact")
    with pytest.raises(ModelNotLoadedError):
        QueryClassifier.load(corrupt)


# --------------------------------------------------------------------------
# Preprocessing regression guards
# --------------------------------------------------------------------------


def test_devanagari_vowel_signs_survive_normalisation():
    """
    Regression: Python's `\\w` does not match Devanagari combining marks, so a
    naive `[^\\w\\s]` filter turns "धान" into "ध न" and destroys every Hindi
    word. Hindi classification accuracy depends on this staying fixed.
    """
    normalized = normalize_text("धान में तना छेदक")
    assert "धान" in normalized
    assert "में" in normalized
    assert "छेदक" in normalized
    # Must not be shredded into isolated consonants.
    assert len(normalized.split()) == 4


def test_normalisation_is_case_and_punctuation_insensitive():
    assert normalize_text("How much CHLORANTRANILIPROLE, per acre?!") == normalize_text(
        "how much chlorantraniliprole per acre"
    )


def test_language_detection_reports_script_and_romanised_hindi():
    assert detect_language("धान में कीट लगा है") == LANGUAGE_HINDI
    assert detect_language("dhan me keede lag gaye hain") == LANGUAGE_HINGLISH
    assert detect_language("how do I control aphids in wheat") == LANGUAGE_ENGLISH


# --------------------------------------------------------------------------
# 1 + 3. English queries across all five pilot crops
# --------------------------------------------------------------------------

ENGLISH_CROP_QUERIES = [
    ("My paddy crop is showing dead heart symptoms, which insect is responsible?", "rice"),
    ("Green aphids are sucking sap from my wheat crop, what should I do?", "wheat"),
    ("Fall armyworm caterpillars are inside the maize whorl", "maize"),
    ("Pink bollworm larvae found inside cotton bolls", "cotton"),
    ("Whiteflies are flying around my tomato plants", "tomato"),
]


@pytest.mark.parametrize("query,expected_crop", ENGLISH_CROP_QUERIES)
def test_english_query_never_confidently_mislabels_the_crop(query, expected_crop):
    """
    Contract: either the crop is right, or the system abstains.

    A confident wrong crop is the one failure mode that must never happen,
    because it would route the user to another crop's guidance. Abstaining is
    acceptable and is surfaced to the user as a clarifying question.
    """
    response = classify_query(query)
    assert response.detected_language == "en"
    if response.crop.label != expected_crop:
        assert response.crop.status != L.STATUS_CONFIDENT, (
            f"{query!r} confidently mislabelled as '{response.crop.label}' "
            f"(expected '{expected_crop}')"
        )
        assert response.requires_clarification is True


def test_english_crop_queries_are_answered_correctly():
    """Measured accuracy floor for clear English crop queries (currently 5/5)."""
    correct = sum(
        1
        for query, expected in ENGLISH_CROP_QUERIES
        if classify_query(query).crop.label == expected
    )
    assert correct >= 5, f"English crop identification regressed: {correct}/{len(ENGLISH_CROP_QUERIES)}"


# --------------------------------------------------------------------------
# 2. Hindi queries across all five pilot crops
# --------------------------------------------------------------------------

HINDI_CROP_QUERIES = [
    ("धान की फसल में तना छेदक कीट लगा है", "rice"),
    ("गेहूं में माहू कीट का प्रकोप है", "wheat"),
    ("मक्का में फॉल आर्मीवर्म सुंडी मिली है", "maize"),
    ("कपास के टिंडों में गुलाबी सुंडी है", "cotton"),
    ("टमाटर के पौधों पर सफेद मक्खी है", "tomato"),
]


@pytest.mark.parametrize("query,expected_crop", HINDI_CROP_QUERIES)
def test_hindi_query_never_confidently_mislabels_the_crop(query, expected_crop):
    response = classify_query(query)
    assert response.detected_language == "hi"
    if response.crop.label != expected_crop:
        assert response.crop.status != L.STATUS_CONFIDENT, (
            f"{query!r} confidently mislabelled as '{response.crop.label}' "
            f"(expected '{expected_crop}')"
        )
        assert response.requires_clarification is True


def test_hindi_crop_queries_are_answered_correctly():
    """
    Measured accuracy floor for Hindi crop queries.

    Currently 4/5: "धान की फसल में तना छेदक कीट लगा है" comes back as an
    abstention (`unsupported_crop` at 0.29 confidence) rather than `rice`. The
    limit is a genuine data-coverage weakness (Hindi rows are ~25% of the
    corpus) and is documented in the Phase 4 report rather than tuned away
    against the test set.
    """
    correct = sum(
        1
        for query, expected in HINDI_CROP_QUERIES
        if classify_query(query).crop.label == expected
    )
    assert correct >= 4, f"Hindi crop identification regressed: {correct}/{len(HINDI_CROP_QUERIES)}"


@pytest.mark.parametrize(
    "query,expected_crop",
    [
        ("dhan me keede lag gaye hain kya karun", "rice"),
        ("kapas me sundi lag gayi hai", "cotton"),
    ],
)
def test_romanised_hindi_query_predicts_the_right_crop(query, expected_crop):
    response = classify_query(query)
    assert response.detected_language == "hi-latn"
    assert response.crop.label == expected_crop


# --------------------------------------------------------------------------
# Safety-topic routing (English and Hindi)
# --------------------------------------------------------------------------


SAFETY_TOPIC_QUERIES = [
    ("What quantity of chlorantraniliprole per acre should I use in rice?", "dosage"),
    ("How long must I wait before harvesting paddy after the last spray?", "phi"),
    ("Is it safe to go back into the cotton field after spraying?", "rei"),
    ("Do I need gloves and a mask while mixing pesticide for tomato?", "ppe"),
    ("Is fipronil harmful to humans?", "toxicity"),
    ("Is chlorpyrifos banned in India?", "regulatory_approval"),
    ("How should I dispose of empty pesticide bottles?", "general_safety"),
    # "how many days before harvest should I stop the medicine"
    ("धान में कटाई से पहले कितने दिन दवा बंद करनी चाहिए", "phi"),
    # "when can we go into the field after spraying"
    ("गेहूं में छिड़काव के बाद खेत में कब जाया जा सकता है", "rei"),
]


@pytest.mark.parametrize("query,expected_topic", SAFETY_TOPIC_QUERIES)
def test_safety_topic_is_never_confidently_mislabelled(query, expected_topic):
    """
    Contract: correct label, or an explicit abstention.

    Mis-routing a PHI question to REI (or vice versa) would hand the user the
    wrong waiting period, so a *confident* wrong answer is the failure that
    matters. Abstaining is acceptable — the caller is asked which safety point
    they mean.
    """
    response = classify_query(query)
    result = response.safety_topic
    if result.label != expected_topic:
        assert result.status != L.STATUS_CONFIDENT, (
            f"{query!r} confidently mislabelled as '{result.label}' "
            f"(expected '{expected_topic}')"
        )
        assert response.requires_clarification is True


def test_safety_topic_queries_are_answered_correctly():
    """
    Measured accuracy floor across the safety-topic benchmark (currently 8/9;
    the miss is the PHI question phrased as "wait before harvesting … after the
    last spray", which abstains between PHI and REI).
    """
    correct = sum(
        1
        for query, expected in SAFETY_TOPIC_QUERIES
        if classify_query(query).safety_topic.label == expected
    )
    assert correct >= 8, f"Safety-topic routing regressed: {correct}/{len(SAFETY_TOPIC_QUERIES)}"


def test_hindi_safety_topic_queries_are_answered_correctly():
    """Both Hindi safety-topic probes (PHI and REI) must route correctly."""
    hindi = [(q, e) for q, e in SAFETY_TOPIC_QUERIES if detect_language(q) == LANGUAGE_HINDI]
    assert len(hindi) == 2
    for query, expected in hindi:
        assert classify_query(query).safety_topic.label == expected


TASK_QUERIES = [
    ("Which insect is making holes in my cotton bolls?", "pest_identification"),
    ("How do I control stem borer in paddy?", "pest_management"),
    ("What disease causes orange powder on wheat leaves?", "disease_management"),
    ("What is integrated pest management?", "general_guidance"),
    ("What is today's mandi price for cotton?", "out_of_scope"),
]


@pytest.mark.parametrize("query,expected_task", TASK_QUERIES)
def test_task_is_never_confidently_mislabelled(query, expected_task):
    response = classify_query(query)
    result = response.task
    if result.label != expected_task:
        assert result.status != L.STATUS_CONFIDENT, (
            f"{query!r} confidently mislabelled as '{result.label}' "
            f"(expected '{expected_task}')"
        )
        assert response.requires_clarification is True


def test_task_queries_are_answered_correctly():
    """
    Measured accuracy floor for task routing (currently 4/5).

    Task is the weakest of the three dimensions: the
    `product_information` / `pest_management` / `general_guidance` boundary is
    genuinely fine-grained, and `out_of_scope` has few examples. Documented in
    the Phase 4 report §Limitations.
    """
    correct = sum(
        1 for query, expected in TASK_QUERIES if classify_query(query).task.label == expected
    )
    assert correct >= 4, f"Task routing regressed: {correct}/{len(TASK_QUERIES)}"


# --------------------------------------------------------------------------
# 4. Ambiguous queries must abstain, not guess
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "Problem in my crop",
        "Is it safe?",
        "फसल में समस्या है",
        "Need help with spraying",
    ],
)
def test_ambiguous_query_requests_clarification(query):
    response = classify_query(query)
    assert response.requires_clarification is True
    assert response.clarification_message, "a clarification must come with a usable question"
    assert not response.unsupported


# --------------------------------------------------------------------------
# 6. Low-confidence fallback / undetermined input
# --------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["ok", "12345", "???"])
def test_too_short_query_is_undetermined_and_asks_for_detail(query):
    response = classify_query(query)
    for target in L.TARGETS:
        assert getattr(response, target).status == L.STATUS_UNDETERMINED
    assert response.requires_clarification is True
    assert response.clarification_message


def test_low_confidence_dimension_is_labelled_ambiguous_not_confident():
    """
    Any dimension whose confidence or margin fails the threshold must be
    reported as `ambiguous` — never as `confident`. Checked against the
    thresholds themselves so the rule is verified, not the model's luck.
    """
    response = classify_query("Problem in my crop")
    for target in L.TARGETS:
        result = getattr(response, target)
        if result.status == L.STATUS_CONFIDENT:
            assert result.confidence >= L.MIN_CONFIDENCE[target]
            assert result.margin >= L.MIN_MARGIN[target]


def test_clarification_message_language_follows_the_query_language():
    hindi = classify_query("फसल में समस्या है")
    english = classify_query("Problem in my crop")
    assert hindi.detected_language == "hi"
    assert any("\u0900" <= ch <= "\u097F" for ch in hindi.clarification_message or "")
    assert not any("\u0900" <= ch <= "\u097F" for ch in english.clarification_message or "")


# --------------------------------------------------------------------------
# 5. Unsupported queries must not be forced into a known category
# --------------------------------------------------------------------------

UNSUPPORTED_QUERIES = [
    "Sugarcane pygmy borer control measures",
    "Potato late blight spray schedule",
    "गन्ना में कीट लगा है",
    "aalu me jhulsa rog ka dawa",
]


@pytest.mark.parametrize("query", UNSUPPORTED_QUERIES)
def test_unsupported_crop_is_never_confidently_mapped_onto_a_pilot_crop(query):
    """
    The critical negative case: a crop outside the pilot scope must never be
    *acted on* as a pilot crop, because that would invite a recommendation for
    the wrong crop.

    The invariant is about confidence, not about the raw argmax: a bag-of-words
    model may well put a little more probability on `wheat` than on
    `unsupported_crop` for a sugarcane sentence, and that is acceptable only if
    the result is reported as uncertain and the user is asked. What must never
    happen is a *confident* pilot-crop label (or an answered query) for an
    out-of-scope crop.
    """
    response = classify_query(query)
    if response.crop.label in L.PILOT_CROPS:
        assert response.crop.status != L.STATUS_CONFIDENT, (
            f"{query!r} was confidently labelled pilot crop '{response.crop.label}' — "
            f"unsupported crops must never be coerced into a supported category."
        )
        assert response.requires_clarification is True, (
            f"{query!r} produced a pilot-crop label without asking the user."
        )
    assert response.requires_clarification or response.unsupported


def test_explicitly_recognised_unsupported_crop_sets_the_flag():
    response = classify_query("Sugarcane pygmy borer control measures")
    if response.crop.status == L.STATUS_UNSUPPORTED:
        assert response.unsupported is True
        assert response.scope_message
        assert response.requires_clarification is False


def test_out_of_scope_query_is_not_confidently_forced_into_an_in_scope_task():
    """
    A market-price question must never be confidently treated as pest advice.

    `out_of_scope` is the smallest task class (15 rows), so the model does not
    always recognise it — for "mandi price for cotton" it currently abstains
    instead. That is the acceptable fallback: abstaining keeps the user in a
    clarification loop rather than answering an agronomy question that was
    never asked. What must not happen is a confident in-scope task label.
    """
    response = classify_query("What is today's mandi price for cotton?")
    assert response.out_of_scope or response.task.status != L.STATUS_CONFIDENT, (
        f"out-of-scope query was confidently routed to '{response.task.label}'"
    )
    if response.out_of_scope:
        assert response.scope_message


# --------------------------------------------------------------------------
# Safety boundary: classification never approves anything
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "query",
    [
        "What is the dose of chlorantraniliprole for rice stem borer?",
        "How many days before harvest in paddy?",
        "Is fipronil approved for rice in India?",
    ],
)
def test_classification_never_approves_a_pesticide_recommendation(query):
    policy = classify_query(query).safety_policy
    assert policy.approves_pesticide_recommendation is False
    assert policy.can_override_educational_only_gate is False
    assert "EDUCATIONAL_ONLY" in policy.advisory_gate


# --------------------------------------------------------------------------
# 7. API validation and behaviour
# --------------------------------------------------------------------------


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_api_classify_returns_structured_output():
    resp = _client().post(
        "/classification/classify",
        json={"query": "How many days before harvest should I stop spraying in paddy?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "query",
        "detected_language",
        "crop",
        "task",
        "safety_topic",
        "requires_clarification",
        "model_version",
        "safety_policy",
    ):
        assert key in body, f"response is missing required field '{key}'"
    assert body["crop"]["label"] == "rice"
    assert body["safety_topic"]["label"] == "phi"
    assert body["safety_policy"]["approves_pesticide_recommendation"] is False


def test_api_model_info_exposes_taxonomy_and_thresholds():
    resp = _client().get("/classification/model-info")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["targets"]) == set(L.TARGETS)
    assert body["thresholds"]["crop"]["min_confidence"] == L.MIN_CONFIDENCE["crop"]
    assert "no dosage" in body["note"].lower() or "not approve" in body["note"].lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "x" * (MAX_QUERY_LENGTH + 1)},
        {},
        {"query": "valid query", "unexpected_field": 1},
    ],
)
def test_api_rejects_invalid_input(payload):
    assert _client().post("/classification/classify", json=payload).status_code == 422


def test_api_rejects_wrong_type():
    assert _client().post("/classification/classify", json={"query": 123}).status_code == 422


def test_api_returns_503_when_model_is_unavailable(monkeypatch, tmp_path: Path):
    """
    With no artifact, the endpoint must fail honestly with 503 — it must never
    fabricate a prediction to keep responding.
    """
    monkeypatch.setenv("CLASSIFIER_ARTIFACT_PATH", str(tmp_path / "missing.joblib"))
    reset_classifier_cache()
    try:
        resp = _client().post("/classification/classify", json={"query": "aphids on wheat"})
        assert resp.status_code == 503
        assert "not available" in resp.json()["error"]["message"].lower()
    finally:
        monkeypatch.delenv("CLASSIFIER_ARTIFACT_PATH")
        reset_classifier_cache()


def test_service_raises_classifier_unavailable_for_missing_artifact(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CLASSIFIER_ARTIFACT_PATH", str(tmp_path / "missing.joblib"))
    reset_classifier_cache()
    try:
        with pytest.raises(ClassifierUnavailableError):
            get_classifier()
    finally:
        monkeypatch.delenv("CLASSIFIER_ARTIFACT_PATH")
        reset_classifier_cache()


def test_request_schema_strips_surrounding_whitespace():
    assert ClassifyRequest(query="  rice pest  ").query == "rice pest"


def test_request_schema_rejects_blank_query():
    with pytest.raises(ValidationError):
        ClassifyRequest(query="   ")


# --------------------------------------------------------------------------
# Existing endpoints must keep working (no regression from Phase 4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/health", "/health/ready", "/health/db", "/health/pgvector", "/health/llm", "/knowledge-base/crops"],
)
def test_existing_endpoints_still_respond(path):
    assert _client().get(path).status_code == 200


# --------------------------------------------------------------------------
# 9. Phase 3.1 safety gating must remain intact
# --------------------------------------------------------------------------


def test_knowledge_base_records_are_still_educational_only():
    """Phase 4 must not have loosened the Phase 3.1 gate in any way."""
    from app.knowledge_base import get_knowledge_base_repository

    repo = get_knowledge_base_repository()
    uses = repo.list_approved_uses()
    assert len(uses) == 9
    for record in uses:
        assert record.advisory_status == "EDUCATIONAL_ONLY"
        for field_name in ("phi", "rei", "ppe"):
            field = getattr(record.safety_restrictions, field_name)
            assert field.status == "NOT_PUBLISHED_IN_SOURCE"
            assert field.note, "an unpublished safety field must still explain the gap"


def test_knowledge_base_provenance_manifest_still_loads():
    from app.knowledge_base.provenance import load_provenance_manifest

    assert len(load_provenance_manifest()) == 9


def test_classification_output_cannot_change_a_kb_record_status():
    """Structural check: the classifier has no handle on the knowledge base at all."""
    import app.classification.service as service_module

    source = Path(service_module.__file__).read_text(encoding="utf-8")
    assert "knowledge_base" not in source, (
        "The classification service must stay independent of the knowledge base; "
        "it must not be able to alter advisory_status."
    )


# --------------------------------------------------------------------------
# Dataset integrity: no leakage, full label coverage
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dataset_module():
    """Import ml/classification/common.py (training-time helpers) for split checks."""
    ml_path = REPO_ROOT / "ml" / "classification"
    if str(ml_path) not in sys.path:
        sys.path.insert(0, str(ml_path))
    import common  # noqa: PLC0415  (import after path setup)

    return common


def test_dataset_has_no_duplicate_queries(dataset_module):
    rows = dataset_module.load_dataset()
    assert len({row.normalized for row in rows}) == len(rows)


def test_dataset_uses_only_declared_labels(dataset_module):
    rows = dataset_module.load_dataset()
    for row in rows:
        assert row.crop in L.CROP_CLASSES
        assert row.task in L.TASK_CLASSES
        assert row.safety_topic in L.SAFETY_CLASSES


def test_splits_are_leakage_free_and_cover_every_label(dataset_module):
    rows = dataset_module.load_dataset()
    split = dataset_module.make_splits(rows, seed=dataset_module.SPLIT_SEED)
    dataset_module.assert_no_leakage(split)  # raises on any shared text
    for split_name in ("train", "dev", "test"):
        part = getattr(split, split_name)
        for target, declared in (
            ("crop", L.CROP_CLASSES),
            ("task", L.TASK_CLASSES),
            ("safety_topic", L.SAFETY_CLASSES),
        ):
            present = {getattr(row, target) for row in part}
            assert present == set(declared), f"{split_name}/{target} missing {set(declared) - present}"


def test_split_is_reproducible_from_the_seed(dataset_module):
    rows = dataset_module.load_dataset()
    first = dataset_module.make_splits(rows, seed=dataset_module.SPLIT_SEED)
    second = dataset_module.make_splits(rows, seed=dataset_module.SPLIT_SEED)
    assert first.ids() == second.ids()
