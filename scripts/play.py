#!/usr/bin/env python3
"""Play the quiz in the terminal, without Alexa.

Type what you would say, for example:
  class 10 physics          class 9 maths trigonometry     b
  repeat   skip   help   chapters   yes   no   stop
This is a rough stand-in for Alexa's language understanding, meant for
checking the questions and the flow; the real skill uses the interaction model.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lambda"))

from quiz.bank import QuestionBank, normalize_grade, normalize_subject  # noqa: E402
from quiz.engine import QuizEngine  # noqa: E402


def to_text(ssml: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ssml)).strip()


def route(engine: QuizEngine, attrs: dict, said: str):
    words = said.lower().strip()
    simple = {
        "repeat": engine.repeat, "skip": engine.skip, "next": engine.skip,
        "help": engine.help, "yes": engine.yes, "no": engine.no,
        "stop": engine.stop, "cancel": engine.stop,
    }
    if words in simple:
        return simple[words](attrs)
    if re.fullmatch(r"(option )?[abcd]", words):
        return engine.answer(attrs, words[-1])

    tokens = words.replace("class", " ").split()
    grade = next((t for t in tokens if normalize_grade(t)), None)
    subject = next((t for t in tokens if normalize_subject(t)), None)
    rest = " ".join(t for t in tokens if t not in (grade, subject))
    if words.startswith(("chapters", "topics", "list")):
        return engine.list_topics(attrs, grade, subject)
    if grade or subject or engine.bank.normalize_topic(rest):
        return engine.start(attrs, grade, subject, rest or None)
    return engine.fallback(attrs)


def main() -> None:
    engine = QuizEngine(QuestionBank.load())
    attrs: dict = {}
    reply = engine.launch(attrs)
    while True:
        print(f"\nAlexa: {to_text(reply.speech)}")
        if reply.end_session:
            return
        try:
            said = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        reply = route(engine, attrs, said)


if __name__ == "__main__":
    main()
