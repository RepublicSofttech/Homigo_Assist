# Homigo Assist

AI chat support for Homigo: a **separate service** plus an **embeddable chat widget**.

It answers questions about Homigo and helps each kind of user:

- books services end-to-end in chat,
- shows booking status, and redirects to the right page,
- escalates to the support team with a chat summary.

It works in **English, Hindi and Hinglish**.

It runs in two modes:

| Mode | Setting | What you get |
|---|---|---|
| **Rules** (default, no key) | `LLM_PROVIDER=none` | Menu and quick replies, FAQ answers from the knowledge base, the guided booking wizard, booking status, cancel, partner checklist, job requests, earnings, coworker jobs, admin summary, and escalation |
| **AI** | `LLM_PROVIDER=groq` or `gemini` plus `LLM_API_KEY` | Everything above, plus free-text understanding and natural replies in the user's language. The model uses the same role-scoped tools. If the AI is down or the daily budget is used up, it falls back to Rules mode automatically |

Free AI options: create a free API key at Groq (`LLM_PROVIDER=groq`) or Google AI Studio (`LLM_PROVIDER=gemini`).
Set `LLM_MODEL` to a current tool-calling model from your provider's console. The defaults are only a starting point.
On free tiers, the provider may use requests to improve its models, so don't put secrets in chat (the widget masks Aadhaar, card and PAN numbers).

## How it fits together

```
Homigo website ──(widget.js)──> Homigo Assist (/assist) ──(user's own token)──> Homigo API (/api/v1)
                                      │                                             ▲
                                      └── optional LLM (Groq / Gemini, OpenAI-compatible)
```

- **Identity and permissions.** The widget sends the signed-in user's Homigo token. Assist calls `GET /me/` to learn the role (guest, customer, partner, coworker or admin), then calls the Homigo API **as that user**. Homigo's own permission rules therefore always apply: a customer only sees their own bookings. Assist never stores tokens.
- **Role-scoped tools** (`assist/tools.py`): each tool lists the roles allowed to use it. The AI only gets the tools for the current role, and the server checks the role again before running any tool.
- **Write actions need confirmation.** Booking, cancelling, profile updates, adding an address, accepting a job and creating a ticket each produce a *confirm card*. Nothing changes until the user taps **Confirm**, and then the server runs it. Admin staff get **information only**.
- **Sessions and summaries.** Every chat is a session. On escalation ("Talk to support", complaints, or a 1–2★ rating), Assist writes a summary and creates a **Homigo support ticket** containing it. Staff see all chats under **Admin → Chat sessions**.
- **Knowledge.** Edit `assist/knowledge/homigo_kb.md` (one `##` section per topic, with keywords in English, Hindi and Hinglish).
- **Safety.** Aadhaar, card and PAN numbers are masked before storage. Rate limits apply per session and per minute, and there is a daily AI call budget. Payments never happen in chat; the user is sent to the booking page instead.

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env            # HOMIGO_API_URL=http://localhost:8000/api/v1
python manage.py migrate && python manage.py createcachetable
python manage.py runserver 8001
python manage.py test tests     # 25 tests, fake Homigo API, no network
```

Frontend: set `VITE_ASSIST_URL=http://localhost:8001` (by default it uses `<API origin>/assist`).

## Embed on any site

```html
<script src="https://YOUR-HOST/assist/widget.js"></script>
<script>
  HomigoAssist.init({
    apiBase: "https://YOUR-HOST/assist",
    getToken: () => localStorage.getItem("hs_token"),
    getContext: () => ({ page: location.pathname, city: "New Delhi", lat: 28.63, lng: 77.21 }),
    navigate: (path) => (location.href = path),
  });
</script>
```

Widget API: `HomigoAssist.open()`, `.close()`, `.toggle()`, `.reset()` (call after login/logout), `.ask("text")`.

## API

| Method | Path | |
|---|---|---|
| GET | `/health/` | status and whether AI mode is on |
| GET | `/widget.js` | the widget |
| POST | `/api/sessions/` | start or resume `{session_id?, language?, context?}` |
| POST | `/api/sessions/{id}/messages/` | `{text, display?, language?, context?}` |
| POST | `/api/sessions/{id}/actions/{action_id}/` | `{decision: confirm\|cancel}` |
| POST | `/api/sessions/{id}/escalate/` | create a ticket with the summary |
| POST | `/api/sessions/{id}/end/` | `{rating 1–5, feedback}` |
| POST | `/api/sessions/{id}/messages/{mid}/feedback/` | `{helpful: true\|false}` |
| GET | `/api/admin/sessions/` | staff list `?status=&role=&q=` |
| GET/POST | `/api/admin/sessions/{id}/` | staff detail / regenerate summary |

## Deploy next to Homigo (EC2, docker compose)

Add the service to `/opt/homigo/docker-compose.yml`:

```yaml
  assist:
    build: ./assist
    env_file: ./assist/.env
    environment:
      DATABASE_URL: postgres://homigo:homigo@db:5432/homigo_assist
      HOMIGO_API_URL: http://api:8000/api/v1
      DJANGO_ALLOWED_HOSTS: assist,localhost,YOUR-DOMAIN
      STATIC_URL: /assist/static/
    depends_on: [db, api]
```

Route it in the Caddyfile, before `reverse_proxy api:8000`:

```
handle_path /assist/* {
    reverse_proxy assist:8001
}
```

Create the database once: `docker compose exec db psql -U homigo -c "CREATE DATABASE homigo_assist;"`.

## Roadmap

- Live human takeover in the same chat window (staff reply inside the widget)
- Photo upload ("show the leak") and voice input
- WhatsApp channel using the same engine
- More languages: add a column in `assist/i18n.py`, and widget strings in `widget.js`
- Analytics: top questions, unanswered questions, drop-off in the booking wizard
