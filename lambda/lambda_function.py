"""Alexa entry point for Exam Buddy.

Handlers are thin: they read slots, pass the session attributes to
``QuizEngine`` and turn its ``Reply`` into an Alexa response.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from ask_sdk_core.dispatch_components import AbstractExceptionHandler, AbstractRequestHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model import Response
from ask_sdk_model.slu.entityresolution import StatusCode

from quiz.bank import QuestionBank
from quiz.engine import QuizEngine, Reply

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

engine = QuizEngine(QuestionBank.load())


def slot_value(handler_input: HandlerInput, name: str) -> Optional[str]:
    """Return the entity-resolved id of a slot, falling back to what was heard."""
    slots = handler_input.request_envelope.request.intent.slots or {}
    slot = slots.get(name)
    if slot is None:
        return None
    resolutions = slot.resolutions.resolutions_per_authority if slot.resolutions else None
    for authority in resolutions or []:
        if authority.status.code == StatusCode.ER_SUCCESS_MATCH and authority.values:
            return authority.values[0].value.id
    return slot.value or None


def respond(handler_input: HandlerInput, reply: Reply) -> Response:
    builder = handler_input.response_builder.speak(reply.speech)
    if reply.reprompt and not reply.end_session:
        builder.ask(reply.reprompt)
    builder.set_should_end_session(reply.end_session)
    return builder.response


class _Handler(AbstractRequestHandler):
    """Routes a request type or intent name(s) to an engine call."""

    def __init__(self, matches: Callable[[HandlerInput], bool],
                 action: Callable[[HandlerInput, dict], Reply]):
        self._matches = matches
        self._action = action

    def can_handle(self, handler_input):
        return self._matches(handler_input)

    def handle(self, handler_input):
        attrs = handler_input.attributes_manager.session_attributes
        return respond(handler_input, self._action(handler_input, attrs))


def intents(*names: str) -> Callable[[HandlerInput], bool]:
    return lambda hi: any(is_intent_name(n)(hi) for n in names)


class SessionEndedHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        request = handler_input.request_envelope.request
        logger.info("Session ended: %s %s", request.reason, request.error)
        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        speech = "Sorry, I had trouble with that. Please try again."
        return handler_input.response_builder.speak(speech).ask(speech).response


sb = SkillBuilder()
sb.add_request_handler(_Handler(
    is_request_type("LaunchRequest"),
    lambda hi, a: engine.launch(a)))
sb.add_request_handler(_Handler(
    intents("StartQuizIntent"),
    lambda hi, a: engine.start(a, slot_value(hi, "grade"), slot_value(hi, "subject"),
                               slot_value(hi, "topic"))))
sb.add_request_handler(_Handler(
    intents("AnswerIntent"),
    lambda hi, a: engine.answer(a, slot_value(hi, "answer"))))
sb.add_request_handler(_Handler(
    intents("ListTopicsIntent"),
    lambda hi, a: engine.list_topics(a, slot_value(hi, "grade"), slot_value(hi, "subject"))))
sb.add_request_handler(_Handler(
    intents("SkipIntent", "AMAZON.NextIntent"),
    lambda hi, a: engine.skip(a)))
sb.add_request_handler(_Handler(
    intents("AMAZON.RepeatIntent"),
    lambda hi, a: engine.repeat(a)))
sb.add_request_handler(_Handler(
    intents("AMAZON.YesIntent", "AMAZON.StartOverIntent"),
    lambda hi, a: engine.yes(a)))
sb.add_request_handler(_Handler(
    intents("AMAZON.NoIntent"),
    lambda hi, a: engine.no(a)))
sb.add_request_handler(_Handler(
    intents("AMAZON.HelpIntent"),
    lambda hi, a: engine.help(a)))
sb.add_request_handler(_Handler(
    intents("AMAZON.CancelIntent", "AMAZON.StopIntent", "AMAZON.NavigateHomeIntent"),
    lambda hi, a: engine.stop(a)))
sb.add_request_handler(SessionEndedHandler())
# Last, so it catches any intent not handled above.
sb.add_request_handler(_Handler(
    is_request_type("IntentRequest"),
    lambda hi, a: engine.fallback(a)))
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
