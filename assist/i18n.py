"""Language detection + UI/rule-engine strings for English, Hindi (Devanagari) and Hinglish.
Add a new language by adding a column to STRINGS and a detector rule."""
import re

LANGS = ("en", "hi", "hinglish")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HINGLISH_WORDS = {
    "kya", "hai", "h", "hain", "mujhe", "mera", "meri", "mere", "karna", "krna", "kro", "karo", "chahiye", "chaiye", "kaise",
    "kab", "kahan", "kitna", "kitne", "nahi", "nhi", "haan", "ha", "ji", "bhai", "aap", "tum", "hum", "kaun", "kyun", "kyu",
    "batao", "btao", "bataiye", "dikhao", "wala", "wali", "abhi", "kal", "aaj", "paisa", "paise", "theek", "thik", "accha",
    "acha", "sahi", "lagwana", "banwana", "chalega", "krdo", "kardo", "ho", "gaya", "gya", "raha", "rha", "se", "ko", "ka", "ki",
}


def detect_language(text, current="en"):
    if not text:
        return current
    if _DEVANAGARI.search(text):
        return "hi"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return current
    hits = sum(1 for w in words if w in _HINGLISH_WORDS)
    if hits >= 2 or (hits == 1 and len(words) <= 3):
        return "hinglish"
    if len(words) >= 3:
        return "en"
    return current


