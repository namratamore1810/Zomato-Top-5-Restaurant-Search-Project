# Google Stitch UI Design Prompt — Zomato Top 5

Copy everything below the line into Google Stitch to generate a polished frontend design.

---

## Prompt (copy from here)

Design a modern, production-quality **web UI** for **“Zomato Top 5”** — an AI-powered restaurant recommendation app inspired by Zomato. The product helps users find their **top 5 restaurant picks** based on preferences, using real restaurant data plus AI-generated rankings and explanations.

### Product context

- **What it does:** User enters dining preferences → system filters thousands of restaurants → AI ranks the best matches and explains why each fits.
- **Core promise:** Personalized, transparent, scannable recommendations grounded in real data (not generic AI guesses).
- **Default result count:** Top **5** restaurants.
- **Tech note (for your awareness only):** Backend is Python; current prototype uses Streamlit, but **design a proper responsive web app UI** (not Streamlit-default styling). We will implement your design in a modern frontend later.

### Brand & visual direction

- **Inspiration:** Zomato — food discovery, trust, appetite appeal.
- **Primary accent:** Zomato red `#E23744` (CTAs, rank badges, key highlights).
- **Neutrals:** Clean whites, soft grays `#F8F8F8` / `#EEEEEE`, dark text `#1C1C1C`.
- **Secondary accents:** Warm food tones (subtle orange/cream) for highlights — avoid clutter.
- **Typography:** Modern sans-serif (e.g. Inter, SF Pro, or similar). Clear hierarchy: bold headlines, readable body for AI explanations.
- **Tone:** Friendly, confident, helpful — “your personal dining concierge,” not corporate or playful-childish.
- **Imagery:** Optional subtle food/location textures or icons; prioritize **content clarity** over decorative photos.

### Target users

- Urban diners in India choosing where to eat (Bangalore, Delhi, etc.).
- Mobile-first but must look excellent on desktop (responsive).
- Users who want quick decisions: scan rating, cost, cuisine, then read a short AI “why this fits you” blurb.

---

### Screens to design (minimum)

#### Screen 1 — Home / Preference form (primary)

**Header**
- App name: **Zomato Top 5**
- Short subtitle: “AI-powered picks from real restaurant data”
- Optional small badge: “Powered by AI”

**Preference form** (all fields required unless noted)

| Field | Control type | Details |
|-------|--------------|---------|
| **Location** | Searchable dropdown | Populated from dataset areas/localities (e.g. Indiranagar, Bellandur, Koramangala, Banashankari). Title-case labels. Helper: “Choose area or city” |
| **Cuisine** | Text input with chips/suggestions | Placeholder: “Italian, Chinese…” Supports comma-separated OR match |
| **Budget** | Segmented control or pill select | Options: **Low · Medium · High** (for two people) |
| **Minimum rating** | Slider 0.0–5.0 | Default 4.0, step 0.1, show current value |
| **Additional preferences** | Optional textarea | Placeholder: “family-friendly, rooftop, quick service…” |

**Primary CTA:** Large button — **“Get my top picks”** (red, full-width on mobile).

**Sidebar / footer info (desktop)**
- Dataset status: “Restaurant data loaded” / “Loading…”
- Small meta: “Showing top 5 by default”
- Optional “Reload data” text button

---

#### Screen 2 — Loading states

Design distinct loading UX (no blank screens):

1. **Initial dataset load** — “Loading restaurant dataset… first run may take a few minutes”
2. **Recommendation in progress** — “Finding your top picks…” with subtle animation/skeleton
3. **Skeleton cards** — 5 placeholder recommendation cards while waiting

---

#### Screen 3 — Results (success)

**Optional AI overview block** (top)
- Section title: “Overview”
- 1 short paragraph summary of the overall selection (from LLM)
- Soft info-style container (not alarming)

**Section: “Your top picks”**
Show **up to 5 ranked recommendation cards**. Each card = `RecommendationCard`:

```
#1  [Rank badge — prominent, red]
Restaurant Name                    ★ 4.5
Italian · ₹800 for two
────────────────────────────────────
AI explanation (2–3 sentences):
“Why this restaurant fits your location, budget, cuisine, and vibe…”
```

**Card fields (must be visible):**
- Rank (1–5) — large, unmistakable
- Restaurant name
- Cuisine
- Star rating (numeric + star icon)
- Estimated cost (e.g. “₹600 for two”; show “Not available” if missing)
- AI-generated explanation (readable paragraph)

