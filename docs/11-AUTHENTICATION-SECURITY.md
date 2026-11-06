# 11. Authentication & Security

How users are authenticated and how the app is protected: sessions, passwords, CSRF, authorisation, secrets, LLM-specific risks, and a pre-demo security checklist.

---

## 11.1 Threat model (scope: local demo, small user base)

| Asset | Threat | Control |
| --- | --- | --- |
| User accounts | Password guessing, credential stuffing | Hashed passwords, login rate limit, generic error messages |
| User data (predictions, chats) | One user reading another's data (IDOR) | Ownership filter on every query; 404 for not-owned |
| Session | Cookie theft, fixation, CSRF | HttpOnly + SameSite cookies, session protection "strong", CSRF tokens |
| Server | Remote code execution via debugger | `FLASK_DEBUG=0` by default |
| API keys | Leak via git, logs, client JS | `.env` only, gitignored, never sent to the browser or logged |
| LLM | Prompt injection, off-topic use, abuse of quota | Grounded system prompt, input limits, rate limit, no tools/actions for the LLM |
| Model file | Malicious pickle/joblib | Only load artifacts you built locally; never accept uploaded models |
| Availability | Chat/weather flooding | Rate limits per user; timeouts on external calls |

## 11.2 Authentication

**Library:** Flask-Login with session cookies.

| Setting | Value |
| --- | --- |
| `login_manager.login_view` | `"auth.login"` |
| `login_manager.login_message_category` | `"warning"` |
| `login_manager.session_protection` | `"strong"` |
| `REMEMBER_COOKIE_DURATION` | 14 days |
| `REMEMBER_COOKIE_HTTPONLY` / `SAMESITE` | `True` / `"Lax"` |

### Registration flow

1. `RegisterForm` validates name, email (`email-validator`), password rules (≥ 8 chars, ≥ 1 letter, ≥ 1 digit), confirm password, language.
2. Email normalised: `email.strip().lower()`; uniqueness checked (case-insensitive).
3. `password_hash = generate_password_hash(password)` (Werkzeug default scrypt).
4. User created, logged in, redirected to `/dashboard`.

### Login flow

```python
@bp.post("/login")
@limiter.limit("5 per minute")
def login_post():
    form = LoginForm()
    if not form.validate_on_submit():
        return render_template("auth/login.html", form=form), 400
    user = User.query.filter_by(email=form.email.data.strip().lower()).first()
    if not user or not check_password_hash(user.password_hash, form.password.data) or not user.is_active:
        flash("Email or password is incorrect.", "danger")
        return render_template("auth/login.html", form=form), 401
    login_user(user, remember=form.remember.data)
    user.last_login_at = utcnow(); db.session.commit()
    return redirect(safe_next(request.args.get("next")) or url_for("core.dashboard"))

def safe_next(target: str | None) -> str | None:
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None
```

`login_user` regenerates session state; never reuse a session identifier from before login.

### Logout

`POST /logout` with CSRF (a GET logout can be triggered by an image tag on another site). Calls `logout_user()` and clears the session.

### Seed account

`seed-demo` creates `demo@example.com` / `Demo@1234` for the demo only. It refuses to run when `FLASK_DEBUG=0` unless `--force` is passed. Change or delete it before any public deployment.

## 11.3 Authorisation

- `@login_required` on: dashboard, predictor, predict, result, history, history/clear, report, all `/api/*`.
- Ownership helper:

```python
def get_owned_prediction_or_404(pid: int) -> Prediction:
    p = db.session.get(Prediction, pid)
    if p is None or p.user_id != current_user.id:
        abort(404)
    return p
```

- Chat API checks `prediction_id` ownership before retrieval or LLM calls.
- JSON APIs return `401 {"error": {"code": "AUTH_REQUIRED"}}` instead of redirecting; implement with `login_manager.unauthorized_handler` checking `request.path.startswith("/api/")`.

## 11.4 Session and cookie settings

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False      # True when served over HTTPS
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
```

`SECRET_KEY` comes from `.env`, is at least 32 random bytes, and is constant across restarts and workers (fixes the v1 random-key bug). `create_app` raises `RuntimeError("SECRET_KEY is not set")` when it is missing and debug is off.

## 11.5 CSRF

- `CSRFProtect(app)` globally.
- Forms: `{{ form.hidden_tag() }}` or `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- `base.html`: `<meta name="csrf-token" content="{{ csrf_token() }}">`; `fetch` sends `X-CSRFToken`.
- CSRF error handler returns the JSON error format for `/api/*` and a friendly flash + redirect for pages.
- Tests disable CSRF only in `TestConfig` (`WTF_CSRF_ENABLED = False`) plus one dedicated test that enables it and asserts 400 without a token.

