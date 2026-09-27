#!/usr/bin/env python3
"""Generate files derived from the question bank.

  skill-package/interactionModels/custom/en-IN.json   Alexa interaction model;
                                                      TOPIC slot values come
                                                      from the bank's chapters
  QUESTION_BANK.md                                    readable copy for review

Usage:
  python scripts/build.py           write the files
  python scripts/build.py --check   exit 1 if they are out of date (used in CI)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lambda"))

from quiz.bank import GRADES, SUBJECTS, QuestionBank  # noqa: E402

MODEL_PATH = ROOT / "skill-package" / "interactionModels" / "custom" / "en-IN.json"
REVIEW_PATH = ROOT / "QUESTION_BANK.md"

INVOCATION_NAME = "exam buddy"

START_SAMPLES = [
    "start a quiz", "start quiz", "quiz me", "give me a quiz", "new quiz", "start",
    "{grade}", "class {grade}", "{grade} class", "{grade} standard", "standard {grade}",
    "grade {grade}",
    "{subject}", "i want {subject}", "start a {subject} quiz", "ask me {subject} questions",
    "{topic}", "chapter {topic}", "the chapter {topic}", "quiz me on {topic}",
    "practise {topic}", "practice {topic}", "let's do {topic}", "start a quiz on {topic}",
    "ask me questions on {topic}",
    "class {grade} {subject}", "{grade} class {subject}", "{grade} standard {subject}",
    "{subject} for class {grade}", "{subject} class {grade}", "quiz me on {subject}",
    "quiz me on class {grade} {subject}", "quiz me on {subject} for class {grade}",
    "i want class {grade} {subject}", "let's do class {grade} {subject}",
    "start a class {grade} {subject} quiz", "practise class {grade} {subject}",
    "{subject} {topic}", "{subject} chapter {topic}", "{topic} in {subject}",
    "{topic} for class {grade}", "{topic} class {grade}", "class {grade} {topic}",
    "quiz me on {topic} for class {grade}",
    "class {grade} {subject} {topic}", "class {grade} {subject} on {topic}",
    "class {grade} {subject} chapter {topic}", "quiz me on class {grade} {subject} {topic}",
    "{grade} class {subject} {topic}", "{topic} for class {grade} {subject}",
]

ANSWER_SAMPLES = [
    "{answer}", "option {answer}", "answer {answer}", "letter {answer}",
    "the answer is {answer}", "my answer is {answer}", "it is {answer}", "it's {answer}",
    "is it {answer}", "i think {answer}", "i think it's {answer}", "i'll go with {answer}",
    "i choose {answer}", "i pick {answer}", "{answer} is my answer", "go with {answer}",
]

LIST_TOPICS_SAMPLES = [
    "what chapters are there", "what topics are there", "list the chapters", "list chapters",
    "list topics", "which chapters do you have", "what chapters do you have",
    "what chapters are there in class {grade} {subject}",
    "what topics are there in class {grade} {subject}",
    "what are the chapters in class {grade} {subject}",
    "list the chapters for class {grade} {subject}",
    "which chapters do you have for class {grade} {subject}",
    "chapters for class {grade} {subject}", "list chapters in {subject}",
    "what chapters are in {subject}", "what chapters are there in {subject}",
]

SKIP_SAMPLES = [
    "skip", "skip this", "skip this question", "skip it", "pass", "i don't know",
    "i do not know", "no idea", "next question", "i give up", "give up",
    "tell me the answer", "i'm not sure",
]

GRADE_VALUES = {
    "9": ["nine", "ninth", "9th"],
    "10": ["ten", "tenth", "10th"],
}

SUBJECT_VALUES = {
    "maths": ["math", "mathematics", "maths quiz"],
    "physics": ["physics quiz"],
    "chemistry": ["chem", "chemistry quiz"],
    "biology": ["bio", "biology quiz"],
    "science": ["sciences", "general science", "all science", "all of science", "science quiz"],
}

ANSWER_VALUES = {
    "A": ["option a", "ay", "eh", "first", "first one", "one"],
    "B": ["option b", "bee", "be", "second", "second one", "two"],
    "C": ["option c", "see", "sea", "si", "third", "third one", "three"],
    "D": ["option d", "dee", "di", "fourth", "fourth one", "four"],
}


def slot_text(text: str) -> str:
    """Lowercase, and drop punctuation that slot values do not accept."""
    text = text.lower().replace("-", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]", "", text)).strip()


def _slot_type(name: str, values: Dict[str, List[str]], names: Dict[str, str] = None) -> dict:
    names = names or {}
    return {
        "name": name,
        "values": [
            {"id": vid, "name": {"value": names.get(vid, vid), "synonyms": syns}}
            for vid, syns in values.items()
        ],
    }


def topic_values(bank: QuestionBank) -> dict:
    values: Dict[str, List[str]] = {}
    names: Dict[str, str] = {}
    for t in bank.topics:
        names.setdefault(t.key, slot_text(t.name))
        syns = values.setdefault(t.key, [])
        for word in (t.key, t.name) + t.synonyms:
            w = slot_text(word)
            if w != names[t.key] and w not in syns:
                syns.append(w)
    return _slot_type("TOPIC", values, names)


def build_model(bank: QuestionBank) -> dict:
    def intent(name, samples=(), slots=()):
        body = {"name": name, "samples": list(samples)}
        if slots:
            body["slots"] = [{"name": n, "type": t} for n, t in slots]
        return body

    builtins = [
        "AMAZON.CancelIntent", "AMAZON.HelpIntent", "AMAZON.StopIntent",
        "AMAZON.NavigateHomeIntent", "AMAZON.FallbackIntent", "AMAZON.RepeatIntent",
        "AMAZON.YesIntent", "AMAZON.NoIntent", "AMAZON.NextIntent", "AMAZON.StartOverIntent",
    ]
    return {
        "interactionModel": {
            "languageModel": {
                "invocationName": INVOCATION_NAME,
                "intents": [intent(n) for n in builtins] + [
                    intent("StartQuizIntent", START_SAMPLES,
                           [("grade", "GRADE"), ("subject", "SUBJECT"), ("topic", "TOPIC")]),
                    intent("AnswerIntent", ANSWER_SAMPLES, [("answer", "ANSWER")]),
                    intent("ListTopicsIntent", LIST_TOPICS_SAMPLES,
                           [("grade", "GRADE"), ("subject", "SUBJECT")]),
                    intent("SkipIntent", SKIP_SAMPLES),
                ],
                "types": [
                    _slot_type("GRADE", GRADE_VALUES),
                    _slot_type("SUBJECT", SUBJECT_VALUES),
                    _slot_type("ANSWER", ANSWER_VALUES),
                    topic_values(bank),
                ],
            }
        }
    }


def build_review(bank: QuestionBank) -> str:
    total = sum(len(t.questions) for t in bank.topics)
    lines = [
        "# Question bank",
        "",
        "Generated from `lambda/data/*.json` by `python scripts/build.py`. Do not edit by hand.",
        "",
        f"{total} questions. Options are shuffled when asked; the **bold** option is correct.",
        "",
        "| Class | Subject | Chapters | Questions |",
        "|---|---|---|---|",
    ]
    for g in GRADES:
        for s in SUBJECTS:
            topics = bank.topics_for(g, s)
            lines.append(f"| {g} | {s.title()} | {len(topics)} | "
                         f"{sum(len(t.questions) for t in topics)} |")
    for g in GRADES:
        for s in SUBJECTS:
            lines += ["", f"## Class {g} {s.title()}"]
            for t in bank.topics_for(g, s):
                lines += ["", f"### {t.name}", ""]
                for n, q in enumerate(t.questions, start=1):
                    opts = [f"**{q.answer}**"] + list(q.distractors)
                    lines.append(f"{n}. {q.text}")
                    lines.append(f"   - Options: {' / '.join(opts)}")
                    lines.append(f"   - Explanation: {q.explanation}")
    return "\n".join(lines) + "\n"


def outputs() -> Dict[Path, str]:
    bank = QuestionBank.load()
    return {
        MODEL_PATH: json.dumps(build_model(bank), indent=2, ensure_ascii=False) + "\n",
        REVIEW_PATH: build_review(bank),
    }


def main(argv: List[str]) -> int:
    check = "--check" in argv
    stale = []
    for path, content in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        if check:
            stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("Out of date, run python scripts/build.py: " + ", ".join(map(str, stale)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
