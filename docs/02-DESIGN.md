# 2. Design (UI/UX)

Visual and interaction design for Smart Fertilizer Advisor. Keep the existing green Bootstrap 5 theme from v1 (`static/css/style.css`) and extend it; do not introduce a new CSS framework.

---

## 2.1 Design principles

1. **Answer first.** The result page leads with the fertilizer, confidence and cost; detail sits below.
2. **Farmer-friendly.** Large inputs, plain words, units on every field (°C, %, kg/ha, acres, ₹).
3. **Honest.** Warnings in amber when inputs are unusual; prices and doses labelled "approximate".
4. **Never a dead end.** Every failure (weather, Gemini, PDF fonts) shows a message and a manual path.
5. **Calm UI.** Remove v1's hover "jump" on forms and tables; motion only on buttons and feature cards.

## 2.2 Design tokens

Extend the existing `:root` variables in `style.css`:

| Token | Value | Use |
| --- | --- | --- |
| `--primary-color` | `#28a745` | Primary actions, brand |
| `--primary-dark` | `#1e7e34` | Gradients, hover |
| `--warning-color` | `#ffc107` | Out-of-range warnings |
| `--danger-color` | `#dc3545` | Errors, delete actions |
| `--chat-user-bg` | `#e8f5e9` | User chat bubble |
| `--chat-bot-bg` | `#ffffff` | Assistant chat bubble |
| `--chat-border` | `#dee2e6` | Chat panel border |
| `--border-radius` | `8px` | All cards, inputs, bubbles |
| Font | `'Segoe UI', 'Noto Sans', 'Noto Sans Telugu', 'Noto Sans Tamil', 'Noto Sans Devanagari', sans-serif` | Latin + Indic scripts |

CSS fixes to apply:

- Restrict hover lift to `.feature-card:hover` and `.btn:hover`; remove `.card:hover` transform and `.table tbody tr:hover` scale.
- Remove `text-transform: uppercase` from `.btn` (hurts Indic text and readability).
- Delete unused `.spinner`; keep `.contact-form` (contact page now exists).
- Remove the duplicate inline `.recommendation-card` style block from `result.html`.
- Upgrade Bootstrap from `5.3.0-alpha1` to the latest stable 5.3.x CDN link (CSS and JS bundle).

## 2.3 Sitemap and navigation

```
Public                         Logged-in
──────                         ─────────
/            Home              /dashboard          Dashboard
/about       About + model card/predictor          Predictor form
/contact     Contact           /result/<id>        Result + dosage + chat
/login       Login             /history            History (paginated)
/register    Register          /report/<id>.pdf    PDF download
                               /logout
```

Navbar: Home · Dashboard* · Predictor* · History* · About · Contact · (right side) Login/Register or "Hi, <name>" ▾ Logout. Items marked * are shown only when logged in.

## 2.4 Page specifications

### 2.4.1 Home (`index.html`)

Keep the hero and three feature cards. Changes:

- Replace the hard-coded stats with values from the model card: crops count (11), soil types (5), CV accuracy from `model_meta.json`, languages (4).
- Add a fourth feature card, "Ask the Advisor": chat in your language, answers with sources.
- Primary button: "Get a recommendation" (goes to login if anonymous).

### 2.4.2 Register / Login (`auth/register.html`, `auth/login.html`)

- Centered card, max-width 420 px.
- Register fields: Full name, Email, Password, Confirm password, Preferred language (select).
- Login fields: Email, Password, "Remember me".
- Field errors shown under each input (`invalid-feedback`), plus one flash at the top for auth failures ("Email or password is incorrect" — never reveal which).

### 2.4.3 Dashboard (`dashboard.html`)

- Greeting row: "Welcome, <name>".
- Three stat tiles: Total predictions, Chats asked, Last recommendation.
- "Recent predictions" table (last 5): date, crop, soil, fertilizer, confidence, actions (View, PDF). Empty state: illustration icon + "No predictions yet" + button to Predictor.
- Keep the "How to use" card from v1.

### 2.4.4 Predictor (`predictor.html`)

Form in four sections, single column on mobile, grid on desktop:

