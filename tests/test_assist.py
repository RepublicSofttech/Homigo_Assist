"""End-to-end tests of the Assist API with a fake Homigo backend (no network, no LLM key)."""
import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from assist.homigo import HomigoClient, HomigoError
from assist.models import ChatSession, PendingAction

USERS = {
    "cust": {"id": 5, "first_name": "Priya", "phone": "9000000005", "user_type": "customer", "admin_role": "", "language": "en"},
    "part": {"id": 2, "first_name": "Ravi", "phone": "9000000002", "user_type": "partner", "admin_role": "", "language": "en"},
    "cow": {"id": 3, "first_name": "Amit", "phone": "9000000003", "user_type": "coworker", "admin_role": "", "language": "en"},
    "adm": {"id": 1, "first_name": "Admin", "phone": "9000000001", "user_type": "admin", "admin_role": "super_admin", "language": "en"},
}


class FakeHomigo:
    def __init__(self):
        self.calls = []

    def __call__(self, client, method, path, params=None, json=None):
        self.calls.append((method, path, params, json))
        tok = client.token
        if path == "/me/" and method == "GET":
            if tok in USERS:
                return USERS[tok]
            raise HomigoError("Invalid token", 401)
        if path == "/services/":
            q = (params or {}).get("q", "")
            svcs = [{"id": 7, "name": "Plumber", "category_name": "Home Repair", "starting_price": "149.00"},
                    {"id": 5, "name": "Home Deep Cleaning", "category_name": "Cleaning", "starting_price": "499.00"}]
            return {"results": [s for s in svcs if not q or q.lower() in s["name"].lower()]}
        if path == "/services/7/":
            return {"id": 7, "name": "Plumber", "description": "Tap and pipe work", "items": [{"id": 71, "name": "Tap repair", "default_price": "149.00", "unit_label": "job", "duration_minutes": 60}]}
        if path == "/addresses/":
            if method == "POST":
                return {"id": 99, **json}
            return [{"id": 11, "label": "Home", "line1": "12 MG Road", "city": "New Delhi", "pincode": "110001", "latitude": "28.63", "longitude": "77.21", "is_default": True}]
        if path == "/slots/":
            return {"date": params["date"], "slots": [{"start": f"{params['date']}T10:00:00+05:30", "available": True}, {"start": f"{params['date']}T11:00:00+05:30", "available": False}]}
        if path == "/bookings/price-preview/":
            return {"lines": [{"name": "Tap repair", "quantity": 1, "total": "149.00"}], "subtotal": "149.00", "discount": "0", "supplies_charge": "0", "total": "178.00"}
        if path == "/bookings/" and method == "POST":
            if tok != "cust":
                raise HomigoError("Only customers can create bookings.", 403, "CUSTOMER_ONLY")
            return {"id": 501, "booking_no": "HG-0501", **json}
        if path == "/bookings/" and method == "GET":
            return {"results": [{"id": 501, "booking_no": "HG-0501", "service_name": "Plumber", "status": "confirmed", "scheduled_start": "2026-11-20T10:00:00+05:30", "total": "178.00"}]}
        if path == "/bookings/501/":
            return {"id": 501, "booking_no": "HG-0501", "service_name": "Plumber", "status": "confirmed", "scheduled_start": "2026-11-20T10:00:00+05:30", "total": "178.00", "items": []}
        if path == "/bookings/501/cancel-preview/":
            return {"fee": 0, "refund": 0}
        if path == "/bookings/501/cancel/":
            return {"id": 501, "status": "cancelled"}
        if path == "/tickets/" and method == "POST":
            return {"id": 42, **json}
        if path == "/partner/go-live-status/":
            if tok != "part":
                raise HomigoError("Partners only", 403)
            return {"is_live": False, "checks": [{"label": "Verification approved", "ok": True}, {"label": "Active subscription", "ok": False}], "verification_status": "approved"}
        if path == "/partner/job-requests/":
            return [{"id": 9, "status": "pending", "service_name": "Plumber", "scheduled_start": "2026-11-20T10:00:00+05:30", "area": "Sector 21", "job_value": "249"}]
        if path == "/partner/job-requests/9/accept/":
            return {"id": 777, "booking_no": "HG-0777"}
        if path == "/partner/earnings/":
            return {"wallet": {"balance": "1200"}, "totals": {"gross": 5000, "commission": 750, "gst": 135, "net": 4115, "tips": 100}, "settlements": []}
        if path == "/coworker/jobs/":
            return {"today": [{"id": 1, "service_name": "Plumber", "scheduled_start": "2026-11-17T10:00:00+05:30", "status": "assigned"}], "upcoming": [], "completed": []}
        if path == "/admin/dashboard/":
            return {"bookings_today": 4, "open_tickets": 2, "partners_live": 3}
        if path == "/me/" and method == "PATCH":
            return {**USERS[tok], **json}
        raise HomigoError(f"Fake: no route {method} {path}", 404)


