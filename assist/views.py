from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.views import exception_handler as drf_handler

from . import engine, summary
from .homigo import HomigoClient, HomigoError, role_of
from .i18n import LANGS
from .llm import provider
from .models import ChatMessage, ChatSession
from .tools import Ctx

WIDGET = Path(__file__).parent / "static" / "assist" / "widget.js"


def exception_handler(exc, context):
    if isinstance(exc, HomigoError):
        return Response({"code": exc.code, "message": exc.message}, status=exc.status if exc.status >= 400 else 400)
    resp = drf_handler(exc, context)
    if resp is not None and isinstance(resp.data, dict) and "detail" in resp.data:
        resp.data = {"code": "ERROR", "message": str(resp.data["detail"])}
    return resp


def _token(request):
    h = request.headers.get("Authorization", "")
    parts = h.split()
    return parts[1] if len(parts) == 2 and parts[0].lower() in ("token", "bearer") else None


def _identity(request):
    client = HomigoClient(_token(request))
    user = client.me()
    if not user:
        client.token = None
    return client, user, role_of(user)


def _clean_context(raw):
    raw = raw if isinstance(raw, dict) else {}
    out = {"page": str(raw.get("page", "/"))[:200], "city": str(raw.get("city", ""))[:60]}
    try:
        lat, lng = float(raw.get("lat")), float(raw.get("lng"))
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            out["lat"], out["lng"] = round(lat, 6), round(lng, 6)
    except (TypeError, ValueError):
        pass
    return out


def _owned_session(request, pk):
    client, user, role = _identity(request)
    s = get_object_or_404(ChatSession, pk=pk)
    if (s.user_id or None) != (user["id"] if user else None):
        raise Http404
    return s, client, user, role


def _ctx(s, client, user, role):
    return Ctx(s, client, user, role, s.language)


class Health(APIView):
    def get(self, request):
        return Response({"status": "ok", "service": "homigo-assist", "ai_mode": provider.enabled(), "provider": settings.LLM_PROVIDER})


class SessionStart(APIView):
    """POST {session_id?, language?, context?} -> resumes the user's open session or starts a new one."""

    def post(self, request):
        client, user, role = _identity(request)
        ctx_data = _clean_context(request.data.get("context"))
        lang = request.data.get("language") if request.data.get("language") in LANGS else None
        s = None
        sid = request.data.get("session_id")
        if sid:
            s = ChatSession.objects.filter(pk=sid, user_id=user["id"] if user else None).exclude(status=ChatSession.Status.CLOSED).first() if _is_uuid(sid) else None
            if s and s.updated_at < timezone.now() - timedelta(minutes=settings.SESSION_IDLE_MINUTES * 12):
                s = None
        new = s is None
        if new:
            s = ChatSession.objects.create(
                user_id=user["id"] if user else None, user_role=role, user_name=(user or {}).get("first_name", "")[:120],
                user_phone_last4=((user or {}).get("phone") or "")[-4:], language=lang or ((user or {}).get("language") if (user or {}).get("language") in LANGS else "en"),
                context=ctx_data,
            )
        else:
            s.context = {**s.context, **{k: v for k, v in ctx_data.items() if v}}
            s.user_role = role
            if lang:
                s.language = lang
            s.save()
        messages = [engine.serialize(m) for m in s.messages.filter(role__in=["user", "assistant"]).order_by("created_at", "id")]
        if new or not messages:
            messages.append(engine.greeting(_ctx(s, client, user, role)))
        return Response({"session": _session_data(s), "messages": messages}, status=201 if new else 200)


def _is_uuid(v):
    import uuid

    try:
        uuid.UUID(str(v))
        return True
    except ValueError:
        return False


def _session_data(s):
    return {"id": str(s.id), "status": s.status, "language": s.language, "role": s.user_role, "ai_mode": provider.enabled()}


class SessionMessages(APIView):
    def post(self, request, pk):
        s, client, user, role = _owned_session(request, pk)
        if request.data.get("context"):
            s.context = {**s.context, **{k: v for k, v in _clean_context(request.data["context"]).items() if v}}
        if request.data.get("language") in LANGS:
            s.language = request.data["language"]
        if s.status == ChatSession.Status.CLOSED:
            s.status = ChatSession.Status.OPEN
        msgs = engine.handle_message(_ctx(s, client, user, role), request.data.get("text", ""), request.data.get("display", ""))
        return Response({"session": _session_data(s), "messages": msgs})


