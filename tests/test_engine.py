import random
import xml.etree.ElementTree as ET

import pytest

from quiz.bank import QuestionBank
from quiz.engine import ENDED, LETTERS, QUIZ, ROUND_SIZE, SETUP, QuizEngine


@pytest.fixture(scope="module")
def bank():
    return QuestionBank.load()


@pytest.fixture
def engine(bank):
    return QuizEngine(bank, random.Random(42))


def parses_as_ssml(speech):
    ET.fromstring(f"<speak>{speech}</speak>")
    return True


def current(engine, attrs):
    qid, order = attrs["round"][attrs["index"]]
    return engine.bank.question(qid), order


def correct_letter(engine, attrs):
    _, order = current(engine, attrs)
    return LETTERS[order.index(0)]


def wrong_letter(engine, attrs):
    return next(l for l in LETTERS if l != correct_letter(engine, attrs))


def test_launch_asks_for_class_and_subject(engine):
    attrs = {"stale": True}
    reply = engine.launch(attrs)
    assert attrs == {"state": SETUP, "last": attrs["last"]}
    assert "class and subject" in reply.speech
    assert reply.reprompt and not reply.end_session


def test_full_request_starts_a_round(engine):
    attrs = {}
    reply = engine.start(attrs, "10", "physics", "refraction-and-lenses")
    assert attrs["state"] == QUIZ
    assert len(attrs["round"]) == ROUND_SIZE
    assert all(engine.bank.question(qid).topic == "refraction-and-lenses"
               for qid, _ in attrs["round"])
    assert "5 questions on class 10 physics, Refraction of Light and Lenses" in reply.speech
    assert "Question 1." in reply.speech


def test_subject_only_asks_for_class_then_starts(engine):
    attrs = {}
    reply = engine.start(attrs, subject="chemistry")
    assert attrs["state"] == SETUP
    assert "Which class" in reply.speech
    engine.start(attrs, grade="nine")
    assert attrs["state"] == QUIZ
    assert {engine.bank.question(q).subject for q, _ in attrs["round"]} == {"chemistry"}
    assert {engine.bank.question(q).grade for q, _ in attrs["round"]} == {9}


def test_class_only_asks_for_subject(engine):
    attrs = {}
    assert "Which subject" in engine.start(attrs, grade="10").speech
    engine.start(attrs, subject="maths")
    assert attrs["state"] == QUIZ


def test_unique_topic_fills_class_and_subject(engine):
    attrs = {}
    engine.start(attrs, topic="genetics")
    assert (attrs["grade"], attrs["subject"], attrs["state"]) == (10, "biology", QUIZ)


def test_topic_in_both_classes_asks_which_class(engine):
    attrs = {}
    reply = engine.start(attrs, topic="trigonometry")
    assert "Which class" in reply.speech
    engine.start(attrs, grade="9")
    assert attrs["state"] == QUIZ
    assert {engine.bank.question(q).grade for q, _ in attrs["round"]} == {9}


def test_science_with_a_chapter(engine):
    attrs = {}
    engine.start(attrs, "10", "science", "electrolysis")
    assert attrs["state"] == QUIZ
    assert {engine.bank.question(q).topic for q, _ in attrs["round"]} == {"electrolysis"}


def test_unknown_chapter_lists_available_ones(engine):
    attrs = {}
    reply = engine.start(attrs, "9", "physics", "rocket science")
    assert attrs["state"] == SETUP
    assert "don't know the chapter rocket science" in reply.speech
    assert "Motion in One Dimension" in reply.speech


def test_chapter_from_another_class_is_refused(engine):
    attrs = {}
    reply = engine.start(attrs, grade="9", topic="genetics")
    assert attrs["state"] == SETUP
    assert "don't have Genetics for class 9" in reply.speech


def test_playing_a_full_round(engine):
    attrs = {}
    engine.start(attrs, "9", "maths")
    for i in range(ROUND_SIZE):
        letter = correct_letter(engine, attrs) if i < 3 else wrong_letter(engine, attrs)
        reply = engine.answer(attrs, letter)
        assert parses_as_ssml(reply.speech)
        if i < 3:
            assert reply.speech.split(" ")[0] in {"Correct!", "That's", "Well", "Yes,"}
        else:
            assert reply.speech.startswith("Not quite. The answer is")
    assert attrs["state"] == ENDED
    assert "You scored 3 out of 5" in reply.speech
    assert "another round of class 9 maths" in reply.speech