@override_settings(LLM_PROVIDER="none", MESSAGES_PER_MINUTE=100)
class AssistTests(TestCase):
    def setUp(self):
        cache.clear()
        self.fake = FakeHomigo()
        p = mock.patch.object(HomigoClient, "_request", lambda client, m, path, params=None, json=None: self.fake(client, m, path, params, json))
        p.start()
        self.addCleanup(p.stop)

    def api(self, token=None):
        c = APIClient()
        if token:
            c.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return c

    def start(self, token=None, **kw):
        r = self.api(token).post("/api/sessions/", {"context": {"page": "/", "city": "New Delhi", "lat": 28.6, "lng": 77.2}, **kw}, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        return r.data

    def say(self, sid, text, token=None, **kw):
        r = self.api(token).post(f"/api/sessions/{sid}/messages/", {"text": text, **kw}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.data["messages"][-1]

    # ---------- basics ----------
    def test_health(self):
        r = self.api().get("/health/")
        self.assertEqual(r.data["service"], "homigo-assist")
        self.assertFalse(r.data["ai_mode"])

    def test_guest_greeting_menu_and_resume(self):
        d = self.start()
        self.assertEqual(d["session"]["role"], "guest")
        greet = d["messages"][0]
        self.assertIn("Homigo Assist", greet["text"])
        self.assertTrue(greet["ui"]["quick_replies"])
        d2 = self.start(session_id=d["session"]["id"])
        self.assertEqual(d2["session"]["id"], d["session"]["id"])
        self.assertEqual(len(d2["messages"]), 1)

    def test_role_from_token_and_session_isolation(self):
        d = self.start("cust")
        self.assertEqual(d["session"]["role"], "customer")
        # someone else cannot use this session
        r = self.api("part").post(f"/api/sessions/{d['session']['id']}/messages/", {"text": "hi"}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_knowledge_answer_hinglish(self):
        sid = self.start()["session"]["id"]
        m = self.say(sid, "cancel karne par paisa wapas kab milega")
        self.assertIn("Cancellation", m["text"])
        self.assertEqual(ChatSession.objects.get(pk=sid).language, "hinglish")

    def test_hindi_greeting(self):
        sid = self.start()["session"]["id"]
        m = self.say(sid, "नमस्ते")
        self.assertIn("नमस्ते", m["text"])

    def test_service_search_cards(self):
        sid = self.start()["session"]["id"]
        m = self.say(sid, "I need a plumber")
        self.assertEqual(m["ui"]["cards"][0]["title"], "Plumber")
        self.assertEqual(m["ui"]["cards"][0]["value"], "__book:7")

    def test_guest_book_button_asks_login(self):
        sid = self.start()["session"]["id"]
        m = self.say(sid, "__book:7", display="Plumber")
        self.assertTrue(any(b.get("href", "").startswith("/login") for b in m["ui"]["buttons"]))

    # ---------- booking wizard + confirmation ----------
    def test_customer_books_in_chat(self):
        sid = self.start("cust")["session"]["id"]
        m = self.say(sid, "__book:7", "cust", display="Plumber")
        self.assertEqual(m["ui"]["quick_replies"][0]["value"], "__item:71")
        m = self.say(sid, "__item:71", "cust")
        self.assertEqual(m["ui"]["quick_replies"][0]["value"], "__addr:11")
        m = self.say(sid, "__addr:11", "cust")
        day = m["ui"]["quick_replies"][1]["value"].split(":", 1)[1]
        m = self.say(sid, f"__date:{day}", "cust")
        slot = m["ui"]["quick_replies"][0]["value"]
        self.assertTrue(slot.startswith("__slot:"))
        self.assertEqual(len(m["ui"]["quick_replies"]), 1)  # unavailable slot hidden
        m = self.say(sid, slot, "cust")
        m = self.say(sid, "__pay:cash", "cust")
        conf = m["ui"]["confirm"]
        self.assertIn(["Total", "₹178"], conf["lines"])
        # nothing booked yet
        self.assertFalse(any(c[0] == "POST" and c[1] == "/bookings/" for c in self.fake.calls))
        r = self.api("cust").post(f"/api/sessions/{sid}/actions/{conf['action_id']}/", {"decision": "confirm"}, format="json")
        self.assertIn("HG-0501", r.data["messages"][0]["text"])
        post = [c for c in self.fake.calls if c[0] == "POST" and c[1] == "/bookings/"][0]
        self.assertEqual(post[3]["items"], [{"service_item": 71, "quantity": 1}])
        self.assertEqual(post[3]["address_id"], 11)
        self.assertEqual(PendingAction.objects.get(pk=conf["action_id"]).status, "done")
        # cannot confirm twice
        r = self.api("cust").post(f"/api/sessions/{sid}/actions/{conf['action_id']}/", {"decision": "confirm"}, format="json")
        self.assertIn("no longer active", r.data["messages"][0]["text"])

    def test_cancel_flow_with_confirm(self):
        sid = self.start("cust")["session"]["id"]
        m = self.say(sid, "cancel my booking", "cust")
        self.assertEqual(m["ui"]["cards"][0]["value"], "__cancel:501")
        m = self.say(sid, "__cancel:501", "cust")
        aid = m["ui"]["confirm"]["action_id"]
        r = self.api("cust").post(f"/api/sessions/{sid}/actions/{aid}/", {"decision": "cancel"}, format="json")
        self.assertFalse(any(c[1] == "/bookings/501/cancel/" for c in self.fake.calls))
        self.assertEqual(PendingAction.objects.get(pk=aid).status, "cancelled")

    def test_profile_name_update_needs_confirm(self):
        sid = self.start("cust")["session"]["id"]
        m = self.say(sid, "my name is Priya Sharma", "cust")
        aid = m["ui"]["confirm"]["action_id"]
        self.api("cust").post(f"/api/sessions/{sid}/actions/{aid}/", {"decision": "confirm"}, format="json")
        patch = [c for c in self.fake.calls if c[0] == "PATCH" and c[1] == "/me/"][0]
        self.assertEqual(patch[3], {"first_name": "Priya", "last_name": "Sharma"})

    # ---------- roles ----------
    def test_partner_checklist_and_accept_job(self):
        sid = self.start("part")["session"]["id"]
        m = self.say(sid, "what is pending for go live?", "part")
        self.assertEqual(m["ui"]["checklist"][1], {"label": "Active subscription", "ok": False})
        m = self.say(sid, "show new job requests", "part")
        self.assertEqual(m["ui"]["cards"][0]["value"], "__accept_job:9")
        m = self.say(sid, "__accept_job:9", "part")
        aid = m["ui"]["confirm"]["action_id"]
        r = self.api("part").post(f"/api/sessions/{sid}/actions/{aid}/", {"decision": "confirm"}, format="json")
        self.assertTrue(any(b.get("href") == "/partner/bookings/777" for b in r.data["messages"][0]["ui"]["buttons"]))

    def test_partner_earnings(self):
        sid = self.start("part")["session"]["id"]
        m = self.say(sid, "meri kamai batao", "part")
        self.assertIn("₹1,200", m["text"])

    def test_customer_cannot_use_partner_features(self):
        sid = self.start("cust")["session"]["id"]
        m = self.say(sid, "show new job requests", "cust")
        self.assertIn("partner", m["text"])
        self.assertFalse(any(c[1] == "/partner/job-requests/" for c in self.fake.calls))

    def test_partner_cannot_book_in_chat(self):
        sid = self.start("part")["session"]["id"]
        m = self.say(sid, "__book:7", "part")
        self.assertIn("customer", m["text"])

    def test_coworker_today_jobs(self):
        sid = self.start("cow")["session"]["id"]
        m = self.say(sid, "today's jobs", "cow")
        self.assertEqual(m["ui"]["cards"][0]["title"], "Plumber")

    def test_admin_info_only(self):
        sid = self.start("adm")["session"]["id"]
        m = self.say(sid, "today's summary", "adm")
        self.assertIn("Bookings today", m["text"])
        from assist import tools
        self.assertFalse(any(n.startswith("propose_booking") or n == "propose_cancel" for n in tools.tools_for("admin")))

    # ---------- escalation / summary ----------
    def test_escalation_creates_ticket_with_summary(self):
        sid = self.start("cust")["session"]["id"]
        self.say(sid, "my plumber did not come yesterday, refund chahiye", "cust")
        m = self.say(sid, "talk to support", "cust")
        self.assertIn("#42", m["text"])
        tk = [c for c in self.fake.calls if c[1] == "/tickets/"][0][3]
        self.assertIn("Homigo Assist chat summary", tk["first_message"])
        self.assertEqual(tk["category"], "payment")
        s = ChatSession.objects.get(pk=sid)
        self.assertEqual(s.status, "escalated")
        self.assertEqual(s.homigo_ticket_id, 42)

    def test_guest_escalation_asks_login_and_keeps_phone(self):
        sid = self.start()["session"]["id"]
        self.say(sid, "please call me on 9876543210 about a partner enquiry")
        m = self.say(sid, "I want to talk to a human")
        self.assertTrue(any(b.get("href") == "/login" for b in m["ui"]["buttons"]))
        s = ChatSession.objects.get(pk=sid)
        self.assertIn("9876543210", s.summary)

    def test_pii_is_masked(self):
        sid = self.start("cust")["session"]["id"]
        r = self.api("cust").post(f"/api/sessions/{sid}/messages/", {"text": "my aadhaar is 1234 5678 9012"}, format="json")
        self.assertNotIn("1234 5678", r.data["messages"][0]["text"])
        self.assertIn("9012", r.data["messages"][0]["text"])
        self.assertIn("Aadhaar", r.data["messages"][1]["text"])

    def test_end_with_low_rating_escalates(self):
        sid = self.start("cust")["session"]["id"]
        self.say(sid, "hello", "cust")
        self.say(sid, "my booking status", "cust")
        r = self.api("cust").post(f"/api/sessions/{sid}/end/", {"rating": 1, "feedback": "not useful"}, format="json")
        self.assertTrue(r.data["summary_saved"])
        self.assertEqual(ChatSession.objects.get(pk=sid).homigo_ticket_id, 42)

    def test_admin_sessions_api(self):
        sid = self.start("cust")["session"]["id"]
        self.say(sid, "how do I pay?", "cust")
        self.assertEqual(self.api("cust").get("/api/admin/sessions/").status_code, 403)
        r = self.api("adm").get("/api/admin/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["count"], 1)
        d = self.api("adm").get(f"/api/admin/sessions/{sid}/")
        self.assertTrue(any(m["text"] == "how do I pay?" for m in d.data["messages"]))

    def test_feedback(self):
        d = self.start()
        sid = d["session"]["id"]
        m = self.say(sid, "how does booking work")
        r = self.api().post(f"/api/sessions/{sid}/messages/{m['id']}/feedback/", {"helpful": True}, format="json")
        self.assertEqual(r.status_code, 200)


@override_settings(LLM_PROVIDER="groq", LLM_API_KEY="test-key", LLM_MODEL="test-model", MESSAGES_PER_MINUTE=100)
class LLMModeTests(TestCase):
    """AI mode with a scripted fake LLM: checks the tool loop, role scoping and fallback."""

    def setUp(self):
        cache.clear()
        self.fake = FakeHomigo()
        p = mock.patch.object(HomigoClient, "_request", lambda client, m, path, params=None, json=None: self.fake(client, m, path, params, json))
        p.start()
        self.addCleanup(p.stop)

    def _post(self, token, sid, text):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return c.post(f"/api/sessions/{sid}/messages/", {"text": text}, format="json")

    def _start(self, token):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return c.post("/api/sessions/", {"context": {"lat": 28.6, "lng": 77.2}}, format="json").data["session"]["id"]

    def test_tool_loop_and_tool_scoping(self):
        script = [
            {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "search_services", "arguments": json.dumps({"query": "plumber"})}}]},
            {"content": "Plumber starts at ₹149. Want me to book it?"},
        ]
        seen_tools = []

        def fake_chat(messages, tools=None, **kw):
            seen_tools.append({t["function"]["name"] for t in (tools or [])})
            return script.pop(0)

        with mock.patch("assist.llm.provider.chat", side_effect=fake_chat):
            sid = self._start("cust")
            r = self._post("cust", sid, "plumber ka rate kya hai")
        last = r.data["messages"][-1]
        self.assertIn("₹149", last["text"])
        self.assertEqual(last["ui"]["cards"][0]["title"], "Plumber")
        self.assertIn("propose_booking", seen_tools[0])
        self.assertNotIn("partner_job_requests", seen_tools[0])
        self.assertNotIn("admin_dashboard", seen_tools[0])

    def test_llm_cannot_call_disallowed_tool(self):
        script = [
            {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "admin_dashboard", "arguments": "{}"}}]},
            {"content": "I can't access that."},
        ]
        with mock.patch("assist.llm.provider.chat", side_effect=lambda *a, **k: script.pop(0)):
            sid = self._start("cust")
            self._post("cust", sid, "show admin dashboard")
        self.assertFalse(any(c[1] == "/admin/dashboard/" for c in self.fake.calls))

    def test_falls_back_to_rules_when_llm_down(self):
        from assist.llm.provider import LLMUnavailable

        with mock.patch("assist.llm.provider.chat", side_effect=LLMUnavailable("down")):
            sid = self._start("cust")
            r = self._post("cust", sid, "how do I cancel a booking")
        self.assertIn("Cancellation", r.data["messages"][-1]["text"])
