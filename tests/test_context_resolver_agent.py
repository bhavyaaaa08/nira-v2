from app.agents.context_resolver_agent import ContextResolverAgent
from app.core.enums import Intent, PendingAction
from app.core.schemas import IntentResult
from app.core.state import CallState


def test_confirms_pending_extension_action():
    state = CallState()
    state.set_pending_action(PendingAction.CONFIRM_EXTENSION_REVIEW)
    state.add_turn("user", "yes")

    intent_result = IntentResult(intent=Intent.GENERAL, confidence=0.45)

    resolver = ContextResolverAgent()
    result = resolver.resolve(state, intent_result)

    assert result.resolved is True
    assert result.resolved_intent == Intent.CONFIRM_PENDING_ACTION
    assert intent_result.intent == Intent.CONFIRM_PENDING_ACTION
    assert intent_result.source == "context_resolver"


def test_confirms_pending_waiver_action_with_natural_text():
    state = CallState()
    state.set_pending_action(PendingAction.CONFIRM_WAIVER_REVIEW)
    state.add_turn("user", "okay pls do it")

    intent_result = IntentResult(intent=Intent.GENERAL, confidence=0.45)

    resolver = ContextResolverAgent()
    result = resolver.resolve(state, intent_result)

    assert result.resolved is True
    assert result.pending_action == PendingAction.CONFIRM_WAIVER_REVIEW
    assert intent_result.intent == Intent.CONFIRM_PENDING_ACTION


def test_cancels_pending_action():
    state = CallState()
    state.set_pending_action(PendingAction.CONFIRM_EXTENSION_REVIEW)
    state.add_turn("user", "no need")

    intent_result = IntentResult(intent=Intent.GENERAL, confidence=0.45)

    resolver = ContextResolverAgent()
    result = resolver.resolve(state, intent_result)

    assert result.resolved is True
    assert result.resolved_intent == Intent.CANCEL_PENDING_ACTION
    assert intent_result.intent == Intent.CANCEL_PENDING_ACTION


def test_does_not_resolve_without_pending_action():
    state = CallState()
    state.add_turn("user", "yes")

    intent_result = IntentResult(intent=Intent.GENERAL, confidence=0.45)

    resolver = ContextResolverAgent()
    result = resolver.resolve(state, intent_result)

    assert result.resolved is False
    assert intent_result.intent == Intent.GENERAL