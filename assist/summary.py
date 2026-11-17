"""Chat summaries for staff + escalation to a Homigo support ticket."""
import logging
import re

from .homigo import HomigoError
from .llm import provider
from .models import ChatMessage, ChatSession, PendingAction

log = logging.getLogger(__name__)

CATEGORY_HINTS = [
    ("payment", ["payment", "refund", "paisa", "money", "upi", "charged", "भुगतान", "रिफंड"]),
    ("safety", ["safety", "unsafe", "misbehave", "harass", "theft", "सुरक्षा"]),
    ("quality", ["quality", "bad work", "not satisfied", "poor", "kharab", "warranty", "खराब"]),
    ("verification", ["verification", "kyc", "document", "approve"]),
    ("partner", ["partner", "job request", "earning", "settlement", "commission"]),
    ("booking", ["booking", "slot", "cancel", "late", "not arrived", "reschedule", "बुकिंग"]),
]


def guess_category(text):
    tl = text.lower()
    for cat, words in CATEGORY_HINTS:
        if any(w in tl for w in words):
            return cat
    return "other"


def transcript(session, limit=40):
    rows = []
    for m in session.messages.filter(role__in=["user", "assistant"]).exclude(text="").order_by("created_at", "id")[:limit]:
        if m.text.startswith("__"):
            continue
        rows.append(f"{'User' if m.role == 'user' else 'Assistant'}: {m.text[:400]}")
    return "\n".join(rows)


def extractive(session, reason=""):
    users = [m.text for m in session.messages.filter(role="user").order_by("created_at") if not m.text.startswith("__")]
    actions = PendingAction.objects.filter(session=session).order_by("created_at")
    phone = next((p for u in users for p in re.findall(r"\b[6-9]\d{9}\b", u)), "")
    lines = [
        f"Role: {session.user_role}{' · ' + session.user_name if session.user_name else ''} · Language: {session.language} · Messages: {session.message_count}",
        f"Reason: {reason or session.summary_reason or 'chat ended'}",
        f"First request: {users[0][:200] if users else '-'}",
    ]
    if len(users) > 1:
        lines.append("Later: " + " | ".join(u[:120] for u in users[1:4]))
    if actions:
        lines.append("Actions: " + "; ".join(f"{a.title} ({a.status})" for a in actions))
    if phone:
        lines.append(f"Contact number given in chat: {phone}")
    if users:
        lines.append(f"Last message: {users[-1][:200]}")
    return "\n".join(lines)


def summarize(session, reason=""):
    text = ""
    if provider.enabled():
        try:
            msg = provider.chat([
                {"role": "system", "content": "Summarise this support chat for Homigo staff in English, max 6 bullet points: who the user is (role), what they wanted, "
                                              "what was done (bookings/cancellations/tickets), what is still unresolved, mood, and the next step for staff. No OTPs or ID numbers."},
                {"role": "user", "content": transcript(session)},
            ], temperature=0.1, max_tokens=300)
            text = (msg.get("content") or "").strip()
        except provider.LLMUnavailable:
            text = ""
    if not text:
        text = extractive(session, reason)
    session.summary = text
    session.summary_reason = reason or session.summary_reason
    session.save(update_fields=["summary", "summary_reason", "updated_at"])
    return text


def escalate(session, client, reason="user asked for support"):
    """Creates a Homigo support ticket with the chat summary (signed-in users). Guests stay escalated in Assist for staff."""
    summary = summarize(session, reason)
    ticket_id = None
    if session.user_id and client.token and not session.homigo_ticket_id:
        first_user = next((m.text for m in session.messages.filter(role="user").order_by("created_at") if not m.text.startswith("__")), "Chat support")
        try:
            tk = client.post("/tickets/", {
                "category": guess_category(transcript(session)),
                "subject": f"Chat: {first_user[:120]}",
                "first_message": f"[Homigo Assist chat summary]\n{summary}\n\nChat id: {session.id}",
            })
            ticket_id = tk.get("id")
            session.homigo_ticket_id = ticket_id
        except HomigoError as e:
            log.warning("Ticket creation failed: %s", e.message)
    session.status = ChatSession.Status.ESCALATED
    session.save(update_fields=["status", "homigo_ticket_id", "updated_at"])
    ChatMessage.objects.create(session=session, role=ChatMessage.Role.SYSTEM, text=f"Escalated: {reason}")
    return ticket_id or session.homigo_ticket_id
