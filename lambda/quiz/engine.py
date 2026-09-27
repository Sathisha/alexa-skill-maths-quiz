"""Quiz conversation logic, independent of the Alexa SDK.

All state lives in the session-attributes dict passed to each method, so a
handler only has to hand over ``attributes_manager.session_attributes`` and
turn the returned ``Reply`` into a response.

Session attributes:
    state     SETUP | QUIZ | ENDED
    grade     9 or 10
    subject   maths | physics | chemistry | biology | science
    topic     topic key, or None for a mix of all chapters
    round     [[question_id, option_order], ...] for the current round
    index     position of the question being asked
    score     correct answers so far this round
    seen      question ids already asked this session
    last      {"speech": ..., "reprompt": ...} for "repeat"
"""
from __future__ import annotations

import random
from typing import List, NamedTuple, Optional
from xml.sax.saxutils import escape

from .bank import SUBJECT_NAMES, QuestionBank, normalize_grade, normalize_subject

ROUND_SIZE = 5
LETTERS = "ABCD"

SETUP, QUIZ, ENDED = "SETUP", "QUIZ", "ENDED"

ASK_CLASS = "Which class would you like, 9 or 10?"
ASK_SUBJECT = "Which subject: maths, physics, chemistry, biology, or all of science?"
ANSWER_HINT = "Say A, B, C or D. You can also say repeat, or skip."

PRAISE = ("Correct!", "That's right!", "Well done, that's correct!", "Yes, correct!")


class Reply(NamedTuple):
    speech: str
    reprompt: Optional[str] = None
    end_session: bool = False


def _pause(ms: int = 300) -> str:
    return f'<break time="{ms}ms"/>'