def test_another_round_avoids_repeats(engine):
    attrs = {}
    engine.start(attrs, "10", "biology")
    first = {q for q, _ in attrs["round"]}
    for _ in range(ROUND_SIZE):
        engine.answer(attrs, "A")
    engine.yes(attrs)
    assert attrs["state"] == QUIZ
    assert first.isdisjoint(q for q, _ in attrs["round"])


def test_no_after_round_says_goodbye(engine):
    attrs = {}
    engine.start(attrs, "10", "biology", "genetics")
    for _ in range(ROUND_SIZE):
        engine.answer(attrs, "A")
    assert engine.no(attrs).end_session


def test_skip_reveals_the_answer(engine):
    attrs = {}
    engine.start(attrs, "9", "biology")
    q, _ = current(engine, attrs)
    reply = engine.skip(attrs)
    assert reply.speech.startswith(f"Skipping. The answer was {correct_letter_after(q, attrs)}")
    assert attrs["index"] == 1 and attrs["score"] == 0


def correct_letter_after(q, attrs):
    # The skipped question is at index 0 of the round.
    order = attrs["round"][0][1]
    return f"{LETTERS[order.index(0)]}, {q.answer}"


def test_repeat_during_quiz_rereads_the_question(engine):
    attrs = {}
    engine.start(attrs, "9", "physics")
    q, _ = current(engine, attrs)
    reply = engine.repeat(attrs)
    assert reply.speech.startswith("Question 1.")
    assert q.text in reply.speech


def test_unrecognised_answer_keeps_the_question(engine):
    attrs = {}
    engine.start(attrs, "9", "physics")
    reply = engine.answer(attrs, "Z")
    assert "didn't catch" in reply.speech
    assert attrs["index"] == 0


def test_answer_before_a_quiz_prompts_for_setup(engine):
    attrs = {}
    engine.launch(attrs)
    reply = engine.answer(attrs, "B")
    assert "class and subject" in reply.speech
    assert attrs["state"] == SETUP


def test_stop_mid_quiz_reports_score(engine):
    attrs = {}
    engine.start(attrs, "10", "maths")
    engine.answer(attrs, correct_letter(engine, attrs))
    reply = engine.stop(attrs)
    assert reply.end_session
    assert "1 out of 1" in reply.speech


def test_new_subject_mid_quiz_keeps_class_and_drops_chapter(engine):
    attrs = {}
    engine.start(attrs, "10", "maths", "matrices")
    engine.start(attrs, subject="physics")
    assert (attrs["grade"], attrs["subject"], attrs["topic"]) == (10, "physics", None)
    assert attrs["state"] == QUIZ


def test_chapter_only_mid_quiz_keeps_class_and_subject(engine):
    attrs = {}
    engine.start(attrs, "9", "maths")
    engine.start(attrs, topic="trigonometry")
    assert (attrs["grade"], attrs["subject"], attrs["topic"]) == (9, "maths", "trigonometry")
    assert attrs["state"] == QUIZ


def test_chapter_elsewhere_mid_quiz_switches_class(engine):
    attrs = {}
    engine.start(attrs, "9", "maths")
    engine.start(attrs, topic="genetics")
    assert (attrs["grade"], attrs["subject"], attrs["state"]) == (10, "biology", QUIZ)


def test_list_topics(engine):
    reply = engine.list_topics({}, "10", "chemistry")
    assert "Organic Chemistry" in reply.speech
    assert "Which chapter" in reply.reprompt


def test_every_question_renders_as_valid_ssml(bank):
    engine = QuizEngine(bank, random.Random(0))
    for q in bank._questions.values():
        attrs = {"state": QUIZ, "grade": q.grade, "subject": q.subject,
                 "round": [[q.id, [0, 1, 2, 3]]], "index": 0, "score": 0}
        assert parses_as_ssml(engine._question_speech(attrs))
        assert parses_as_ssml(engine.skip(attrs).speech)