## 11.6 Input validation and output encoding

| Input | Validation |
| --- | --- |
| Predictor fields | Flask-WTF types and ranges (API §5.2); soil/crop whitelisted from model meta |
| Chat question | 1–500 chars; strip control characters; reject if > 500 |
| Language | Whitelist `en/te/ta/hi` |
| Weather `q` | 2–80 chars; letters, spaces, `-`, `.`, `,` only |
| IDs | `<int:id>` converters |

Output:

- Jinja autoescaping stays on; never mark user or LLM text `|safe`.
- Chat JS inserts text with `textContent`, then converts newlines/bullets by creating elements, never `innerHTML` with model output.
- PDF: text is drawn, not interpreted; no HTML-to-PDF conversion of user content.

## 11.7 Secrets management

- `.env` (gitignored) holds `SECRET_KEY`, `GEMINI_API_KEY`. `.env.example` has empty placeholders.
- Never log request bodies of `/login` or `/register`; never log prompts containing keys (keys are not in prompts anyway).
- `/health` reports `llm_configured: true/false`, never the key.
- If a key is ever committed: revoke it in Google AI Studio immediately, generate a new one, and purge it from git history (`git filter-repo`), then force-push.
- Antigravity MCP config (`~/.gemini/config/mcp_config.json`) may contain tokens; it lives outside the repo. Never copy it into the project.

## 11.8 Rate limiting

Flask-Limiter with `key_func` = user id when logged in, else remote address; storage `memory://` for the demo.

| Endpoint | Limit |
| --- | --- |
| `POST /login` | 5 per minute per IP |
| `POST /register` | 3 per minute per IP |
| `POST /api/chat` | `RATELIMIT_CHAT` (10 per minute) per user |
| `GET /api/weather` | 30 per minute per user |
| Default | 200 per hour per user/IP |

429 responses use the JSON error format for APIs and a flash for pages.

## 11.9 LLM and RAG security

| Risk | Mitigation |
| --- | --- |
| Prompt injection in the user's question ("ignore your rules…") | System instruction is separate from user content; the model has no tools, no data access and no ability to act; answers must be grounded in passages; off-topic rule |
| Prompt injection inside knowledge-base files | KB is authored and reviewed by the team only; never index user uploads or web pages |
| Hallucinated doses | Rule 3 in the system prompt; dosage numbers come from `dosage_service` and are passed in context; UI shows the computed table separately from chat |
| Sensitive data sent to Gemini | Only question, prediction context and passages; no name, email or IDs |
| Quota exhaustion / cost | Rate limit, 500-char questions, `max_output_tokens=600`, top-k 4 with a 4,000-char context cap |
| Harmful advice | Disclaimer under the chat and in PDFs; refusal rule for pesticides/health |
| Over-trust | Every answer ends with "Please confirm with your local agriculture officer" |

## 11.10 Security headers

Add in an `after_request` hook:

```python
resp.headers["X-Content-Type-Options"] = "nosniff"
resp.headers["X-Frame-Options"] = "DENY"
resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
resp.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; connect-src 'self'"
)
```

Inline `<script>` blocks from v1 (predictor) must move to `static/js/predictor.js` for this CSP to work.

## 11.11 Dependency hygiene

- Use version ranges in `requirements.txt`, freeze exact versions in `requirements.lock`.
- Run `pip install pip-audit && pip-audit` before the demo; fix critical findings if trivial.
- Bootstrap from the official jsDelivr URL with Subresource Integrity (`integrity` + `crossorigin`) attributes.

## 11.12 Pre-demo security checklist

- [ ] `FLASK_DEBUG=0`; no `app.run(debug=True)` anywhere
- [ ] `SECRET_KEY` set, 64 hex chars, not the example value
- [ ] `.env` not tracked (`git ls-files .env` prints nothing)
- [ ] User B cannot open user A's `/result/<id>`, `/report/<id>.pdf` or `/api/chat/<id>` (404)
- [ ] POST without CSRF token → 400
- [ ] 6 rapid wrong logins → 429
- [ ] Chat answer with `<script>alert(1)</script>` in the question renders as text
- [ ] No stack trace visible on any error page
- [ ] Demo account password not reused anywhere real
