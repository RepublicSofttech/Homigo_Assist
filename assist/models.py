import uuid

from django.db import models


class ChatSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ESCALATED = "escalated", "Escalated to staff"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Homigo identity (None for guests). We never store the user's token.
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    user_role = models.CharField(max_length=20, default="guest")  # guest | customer | partner | coworker | admin
    user_name = models.CharField(max_length=120, blank=True)
    user_phone_last4 = models.CharField(max_length=4, blank=True)
    language = models.CharField(max_length=10, default="en")  # en | hi | hinglish
    channel = models.CharField(max_length=20, default="web")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    # Page context from the widget: page path, city, lat/lng (helps answer "near me")
    context = models.JSONField(default=dict, blank=True)
    # Small state machine data for guided flows (booking wizard, etc.)
    state = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    summary_reason = models.CharField(max_length=40, blank=True)
    homigo_ticket_id = models.IntegerField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.CharField(max_length=500, blank=True)
    message_count = models.PositiveIntegerField(default=0)
    engine = models.CharField(max_length=20, default="rules")  # rules | llm
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.id} ({self.user_role})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Tool"
        SYSTEM = "system", "System"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    text = models.TextField(blank=True)
    # UI payload for the widget: buttons, quick replies, cards, confirm prompts
    ui = models.JSONField(default=dict, blank=True)
    tool_name = models.CharField(max_length=60, blank=True)
    tool_call_id = models.CharField(max_length=80, blank=True)
    tool_args = models.JSONField(default=dict, blank=True)
    helpful = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class PendingAction(models.Model):
    """A write action (booking, cancel, profile update...) waiting for the user's explicit confirmation.
    The assistant can only *propose* it; the server executes it when the user taps Confirm."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="actions")
    kind = models.CharField(max_length=40)
    payload = models.JSONField(default=dict)
    title = models.CharField(max_length=160)
    lines = models.JSONField(default=list)  # [[label, value], ...] shown on the confirm card
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
