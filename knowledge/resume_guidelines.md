# Resume Writing Guidelines

These guidelines are provided to the CareerCrew agents as reference knowledge.
They define how resume bullets are written, how gaps are described, and how
screening answers are grounded. Follow them exactly.

## 1. Honesty rules (non-negotiable)

- Every claim in a rewritten bullet must trace to a fact that appears in the
  parsed candidate profile. If a fact is not in the resume, do not invent it.
- Never invent employers, job titles, employment dates, technologies, metrics,
  certifications, or achievements.
- A requirement with no supporting resume fact is **out of scope**. List it in
  `do_not_claim` instead of writing a bullet for it.
- It is always acceptable — and expected — to say that something cannot be
  claimed.

## 2. Strong bullet patterns

Prefer the action + object + measurable result shape:

1. **Action verb first.** Built, Led, Cut, Migrated, Automated, Designed.
2. **Name the object.** What system, product, or process was affected?
3. **Quantify the result** when the resume already contains a number. Never
   invent a number to fill the gap.
4. **Keep it one line.** Roughly 15-25 words.

Examples grounded in a profile:

- "Built REST APIs in FastAPI serving 2M requests per day" (fact: FastAPI APIs,
  2M requests/day).
- "Cut report generation time from 2 hours to 5 minutes with async workers"
  (fact: 2h to 5m, async workers).

## 3. Describing gaps honestly

Use exactly three verdicts for each requirement:

- **covered** — a resume fact directly demonstrates it.
- **reframeable** — the candidate has real, related experience that can be
  reframed to speak to the requirement, without overstating it.
- **out_of_scope** — no supporting fact exists. Do not claim it.

The coverage score is a heuristic signal for prioritization, not an official
ATS score, and must never be presented as one.

## 4. Interview talking points

- Three talking points grounded in documented experience.
- Each point should connect a real achievement to what the target role values.
- No rehearsed claims that are not supported by the profile.

## 5. Tone

- Professional, specific, and confident without exaggeration.
- Prefer concrete evidence over adjectives ("expert", "world-class").
