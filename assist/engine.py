"""Turn handling: language, safety, rate limits, AI-or-rules routing, confirmations, escalation."""
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import rules, summary
from . import tools as T
from .homigo import HomigoError
from .i18n import detect_language, q, t
from .llm import agent, provider
from .models import ChatMessage, ChatSession, PendingAction

log = logging.getLogger(__name__)

# Aadhaar (12 digits), card numbers (13–19 digits), bank account-like long numbers, PAN.
_SENSITIVE = [
    re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"),
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
]


def mask_sensitive(text):
    masked = text
    for rx in _SENSITIVE:
        masked = rx.sub(lambda m: "•" * max(4, len(m.group()) - 4) + m.group()[-4:], masked)
    return masked, masked != text


def _assistant(session, text, ui=None):
    m = ChatMessage.objects.create(session=session, role=ChatMessage.Role.ASSISTANT, text=text or "", ui=ui or {})
    return serialize(m)


def serialize(m):
    return {"id": m.id, "role": m.role, "text": m.text, "ui": m.ui, "created_at": m.created_at.isoformat(), "helpful": m.helpful}


def greeting(ctx):
    name = f" {ctx.user.get('first_name')}" if ctx.user and ctx.user.get("first_name") else ""
    rules.menu(ctx)
    return _assistant(ctx.session, t("greet", ctx.lang, name=name), ctx.clean_ui())


def _rate_limited(session):
    key = f"rl:{session.id}:{timezone.now().strftime('%Y%m%d%H%M')}"
    n = cache.get(key, 0) + 1
    cache.set(key, n, 70)
    return n > settings.MESSAGES_PER_MINUTE


def handle_message(ctx, text, display=""):
    """Saves the user message, produces assistant message(s). Returns list of serialized messages (user + replies)."""
    s = ctx.session
    text = (text or "").strip()[:2000]
    if not text:
        return []
    clean, had_pii = mask_sensitive(text)
    if not clean.startswith("__"):
        s.language = detect_language(clean, s.language)
        ctx.lang = s.language
    ui = {"display": str(display)[:120]} if display and clean.startswith("__") else {}
    user_msg = ChatMessage.objects.create(session=s, role=ChatMessage.Role.USER, text=clean, ui=ui)
    s.message_count += 1
    out = [serialize(user_msg)]

    if _rate_limited(s):
        out.append(_assistant(s, t("rate_limited", ctx.lang)))
        return out
    if s.message_count > settings.MAX_MESSAGES_PER_SESSION:
        ctx.quick(q("human", ctx.lang), "human")
        out.append(_assistant(s, t("limit_reached", ctx.lang), ctx.clean_ui()))
        s.save()
        return out
    if had_pii:
        out.append(_assistant(s, t("pii_warning", ctx.lang)))

    # explicit human request (any mode)
    if rules.detect_intent(clean) == "human" or clean == "__human":
        out.append(escalate(ctx, "user asked for support"))
        s.save()
        return out

    reply_text = None
    if clean.startswith("__") or not provider.enabled():
        reply_text = rules.reply(ctx, clean)
        s.engine = "rules" if not provider.enabled() else s.engine
    else:
        try:
            reply_text = agent.reply(ctx)
            s.engine = "llm"
        except provider.LLMUnavailable as e:
            log.info("LLM unavailable, using rules: %s", e)
            ctx.ui = {"cards": [], "buttons": [], "quick_replies": []}
            reply_text = rules.reply(ctx, clean)
        except HomigoError as e:
            reply_text = t("action_failed", ctx.lang, error=e.message)
    if reply_text is None:  # rules asked to escalate
        out.append(escalate(ctx, "user asked for support"))
    else:
        out.append(_assistant(s, reply_text, ctx.clean_ui()))
    s.save()
    return out


def escalate(ctx, reason):
    s = ctx.session
    if not s.user_id:
        summary.summarize(s, reason)
        s.status = ChatSession.Status.ESCALATED
        s.save(update_fields=["status", "updated_at"])
        ctx.button(q("login", ctx.lang), href="/login")
        return _assistant(s, t("escalate_guest", ctx.lang), ctx.clean_ui())
    ticket = summary.escalate(s, ctx.client, reason)
    if ticket:
        ctx.button({"en": "Open support", "hi": "सपोर्ट खोलें", "hinglish": "Support kholo"}[ctx.lang], href="/support" if ctx.role == "customer" else f"/{ctx.role}/support")
    return _assistant(s, t("escalated", ctx.lang, ticket=f" (ticket #{ticket})" if ticket else ""), ctx.clean_ui())


def decide_action(ctx, action_id, decision):
    s = ctx.session
    a = PendingAction.objects.filter(session=s, id=action_id).first()
    if not a or a.status != PendingAction.Status.PENDING:
        return [_assistant(s, {"en": "This request is no longer active.", "hi": "यह अनुरोध अब सक्रिय नहीं है।", "hinglish": "Ye request ab active nahi hai."}[ctx.lang])]
    a.decided_at = timezone.now()
    if decision != "confirm":
        a.status = PendingAction.Status.CANCELLED
        a.save()
        s.state = {}
        s.save(update_fields=["state", "updated_at"])
        rules.menu(ctx)
        return [_assistant(s, t("action_cancelled", ctx.lang), ctx.clean_ui())]
    try:
        text, result = T.execute_action(ctx, a)
        a.status, a.result = PendingAction.Status.DONE, result
    except HomigoError as e:
        a.status, a.result = PendingAction.Status.FAILED, {"error": e.message}
        text = t("action_failed", ctx.lang, error=e.message)
        ctx.quick(q("human", ctx.lang), "human")
    a.save()
    s.state = {}
    s.save(update_fields=["state", "updated_at"])
    ChatMessage.objects.create(session=s, role=ChatMessage.Role.SYSTEM, text=f"Action {a.kind}: {a.status}")
    return [_assistant(s, text, ctx.clean_ui())]


def end_session(ctx, rating=None, feedback=""):
    s = ctx.session
    if rating:
        s.rating = max(1, min(5, int(rating)))
    if feedback:
        s.feedback = feedback[:500]
    if s.status == ChatSession.Status.OPEN:
        s.status = ChatSession.Status.CLOSED
    s.save()
    users = s.messages.filter(role="user").count()
    if users >= 2 and not s.summary:
        summary.summarize(s, "chat ended")
    # Low rating on a signed-in chat that wasn't escalated -> let staff know.
    if s.rating and s.rating <= 2 and s.user_id and not s.homigo_ticket_id:
        summary.escalate(s, ctx.client, f"low rating ({s.rating}/5)")
    return {"status": s.status, "summary_saved": bool(s.summary)}