STRINGS = {
    "greet": {
        "en": "Hi{name}! I'm Homigo Assist. I can answer questions, book a service, check your bookings and connect you to our team. How can I help?",
        "hi": "नमस्ते{name}! मैं Homigo Assist हूँ। मैं सवालों के जवाब, सर्विस बुकिंग, आपकी बुकिंग का स्टेटस और हमारी टीम से बात कराने में मदद कर सकता हूँ। बताइए, क्या मदद करूँ?",
        "hinglish": "Namaste{name}! Main Homigo Assist hoon. Main sawaalon ke jawab, service booking, booking status aur team se baat karane mein madad kar sakta hoon. Bataiye, kya madad karoon?",
    },
    "menu_prompt": {"en": "Here's what I can do:", "hi": "मैं ये कर सकता हूँ:", "hinglish": "Main ye kar sakta hoon:"},
    "not_sure": {
        "en": "I'm not fully sure about that. You can rephrase, pick an option below, or talk to our support team.",
        "hi": "मुझे इसका पक्का जवाब नहीं पता। आप दूसरे शब्दों में पूछें, नीचे से कोई विकल्प चुनें, या हमारी सपोर्ट टीम से बात करें।",
        "hinglish": "Mujhe iska pakka jawab nahi pata. Aap dusre shabdon mein poochiye, neeche se option chuniye, ya support team se baat kariye.",
    },
    "kb_lead": {"en": "Here's what I found:", "hi": "यह जानकारी मिली:", "hinglish": "Ye jaankari mili:"},
    "login_needed": {
        "en": "Please log in first so I can do this for your account.",
        "hi": "यह आपके अकाउंट के लिए करने के लिए कृपया पहले लॉग इन करें।",
        "hinglish": "Ye aapke account ke liye karne ke liye pehle login kariye.",
    },
    "role_only": {
        "en": "This option is available for {role} accounts only.",
        "hi": "यह विकल्प केवल {role} अकाउंट के लिए है।",
        "hinglish": "Ye option sirf {role} account ke liye hai.",
    },
    "services_found": {"en": "These services match:", "hi": "ये सर्विस मिलीं:", "hinglish": "Ye services mili:"},
    "no_services": {
        "en": "I couldn't find that service. Try another word, or browse all services.",
        "hi": "यह सर्विस नहीं मिली। कोई दूसरा शब्द आज़माएँ या सभी सर्विस देखें।",
        "hinglish": "Ye service nahi mili. Koi aur shabd try kariye ya saari services dekhiye.",
    },
    "no_bookings": {"en": "You don't have any bookings yet.", "hi": "अभी आपकी कोई बुकिंग नहीं है।", "hinglish": "Abhi aapki koi booking nahi hai."},
    "your_bookings": {"en": "Your bookings:", "hi": "आपकी बुकिंग:", "hinglish": "Aapki bookings:"},
    "pick_items": {
        "en": "Great choice — {service}. What do you need? Tap an option (you can add more later).",
        "hi": "बढ़िया — {service}। आपको क्या चाहिए? एक विकल्प चुनें।",
        "hinglish": "Badhiya — {service}. Aapko kya chahiye? Ek option chuniye.",
    },
    "pick_address": {"en": "Which address should the pro come to?", "hi": "प्रोफेशनल किस पते पर आए?", "hinglish": "Pro kis address par aaye?"},
    "no_address": {
        "en": "You don't have a saved address yet. Please add one — I'll open the address page for you.",
        "hi": "आपका कोई पता सेव नहीं है। कृपया एक पता जोड़ें — मैं पेज खोल देता हूँ।",
        "hinglish": "Aapka koi address saved nahi hai. Pehle ek address add kariye — main page khol deta hoon.",
    },
    "pick_date": {"en": "Which day?", "hi": "कौन सा दिन?", "hinglish": "Kaunsa din?"},
    "pick_slot": {"en": "Pick a time slot:", "hi": "समय चुनें:", "hinglish": "Time slot chuniye:"},
    "no_slots": {
        "en": "No free slots on that day near your address. Try another day.",
        "hi": "उस दिन आपके पास कोई स्लॉट खाली नहीं है। दूसरा दिन चुनें।",
        "hinglish": "Us din koi slot khaali nahi hai. Dusra din chuniye.",
    },
    "pick_payment": {"en": "How would you like to pay?", "hi": "भुगतान कैसे करेंगे?", "hinglish": "Payment kaise karenge?"},
    "confirm_prompt": {
        "en": "Please check the details and tap Confirm.",
        "hi": "कृपया विवरण जाँचें और Confirm दबाएँ।",
        "hinglish": "Details check karke Confirm dabaiye.",
    },
    "action_done": {"en": "Done! ✅", "hi": "हो गया! ✅", "hinglish": "Ho gaya! ✅"},
    "action_cancelled": {"en": "Okay, I've cancelled that request.", "hi": "ठीक है, वह अनुरोध रद्द कर दिया।", "hinglish": "Theek hai, wo request cancel kar di."},
    "action_failed": {"en": "That didn't go through: {error}", "hi": "यह नहीं हो पाया: {error}", "hinglish": "Ye nahi ho paya: {error}"},
    "booking_created": {
        "en": "Your booking {no} is placed. {next}",
        "hi": "आपकी बुकिंग {no} हो गई है। {next}",
        "hinglish": "Aapki booking {no} ho gayi hai. {next}",
    },
    "booking_next_cash": {"en": "We're finding the best pro for you.", "hi": "हम आपके लिए सबसे अच्छा प्रोफेशनल ढूँढ रहे हैं।", "hinglish": "Hum aapke liye best pro dhoondh rahe hain."},
    "booking_next_online": {"en": "Please complete the payment on the booking page.", "hi": "कृपया बुकिंग पेज पर भुगतान पूरा करें।", "hinglish": "Booking page par payment complete kariye."},
    "escalated": {
        "en": "I've shared a summary of our chat with the Homigo support team{ticket}. They'll get back to you soon.",
        "hi": "मैंने हमारी बातचीत का सार Homigo सपोर्ट टीम को भेज दिया है{ticket}। वे जल्द संपर्क करेंगे।",
        "hinglish": "Maine hamari chat ka summary Homigo support team ko bhej diya hai{ticket}. Wo jaldi contact karenge.",
    },
    "escalate_guest": {
        "en": "To connect you with our team, please log in (so they can reach you) — or share your phone number here.",
        "hi": "टीम से जोड़ने के लिए कृपया लॉग इन करें — या यहाँ अपना फ़ोन नंबर लिखें।",
        "hinglish": "Team se connect karne ke liye login kariye — ya yahan apna phone number likhiye.",
    },
    "ended": {"en": "Thanks for chatting! How was your experience?", "hi": "बात करने के लिए धन्यवाद! आपका अनुभव कैसा रहा?", "hinglish": "Chat ke liye shukriya! Experience kaisa raha?"},
    "pii_warning": {
        "en": "For your safety, please don't share Aadhaar, card or bank numbers in chat. I've hidden it.",
        "hi": "आपकी सुरक्षा के लिए चैट में आधार, कार्ड या बैंक नंबर न लिखें। मैंने इसे छुपा दिया है।",
        "hinglish": "Safety ke liye chat mein Aadhaar, card ya bank number mat likhiye. Maine use chhupa diya hai.",
    },
    "rate_limited": {"en": "You're sending messages too fast. Please wait a moment.", "hi": "आप बहुत जल्दी संदेश भेज रहे हैं। थोड़ा रुकें।", "hinglish": "Aap bahut jaldi messages bhej rahe hain. Thoda rukiye."},
    "limit_reached": {
        "en": "This chat has become long. Please start a new chat or talk to our team.",
        "hi": "यह चैट बहुत लंबी हो गई है। नई चैट शुरू करें या टीम से बात करें।",
        "hinglish": "Ye chat lambi ho gayi hai. Nayi chat shuru kariye ya team se baat kariye.",
    },
    "partner_checklist": {"en": "Your go-live checklist:", "hi": "आपकी गो-लाइव चेकलिस्ट:", "hinglish": "Aapki go-live checklist:"},
    "partner_live": {"en": "You're live — customers near you can book you. 🎉", "hi": "आप लाइव हैं — आसपास के ग्राहक आपको बुक कर सकते हैं। 🎉", "hinglish": "Aap live hain — aaspaas ke customers aapko book kar sakte hain. 🎉"},
    "no_requests": {"en": "No new job requests right now.", "hi": "अभी कोई नई जॉब रिक्वेस्ट नहीं है।", "hinglish": "Abhi koi nayi job request nahi hai."},
    "no_jobs": {"en": "No jobs for today.", "hi": "आज कोई जॉब नहीं है।", "hinglish": "Aaj koi job nahi hai."},
    "cancel_reason": {"en": "Cancelled by customer via chat", "hi": "Cancelled by customer via chat", "hinglish": "Cancelled by customer via chat"},
    "today": {"en": "Today", "hi": "आज", "hinglish": "Aaj"},
    "tomorrow": {"en": "Tomorrow", "hi": "कल", "hinglish": "Kal"},
}

