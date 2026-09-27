"""End-to-end: raw Alexa request JSON in, response JSON out."""
import copy

import pytest

import lambda_function

BASE = {
    "version": "1.0",
    "session": {
        "new": True, "sessionId": "session-1", "attributes": {},
        "application": {"applicationId": "app"}, "user": {"userId": "user"},
    },
    "context": {"System": {
        "application": {"applicationId": "app"}, "user": {"userId": "user"},
        "device": {"deviceId": "device", "supportedInterfaces": {}},
        "apiEndpoint": "https://api.amazonalexa.com",
    }},
}


def request(req, attributes=None):
    event = copy.deepcopy(BASE)
    event["session"]["attributes"] = attributes or {}
    event["session"]["new"] = attributes is None
    event["request"] = {"requestId": "r", "timestamp": "2026-01-01T00:00:00Z",
                        "locale": "en-IN", **req}
    return lambda_function.lambda_handler(event, None)


def intent(name, attributes=None, **slots):
    return request({"type": "IntentRequest", "intent": {
        "name": name, "confirmationStatus": "NONE",
        "slots": {k: slot(k, v) for k, v in slots.items()},
    }}, attributes)


def slot(name, value):
    """A slot as Alexa sends it; a tuple is (heard, resolved id)."""
    body = {"name": name, "confirmationStatus": "NONE"}
    if value is None:
        return body
    heard, resolved = value if isinstance(value, tuple) else (value, None)
    body["value"] = heard
    if resolved:
        body["resolutions"] = {"resolutionsPerAuthority": [{
            "authority": f"amzn1.er-authority.echo-sdk.app.{name.upper()}",
            "status": {"code": "ER_SUCCESS_MATCH"},
            "values": [{"value": {"name": heard, "id": resolved}}],
        }]}
    return body


def speech(response):
    return response["response"]["outputSpeech"]["ssml"]


def test_launch():
    response = request({"type": "LaunchRequest"})
    assert "Welcome to Exam Buddy" in speech(response)
    assert response["response"]["shouldEndSession"] is False
    assert response["sessionAttributes"]["state"] == "SETUP"


def test_start_quiz_with_resolved_slots_then_answer():
    response = intent("StartQuizIntent",
                      grade=("tenth", "10"), subject=("physics", "physics"),
                      topic=("lenses", "refraction-and-lenses"))
    attrs = response["sessionAttributes"]
    assert attrs["state"] == "QUIZ"
    assert "class 10 physics, Refraction of Light and Lenses" in speech(response)

    response = intent("AnswerIntent", attrs, answer=("bee", "B"))
    assert response["sessionAttributes"]["index"] == 1
    assert "Question 2." in speech(response)


def test_unresolved_slot_falls_back_to_heard_value():
    response = intent("StartQuizIntent", grade="9", subject="maths", topic=None)
    assert response["sessionAttributes"]["state"] == "QUIZ"


@pytest.mark.parametrize("name", ["AMAZON.StopIntent", "AMAZON.CancelIntent"])
def test_stop_ends_session(name):
    response = intent(name, {"state": "SETUP"})
    assert response["response"]["shouldEndSession"] is True


def test_unhandled_intent_goes_to_fallback():
    response = intent("AMAZON.FallbackIntent", {"state": "SETUP"})
    assert "didn't get that" in speech(response)


def test_session_ended():
    response = request({"type": "SessionEndedRequest", "reason": "USER_INITIATED"}, {})
    assert "outputSpeech" not in (response.get("response") or {})