**Footer meta (subtle caption):**
“Considered 28 matching restaurants · showing top 5”

**Edge case on card:** If fewer than 5 matches, show caption: “Showing 3 recommendations based on available matches.”

---

#### Screen 4 — Degraded / partial AI mode

When AI ranking fails but filter results exist, show a **yellow/amber info banner** above cards:

> “AI ranking is temporarily unavailable. Showing top-rated matches from your filters.”

Cards still display; explanations may be template-style (shorter).

---

#### Screen 5 — No results (empty state)

Friendly empty state — **no error stack traces, no harsh red error page.**

- Illustration or icon (empty plate / search)
- Headline: “No restaurants match your preferences in [Location].”
- Bulleted suggestions:
  - Try lowering your minimum rating
  - Try a different cuisine or location
- Secondary CTA: “Adjust preferences” (scrolls to form)

---

#### Screen 6 — Error state

User-safe error banner (red/pink alert, not developer debug):

- “Unable to load restaurant data. Please try again later.”
- Or: “Invalid preferences. Check location, budget, cuisine, and rating.”
- Single action: “Try again”

---

### Component library to include

1. **Preference form** — labeled inputs, helper text, validation hints
2. **Primary button** — default, hover, disabled, loading
3. **Recommendation card** — default, hover (desktop), long-name truncation
4. **Rank badge** — #1–#5 with distinct treatment for #1 (slightly emphasized)
5. **Rating display** — star + number
6. **Cost chip** — rupee format
7. **AI explanation block** — quote or subtle left border accent
8. **Alert banners** — info (overview), warning (degraded), error, success (data loaded)
9. **Empty state** — illustration + copy + CTA
10. **Loading skeleton** — card list
11. **Searchable select** — location dropdown with typeahead

---

### Layout & responsive rules

- **Desktop (≥1024px):** Two-column form (location/cuisine left, budget/rating right); results full width below; optional sidebar for status.
- **Tablet (768–1023px):** Stacked form, 2-column card grid if space allows.
- **Mobile (≤767px):** Single column; sticky bottom CTA optional; cards full width stacked.
- **Spacing:** Generous whitespace; cards separated clearly; 16–24px padding.
- **Accessibility:** Visible labels, focus rings, contrast WCAG AA, touch targets ≥44px.

---

### UX principles (must follow)

| Principle | UI expression |
|-----------|----------------|
| **Transparency** | Every card shows *why* it was recommended (AI explanation visible, not hidden) |
| **Scannability** | Name, cuisine, rating, cost scannable in &lt;2 seconds |
| **Trust** | Show “Considered N candidates”; no fake/hallucinated venues |
| **Personalization** | Reflect user’s location, budget, cuisine in overview copy |
| **Calm errors** | Friendly copy, suggestions — never raw Python/traceback text |

---

### Sample content (use in mockups)

**Form values**
- Location: Indiranagar
- Cuisine: Italian
- Budget: Medium
- Min rating: 4.0
- Additional: “Rooftop seating, date night”

**Overview summary**
> “These five spots balance authentic Italian flavors with your medium budget and 4.0+ rating bar — strong choices for a relaxed date night around Indiranagar.”

**Sample cards**
1. **Trattoria Milano** — Italian · ★4.6 · ₹750 for two — “Excellent pasta and intimate ambiance; fits your rooftop preference and medium budget.”
2. **Bella Roma** — Italian, Pizza · ★4.4 · ₹650 for two — “Highly rated pizzas, lively but not too loud for date night.”
3. *(continue through #5)*

---

### Do NOT design

- Admin dashboards, login/signup, payment flows
- Restaurant detail pages with menus/photos (out of scope v1)
- Map view (optional P2 — skip for now)
- Backend architecture diagrams
- Streamlit-specific widgets or default theme

---

### Deliverables requested from Stitch

1. **High-fidelity mockups** — all 6 screen states above (desktop + mobile for home and results)
2. **Design system page** — colors, type scale, buttons, inputs, cards, alerts
3. **Component specs** — spacing, border radius, shadows, hover states
4. **Interactive prototype flow:** Form → Loading → Results (and No results variant)
5. **Export-friendly assets** — icons for rating, location, budget, AI sparkle/badge

Make the design feel like a **real Zomato-quality consumer product**, not a student demo or generic admin template.

---

## End of prompt
