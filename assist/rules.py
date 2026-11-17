"""Built-in rule-based assistant. Works with no AI key, and also handles the deterministic button flows
(booking wizard, confirmations) in AI mode. Replies follow the session language (en / hi / hinglish)."""
import re
from datetime import datetime

from . import knowledge
from . import tools as T
from .i18n import q, t

INTENTS = [
    ("human", ["human", "agent", "real person", "support team", "talk to", "complaint", "complain", "insaan", "shikayat", "baat karni", "baat karo", "customer care",
               "शिकायत", "सपोर्ट", "इंसान", "बात करनी"]),
    ("cancel", ["cancel", "radd", "रद्द", "cancel karo", "cancel krna"]),
    ("my_bookings", ["my booking", "my bookings", "booking status", "status", "meri booking", "mera order", "kab aayega", "where is my", "track",
                     "मेरी बुकिंग", "स्टेटस", "कब आएगा"]),
    ("partner_status", ["go live", "go-live", "golive", "checklist", "verification status", "kya baaki", "pending", "approved kab", "लाइव", "बाकी"]),
    ("job_requests", ["job request", "new job", "nayi job", "naya kaam", "requests", "नई जॉब"]),
    ("earnings", ["earning", "earnings", "kamai", "wallet", "payout", "settlement", "कमाई", "पैसा कब"]),
    ("today_jobs", ["today job", "today's job", "my jobs", "aaj ki job", "aaj ka kaam", "आज की जॉब"]),
    ("admin_summary", ["dashboard", "today's summary", "summary", "report", "aaj ka summary", "kpi"]),
    ("verification_queue", ["verification queue", "pending verification", "verification cases"]),
    ("profile", ["profile", "my name", "change name", "update email", "naam badal", "प्रोफ़ाइल", "प्रोफाइल"]),
    ("become_partner", ["become partner", "become a partner", "join as partner", "partner kaise", "partner bano", "पार्टनर"]),
    ("book", ["book", "booking", "chahiye", "chaiye", "karwana", "krwana", "lagwana", "banwana", "need a", "need an", "want a", "बुक", "चाहिए"]),
    ("greet", ["hi", "hello", "hey", "namaste", "namaskar", "hii", "good morning", "good evening", "नमस्ते", "हेलो", "help", "menu", "madad", "मदद"]),
]

BOOK_FILLER = {"book", "booking", "chahiye", "chaiye", "karwana", "krwana", "lagwana", "banwana", "need", "want", "a", "an", "the", "i", "mujhe", "please", "karna",
               "krna", "hai", "ek", "service", "for", "my", "home", "ghar", "par", "pe", "ka", "ki", "ke", "बुक", "चाहिए", "करना", "है", "मुझे", "kar", "do", "karo", "kro"}


QUESTION_WORDS = ("how", "what", "when", "why", "can i", "is there", "do you", "does", "kaise", "kya", "kab", "kitna", "kitne", "kyun", "kyu", "policy",
                  "कैसे", "क्या", "कब", "कितना", "क्यों")


PERSONAL = ("my", "mine", "mera", "meri", "mere", "mujhe", "hamara", "hamari", "pending", "baaki", "मेरा", "मेरी", "मेरे", "मुझे", "बाकी")


def is_personal(text):
    tl = text.lower()
    return any(re.search(rf"(?<![a-z\u0900-\u097F]){re.escape(w)}(?![a-z\u0900-\u097F])", tl) for w in PERSONAL)


def is_question(text):
    tl = text.lower().strip()
    return "?" in tl or any(re.search(rf"(?<![a-z\u0900-\u097F]){re.escape(w)}(?![a-z\u0900-\u097F])", tl) for w in QUESTION_WORDS)


