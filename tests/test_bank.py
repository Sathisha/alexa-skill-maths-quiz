import json
import random

import pytest

import build
import validate_bank
from quiz.bank import QuestionBank, normalize_grade, normalize_subject


@pytest.fixture(scope="module")
def bank():
    return QuestionBank.load()


def test_question_bank_is_valid():
    assert validate_bank.validate() == []


def test_generated_files_are_up_to_date():
    for path, content in build.outputs().items():
        assert path.read_text(encoding="utf-8") == content, (
            f"{path.name} is stale; run python scripts/build.py")


def test_every_class_and_subject_has_questions(bank):
    for grade in (9, 10):
        for subject in ("maths", "physics", "chemistry", "biology", "science"):
            assert bank.pick(grade, subject, count=5), (grade, subject)


@pytest.mark.parametrize("value,expected", [
    ("10", 10), ("ten", 10), ("tenth", 10), ("Class 9", 9), ("ninth", 9), ("11", None), (None, None),
])
def test_normalize_grade(value, expected):
    assert normalize_grade(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("maths", "maths"), ("Mathematics", "maths"), ("bio", "biology"), ("science", "science"),
    ("history", None),
])
def test_normalize_subject(value, expected):
    assert normalize_subject(value) == expected


def test_normalize_topic_accepts_key_name_and_synonym(bank):
    assert bank.normalize_topic("refraction-and-lenses") == "refraction-and-lenses"
    assert bank.normalize_topic("Refraction of Light and Lenses") == "refraction-and-lenses"
    assert bank.normalize_topic("ohm's law") == "current-electricity"
    assert bank.normalize_topic("cricket") is None


def test_science_mixes_the_three_sciences(bank):
    subjects = {t.subject for t in bank.topics_for(10, "science")}
    assert subjects == {"physics", "chemistry", "biology"}


def test_pick_prefers_unseen_questions(bank):
    rng = random.Random(1)
    first = bank.pick(9, "maths", "trigonometry", count=3, rng=rng)
    second = bank.pick(9, "maths", "trigonometry", count=3,
                       exclude=[q.id for q in first], rng=rng)
    pool = {q.id for q in bank.find_topics("trigonometry", 9, "maths")[0].questions}
    fresh = pool - {q.id for q in first}
    # Only 2 unseen remain, so both appear before any repeat.
    assert fresh <= {q.id for q in second}


def _write(tmp_path, questions, **overrides):
    data = {
        "grade": 9, "subject": "maths",
        "topics": [{"key": "demo", "name": "Demo", "synonyms": [], "questions": questions}],
    }
    data.update(overrides)
    (tmp_path / "class9_maths.json").write_text(json.dumps(data))
    return tmp_path


def _q(n, **overrides):
    q = {"question": f"What is {n} plus 1?", "answer": str(n + 1),
         "distractors": [str(n + 2), str(n + 3), str(n + 4)],
         "explanation": f"{n} plus 1 is {n + 1}."}
    q.update(overrides)
    return q


def test_validator_accepts_a_good_file(tmp_path):
    assert validate_bank.validate(_write(tmp_path, [_q(n) for n in range(5)])) == []


@pytest.mark.parametrize("bad,message", [
    (_q(0, question="What is 2 ^ 3?"), "misread"),
    (_q(0, distractors=["1", "2"]), "exactly 3 distractors"),
    (_q(0, distractors=["1", "1", "3"]), "must all be different"),
    (_q(0, distractors=["2", "3", "all of the above"]), "shuffled"),
    (_q(0, explanation="Option B is right."), "option letter"),
    (_q(1), "duplicate"),
])
def test_validator_rejects_problems(tmp_path, bad, message):
    errors = validate_bank.validate(_write(tmp_path, [_q(n) for n in range(1, 5)] + [bad]))
    assert any(message in e for e in errors), errors


def test_validator_requires_a_full_round_per_topic(tmp_path):
    errors = validate_bank.validate(_write(tmp_path, [_q(n) for n in range(2)]))
    assert any("at least" in e for e in errors), errors