1. **Location & weather** — Location (text, e.g. "Guntur") + "Get weather" button (outline). Shows a small status line: "Filled from Open-Meteo at 14:05" or the error. If several places match, a dropdown of up to 5 appears below.
2. **Environment** — Temperature (°C), Humidity (%), Soil moisture (%). Helper text shows the training range: "Model trained on 25–38 °C".
3. **Soil & crop** — Soil type, Crop type (from the model's encoders). Paddy labelled "Paddy (Rice)".
4. **Soil nutrients** — Nitrogen, Phosphorous, Potassium (numbers) with helper text showing training ranges. Collapsible "Soil test ratings (optional)": N/P/K each Low/Medium/High, default Medium.
5. **Farm** — Area (number) + unit toggle (acres | hectares).

Buttons: "Fill sample values" (in-range sample: 30 °C, 60 %, 45 %, Loamy, Wheat, N 12, P 36, K 0) and primary "Get recommendation". Out-of-range values turn the field border amber (not red) with helper text "Outside training range — result may be less reliable". The submit button shows a spinner until the response arrives (no fixed 3 s timeout).

### 2.4.5 Result (`result.html`)

Layout (desktop: two columns 7/5; mobile: stacked):

**Left column**

1. **Recommendation card** — large fertilizer name; confidence badge (green ≥ 70 %, amber 40–69 %, grey < 40 %); "Also possible:" top-2 alternatives with percentages. Amber alert if any input is out of range, listing the fields.
2. **Dosage & cost card** — table: Product · kg/ha · kg for your farm · Bags · Cost (₹). Footer row: Total cost. Note: "Approximate. Prices from configured MRP dated <price_as_of>. Verify with your dealer."
3. **When to apply card** — timeline list: Basal (at sowing), Top dress 1 (e.g. 20–25 days), Top dress 2. From crop requirements.
4. **Your inputs** — compact two-column table (v1's three tables merged).
5. Actions: "Download PDF", "New prediction".

**Right column — Chat panel** (`partials/_chat.html`)

- Header: "Ask the Advisor" + language select (English / తెలుగు / தமிழ் / हिन्दी), default from user profile.
- Message list (scrollable, max-height 520 px): user bubbles right-aligned (`--chat-user-bg`), assistant bubbles left (`--chat-bot-bg`, border). Each assistant bubble ends with "Sources: urea.md · wheat.md" as small badges.
- Suggested question chips (shown until first question): "Why this fertilizer?", "How and when do I apply it?", "What if it rains after applying?", "Is there an organic alternative?"
- Input row: textarea (Enter to send, Shift+Enter newline, max 500 chars with counter) + Send button.
- Typing indicator ("Advisor is thinking…") while waiting.
- Fallback state: amber bubble "The AI service is unavailable. Here are the most relevant passages:" followed by passages.
- Disclaimer line under input: "Educational guidance. Confirm with your local agriculture officer."

### 2.4.6 History (`history.html`)

- Table: Date · Location · Crop · Soil · Fertilizer · Confidence · Total cost · Actions (View, PDF).
- Pagination 10 per page.
- "Clear history" danger button → Bootstrap modal confirm.
- Empty state like Dashboard.

### 2.4.7 About (`about.html`)

- Keep description and tech stack (update stack: Gemini, FAISS, SQLite, Flask-Login, fpdf2, Open-Meteo).
- **Model card** section (from `model_meta.json`): algorithm, training rows, features, classes, CV accuracy ± std, training ranges table, trained date, scikit-learn version.
- **Limitations** section: small public dataset; NPK inputs are dataset index values, not lab kg/ha; environment, soil and crop inputs add little signal; doses and prices are approximate.

### 2.4.8 Contact (`contact.html`)

Simple form (name, email, message) that stores to a `contact_messages` table and flashes "Thanks, we'll get back to you". No email sending.

### 2.4.9 Error pages

`errors/404.html` and `errors/500.html` extending `base.html`: friendly message, button home. Never show stack traces.

## 2.5 PDF report layout (A4 portrait)

1. Header band: "Smart Fertilizer Advisor — Recommendation Report", farmer name, date, location.
2. Inputs table (2 columns).
3. Recommendation box: fertilizer, confidence, alternatives, warnings.
4. Dosage & cost table + total.
5. Application schedule.
6. Advisor Q&A: last 5 questions with answers (truncated to 600 chars each) and sources.
7. Footer on every page: disclaimer + page x/y.

## 2.6 Copy guidelines

- Use "fertilizer" consistently (US spelling, matches code).
- Numbers: one decimal for kg/ha, whole kg for farm totals, bags to one decimal plus "≈ N bags (rounded up)", ₹ with Indian grouping (₹5,702).
- Avoid jargon in UI; the chat can explain terms.

## 2.7 Accessibility checklist

- Every input has a `<label for>`; helper text linked with `aria-describedby`.
- Chat list has `aria-live="polite"`; Send button has an accessible name.
- Confidence badge has text, not colour only.
- Contrast ≥ 4.5:1 for body text; check amber warning text on white.
- Focus visible on all interactive elements.

## 2.8 Responsive behaviour

| Breakpoint | Behaviour |
| --- | --- |
| < 576 px | Single column; chat panel below result cards; tables scroll horizontally inside `.table-responsive` |
| 576–991 px | Form two columns; result stacked |
| ≥ 992 px | Result 7/5 columns with sticky chat panel (`position: sticky; top: 1rem`) |
