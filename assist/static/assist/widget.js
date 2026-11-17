/*!
 * Homigo Assist chat widget — framework-free, embeddable on any site.
 *
 *   <script src="https://YOUR-HOST/assist/widget.js"></script>
 *   <script>
 *     HomigoAssist.init({
 *       apiBase: "https://YOUR-HOST/assist",          // Homigo Assist service
 *       getToken: () => localStorage.getItem("hs_token"), // signed-in user's Homigo token (optional)
 *       getContext: () => ({ page: location.pathname, city: "New Delhi", lat: 28.63, lng: 77.21 }),
 *       navigate: (path) => router.push(path),         // SPA navigation for buttons
 *     });
 *   </script>
 *
 * API: HomigoAssist.open(), .close(), .toggle(), .reset() (call after login/logout), .ask(text)
 */
(function () {
  "use strict";
  if (window.HomigoAssist && window.HomigoAssist.__loaded) return;

  var I18N = {
    en: { title: "Homigo Assist", sub: "Replies instantly · 24×7", placeholder: "Type your message…", send: "Send", human: "Talk to support", end: "End chat", newChat: "New chat",
      confirm: "Confirm", cancel: "Cancel", rate: "How was your chat?", feedback: "Anything we can improve? (optional)", submit: "Submit", thanks: "Thank you! 🙏",
      privacy: "Chats are saved to help you. Don't share card, bank or Aadhaar numbers.", tip: "Need help? Chat with us", offline: "Couldn't reach support. Please try again.",
      helpful: "Helpful", notHelpful: "Not helpful", menu: "Menu", close: "Close", done: "Done", lang: "Language", aiOn: "AI assistant", aiOff: "Assistant" },
    hi: { title: "Homigo Assist", sub: "तुरंत जवाब · 24×7", placeholder: "अपना संदेश लिखें…", send: "भेजें", human: "सपोर्ट से बात करें", end: "चैट खत्म करें", newChat: "नई चैट",
      confirm: "पक्का करें", cancel: "रद्द करें", rate: "चैट कैसी रही?", feedback: "कोई सुझाव? (वैकल्पिक)", submit: "भेजें", thanks: "धन्यवाद! 🙏",
      privacy: "चैट आपकी मदद के लिए सेव होती है। कार्ड, बैंक या आधार नंबर न लिखें।", tip: "मदद चाहिए? हमसे चैट करें", offline: "सपोर्ट से जुड़ नहीं पाए। फिर कोशिश करें।",
      helpful: "मददगार", notHelpful: "मददगार नहीं", menu: "मेन्यू", close: "बंद करें", done: "हो गया", lang: "भाषा", aiOn: "AI सहायक", aiOff: "सहायक" },
    hinglish: { title: "Homigo Assist", sub: "Turant jawab · 24×7", placeholder: "Apna message likhiye…", send: "Bhejo", human: "Support se baat karo", end: "Chat khatam karo", newChat: "Nayi chat",
      confirm: "Confirm", cancel: "Cancel", rate: "Chat kaisi rahi?", feedback: "Koi suggestion? (optional)", submit: "Bhejo", thanks: "Shukriya! 🙏",
      privacy: "Chat aapki madad ke liye save hoti hai. Card, bank ya Aadhaar number mat likhiye.", tip: "Madad chahiye? Chat kariye", offline: "Support se connect nahi ho paya. Dobara try kariye.",
      helpful: "Helpful", notHelpful: "Helpful nahi", menu: "Menu", close: "Band karo", done: "Ho gaya", lang: "Bhasha", aiOn: "AI assistant", aiOff: "Assistant" },
  };
  var LANG_LABEL = { en: "English", hi: "हिंदी", hinglish: "Hinglish" };

  var CSS = "\
:host{all:initial}\
*{box-sizing:border-box;font-family:Inter,system-ui,-apple-system,'Segoe UI',Roboto,'Noto Sans Devanagari',sans-serif}\
.launcher{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;color:#fff;\
background:linear-gradient(135deg,var(--c1),var(--c2));box-shadow:0 10px 30px rgba(79,70,229,.45);display:flex;align-items:center;justify-content:center;transition:transform .2s}\
.launcher:hover{transform:scale(1.07)}.launcher svg{width:28px;height:28px}\
.launcher .dot{position:absolute;top:4px;right:4px;width:13px;height:13px;border-radius:50%;background:#22c55e;border:2px solid #fff}\
.tip{position:fixed;right:90px;bottom:32px;z-index:2147483000;background:#fff;color:#0f172a;padding:10px 14px;border-radius:14px;font-size:14px;font-weight:600;\
box-shadow:0 10px 30px rgba(15,23,42,.18);display:flex;gap:8px;align-items:center;animation:pop .35s ease-out}\
.tip button{border:0;background:none;color:#94a3b8;cursor:pointer;font-size:16px;line-height:1}\
.panel{position:fixed;right:20px;bottom:92px;z-index:2147483001;width:384px;max-width:calc(100vw - 24px);height:620px;max-height:calc(100vh - 120px);\
background:#f8fafc;border-radius:22px;box-shadow:0 24px 60px rgba(15,23,42,.28);display:flex;flex-direction:column;overflow:hidden;animation:pop .25s ease-out}\
@media (max-width:520px){.panel{right:0;bottom:0;width:100vw;max-width:100vw;height:100%;max-height:100%;border-radius:0}.launcher.hide-m{display:none}.tip{display:none}}\
@keyframes pop{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:none}}\
.head{background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff;padding:14px 14px 14px 16px;display:flex;align-items:center;gap:10px}\
.avatar{width:38px;height:38px;border-radius:12px;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-weight:800}\
.htext{flex:1;min-width:0}.htitle{font-weight:700;font-size:15px}.hsub{font-size:12px;opacity:.85;display:flex;align-items:center;gap:6px}\
.hsub i{width:7px;height:7px;border-radius:50%;background:#4ade80;display:inline-block}\
.hbtn{border:0;background:rgba(255,255,255,.14);color:#fff;width:32px;height:32px;border-radius:10px;cursor:pointer;display:flex;align-items:center;justify-content:center}\
.hbtn:hover{background:rgba(255,255,255,.26)}.hbtn svg{width:18px;height:18px}\
select.lang{border:0;background:rgba(255,255,255,.14);color:#fff;border-radius:10px;height:32px;padding:0 6px;font-size:12px;cursor:pointer}\
select.lang option{color:#0f172a}\
.menu{position:absolute;right:12px;top:62px;background:#fff;border-radius:14px;box-shadow:0 12px 30px rgba(15,23,42,.2);padding:6px;z-index:5;min-width:190px}\
.menu button{display:block;width:100%;text-align:left;border:0;background:none;padding:10px 12px;border-radius:10px;font-size:14px;color:#0f172a;cursor:pointer}\
.menu button:hover{background:#f1f5f9}\
.body{flex:1;overflow-y:auto;padding:16px 14px 8px;display:flex;flex-direction:column;gap:10px}\
.row{display:flex;gap:8px;align-items:flex-end}.row.user{justify-content:flex-end}\
.mini{width:26px;height:26px;border-radius:9px;background:linear-gradient(135deg,var(--c1),var(--c2));color:#fff;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;flex:none}\
.bubble{max-width:82%;padding:10px 13px;border-radius:16px;font-size:14px;line-height:1.5;white-space:pre-wrap;word-wrap:break-word}\
.assistant .bubble{background:#fff;color:#0f172a;border-bottom-left-radius:5px;box-shadow:0 1px 2px rgba(15,23,42,.06);border:1px solid #eef2f7}\
.user .bubble{background:var(--c1);color:#fff;border-bottom-right-radius:5px}\
.system{align-self:center;font-size:11px;color:#94a3b8}\
.extra{margin-left:34px;display:flex;flex-direction:column;gap:8px;max-width:calc(100% - 34px)}\
.cards{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;scrollbar-width:thin}\
.card{min-width:180px;max-width:200px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:10px 12px;cursor:pointer;flex:none;text-align:left;transition:border-color .15s,box-shadow .15s}\
.card:hover{border-color:var(--c1);box-shadow:0 4px 14px rgba(79,70,229,.15)}\
.card b{display:block;font-size:13px;color:#0f172a}.card span{display:block;font-size:12px;color:#64748b;margin-top:2px}.card em{display:block;font-style:normal;font-size:12px;font-weight:700;color:var(--c1);margin-top:6px}\
.btns{display:flex;flex-wrap:wrap;gap:6px}\
.lnk{border:1px solid var(--c1);color:var(--c1);background:#fff;border-radius:999px;padding:7px 12px;font-size:13px;font-weight:600;cursor:pointer}\
.lnk:hover{background:var(--c1);color:#fff}\
.chips{display:flex;flex-wrap:wrap;gap:6px}\
.chip{border:1px solid #c7d2fe;background:#eef2ff;color:#3730a3;border-radius:999px;padding:7px 12px;font-size:13px;cursor:pointer}\
.chip:hover{background:#e0e7ff}\
.check{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:10px 12px;font-size:13px}\
.check div{display:flex;gap:8px;align-items:flex-start;padding:3px 0}.ok{color:#16a34a}.no{color:#dc2626}\
.confirm{background:#fff;border:2px solid var(--c1);border-radius:16px;padding:12px;font-size:13px}\
.confirm h4{margin:0 0 8px;font-size:14px;color:#0f172a}\
.confirm table{width:100%;border-collapse:collapse}.confirm td{padding:4px 0;color:#334155;vertical-align:top}.confirm td:last-child{text-align:right;font-weight:600;color:#0f172a}\
.confirm .acts{display:flex;gap:8px;margin-top:10px}\
.btn{flex:1;border:0;border-radius:12px;padding:10px;font-weight:700;font-size:14px;cursor:pointer}\
.btn.p{background:var(--c1);color:#fff}.btn.p:hover{filter:brightness(1.07)}.btn.s{background:#f1f5f9;color:#334155}\
.btn:disabled{opacity:.55;cursor:default}\
.fb{display:flex;gap:4px;margin-left:34px}.fb button{border:0;background:none;cursor:pointer;font-size:13px;opacity:.45;padding:2px 4px}.fb button:hover,.fb button.on{opacity:1}\
.typing{display:flex;gap:4px;padding:12px 14px}.typing span{width:7px;height:7px;border-radius:50%;background:#94a3b8;animation:b 1.2s infinite}\
.typing span:nth-child(2){animation-delay:.15s}.typing span:nth-child(3){animation-delay:.3s}\
@keyframes b{0%,60%,100%{transform:translateY(0);opacity:.5}30%{transform:translateY(-5px);opacity:1}}\
.foot{border-top:1px solid #e2e8f0;background:#fff;padding:10px 10px 8px}\
.inrow{display:flex;gap:8px;align-items:flex-end}\
textarea{flex:1;resize:none;border:1px solid #e2e8f0;border-radius:14px;padding:10px 12px;font-size:14px;max-height:110px;min-height:42px;outline:none;color:#0f172a;background:#f8fafc}\
textarea:focus{border-color:var(--c1);background:#fff}\
.send{width:42px;height:42px;border-radius:12px;border:0;background:var(--c1);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none}\
.send:disabled{opacity:.5;cursor:default}.send svg{width:18px;height:18px}\
.priv{font-size:10.5px;color:#94a3b8;margin-top:6px;text-align:center}\
.rate{padding:24px 18px;text-align:center}.rate h3{margin:0 0 10px;font-size:16px;color:#0f172a}\
.stars{display:flex;justify-content:center;gap:6px;margin:8px 0 12px}.stars button{border:0;background:none;font-size:30px;cursor:pointer;color:#cbd5e1}.stars button.on{color:#f59e0b}\
.rate textarea{width:100%;margin-bottom:10px}\
a{color:var(--c1)}\
";

  var ICON = {
    chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8M8 13h5"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg>',
    more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>',
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg>',
  };

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function (c) { if (c) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function md(s) { // tiny safe markdown: **bold**, links to same-site paths
    return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } }
  function hash(s) { var h = 0; s = String(s || "guest"); for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); }

  var A = {
    __loaded: true, opts: null, root: null, shadow: null, isOpen: false, session: null, messages: [], busy: false, lang: "en", view: "chat",

    init: function (opts) {
      this.opts = Object.assign({ apiBase: "", getToken: function () { return null; }, getContext: function () { return { page: location.pathname }; },
        navigate: function (p) { location.href = p; }, colors: ["#4f46e5", "#7c3aed"], showTip: true }, opts || {});
      this.opts.apiBase = this.opts.apiBase.replace(/\/$/, "");
      this.lang = store("homigo_assist_lang") || this.opts.language || "en";
      if (!this.root) this._mount();
      return this;
    },

    _mount: function () {
      this.root = el("div", { id: "homigo-assist" });
      document.body.appendChild(this.root);
      this.shadow = this.root.attachShadow({ mode: "open" });
      var st = el("style", { text: CSS });
      this.shadow.appendChild(st);
      this.root.style.setProperty("--c1", this.opts.colors[0]);
      this.root.style.setProperty("--c2", this.opts.colors[1]);
      this.wrap = el("div");
      this.wrap.style.setProperty("--c1", this.opts.colors[0]);
      this.wrap.style.setProperty("--c2", this.opts.colors[1]);
      this.shadow.appendChild(this.wrap);
      this._render();
    },

    _t: function (k) { return (I18N[this.lang] || I18N.en)[k] || I18N.en[k]; },
    _key: function () { return "homigo_assist_session_" + hash(this.opts.getToken && this.opts.getToken()); },

    _api: function (method, path, body) {
      var headers = { "Content-Type": "application/json" };
      var tok = this.opts.getToken && this.opts.getToken();
      if (tok) headers.Authorization = "Token " + tok;
      return fetch(this.opts.apiBase + path, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { if (!r.ok) throw d; return d; }); });
    },
    _context: function () { try { return this.opts.getContext() || {}; } catch (e) { return {}; } },

    open: function () {
      this.isOpen = true; store("homigo_assist_tip", "1");
      if (!this.session) this._start(); else this._render();
      this._render();
    },
    close: function () { this.isOpen = false; this.menuOpen = false; this._render(); },
    toggle: function () { this.isOpen ? this.close() : this.open(); },
    reset: function () { this.session = null; this.messages = []; this.view = "chat"; if (this.isOpen) this._start(); else this._render(); },
    ask: function (text) { var self = this; if (!this.session) { this.open(); setTimeout(function () { self.send(text); }, 600); } else { this.open(); this.send(text); } },

    _start: function (fresh) {
      var self = this; this.busy = true; this.view = "chat"; this._render();
      var sid = fresh ? null : store(this._key());
      this._api("POST", "/api/sessions/", { session_id: sid, language: this.lang, context: this._context() })
        .then(function (d) { self.session = d.session; self.messages = d.messages || []; self.lang = d.session.language || self.lang; store(self._key(), d.session.id); })
        .catch(function () { self.messages = [{ role: "assistant", text: self._t("offline"), ui: {} }]; })
        .then(function () { self.busy = false; self._render(); });
    },

    send: function (text, display) {
      var self = this; text = (text || "").trim();
      if (!text || this.busy || !this.session) return;
      this.messages.push({ role: "user", text: text, ui: display ? { display: display } : {}, _local: true });
      this.busy = true; this._forceBottom = true; this._render();
      this._api("POST", "/api/sessions/" + this.session.id + "/messages/", { text: text, display: display || "", language: this.langChanged ? this.lang : undefined, context: this._context() })
        .then(function (d) {
          self.messages = self.messages.filter(function (m) { return !m._local; }).concat(d.messages || []);
          if (d.session) { self.session = d.session; self.lang = d.session.language || self.lang; }
          self.langChanged = false; self._after(d.messages);
        })
        .catch(function (e) {
          if (e && e.code === "ERROR" && /not found/i.test(e.message || "")) { store(self._key(), null); self.session = null; return self._start(true); }
          self.messages.push({ role: "assistant", text: self._t("offline"), ui: {} });
        })
        .then(function () { self.busy = false; self._forceBottom = true; self._render(); });
    },

    _after: function (msgs) {
      var self = this;
      (msgs || []).forEach(function (m) { if (m.ui && m.ui.navigate) setTimeout(function () { self.opts.navigate(m.ui.navigate); }, 900); });
    },

    _decide: function (actionId, decision, btns) {
      var self = this; if (this.busy) return;
      btns.forEach(function (b) { b.disabled = true; });
      this.busy = true; this._render();
      this._api("POST", "/api/sessions/" + this.session.id + "/actions/" + actionId + "/", { decision: decision })
        .then(function (d) { self.messages = self.messages.concat(d.messages || []); self._doneActions = (self._doneActions || {}); self._doneActions[actionId] = decision; self._after(d.messages); })
        .catch(function () { self.messages.push({ role: "assistant", text: self._t("offline"), ui: {} }); })
        .then(function () { self.busy = false; self._render(); });
    },

    _escalate: function () {
      var self = this; this.menuOpen = false; if (!this.session || this.busy) return;
      this.busy = true; this._render();
      this._api("POST", "/api/sessions/" + this.session.id + "/escalate/", { reason: "user pressed Talk to support" })
        .then(function (d) { self.messages = self.messages.concat(d.messages || []); })
        .catch(function () { self.messages.push({ role: "assistant", text: self._t("offline"), ui: {} }); })
        .then(function () { self.busy = false; self._render(); });
    },

    _end: function (rating, feedback) {
      var self = this;
      if (!this.session) return;
      this._api("POST", "/api/sessions/" + this.session.id + "/end/", { rating: rating, feedback: feedback }).catch(function () {});
      store(this._key(), null);
      this.view = "thanks"; this._render();
      setTimeout(function () { self.session = null; self.messages = []; self.view = "chat"; if (self.isOpen) self._start(true); }, 2200);
    },

    _feedback: function (m, helpful) {
      if (!this.session || !m.id) return;
      m.helpful = helpful; this._render();
      this._api("POST", "/api/sessions/" + this.session.id + "/messages/" + m.id + "/feedback/", { helpful: helpful }).catch(function () {});
    },

    _go: function (href) {
      if (!href) return;
      if (/^https?:\/\//.test(href)) window.open(href, "_blank", "noopener"); else this.opts.navigate(href);
      if (window.innerWidth <= 520) this.close();
    },

    _render: function () {
      var self = this, w = this.wrap; if (!w) return;
      var prevTop = this.bodyEl ? this.bodyEl.scrollTop : 0;
      var keepScroll = !this.bodyEl || !this.bodyEl.isConnected || this.bodyEl.scrollHeight - this.bodyEl.scrollTop - this.bodyEl.clientHeight < 120 || this._forceBottom;
      this._forceBottom = false;
      var draft = this.inputEl ? this.inputEl.value : "";
      w.innerHTML = "";
      w.appendChild(el("button", { class: "launcher" + (this.isOpen ? " hide-m" : ""), "aria-label": this.isOpen ? this._t("close") : this._t("tip"),
        html: (this.isOpen ? ICON.down : ICON.chat) + (this.isOpen ? "" : '<span class="dot"></span>'), onclick: function () { self.toggle(); } }));
      if (!this.isOpen) {
        if (this.opts.showTip && !store("homigo_assist_tip")) {
          w.appendChild(el("div", { class: "tip" }, [this._t("tip"), el("button", { "aria-label": "dismiss", text: "×", onclick: function () { store("homigo_assist_tip", "1"); self._render(); } })]));
        }
        return;
      }
      var panel = el("div", { class: "panel", role: "dialog", "aria-label": this._t("title") });
      // header
      var langSel = el("select", { class: "lang", "aria-label": this._t("lang"), onchange: function (e) { self.lang = e.target.value; self.langChanged = true; store("homigo_assist_lang", self.lang); self._render(); } });
      Object.keys(LANG_LABEL).forEach(function (k) { var o = el("option", { value: k, text: LANG_LABEL[k] }); if (k === self.lang) o.selected = true; langSel.appendChild(o); });
      panel.appendChild(el("div", { class: "head" }, [
        el("div", { class: "avatar", text: "H" }),
        el("div", { class: "htext" }, [el("div", { class: "htitle", text: this._t("title") }), el("div", { class: "hsub", html: "<i></i>" + esc((this.session && this.session.ai_mode ? this._t("aiOn") : this._t("aiOff")) + " · " + this._t("sub")) })]),
        langSel,
        el("button", { class: "hbtn", "aria-label": this._t("menu"), html: ICON.more, onclick: function () { self.menuOpen = !self.menuOpen; self._render(); } }),
        el("button", { class: "hbtn", "aria-label": this._t("close"), html: ICON.close, onclick: function () { self.close(); } }),
      ]));
      if (this.menuOpen) {
        panel.appendChild(el("div", { class: "menu" }, [
          el("button", { text: "🎧 " + this._t("human"), onclick: function () { self._escalate(); } }),
          el("button", { text: "✨ " + this._t("newChat"), onclick: function () { self.menuOpen = false; if (self.session) self._api("POST", "/api/sessions/" + self.session.id + "/end/", {}).catch(function () {}); store(self._key(), null); self.session = null; self._start(true); } }),
          el("button", { text: "⭐ " + this._t("end"), onclick: function () { self.menuOpen = false; self.view = "rate"; self._render(); } }),
        ]));
      }
      if (this.view === "rate" || this.view === "thanks") {
        panel.appendChild(this._rateView());
        w.appendChild(panel);
        return;
      }
      // body
      var body = el("div", { class: "body", "aria-live": "polite" });
      var lastAssistant = -1;
      this.messages.forEach(function (m, i) { if (m.role === "assistant") lastAssistant = i; });
      this.messages.forEach(function (m, i) { self._renderMsg(body, m, i === lastAssistant, i); });
      if (this.busy) body.appendChild(el("div", { class: "row assistant" }, [el("div", { class: "mini", text: "H" }), el("div", { class: "bubble typing", html: "<span></span><span></span><span></span>" })]));
      panel.appendChild(body);
      // footer
      var ta = el("textarea", { rows: "1", placeholder: this._t("placeholder"), "aria-label": this._t("placeholder") });
      ta.value = draft;
      ta.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); var v = ta.value; ta.value = ""; self.send(v); } });
      ta.addEventListener("input", function () { ta.style.height = "auto"; ta.style.height = Math.min(110, ta.scrollHeight) + "px"; });
      var sendBtn = el("button", { class: "send", "aria-label": this._t("send"), html: ICON.send, onclick: function () { var v = ta.value; ta.value = ""; self.send(v); } });
      if (this.busy) sendBtn.disabled = true;
      panel.appendChild(el("div", { class: "foot" }, [el("div", { class: "inrow" }, [ta, sendBtn]), el("div", { class: "priv", text: this._t("privacy") })]));
      w.appendChild(panel);
      this.bodyEl = body; this.inputEl = ta;
      body.scrollTop = keepScroll ? body.scrollHeight : prevTop;
      if (!this.busy) setTimeout(function () { try { ta.focus({ preventScroll: true }); } catch (e) {} }, 30);
    },

    _renderMsg: function (body, m, isLast, idx) {
      var self = this, ui = m.ui || {};
      if (m.role === "system") return;
      if (m.role === "user") {
        var shown = ui.display || (m.text.indexOf("__") === 0 ? "✓" : m.text);
        body.appendChild(el("div", { class: "row user" }, [el("div", { class: "bubble", text: shown })]));
        return;
      }
      if (m.text) body.appendChild(el("div", { class: "row assistant" }, [el("div", { class: "mini", text: "H" }), el("div", { class: "bubble", html: md(m.text) })]));
      var extra = el("div", { class: "extra" });
      if (ui.checklist && ui.checklist.length) {
        extra.appendChild(el("div", { class: "check" }, ui.checklist.map(function (c) {
          return el("div", {}, [el("span", { class: c.ok ? "ok" : "no", text: c.ok ? "✔" : "✖" }), el("span", { text: c.label })]);
        })));
      }
      if (ui.cards && ui.cards.length) {
        extra.appendChild(el("div", { class: "cards" }, ui.cards.map(function (c) {
          return el("button", { class: "card", onclick: function () { if (c.value && (isLast || !c.href)) self.send(c.value, c.title); else self._go(c.href); } }, [
            el("b", { text: c.title }), c.subtitle ? el("span", { text: c.subtitle }) : null, c.meta ? el("span", { text: c.meta }) : null,
            el("em", { text: c.action_label || (c.value && c.value.indexOf("__book") === 0 ? "Book →" : c.value && c.value.indexOf("__accept") === 0 ? "Accept →" : "Open →") }),
          ]);
        })));
      }
      if (ui.confirm) {
        var done = (this._doneActions || {})[ui.confirm.action_id];
        var tbl = el("table", {}, ui.confirm.lines.map(function (l) { return el("tr", {}, [el("td", { text: l[0] }), el("td", { text: l[1] })]); }));
        var bC = el("button", { class: "btn p", text: done === "confirm" ? this._t("done") : this._t("confirm") });
        var bX = el("button", { class: "btn s", text: this._t("cancel") });
        if (done || !isLast) { bC.disabled = true; bX.disabled = true; }
        bC.onclick = function () { self._decide(ui.confirm.action_id, "confirm", [bC, bX]); };
        bX.onclick = function () { self._decide(ui.confirm.action_id, "cancel", [bC, bX]); };
        extra.appendChild(el("div", { class: "confirm" }, [el("h4", { text: ui.confirm.title }), tbl, el("div", { class: "acts" }, [bX, bC])]));
      }
      if (ui.buttons && ui.buttons.length) {
        extra.appendChild(el("div", { class: "btns" }, ui.buttons.map(function (b) {
          return el("button", { class: "lnk", text: b.label + (b.href ? " →" : ""), onclick: function () { if (b.href) self._go(b.href); else self.send(b.value, b.label); } });
        })));
      }
      if (isLast && ui.quick_replies && ui.quick_replies.length) {
        extra.appendChild(el("div", { class: "chips" }, ui.quick_replies.map(function (qr) {
          return el("button", { class: "chip", text: qr.label, onclick: function () { self.send(qr.value, qr.label); } });
        })));
      }
      if (extra.childNodes.length) body.appendChild(extra);
      if (m.id && idx > 0 && m.text) {
        body.appendChild(el("div", { class: "fb" }, [
          el("button", { class: m.helpful === true ? "on" : "", title: this._t("helpful"), "aria-label": this._t("helpful"), text: "👍", onclick: function () { self._feedback(m, true); } }),
          el("button", { class: m.helpful === false ? "on" : "", title: this._t("notHelpful"), "aria-label": this._t("notHelpful"), text: "👎", onclick: function () { self._feedback(m, false); } }),
        ]));
      }
    },

    _rateView: function () {
      var self = this;
      if (this.view === "thanks") return el("div", { class: "rate" }, [el("h3", { text: this._t("thanks") })]);
      var rating = 0, starsEl = el("div", { class: "stars" });
      var fb = el("textarea", { rows: "2", placeholder: this._t("feedback") });
      function paint() { Array.prototype.forEach.call(starsEl.children, function (b, i) { b.className = i < rating ? "on" : ""; }); }
      for (var i = 1; i <= 5; i++) (function (n) { starsEl.appendChild(el("button", { "aria-label": n + " star", text: "★", onclick: function () { rating = n; paint(); } })); })(i);
      return el("div", { class: "rate" }, [el("h3", { text: this._t("rate") }), starsEl, fb,
        el("div", { class: "acts", style: "display:flex;gap:8px" }, [
          el("button", { class: "btn s", text: this._t("cancel"), onclick: function () { self.view = "chat"; self._render(); } }),
          el("button", { class: "btn p", text: this._t("submit"), onclick: function () { self._end(rating || null, fb.value); } }),
        ])]);
    },
  };

  window.HomigoAssist = A;
})();