class QuizEngine:
    def __init__(self, bank: QuestionBank, rng: Optional[random.Random] = None):
        self.bank = bank
        self.rng = rng or random.Random()

    # ----- entry points -------------------------------------------------

    def launch(self, attrs: dict) -> Reply:
        attrs.clear()
        attrs["state"] = SETUP
        return self._say(
            attrs,
            "Welcome to Exam Buddy, your I C S E quiz partner for classes 9 and 10. "
            "Tell me a class and subject, like class 10 physics. "
            "You can also add a chapter, like class 9 maths, trigonometry. "
            "What would you like to practise?",
            "Tell me a class and subject, like class 10 physics.",
        )

    def start(self, attrs: dict, grade: Optional[str] = None, subject: Optional[str] = None,
              topic: Optional[str] = None) -> Reply:
        """Handle a (possibly partial) request for a quiz and start it once complete."""
        g = normalize_grade(grade)
        s = normalize_subject(subject)
        t = self.bank.normalize_topic(topic)
        state = attrs.get("state", SETUP)

        if state in (QUIZ, ENDED) and (g or s or t or topic):
            # A new request mid-session: what was said replaces the old
            # selection, the rest ("physics" after class 10 maths) carries over.
            attrs["topic"] = None

        # Set explicitly: a one-shot request ("ask exam buddy for ...") has no launch.
        attrs["state"] = SETUP
        if g:
            attrs["grade"] = g
        if s:
            attrs["subject"] = s
        if t:
            attrs["topic"] = t
        elif topic:
            attrs["topic"] = None
            return self._say(
                attrs,
                f"Sorry, I don't know the chapter {escape(topic)}. " + self._topics_hint(attrs),
                "Which chapter would you like?",
            )

        problem = self._resolve(attrs, inherited=not (g or s) and bool(t))
        if problem:
            return problem
        return self._begin_round(attrs)

    def answer(self, attrs: dict, letter: Optional[str]) -> Reply:
        state = attrs.get("state")
        if state == ENDED:
            return self._say(attrs, "That round is over. " + self._again_prompt(attrs),
                             self._again_prompt(attrs))
        if state != QUIZ:
            return self._setup_reprompt(attrs)
        letter = (letter or "").strip().upper()[:1]
        if letter not in LETTERS:
            return self._say(attrs, "Sorry, I didn't catch that. " + ANSWER_HINT, ANSWER_HINT,
                             remember=False)
        return self._mark(attrs, LETTERS.index(letter))

    def skip(self, attrs: dict) -> Reply:
        if attrs.get("state") != QUIZ:
            return self.fallback(attrs)
        return self._mark(attrs, None)

    def repeat(self, attrs: dict) -> Reply:
        if attrs.get("state") == QUIZ:
            return Reply(self._question_speech(attrs), ANSWER_HINT)
        last = attrs.get("last")
        if not last:
            return self.help(attrs)
        return Reply(last["speech"], last.get("reprompt"))

    def yes(self, attrs: dict) -> Reply:
        state = attrs.get("state")
        if state == ENDED:
            return self._begin_round(attrs)
        if state == QUIZ:
            return self._say(attrs, "Please answer this one first. " + ANSWER_HINT, ANSWER_HINT,
                             remember=False)
        return self._setup_reprompt(attrs)

    def no(self, attrs: dict) -> Reply:
        if attrs.get("state") == QUIZ:
            return self._say(attrs, "Please answer this one first. " + ANSWER_HINT, ANSWER_HINT,
                             remember=False)
        return self.stop(attrs)

    def list_topics(self, attrs: dict, grade: Optional[str] = None,
                    subject: Optional[str] = None) -> Reply:
        g = normalize_grade(grade) or attrs.get("grade")
        s = normalize_subject(subject) or attrs.get("subject")
        if not g or not s:
            return self._say(
                attrs,
                "I can list chapters for one class and subject at a time, "
                "for example, what chapters are there in class 10 chemistry?",
                "Which class and subject would you like?",
            )
        names = [t.name for t in self.bank.topics_for(g, s)]
        speech = (
            f"For class {g} {SUBJECT_NAMES[s]}, I have: {escape(self._join(names))}. "
            f"To start, say something like class {g} {SUBJECT_NAMES[s]}, {escape(names[0])}."
        )
        return self._say(attrs, speech, "Which chapter would you like?")

    def help(self, attrs: dict) -> Reply:
        state = attrs.get("state")
        if state == QUIZ:
            return self._say(
                attrs,
                "I read each question with four options, A to D. Say the letter of your answer. "
                "Say repeat to hear the question again, or skip to move on. "
                + self._question_speech(attrs),
                ANSWER_HINT,
            )
        if state == ENDED:
            return self._say(attrs, self._again_prompt(attrs), self._again_prompt(attrs))
        return self._say(
            attrs,
            "I ask five multiple choice questions from the I C S E class 9 and 10 syllabus. "
            "Pick a class and subject: maths, physics, chemistry, biology, or all of science. "
            "You can also name a chapter, like class 10 biology, genetics. "
            "To hear the chapters, say, what chapters are there in class 9 physics? "
            "What would you like to practise?",
            "Tell me a class and subject, like class 10 physics.",
        )

    def fallback(self, attrs: dict) -> Reply:
        state = attrs.get("state")
        if state == QUIZ:
            return self._say(attrs, "Sorry, I didn't get that. " + ANSWER_HINT, ANSWER_HINT,
                             remember=False)
        if state == ENDED:
            return self._say(attrs, "Sorry, I didn't get that. " + self._again_prompt(attrs),
                             self._again_prompt(attrs))
        return self._setup_reprompt(attrs, "Sorry, I didn't get that. ")

    def stop(self, attrs: dict) -> Reply:
        answered = attrs.get("index", 0)
        if attrs.get("state") == QUIZ and answered:
            return Reply(
                f"You scored {attrs.get('score', 0)} out of {answered} so far. "
                "Keep practising. Goodbye!",
                end_session=True,
            )
        return Reply("Good luck with your studies. Goodbye!", end_session=True)

    # ----- internals ----------------------------------------------------

    def _resolve(self, attrs: dict, inherited: bool) -> Optional[Reply]:
        """Fill class/subject from the topic where possible; ask for what's missing."""
        grade, subject, topic = attrs.get("grade"), attrs.get("subject"), attrs.get("topic")
        if topic:
            candidates = self.bank.find_topics(topic, grade, subject)
            if not candidates and inherited:
                # The class/subject came from an earlier round; the student
                # may be switching to a chapter elsewhere.
                candidates = self.bank.find_topics(topic)
                if candidates:
                    grade = subject = None
            if not candidates:
                attrs["topic"] = None
                name = self.bank.topic_name(topic)
                return self._say(
                    attrs,
                    f"Sorry, I don't have {escape(name)} {self._scope(grade, subject)}. "
                    + self._topics_hint(attrs),
                    ASK_SUBJECT if grade and not subject else "What would you like to practise?",
                )
            grades = {c.grade for c in candidates}
            subjects = {c.subject for c in candidates}
            if grade is None and len(grades) == 1:
                grade = grades.pop()
            if subject is None and len(subjects) == 1:
                subject = subjects.pop()
            attrs["grade"], attrs["subject"] = grade, subject
        if not grade:
            return self._say(attrs, ASK_CLASS, ASK_CLASS)
        if not subject:
            return self._say(attrs, ASK_SUBJECT, ASK_SUBJECT)
        return None

    def _begin_round(self, attrs: dict) -> Reply:
        grade, subject, topic = attrs["grade"], attrs["subject"], attrs.get("topic")
        questions = self.bank.pick(grade, subject, topic, ROUND_SIZE,
                                   exclude=attrs.get("seen", []), rng=self.rng)
        attrs["round"] = [[q.id, self._order()] for q in questions]
        attrs["index"] = 0
        attrs["score"] = 0
        attrs["state"] = QUIZ
        attrs["seen"] = list(dict.fromkeys(attrs.get("seen", []) + [q.id for q in questions]))
        n = len(questions)
        intro = (
            f"Here {'is' if n == 1 else 'are'} {n} question{'' if n == 1 else 's'} on "
            f"{escape(self._describe(attrs))}. Say the letter of your answer. {_pause(500)}"
        )
        return self._say(attrs, intro + self._question_speech(attrs), ANSWER_HINT)

    def _mark(self, attrs: dict, choice: Optional[int]) -> Reply:
        qid, order = attrs["round"][attrs["index"]]
        q = self.bank.question(qid)
        options = q.options
        correct = order.index(0)
        right_text = f"{LETTERS[correct]}, {escape(options[0])}"

        if choice is None:
            feedback = f"Skipping. The answer was {right_text}."
        elif choice == correct:
            attrs["score"] += 1
            feedback = self.rng.choice(PRAISE)
        else:
            feedback = f"Not quite. The answer is {right_text}."
        feedback += f" {escape(q.explanation)} {_pause(600)}"

        attrs["index"] += 1
        if attrs["index"] < len(attrs["round"]):
            return self._say(attrs, feedback + self._question_speech(attrs), ANSWER_HINT)

        attrs["state"] = ENDED
        score, total = attrs["score"], len(attrs["round"])
        return self._say(
            attrs,
            f"{feedback}That's the end of the round. You scored {score} out of {total}. "
            f"{self._comment(score, total)} {self._again_prompt(attrs)}",
            self._again_prompt(attrs),
        )

    def _question_speech(self, attrs: dict) -> str:
        qid, order = attrs["round"][attrs["index"]]
        q = self.bank.question(qid)
        options = q.options
        parts = [
            f"Question {attrs['index'] + 1}. {escape(q.text)} {_pause(400)}"
        ]
        for letter, i in zip(LETTERS, order):
            parts.append(f"{letter}: {escape(options[i])}. {_pause(250)}")
        return " ".join(parts)

    def _order(self) -> List[int]:
        order = list(range(len(LETTERS)))
        self.rng.shuffle(order)
        return order

    def _describe(self, attrs: dict) -> str:
        grade, subject, topic = attrs["grade"], attrs["subject"], attrs.get("topic")
        base = f"class {grade} {SUBJECT_NAMES[subject]}"
        return f"{base}, {self.bank.topic_name(topic)}" if topic else base

    def _again_prompt(self, attrs: dict) -> str:
        return (
            f"Would you like another round of {escape(self._describe(attrs))}? "
            "Or name a different subject or chapter."
        )

    def _setup_reprompt(self, attrs: dict, prefix: str = "") -> Reply:
        if attrs.get("grade") and not attrs.get("subject"):
            return self._say(attrs, prefix + ASK_SUBJECT, ASK_SUBJECT)
        if attrs.get("subject") and not attrs.get("grade"):
            return self._say(attrs, prefix + ASK_CLASS, ASK_CLASS)
        prompt = "Tell me a class and subject, like class 10 physics."
        return self._say(attrs, prefix + prompt, prompt)

    def _topics_hint(self, attrs: dict) -> str:
        grade, subject = attrs.get("grade"), attrs.get("subject")
        if grade and subject:
            names = [t.name for t in self.bank.topics_for(grade, subject)]
            return (f"For class {grade} {SUBJECT_NAMES[subject]}, I have: "
                    f"{escape(self._join(names))}. Which one would you like?")
        return "Tell me a class and subject, like class 10 physics."

    @staticmethod
    def _scope(grade: Optional[int], subject: Optional[str]) -> str:
        if grade and subject:
            return f"for class {grade} {SUBJECT_NAMES[subject]}"
        if grade:
            return f"for class {grade}"
        if subject:
            return f"in {SUBJECT_NAMES[subject]}"
        return "yet"

    @staticmethod
    def _comment(score: int, total: int) -> str:
        if score == total:
            return "Perfect score!"
        if score * 2 >= total:
            return "Good effort."
        return "Keep practising, you'll get there."

    @staticmethod
    def _join(items: List[str]) -> str:
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + ", and " + items[-1]

    @staticmethod
    def _say(attrs: dict, speech: str, reprompt: Optional[str] = None,
             remember: bool = True) -> Reply:
        if remember:
            attrs["last"] = {"speech": speech, "reprompt": reprompt}
        return Reply(speech, reprompt)