# Common Hindi words -> English service keywords (services are named in English in the catalogue)
HI_SERVICE_WORDS = {
    "प्लंबर": "plumber", "प्लम्बर": "plumber", "नल": "plumber", "पाइप": "plumber", "इलेक्ट्रीशियन": "electrician", "बिजली": "electrician", "बिजलीवाला": "electrician",
    "सफाई": "cleaning", "क्लीनिंग": "cleaning", "डीप": "deep", "मेड": "maid", "बाई": "maid", "कामवाली": "maid", "गार्ड": "security", "सिक्योरिटी": "security",
    "चौकीदार": "security", "फिजियो": "physiotherapy", "फिजियोथेरेपी": "physiotherapy", "टेंट": "tent", "पानी": "water", "कैन": "water", "एसी": "ac",
    "safai": "cleaning", "bijli": "electrician", "nal": "plumber", "kaamwali": "maid", "bai": "maid", "chowkidar": "security", "paani": "water",
}


def to_service_query(words):
    return " ".join(HI_SERVICE_WORDS.get(w, w) for w in words if HI_SERVICE_WORDS.get(w, w) not in ("deep",) or len(words) > 1)


def detect_intent(text):
    tl = f" {text.lower()} "
    for name, words in INTENTS:
        for w in words:
            if (" " in w and w in tl) or re.search(rf"(?<![a-zऀ-ॿ]){re.escape(w)}(?![a-zऀ-ॿ])", tl):
                return name
    return None


def menu(ctx):
    r, L = ctx.role, ctx.lang
    keys = {
        "guest": ["book", "faq", "become_partner", "login", "human"],
        "customer": ["book", "my_bookings", "cancel", "profile", "human"],
        "partner": ["partner_status", "job_requests", "earnings", "my_bookings", "human"],
        "coworker": ["today_jobs", "faq", "profile", "human"],
        "admin": ["admin_summary", "verification_queue", "faq"],
    }[r]
    for k in keys:
        if k == "login":
            ctx.button(q("login", L), href="/login")
        else:
            ctx.quick(q(k, L), q(k, "en") if k != "verification_queue" else "verification queue")