class SessionAction(APIView):
    def post(self, request, pk, action_id):
        s, client, user, role = _owned_session(request, pk)
        msgs = engine.decide_action(_ctx(s, client, user, role), action_id, request.data.get("decision", "cancel"))
        return Response({"session": _session_data(s), "messages": msgs})


class SessionEscalate(APIView):
    def post(self, request, pk):
        s, client, user, role = _owned_session(request, pk)
        msg = engine.escalate(_ctx(s, client, user, role), (request.data.get("reason") or "user asked for support")[:200])
        return Response({"session": _session_data(s), "messages": [msg]})


class SessionEnd(APIView):
    def post(self, request, pk):
        s, client, user, role = _owned_session(request, pk)
        res = engine.end_session(_ctx(s, client, user, role), request.data.get("rating"), request.data.get("feedback", ""))
        return Response(res)


class MessageFeedback(APIView):
    def post(self, request, pk, message_id):
        s, *_ = _owned_session(request, pk)
        m = get_object_or_404(ChatMessage, pk=message_id, session=s, role="assistant")
        m.helpful = bool(request.data.get("helpful"))
        m.save(update_fields=["helpful"])
        return Response({"ok": True})


# ---------------- staff (read-only) ----------------
class _AdminView(APIView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.client, self.user, self.role = _identity(request)
        if self.role != "admin":
            raise HomigoError("Staff access only.", 403, "FORBIDDEN")


class AdminSessions(_AdminView):
    def get(self, request):
        qs = ChatSession.objects.all()
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("role"):
            qs = qs.filter(user_role=p["role"])
        if p.get("q"):
            qs = qs.filter(Q(summary__icontains=p["q"]) | Q(user_name__icontains=p["q"]) | Q(messages__text__icontains=p["q"])).distinct()
        total = qs.count()
        rows = [{
            "id": str(s.id), "status": s.status, "role": s.user_role, "user_name": s.user_name, "user_id": s.user_id, "language": s.language,
            "engine": s.engine, "message_count": s.message_count, "rating": s.rating, "ticket_id": s.homigo_ticket_id, "summary": s.summary[:300],
            "first_message": (s.messages.filter(role="user").exclude(text__startswith="__").values_list("text", flat=True).first() or "")[:140],
            "created_at": s.created_at, "updated_at": s.updated_at,
        } for s in qs[: min(int(p.get("limit", 50)), 200)]]
        today = timezone.localdate()
        stats = ChatSession.objects.filter(created_at__date=today).aggregate(
            today=Count("id"), escalated=Count("id", filter=Q(status="escalated")))
        helpful = ChatMessage.objects.filter(helpful__isnull=False).aggregate(up=Count("id", filter=Q(helpful=True)), all=Count("id"))
        return Response({"count": total, "results": rows, "stats": {**stats, "helpful_up": helpful["up"], "helpful_total": helpful["all"]}})


class AdminSessionDetail(_AdminView):
    def get(self, request, pk):
        s = get_object_or_404(ChatSession, pk=pk)
        msgs = [engine.serialize(m) for m in s.messages.exclude(role="tool").order_by("created_at", "id")]
        actions = [{"title": a.title, "kind": a.kind, "status": a.status, "created_at": a.created_at} for a in s.actions.order_by("created_at")]
        return Response({"session": {**_session_data(s), "user_name": s.user_name, "user_id": s.user_id, "summary": s.summary, "summary_reason": s.summary_reason,
                                     "ticket_id": s.homigo_ticket_id, "rating": s.rating, "feedback": s.feedback, "context": s.context,
                                     "created_at": s.created_at, "updated_at": s.updated_at}, "messages": msgs, "actions": actions})

    def post(self, request, pk):
        s = get_object_or_404(ChatSession, pk=pk)
        return Response({"summary": summary.summarize(s, s.summary_reason or "staff requested")})


def widget_js(request):
    if not WIDGET.exists():
        raise Http404
    resp = FileResponse(open(WIDGET, "rb"), content_type="application/javascript")
    resp["Cache-Control"] = "public, max-age=300"
    resp["Access-Control-Allow-Origin"] = "*"
    return resp
