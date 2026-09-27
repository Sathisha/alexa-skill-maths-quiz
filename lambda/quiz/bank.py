"""Question bank: loads the per-class, per-subject JSON files and picks questions.

Each data file holds the topics (chapters) for one class and subject. A
question stores its correct answer and three distractors separately; the four
options are shuffled when a round is built, so the answer letter varies.
"""
from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

GRADES = (9, 10)
SUBJECTS = ("maths", "physics", "chemistry", "biology")
SCIENCE = ("physics", "chemistry", "biology")
# "science" is a selectable subject that mixes the three science papers.
SELECTABLE_SUBJECTS = SUBJECTS + ("science",)

SUBJECT_NAMES = {
    "maths": "maths",
    "physics": "physics",
    "chemistry": "chemistry",
    "biology": "biology",
    "science": "science",
}

_GRADE_WORDS = {
    "9": 9, "nine": 9, "ninth": 9, "ix": 9, "9th": 9,
    "10": 10, "ten": 10, "tenth": 10, "x": 10, "10th": 10,
}

_SUBJECT_WORDS = {
    "maths": "maths", "math": "maths", "mathematics": "maths",
    "physics": "physics",
    "chemistry": "chemistry",
    "biology": "biology", "bio": "biology",
    "science": "science", "sciences": "science",
}


@dataclass(frozen=True)
class Question:
    id: str
    grade: int
    subject: str
    topic: str
    text: str
    answer: str
    distractors: Tuple[str, ...]
    explanation: str

    @property
    def options(self) -> Tuple[str, ...]:
        """All four options, correct answer first (index 0)."""
        return (self.answer,) + self.distractors


@dataclass(frozen=True)
class Topic:
    key: str
    name: str
    synonyms: Tuple[str, ...]
    grade: int
    subject: str
    questions: Tuple[Question, ...]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower().replace("-", " ")).strip()


def normalize_grade(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    return _GRADE_WORDS.get(_norm(str(value)).replace("class ", "").replace("standard ", ""))


def normalize_subject(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _SUBJECT_WORDS.get(_norm(value))


def subjects_in(subject: Optional[str]) -> Sequence[str]:
    """Expand a selectable subject to the data subjects it covers."""
    if subject is None:
        return SUBJECTS
    if subject == "science":
        return SCIENCE
    return (subject,)


class QuestionBank:
    def __init__(self, topics: Iterable[Topic]):
        self.topics: List[Topic] = list(topics)
        self._questions: Dict[str, Question] = {
            q.id: q for t in self.topics for q in t.questions
        }
        self._topic_names: Dict[str, str] = {}
        self._topic_words: Dict[str, str] = {}
        for t in self.topics:
            self._topic_names.setdefault(t.key, t.name)
            for word in (t.key, t.name) + t.synonyms:
                self._topic_words.setdefault(_norm(word), t.key)

    @classmethod
    def load(cls, data_dir: Path = DATA_DIR) -> "QuestionBank":
        topics: List[Topic] = []
        for path in sorted(Path(data_dir).glob("*.json")):
            topics.extend(parse_file(json.loads(path.read_text(encoding="utf-8"))))
        return cls(topics)

    def question(self, question_id: str) -> Question:
        return self._questions[question_id]

    def normalize_topic(self, value: Optional[str]) -> Optional[str]:
        """Map a topic slot id, name or synonym to a topic key."""
        if value is None:
            return None
        return self._topic_words.get(_norm(value))

    def topic_name(self, key: str) -> str:
        return self._topic_names.get(key, key.replace("-", " "))

    def topics_for(self, grade: Optional[int] = None, subject: Optional[str] = None) -> List[Topic]:
        wanted = subjects_in(subject)
        return [
            t for t in self.topics
            if (grade is None or t.grade == grade) and t.subject in wanted
        ]

    def find_topics(self, key: str, grade: Optional[int] = None,
                    subject: Optional[str] = None) -> List[Topic]:
        return [t for t in self.topics_for(grade, subject) if t.key == key]

    def pick(self, grade: int, subject: str, topic: Optional[str] = None,
             count: int = 5, exclude: Iterable[str] = (),
             rng: Optional[random.Random] = None) -> List[Question]:
        """Pick up to ``count`` random questions, preferring ones not in ``exclude``."""
        rng = rng or random.Random()
        pool = [
            q for t in self.topics_for(grade, subject)
            if topic is None or t.key == topic
            for q in t.questions
        ]
        seen = set(exclude)
        fresh = [q for q in pool if q.id not in seen]
        stale = [q for q in pool if q.id in seen]
        rng.shuffle(fresh)
        rng.shuffle(stale)
        return (fresh + stale)[:count]


def parse_file(data: dict) -> List[Topic]:
    grade = int(data["grade"])
    subject = data["subject"]
    topics = []
    for t in data["topics"]:
        questions = tuple(
            Question(
                id=f"{grade}-{subject}-{t['key']}-{n}",
                grade=grade,
                subject=subject,
                topic=t["key"],
                text=q["question"],
                answer=q["answer"],
                distractors=tuple(q["distractors"]),
                explanation=q["explanation"],
            )
            for n, q in enumerate(t["questions"], start=1)
        )
        topics.append(Topic(
            key=t["key"],
            name=t["name"],
            synonyms=tuple(t.get("synonyms", ())),
            grade=grade,
            subject=subject,
            questions=questions,
        ))
    return topics