def reply(ctx, text):
    """Returns assistant text; UI goes to ctx.ui."""
    L, role = ctx.lang, ctx.role
    raw = text.strip()

    # ---- button payloads (deterministic flows) ----
    if raw.startswith("__"):
        return _button(ctx, raw)

    # "my name is ..." -> prepare a profile update
    name_m = re.search(r"(?:my name is|mera naam|मेरा नाम)\s+([A-Za-z\u0900-\u097F]+)(?:\s+([A-Za-z\u0900-\u097F]+))?", raw, re.I)
    if name_m and role != "guest":
        last = (name_m.group(2) or "").title()
        if last.lower() in ("hai", "h", "है"):
            last = ""
        T.call(ctx, "propose_profile_update", {"first_name": name_m.group(1).title(), "last_name": last or None})
        return t("confirm_prompt", L)

    intent = detect_intent(raw)
    # Policy questions ("how do I cancel?", "refund kab milega?") are answered from the knowledge base first.
    if intent in ("cancel", "book", "my_bookings", "profile", "earnings", "partner_status") and is_question(raw) and not is_personal(raw):
        hits = knowledge.search(raw, role, limit=1)
        if hits and hits[0][0] >= 2:
            follow = {"cancel": "cancel", "book": "book", "my_bookings": "my_bookings", "earnings": "earnings", "partner_status": "partner_status"}.get(intent)
            if follow:
                ctx.quick(q(follow, L), q(follow, "en"))
            return f"**{hits[0][1]['title']}**\n{hits[0][1]['body']}"
    if intent == "greet" and len(raw.split()) <= 4:
        name = f" {ctx.user.get('first_name')}" if ctx.user and ctx.user.get("first_name") else ""
        menu(ctx)
        return t("greet", L, name=name)
    if intent == "human":
        return None  # caller escalates
    if intent == "cancel":
        return _need(ctx, ("customer",)) or _cancel_list(ctx)
    if intent == "my_bookings":
        if role == "guest":
            ctx.button(q("login", L), href="/login")
            return t("login_needed", L)
        if role == "coworker":
            return _today_jobs(ctx)
        res = T.call(ctx, "my_bookings", {"bucket": "upcoming"})
        if not res.get("bookings"):
            res = T.call(ctx, "my_bookings", {"bucket": "past"})
        if not res.get("bookings"):
            ctx.quick(q("book", L), "book")
            return t("no_bookings", L)
        return t("your_bookings", L)
    if intent == "partner_status":
        return _need(ctx, ("partner",)) or _partner_status(ctx)
    if intent == "job_requests":
        return _need(ctx, ("partner",)) or _job_requests(ctx)
    if intent == "earnings":
        return _need(ctx, ("partner",)) or _earnings(ctx)
    if intent == "today_jobs":
        return _need(ctx, ("coworker",)) or _today_jobs(ctx)
    if intent == "admin_summary":
        return _need(ctx, ("admin",)) or _admin_summary(ctx)
    if intent == "verification_queue":
        return _need(ctx, ("admin",)) or _verification(ctx)
    if intent == "profile":
        if role == "guest":
            ctx.button(q("login", L), href="/login")
            return t("login_needed", L)
        ctx.button({"en": "Open my account", "hi": "मेरा अकाउंट खोलें", "hinglish": "Account kholo"}[L], href="/partner/onboarding" if role == "partner" else "/account")
        return {"en": "You can update your name, email and addresses on your account page. Tell me what to change (e.g. \"my name is Priya Sharma\") and I'll prepare it for you.",
                "hi": "आप अपने अकाउंट पेज पर नाम, ईमेल और पते बदल सकते हैं। बताइए क्या बदलना है (जैसे \"मेरा नाम प्रिया शर्मा है\"), मैं तैयार कर दूँगा।",
                "hinglish": "Aap account page par naam, email aur address badal sakte hain. Bataiye kya badalna hai (jaise \"mera naam Priya Sharma hai\"), main ready kar dunga."}[L]
    # ---- book <something> ----
    if intent in ("book", "become_partner") or intent is None:
        if intent == "become_partner":
            hits = knowledge.search("how to become a partner", role, 1)
            ctx.button({"en": "Become a partner", "hi": "पार्टनर बनें", "hinglish": "Partner bano"}[L], href="/partner/join")
            return hits[0][1]["body"] if hits else ""
        words = [w for w in re.findall(r"[a-zA-Zऀ-ॿ]+", raw.lower()) if w not in BOOK_FILLER]
        if intent == "book":
            query = to_service_query(words)
            if query:
                res = T.call(ctx, "search_services", {"query": query})
                if res.get("services"):
                    return t("services_found", L)
            ctx.ui["cards"] = []
            T.call(ctx, "search_services", {"query": ""})
            return {"en": "Which service do you need? Pick one below or type it (e.g. \"plumber\", \"deep cleaning\").",
                    "hi": "आपको कौन सी सर्विस चाहिए? नीचे से चुनें या लिखें (जैसे \"प्लंबर\")।",
                    "hinglish": "Kaunsi service chahiye? Neeche se chuniye ya likhiye (jaise \"plumber\", \"deep cleaning\")."}[L]

    # ---- knowledge base ----
    hits = knowledge.search(raw, role, limit=2)
    if hits and hits[0][0] >= 2:
        best = hits[0][1]
        if len(hits) > 1 and hits[1][0] >= 2:
            ctx.quick(hits[1][1]["title"], hits[1][1]["title"])
        return f"**{best['title']}**\n{best['body']}"
    # maybe they typed a service name
    words = [w for w in re.findall(r"[a-zA-Z\u0900-\u097F]+", raw.lower()) if w not in BOOK_FILLER]
    res = T.call(ctx, "search_services", {"query": to_service_query(words) or raw}) if words else {}
    if res.get("services"):
        return t("services_found", L)
    ctx.ui["cards"] = []
    menu(ctx)
    ctx.quick(q("human", L), "human")
    return t("not_sure", L)


def _need(ctx, roles):
    if ctx.role in roles:
        return None
    if ctx.role == "guest":
        ctx.button(q("login", ctx.lang), href="/login")
        return t("login_needed", ctx.lang)
    return t("role_only", ctx.lang, role="/".join(roles))


