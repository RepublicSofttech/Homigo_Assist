"""Role-aware tools the assistant can use. Each tool:
  - declares which roles may call it,
  - has a JSON schema (used for LLM tool calling),
  - returns compact data for the model and may add UI (cards, buttons, confirm prompts) for the widget.

Write operations never run directly: they create a PendingAction that the user must confirm in the widget.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from . import knowledge
from .homigo import HomigoError
from .i18n import t
from .models import PendingAction

ALL = ("guest", "customer", "partner", "coworker", "admin")
SIGNED_IN = ("customer", "partner", "coworker", "admin")


class Ctx:
    """Everything a tool needs for one turn."""

    def __init__(self, session, client, user, role, lang):
        self.session, self.client, self.user, self.role, self.lang = session, client, user, role, lang
        self.ui = {"cards": [], "buttons": [], "quick_replies": []}

    # UI helpers
    def card(self, **c):
        self.ui["cards"].append(c)

    def button(self, label, href=None, value=None):
        b = {"label": label}
        if href:
            b["href"] = href
        if value:
            b["value"] = value
        if b not in self.ui["buttons"]:
            self.ui["buttons"].append(b)

    def quick(self, label, value=None):
        self.ui["quick_replies"].append({"label": label, "value": value or label})

    def set(self, key, value):
        self.ui[key] = value

    def clean_ui(self):
        return {k: v for k, v in self.ui.items() if v}


def money(v):
    try:
        d = Decimal(str(v))
    except Exception:
        return str(v)
    return f"₹{d:,.0f}" if d == d.to_integral() else f"₹{d:,.2f}"


def fmt_dt(iso):
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return timezone.localtime(dt).strftime("%a %d %b, %I:%M %p")
    except Exception:
        return str(iso)


def location(ctx):
    c = ctx.session.context or {}
    lat, lng = c.get("lat"), c.get("lng")
    return (lat, lng) if lat and lng else (None, None)


# --------------------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------------------
def search_knowledge(ctx, query):
    hits = knowledge.search(query, ctx.role, limit=3)
    return {"results": [{"title": s["title"], "answer": s["body"]} for _, s in hits]} if hits else {"results": [], "note": "No matching article."}


def search_services(ctx, query="", category_id=None):
    data = ctx.client.results(ctx.client.get("/services/", q=query, category=category_id, page_size=6))
    out = []
    for s in data[:6]:
        out.append({"id": s["id"], "name": s["name"], "category": s.get("category_name"), "starting_price": s.get("starting_price")})
        ctx.card(title=s["name"], subtitle=s.get("category_name", ""), meta=f"From {money(s['starting_price'])}" if s.get("starting_price") else "",
                 href=f"/services/{s['id']}", value=f"__book:{s['id']}")
    return {"services": out}


def get_service(ctx, service_id):
    s = ctx.client.get(f"/services/{int(service_id)}/")
    return {
        "id": s["id"], "name": s["name"], "description": (s.get("description") or "")[:300],
        "warranty_days": s.get("warranty_days"), "supplies_mode": s.get("supplies_mode"), "supplies_charge": s.get("supplies_charge"),
        "items": [{"id": i["id"], "name": i["name"], "price": i["default_price"], "unit": i.get("unit_label"), "duration_minutes": i.get("duration_minutes")}
                  for i in s.get("items", [])],
    }


def list_offers(ctx):
    data = ctx.client.results(ctx.client.get("/offers/"))
    return {"offers": [{"code": o["code"], "title": o["title"], "min_order": o.get("min_order_value"), "valid_to": o.get("valid_to")} for o in data[:6]]}


def get_slots(ctx, service_id, day=None):
    lat, lng = location(ctx)
    if not lat:
        return {"error": "Location unknown. Ask the user to pick their city or address first."}
    day = day or date.today().isoformat()
    data = ctx.client.get("/slots/", service_id=service_id, date=day, lat=lat, lng=lng)
    free = [s for s in data.get("slots", []) if s.get("available")]
    return {"date": day, "free_slots": [s["start"] for s in free[:12]]}


def price_quote(ctx, service_id, items, coupon_code="", bring_supplies=False):
    q = ctx.client.post("/bookings/price-preview/", {"service_id": int(service_id), "items": items, "coupon_code": coupon_code or "", "bring_supplies": bool(bring_supplies)})
    return {k: q.get(k) for k in ("lines", "subtotal", "visit_charge", "discount", "convenience_fee", "tax", "supplies_charge", "total", "coupon")}


def navigate(ctx, path, label="Open"):
    if not str(path).startswith("/"):
        return {"error": "path must start with /"}
    ctx.button(label, href=path)
    return {"ok": True, "note": "A button was shown to the user."}


def my_profile(ctx):
    u = ctx.client.get("/me/")
    return {k: u.get(k) for k in ("first_name", "last_name", "email", "language", "user_type")} | {"phone_last4": (u.get("phone") or "")[-4:]}


def list_addresses(ctx):
    data = ctx.client.results(ctx.client.get("/addresses/"))
    return {"addresses": [{"id": a["id"], "label": a["label"], "text": f"{a['line1']}, {a['city']} {a['pincode']}", "default": a.get("is_default")} for a in data]}


def my_bookings(ctx, bucket="upcoming"):
    data = ctx.client.results(ctx.client.get("/bookings/", bucket=bucket if bucket in ("upcoming", "past", "today") else None, page_size=6))
    out = []
    base = {"customer": "/bookings", "partner": "/partner/bookings", "coworker": "/coworker", "admin": "/admin/bookings"}.get(ctx.role, "/bookings")
    for b in data[:6]:
        out.append({"id": b["id"], "booking_no": b.get("booking_no"), "service": b.get("service_name"), "status": b.get("status"),
                    "when": b.get("scheduled_start"), "total": b.get("total"), "payment_status": b.get("payment_status")})
        ctx.card(title=f"{b.get('service_name', 'Booking')} · {b.get('booking_no', '')}", subtitle=fmt_dt(b.get("scheduled_start")),
                 meta=f"{str(b.get('status', '')).replace('_', ' ').title()} · {money(b.get('total', 0))}", href=f"{base}/{b['id']}" if ctx.role != "coworker" else base)
    return {"bookings": out}


def booking_details(ctx, booking_id):
    b = ctx.client.get(f"/bookings/{int(booking_id)}/")
    keep = ("id", "booking_no", "service_name", "status", "scheduled_start", "total", "payment_status", "payment_mode", "partner_name")
    out = {k: b.get(k) for k in keep}
    out["items"] = [{"name": i["name"], "qty": i["quantity"], "total": i["total"], "addon_status": i.get("addon_status")} for i in b.get("items", [])]
    if ctx.role == "customer":
        out["start_otp_hint"] = "The customer can see the OTP on the booking page; never read it out."
    ctx.button("Open booking", href={"customer": "/bookings", "partner": "/partner/bookings", "admin": "/admin/bookings"}.get(ctx.role, "/bookings") + f"/{b['id']}")
    return out


def cancel_preview(ctx, booking_id):
    return ctx.client.get(f"/bookings/{int(booking_id)}/cancel-preview/")


def partner_status(ctx):
    s = ctx.client.get("/partner/go-live-status/")
    checks = s.get("checks") or s.get("checklist") or []
    items = []
    for c in checks:
        if isinstance(c, (list, tuple)):
            items.append({"label": c[0], "ok": bool(c[1])})
        elif isinstance(c, dict):
            items.append({"label": c.get("label") or c.get("name"), "ok": bool(c.get("ok") or c.get("done"))})
    ctx.set("checklist", items)
    ctx.button("Open business profile", href="/partner/onboarding")
    return {"is_live": s.get("is_live") or s.get("live"), "checklist": items, "verification_status": s.get("verification_status")}


def partner_job_requests(ctx):
    data = ctx.client.results(ctx.client.get("/partner/job-requests/"))
    out = []
    for o in data[:6]:
        if o.get("status") not in (None, "pending"):
            continue
        out.append({"id": o["id"], "service": o.get("service_name"), "when": o.get("scheduled_start"), "area": o.get("area"), "job_value": o.get("job_value"), "expires_at": o.get("expires_at")})
        ctx.card(title=o.get("service_name", "Job"), subtitle=fmt_dt(o.get("scheduled_start")), meta=f"{o.get('area') or ''} · {money(o.get('job_value') or 0)}", value=f"__accept_job:{o['id']}")
    ctx.button("Open job requests", href="/partner/requests")
    return {"requests": out}


def partner_earnings(ctx):
    e = ctx.client.get("/partner/earnings/")
    w, tot = e.get("wallet") or {}, e.get("totals") or {}
    ctx.button("Open earnings", href="/partner/earnings")
    return {"wallet_balance": w.get("balance"), "total_service_value": tot.get("gross"), "total_commission": tot.get("commission"),
            "gst_on_commission": tot.get("gst"), "total_net_earned": tot.get("net"), "tips": tot.get("tips"), "recent_settlements": (e.get("settlements") or [])[:3]}


def partner_dashboard(ctx):
    d = ctx.client.get("/partner/dashboard/")
    return {k: v for k, v in d.items() if not isinstance(v, list)}


def coworker_jobs(ctx, bucket="today"):
    resp = ctx.client.get("/coworker/jobs/")
    data = resp.get(bucket if bucket in ("today", "upcoming", "completed") else "today", []) if isinstance(resp, dict) else resp
    out = [{"id": b["id"], "service": b.get("service_name"), "when": b.get("scheduled_start"), "status": b.get("status"), "area": b.get("address_area") or b.get("city")} for b in data[:8]]
    for j in out:
        ctx.card(title=j["service"] or "Job", subtitle=fmt_dt(j["when"]), meta=str(j["status"]).replace("_", " ").title(), href="/coworker")
    return {"jobs": out}


def admin_dashboard(ctx):
    d = ctx.client.get("/admin/dashboard/")
    return {k: v for k, v in d.items() if not isinstance(v, list)}


def admin_find_booking(ctx, query):
    data = ctx.client.results(ctx.client.get("/bookings/", search=query, page_size=5))
    out = [{"id": b["id"], "booking_no": b.get("booking_no"), "service": b.get("service_name"), "status": b.get("status"), "when": b.get("scheduled_start"), "customer": b.get("customer_name"), "partner": b.get("partner_name")} for b in data[:5]]
    for b in out:
        ctx.card(title=f"{b['booking_no']} · {b['service']}", subtitle=fmt_dt(b["when"]), meta=str(b["status"]), href=f"/admin/bookings/{b['id']}")
    return {"bookings": out}


def admin_verification_queue(ctx):
    data = ctx.client.results(ctx.client.get("/admin/verification-cases/", status="open", page_size=20))
    ctx.button("Open verification queue", href="/admin/verification")
    return {"open_cases": len(data), "oldest": [{"id": c["id"], "type": c.get("subject_type"), "name": c.get("subject_name")} for c in data[:5]]}


# ---- proposals (need confirmation) ----
def _propose(ctx, kind, payload, title, lines):
    PendingAction.objects.filter(session=ctx.session, status=PendingAction.Status.PENDING).update(status=PendingAction.Status.EXPIRED)
    a = PendingAction.objects.create(session=ctx.session, kind=kind, payload=payload, title=title, lines=lines)
    ctx.set("confirm", {"action_id": str(a.id), "title": title, "lines": lines})
    return {"status": "awaiting_user_confirmation", "action_id": str(a.id), "note": "Ask the user to tap Confirm on the card. Do not claim it is done."}


def propose_booking(ctx, service_id, items, address_id, scheduled_start, payment_mode="cash", coupon_code="", bring_supplies=False, notes="", partner_id=None):
    svc = ctx.client.get(f"/services/{int(service_id)}/")
    q = ctx.client.post("/bookings/price-preview/", {"service_id": int(service_id), "items": items, "coupon_code": coupon_code or "", "bring_supplies": bool(bring_supplies), "partner_id": partner_id})
    addr = next((a for a in ctx.client.results(ctx.client.get("/addresses/")) if a["id"] == int(address_id)), None)
    if not addr:
        return {"error": "Address not found in the user's saved addresses."}
    lines = [["Service", svc["name"]]]
    for ln in q.get("lines", []):
        lines.append([f"{ln.get('name')} × {ln.get('quantity', 1)}", money(ln.get("total"))])
    for key, label in (("visit_charge", "Visit charge"), ("supplies_charge", "Kit charge"), ("convenience_fee", "Convenience fee"), ("tax", "Taxes")):
        if Decimal(str(q.get(key) or 0)) > 0:
            lines.append([label, money(q[key])])
    if Decimal(str(q.get("discount") or 0)) > 0:
        lines.append(["Discount", f"− {money(q['discount'])}"])
    lines += [["Total", money(q.get("total"))], ["When", fmt_dt(scheduled_start)], ["Address", f"{addr['label']}: {addr['line1']}, {addr['city']}"],
              ["Payment", "Pay after service" if payment_mode == "cash" else "Online"]]
    payload = {"service_id": int(service_id), "items": items, "address_id": int(address_id), "scheduled_start": scheduled_start, "payment_mode": payment_mode,
               "coupon_code": coupon_code or "", "bring_supplies": bool(bring_supplies), "notes": notes or "Booked via Homigo Assist"}
    if partner_id:
        payload["partner_id"] = int(partner_id)
    return _propose(ctx, "create_booking", payload, f"Book {svc['name']}", lines)


def propose_cancel(ctx, booking_id, reason=""):
    b = ctx.client.get(f"/bookings/{int(booking_id)}/")
    p = ctx.client.get(f"/bookings/{int(booking_id)}/cancel-preview/")
    lines = [["Booking", f"{b.get('booking_no')} · {b.get('service_name')}"], ["When", fmt_dt(b.get("scheduled_start"))],
             ["Cancellation fee", money(p.get("fee", 0))], ["Refund", money(p.get("refund", 0))]]
    return _propose(ctx, "cancel_booking", {"booking_id": int(booking_id), "reason": reason or t("cancel_reason", ctx.lang)}, "Cancel booking", lines)


def propose_profile_update(ctx, first_name=None, last_name=None, email=None, language=None):
    data = {k: v for k, v in {"first_name": first_name, "last_name": last_name, "email": email, "language": language}.items() if v}
    if not data:
        return {"error": "Nothing to update."}
    return _propose(ctx, "update_profile", data, "Update profile", [[k.replace("_", " ").title(), str(v)] for k, v in data.items()])


def propose_address(ctx, line1, city, pincode, label="Home", line2="", landmark="", state=""):
    lat, lng = location(ctx)
    if not lat:
        return {"error": "Need the user's location (city/GPS) for the map pin. Ask them to pick a city or add the address on the address page.", "href": "/account"}
    data = {"label": label or "Home", "line1": line1, "line2": line2, "landmark": landmark, "city": city, "state": state, "pincode": str(pincode),
            "latitude": round(float(lat), 6), "longitude": round(float(lng), 6)}
    return _propose(ctx, "add_address", data, "Save address", [["Label", data["label"]], ["Address", f"{line1}, {line2} {landmark}".strip(" ,")], ["City", f"{city} {pincode}"],
                                                               ["Map pin", "Your current location (you can adjust it later)"]])


def propose_accept_job(ctx, request_id):
    return _propose(ctx, "accept_job", {"request_id": int(request_id)}, "Accept job request", [["Request", f"#{request_id}"]])


def propose_ticket(ctx, subject, message, category="other", booking_id=None):
    cats = {"booking", "quality", "payment", "safety", "partner", "verification", "other"}
    data = {"subject": subject[:150], "first_message": message[:2000], "category": category if category in cats else "other"}
    if booking_id:
        data["booking"] = int(booking_id)
    return _propose(ctx, "create_ticket", data, "Create support ticket", [["Topic", data["subject"]], ["Category", data["category"].title()]])


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------
def S(props=None, required=None):
    return {"type": "object", "properties": props or {}, "required": required or []}


ITEMS_SCHEMA = {"type": "array", "items": {"type": "object", "properties": {"service_item": {"type": "integer"}, "quantity": {"type": "integer"}}, "required": ["service_item"]}}

TOOLS = {
    "search_knowledge": (ALL, search_knowledge, "Search Homigo help articles (policies, how things work, partner info). Use for any question about Homigo.", S({"query": {"type": "string"}}, ["query"])),
    "search_services": (ALL, search_services, "Find services by keyword (shows cards).", S({"query": {"type": "string"}, "category_id": {"type": "integer"}})),
    "get_service": (ALL, get_service, "Get a service with its bookable items and prices.", S({"service_id": {"type": "integer"}}, ["service_id"])),
    "list_offers": (ALL, list_offers, "List active offers/coupons.", S()),
    "get_slots": (ALL, get_slots, "Free time slots near the user for a service on a date (YYYY-MM-DD).", S({"service_id": {"type": "integer"}, "day": {"type": "string"}}, ["service_id"])),
    "price_quote": (ALL, price_quote, "Exact price for selected items (server-side).", S({"service_id": {"type": "integer"}, "items": ITEMS_SCHEMA, "coupon_code": {"type": "string"}, "bring_supplies": {"type": "boolean"}}, ["service_id", "items"])),
    "navigate": (ALL, navigate, "Show a button that opens a page on the Homigo website, e.g. /services/5, /bookings, /partner/onboarding, /login, /faq.", S({"path": {"type": "string"}, "label": {"type": "string"}}, ["path"])),
    "my_profile": (SIGNED_IN, my_profile, "The signed-in user's profile.", S()),
    "list_addresses": (("customer",), list_addresses, "The customer's saved addresses.", S()),
    "my_bookings": (SIGNED_IN, my_bookings, "List bookings visible to this user. bucket: upcoming | past | today.", S({"bucket": {"type": "string"}})),
    "booking_details": (SIGNED_IN, booking_details, "Details of one booking by id.", S({"booking_id": {"type": "integer"}}, ["booking_id"])),
    "cancel_preview": (("customer",), cancel_preview, "Cancellation fee/refund for a booking.", S({"booking_id": {"type": "integer"}}, ["booking_id"])),
    "partner_status": (("partner",), partner_status, "Partner go-live checklist: what is done and what is pending.", S()),
    "partner_job_requests": (("partner",), partner_job_requests, "Open broadcast job requests for this partner.", S()),
    "partner_earnings": (("partner",), partner_earnings, "Partner earnings/wallet summary.", S()),
    "partner_dashboard": (("partner",), partner_dashboard, "Partner dashboard numbers.", S()),
    "coworker_jobs": (("coworker",), coworker_jobs, "Professional's jobs. bucket: today | upcoming | completed.", S({"bucket": {"type": "string"}})),
    "admin_dashboard": (("admin",), admin_dashboard, "Admin KPI numbers (read-only).", S()),
    "admin_find_booking": (("admin",), admin_find_booking, "Find bookings by booking number / phone / name (read-only).", S({"query": {"type": "string"}}, ["query"])),
    "admin_verification_queue": (("admin",), admin_verification_queue, "Open verification cases (read-only).", S()),
    # proposals (user must confirm)
    "propose_booking": (("customer",), propose_booking, "Prepare a booking for confirmation. Needs service_id, items, address_id, scheduled_start (ISO from get_slots), payment_mode cash|online.",
                        S({"service_id": {"type": "integer"}, "items": ITEMS_SCHEMA, "address_id": {"type": "integer"}, "scheduled_start": {"type": "string"},
                           "payment_mode": {"type": "string", "enum": ["cash", "online"]}, "coupon_code": {"type": "string"}, "bring_supplies": {"type": "boolean"}, "notes": {"type": "string"}},
                          ["service_id", "items", "address_id", "scheduled_start"])),
    "propose_cancel": (("customer",), propose_cancel, "Prepare cancelling a booking (shows fee) for confirmation.", S({"booking_id": {"type": "integer"}, "reason": {"type": "string"}}, ["booking_id"])),
    "propose_profile_update": (SIGNED_IN, propose_profile_update, "Prepare a profile update (name, email, language) for confirmation.",
                               S({"first_name": {"type": "string"}, "last_name": {"type": "string"}, "email": {"type": "string"}, "language": {"type": "string"}})),
    "propose_address": (("customer",), propose_address, "Prepare saving a new address for confirmation (uses the user's current map location).",
                        S({"line1": {"type": "string"}, "line2": {"type": "string"}, "landmark": {"type": "string"}, "city": {"type": "string"}, "pincode": {"type": "string"}, "label": {"type": "string"}, "state": {"type": "string"}},
                          ["line1", "city", "pincode"])),
    "propose_accept_job": (("partner",), propose_accept_job, "Prepare accepting a broadcast job request for confirmation.", S({"request_id": {"type": "integer"}}, ["request_id"])),
    "propose_ticket": (SIGNED_IN, propose_ticket, "Prepare a support ticket for confirmation. category: booking|quality|payment|safety|partner|verification|other.",
                       S({"subject": {"type": "string"}, "message": {"type": "string"}, "category": {"type": "string"}, "booking_id": {"type": "integer"}}, ["subject", "message"])),
}


def tools_for(role):
    return {name: spec for name, spec in TOOLS.items() if role in spec[0]}


def openai_tools(role):
    return [{"type": "function", "function": {"name": n, "description": spec[2], "parameters": spec[3]}} for n, spec in tools_for(role).items()]


def call(ctx, name, args):
    spec = TOOLS.get(name)
    if not spec:
        return {"error": f"Unknown tool {name}"}
    if ctx.role not in spec[0]:
        return {"error": "not_allowed_for_role", "message": "This needs a different account type or login."}
    try:
        return spec[1](ctx, **(args or {}))
    except HomigoError as e:
        return {"error": e.code, "message": e.message}
    except TypeError as e:
        return {"error": "bad_arguments", "message": str(e)}


# --------------------------------------------------------------------------------------
# Executing confirmed actions
# --------------------------------------------------------------------------------------
def execute_action(ctx, action):
    """Runs a confirmed PendingAction with the user's token. Returns (text, ui)."""
    p, lang = action.payload, ctx.lang
    if action.kind == "create_booking":
        b = ctx.client.post("/bookings/", p)
        nxt = t("booking_next_online" if p.get("payment_mode") == "online" else "booking_next_cash", lang)
        ctx.button("View booking" if lang == "en" else "बुकिंग देखें" if lang == "hi" else "Booking dekho", href=f"/bookings/{b['id']}")
        if p.get("payment_mode") == "online":
            ctx.set("navigate", f"/bookings/{b['id']}")
        return t("booking_created", lang, no=b.get("booking_no", ""), next=nxt), {"booking_id": b["id"], "booking_no": b.get("booking_no")}
    if action.kind == "cancel_booking":
        b = ctx.client.post(f"/bookings/{p['booking_id']}/cancel/", {"reason": p["reason"]})
        ctx.button("Open booking", href=f"/bookings/{b['id']}")
        return t("action_done", lang), {"status": b.get("status")}
    if action.kind == "update_profile":
        ctx.client.patch("/me/", p)
        return t("action_done", lang), {}
    if action.kind == "add_address":
        a = ctx.client.post("/addresses/", p)
        return t("action_done", lang), {"address_id": a.get("id")}
    if action.kind == "accept_job":
        r = ctx.client.post(f"/partner/job-requests/{p['request_id']}/accept/")
        bid = r.get("id")
        ctx.button("Open bookings", href=f"/partner/bookings/{bid}" if bid else "/partner/bookings")
        return t("action_done", lang), {}
    if action.kind == "create_ticket":
        tk = ctx.client.post("/tickets/", p)
        ctx.button("Open ticket", href="/support")
        return t("action_done", lang) + f" (#{tk.get('id')})", {"ticket_id": tk.get("id")}
    raise HomigoError("Unknown action", 400)


def days_choices(lang, n=4):
    out, today = [], date.today()
    for i in range(n):
        d = today + timedelta(days=i)
        label = t("today", lang) if i == 0 else t("tomorrow", lang) if i == 1 else d.strftime("%a %d %b")
        out.append((label, d.isoformat()))
    return out


def ctx_addresses(ctx):
    """Raw saved addresses (with lat/lng) for the signed-in customer."""
    return ctx.client.results(ctx.client.get("/addresses/"))