QUICK = {
    # label per language for quick-reply chips; value is what gets sent
    "book": {"en": "Book a service", "hi": "सर्विस बुक करें", "hinglish": "Service book karo"},
    "my_bookings": {"en": "My bookings", "hi": "मेरी बुकिंग", "hinglish": "Meri bookings"},
    "cancel": {"en": "Cancel a booking", "hi": "बुकिंग रद्द करें", "hinglish": "Booking cancel karo"},
    "faq": {"en": "How it works", "hi": "यह कैसे काम करता है", "hinglish": "Kaise kaam karta hai"},
    "human": {"en": "Talk to support", "hi": "सपोर्ट से बात करें", "hinglish": "Support se baat karo"},
    "partner_status": {"en": "What's pending for go-live?", "hi": "गो-लाइव के लिए क्या बाकी है?", "hinglish": "Go-live ke liye kya baaki hai?"},
    "job_requests": {"en": "New job requests", "hi": "नई जॉब रिक्वेस्ट", "hinglish": "Nayi job requests"},
    "earnings": {"en": "My earnings", "hi": "मेरी कमाई", "hinglish": "Meri kamai"},
    "today_jobs": {"en": "Today's jobs", "hi": "आज की जॉब", "hinglish": "Aaj ki jobs"},
    "admin_summary": {"en": "Today's summary", "hi": "आज का सारांश", "hinglish": "Aaj ka summary"},
    "become_partner": {"en": "Become a partner", "hi": "पार्टनर बनें", "hinglish": "Partner bano"},
    "profile": {"en": "Update my profile", "hi": "प्रोफ़ाइल अपडेट करें", "hinglish": "Profile update karo"},
    "login": {"en": "Log in", "hi": "लॉग इन", "hinglish": "Login"},
    "cash": {"en": "Pay after service (cash/UPI)", "hi": "सर्विस के बाद (कैश/UPI)", "hinglish": "Service ke baad (cash/UPI)"},
    "online": {"en": "Pay online now", "hi": "अभी ऑनलाइन", "hinglish": "Abhi online"},
    "stop": {"en": "Stop", "hi": "रोकें", "hinglish": "Ruko"},
}


def t(key, lang="en", **kw):
    row = STRINGS.get(key, {})
    s = row.get(lang) or row.get("en") or key
    return s.format(**kw) if kw else s


def q(key, lang="en"):
    row = QUICK.get(key, {})
    return row.get(lang) or row.get("en") or key