# --------------------------------------------------------------------------------------
# Button flows
# --------------------------------------------------------------------------------------
def _button(ctx, raw):
    L = ctx.lang
    kind, _, val = raw[2:].partition(":")
    st = dict(ctx.session.state or {})
    if kind == "menu":
        menu(ctx)
        return t("menu_prompt", L)
    if kind == "stop":
        ctx.session.state = {}
        menu(ctx)
        return t("action_cancelled", L)
    if kind == "book":
        if ctx.role == "guest":
            ctx.button(q("login", L), href=f"/login?next=/services/{val}")
            ctx.button({"en": "Open service", "hi": "सर्विस खोलें", "hinglish": "Service kholo"}[L], href=f"/services/{val}")
            return t("login_needed", L)
        if ctx.role != "customer":
            ctx.button({"en": "Open service", "hi": "सर्विस खोलें", "hinglish": "Service kholo"}[L], href=f"/services/{val}")
            return t("role_only", L, role="customer")
        svc = T.call(ctx, "get_service", {"service_id": int(val)})
        if svc.get("error"):
            return t("action_failed", L, error=svc.get("message", ""))
        ctx.session.state = {"flow": "book", "service_id": svc["id"], "service": svc["name"]}
        for it in svc["items"][:8]:
            ctx.quick(f"{it['name']} · {T.money(it['price'])}", f"__item:{it['id']}")
        ctx.quick(q("stop", L), "__stop")
        ctx.button({"en": "See full details", "hi": "पूरी जानकारी", "hinglish": "Poori details"}[L], href=f"/services/{svc['id']}")
        return t("pick_items", L, service=svc["name"])
    if st.get("flow") != "book" and kind in ("item", "addr", "date", "slot", "pay"):
        menu(ctx)
        return t("menu_prompt", L)
    if kind == "item":
        st["items"] = [{"service_item": int(val), "quantity": 1}]
        ctx.session.state = st
        addrs = T.call(ctx, "list_addresses", {}).get("addresses", [])
        if not addrs:
            ctx.button({"en": "Add address", "hi": "पता जोड़ें", "hinglish": "Address add karo"}[L], href="/account")
            return t("no_address", L)
        for a in addrs[:5]:
            ctx.quick(f"{a['label']}: {a['text'][:40]}", f"__addr:{a['id']}")
        ctx.quick(q("stop", L), "__stop")
        return t("pick_address", L)
    if kind == "addr":
        addr = next((a for a in T.ctx_addresses(ctx) if a["id"] == int(val)), None)
        if addr:
            st["address_id"] = addr["id"]
            ctx.session.context = {**(ctx.session.context or {}), "lat": float(addr["latitude"]), "lng": float(addr["longitude"]), "city": addr["city"]}
        ctx.session.state = st
        for label, iso in T.days_choices(L):
            ctx.quick(label, f"__date:{iso}")
        return t("pick_date", L)
    if kind == "date":
        res = T.call(ctx, "get_slots", {"service_id": st["service_id"], "day": val})
        slots = res.get("free_slots", [])
        if not slots:
            for label, iso in T.days_choices(L):
                if iso != val:
                    ctx.quick(label, f"__date:{iso}")
            return t("no_slots", L) if not res.get("error") else t("action_failed", L, error=res.get("message") or res["error"])
        st["date"] = val
        ctx.session.state = st
        for s in slots[:10]:
            try:
                label = datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%I:%M %p").lstrip("0")
            except ValueError:
                label = s
            ctx.quick(label, f"__slot:{s}")
        return t("pick_slot", L)
    if kind == "slot":
        st["slot"] = val
        ctx.session.state = st
        ctx.quick(q("cash", L), "__pay:cash")
        ctx.quick(q("online", L), "__pay:online")
        return t("pick_payment", L)
    if kind == "pay":
        st["pay"] = val if val in ("cash", "online") else "cash"
        ctx.session.state = st
        res = T.call(ctx, "propose_booking", {"service_id": st["service_id"], "items": st["items"], "address_id": st["address_id"],
                                              "scheduled_start": st["slot"], "payment_mode": st["pay"]})
        if res.get("error"):
            return t("action_failed", L, error=res.get("message") or res["error"])
        return t("confirm_prompt", L)
    if kind == "cancel":
        res = T.call(ctx, "propose_cancel", {"booking_id": int(val)})
        return t("confirm_prompt", L) if not res.get("error") else t("action_failed", L, error=res.get("message") or res["error"])
    if kind == "accept_job":
        res = T.call(ctx, "propose_accept_job", {"request_id": int(val)})
        return t("confirm_prompt", L) if not res.get("error") else t("action_failed", L, error=res.get("message") or res["error"])
    menu(ctx)
    return t("menu_prompt", L)


