#!/usr/bin/env python3
"""Check the question bank for structural and speech problems.

Usage: python scripts/validate_bank.py   (exit code 1 if anything is wrong)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambda"))

from quiz.bank import DATA_DIR, GRADES, SUBJECTS, _norm  # noqa: E402
from quiz.engine import ROUND_SIZE  # noqa: E402

# A chapter-only quiz should fill a whole round.
MIN_QUESTIONS_PER_TOPIC = ROUND_SIZE
MAX_QUESTION = 220
MAX_OPTION = 70
MAX_EXPLANATION = 200

# Everything Alexa reads aloud must be plain words, digits and simple
# punctuation. Symbols such as ^, /, =, + or the square root sign are read
# inconsistently (or not at all), so maths is written the way it is spoken.
SPEECH_SAFE = re.compile(r"^[A-Za-z0-9 ,.;:'?!()%\-]+$")
KEY_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Options are shuffled, so they cannot refer to each other or to letters.
BANNED_OPTION = re.compile(r"\b(all of the above|none of the above|both a and b)\b", re.I)
LETTER_REFERENCE = re.compile(r"\boption [a-d]\b", re.I)


def validate(data_dir: Path = DATA_DIR) -> List[str]:
    errors: List[str] = []
    seen_questions: Dict[str, str] = {}
    word_owner: Dict[str, str] = {}

    files = sorted(Path(data_dir).glob("*.json"))
    if not files:
        return [f"no data files in {data_dir}"]

    for path in files:
        where = path.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{where}: invalid JSON: {e}")
            continue

        grade, subject = data.get("grade"), data.get("subject")
        if grade not in GRADES:
            errors.append(f"{where}: grade must be one of {GRADES}")
        if subject not in SUBJECTS:
            errors.append(f"{where}: subject must be one of {SUBJECTS}")
        if path.stem != f"class{grade}_{subject}":
            errors.append(f"{where}: file should be named class{grade}_{subject}.json")

        topics = data.get("topics") or []
        if not topics:
            errors.append(f"{where}: no topics")
        keys = set()
        for t in topics:
            key = t.get("key", "")
            tw = f"{where} [{key}]"
            if not KEY_PATTERN.match(key):
                errors.append(f"{tw}: key must be lowercase words joined by hyphens")
            if key in keys:
                errors.append(f"{tw}: duplicate topic key")
            keys.add(key)
            if not t.get("name"):
                errors.append(f"{tw}: missing name")

            for word in [key, t.get("name", "")] + list(t.get("synonyms", [])):
                if not SPEECH_SAFE.match(word):
                    errors.append(f"{tw}: topic word has unsupported characters: {word!r}")
                owner = word_owner.setdefault(_norm(word), key)
                if owner != key:
                    errors.append(f"{tw}: {word!r} is already used by topic {owner!r}")

            questions = t.get("questions") or []
            if len(questions) < MIN_QUESTIONS_PER_TOPIC:
                errors.append(f"{tw}: needs at least {MIN_QUESTIONS_PER_TOPIC} questions")
            for n, q in enumerate(questions, start=1):
                errors.extend(_check_question(f"{tw} Q{n}", q, seen_questions))
    return errors


def _check_question(where: str, q: dict, seen: Dict[str, str]) -> List[str]:
    errors = []
    expected = {"question", "answer", "distractors", "explanation"}
    if set(q) != expected:
        return [f"{where}: fields must be exactly {sorted(expected)}"]

    text, answer, distractors, explanation = (
        q["question"], q["answer"], q["distractors"], q["explanation"])
    if not isinstance(distractors, list) or len(distractors) != 3:
        return [f"{where}: needs exactly 3 distractors"]

    options = [answer] + distractors
    if len({o.strip().lower() for o in options}) != 4:
        errors.append(f"{where}: options must all be different")

    for label, value, limit in (
        [("question", text, MAX_QUESTION), ("explanation", explanation, MAX_EXPLANATION)]
        + [("option", o, MAX_OPTION) for o in options]
    ):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{where}: empty {label}")
            continue
        if not SPEECH_SAFE.match(value):
            bad = sorted(set(re.sub(r"[A-Za-z0-9 ,.;:'?!()%\-]", "", value)))
            errors.append(f"{where}: {label} has characters Alexa may misread: {''.join(bad)!r}")
        if len(value) > limit:
            errors.append(f"{where}: {label} longer than {limit} characters")

    for o in options:
        if BANNED_OPTION.search(o):
            errors.append(f"{where}: option {o!r} depends on option order, which is shuffled")
    if LETTER_REFERENCE.search(explanation):
        errors.append(f"{where}: explanation refers to an option letter, which is shuffled")

    key = _norm(text)
    if key in seen:
        errors.append(f"{where}: duplicate of {seen[key]}")
    seen.setdefault(key, where)
    return errors


def main() -> int:
    errors = validate()
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"{len(errors)} problem(s) found.")
        return 1
    print("Question bank OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