def _cancel_list(ctx):
    L = ctx.lang
    res = T.call(ctx, "my_bookings", {"bucket": "upcoming"})
    cancellable = [b for b in res.get("bookings", []) if b["status"] not in ("completed", "cancelled", "in_progress", "completion_requested")]
    ctx.ui["cards"] = []
    if not cancellable:
        return t("no_bookings", L)
    for b in cancellable:
        ctx.card(title=f"{b['service']} · {b['booking_no']}", subtitle=T.fmt_dt(b["when"]), meta=str(b["status"]).replace("_", " ").title(),
                 value=f"__cancel:{b['id']}", action_label={"en": "Cancel this", "hi": "इसे रद्द करें", "hinglish": "Isse cancel karo"}[L])
    return {"en": "Which booking do you want to cancel?", "hi": "कौन सी बुकिंग रद्द करनी है?", "hinglish": "Kaunsi booking cancel karni hai?"}[L]


def _partner_status(ctx):
    res = T.call(ctx, "partner_status", {})
    if res.get("error"):
        return t("action_failed", ctx.lang, error=res.get("message", ""))
    return t("partner_live", ctx.lang) if res.get("is_live") else t("partner_checklist", ctx.lang)


def _job_requests(ctx):
    res = T.call(ctx, "partner_job_requests", {})
    return t("no_requests", ctx.lang) if not res.get("requests") else {"en": "Open job requests — tap one to accept:", "hi": "खुली जॉब रिक्वेस्ट — स्वीकार करने के लिए टैप करें:",
                                                                         "hinglish": "Open job requests — accept karne ke liye tap kariye:"}[ctx.lang]


def _earnings(ctx):
    e = T.call(ctx, "partner_earnings", {})
    if e.get("error"):
        return t("action_failed", ctx.lang, error=e.get("message", ""))
    rows = [("Wallet balance", e.get("wallet_balance")), ("Total earned (net)", e.get("total_net_earned")), ("Commission paid", e.get("total_commission")), ("Tips", e.get("tips"))]
    return "\n".join(f"• {k}: {T.money(v or 0)}" for k, v in rows)


def _today_jobs(ctx):
    res = T.call(ctx, "coworker_jobs", {"bucket": "today"})
    return t("no_jobs", ctx.lang) if not res.get("jobs") else {"en": "Your jobs today:", "hi": "आज की आपकी जॉब:", "hinglish": "Aaj ki aapki jobs:"}[ctx.lang]


def _admin_summary(ctx):
    d = T.call(ctx, "admin_dashboard", {})
    if d.get("error"):
        return t("action_failed", ctx.lang, error=d.get("message", ""))
    lines = [f"• {k.replace('_', ' ').capitalize()}: {v}" for k, v in d.items() if isinstance(v, (int, float, str)) and not k.endswith("_id")][:12]
    return "Today at a glance:\n" + "\n".join(lines)


def _verification(ctx):
    d = T.call(ctx, "admin_verification_queue", {})
    if d.get("error"):
        return t("action_failed", ctx.lang, error=d.get("message", ""))
    return f"Open verification cases: {d.get('open_cases', 0)}"
