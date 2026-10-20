"""CareerCrew Gradio custom CSS (extracted for a thinner app.py)."""

CUSTOM_CSS = """
:root {
  --cc-bg: #f4f6fb;
  --cc-surface: #ffffff;
  --cc-surface-2: #f8fafc;
  --cc-line: #e5e9f2;
  --cc-ink: #0f172a;
  --cc-ink-2: #334155;
  --cc-muted: #64748b;
  --cc-soft: #f1f5f9;
  --cc-accent: #4f46e5;
  --cc-accent-2: #6366f1;
  --cc-ok: #16a34a;
  --cc-warn: #d97706;
  --cc-bad: #dc2626;
  --cc-shadow: rgba(15, 23, 42, .18);
}
body.dark {
  --cc-bg: #0b1220;
  --cc-surface: #121a2b;
  --cc-surface-2: #172033;
  --cc-line: #273449;
  --cc-ink: #f1f5f9;
  --cc-ink-2: #cbd5e1;
  --cc-muted: #94a3b8;
  --cc-soft: #1e293b;
  --cc-accent: #818cf8;
  --cc-accent-2: #a5b4fc;
  --cc-ok: #4ade80;
  --cc-warn: #fbbf24;
  --cc-bad: #f87171;
  --cc-shadow: rgba(0, 0, 0, .45);
}

/* Fixed page width so switching tabs does not reflow the viewport. */
.gradio-container {
  width: min(1180px, calc(100vw - 32px)) !important;
  max-width: 1180px !important;
  min-width: min(1180px, calc(100vw - 32px)) !important;
  margin: 0 auto !important;
  padding-top: 18px !important;
  box-sizing: border-box !important;
  background:
    radial-gradient(900px 380px at 12% -8%, color-mix(in srgb, var(--cc-accent) 14%, transparent), transparent 58%),
    radial-gradient(700px 320px at 92% 0%, color-mix(in srgb, #06b6d4 10%, transparent), transparent 52%),
    var(--cc-bg) !important;
  color: var(--cc-ink) !important;
}
footer { display: none !important; }
.contain {
  gap: 14px !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}

[data-testid="block-info"] {
  background: transparent !important; border: none !important;
  color: var(--cc-muted) !important; font-size: 12px !important;
  font-weight: 600 !important; padding: 0 !important; margin-bottom: 6px !important;
}

/* ---- brand bar ---- */
.cc-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 10px 4px 4px 4px;
}
.cc-brand { display: flex; align-items: center; gap: 10px; }
.cc-mark {
  width: 34px; height: 34px; border-radius: 10px;
  background: linear-gradient(135deg, var(--cc-accent), #06b6d4);
  color: #fff; display: grid; place-items: center; font-weight: 800; font-size: 14px;
  box-shadow: 0 10px 22px -14px var(--cc-accent);
}
.cc-brand-name { font-size: 18px; font-weight: 760; letter-spacing: -0.02em; color: var(--cc-ink); }
.cc-brand-tag { font-size: 12px; color: var(--cc-muted); margin-top: 1px; }
.cc-status-chip {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 12px; border-radius: 999px; font-size: 12px; font-weight: 650;
  border: 1px solid var(--cc-line); background: var(--cc-surface); color: var(--cc-ink-2);
}
.cc-status-chip .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--cc-ok); }
.cc-status-chip.warn .dot { background: var(--cc-warn); }

.cc-hero {
  border: 1px solid var(--cc-line); border-radius: 22px; padding: 28px 28px 24px;
  background:
    linear-gradient(145deg, color-mix(in srgb, var(--cc-accent) 12%, transparent), transparent 55%),
    var(--cc-surface);
  box-shadow: 0 24px 48px -36px var(--cc-shadow);
}
.cc-hero h1 {
  margin: 0 0 8px 0; font-size: clamp(28px, 4vw, 40px); line-height: 1.12;
  letter-spacing: -0.03em; font-weight: 780; color: var(--cc-ink); max-width: 18ch;
}
.cc-hero .cc-sub {
  margin: 0 0 16px 0; color: var(--cc-ink-2); font-size: 15.5px; line-height: 1.55; max-width: 54ch;
}
.cc-trust { display: flex; flex-wrap: wrap; gap: 8px; }
.cc-trust span {
  font-size: 12px; font-weight: 650; color: var(--cc-ink-2);
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  padding: 6px 11px; border-radius: 999px;
}

.cc-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 650;
  border: 1px solid transparent;
}
.cc-badge.on  { background: color-mix(in srgb, var(--cc-ok) 14%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 34%, transparent); }
.cc-badge.off { background: color-mix(in srgb, var(--cc-warn) 14%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 34%, transparent); }
.cc-badge.ghost { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); }
.cc-badge.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-badge.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-badge.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }
.cc-badge.src { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); font-family: ui-monospace, monospace; }

.cc-card {
  border: 1px solid var(--cc-line); border-radius: 18px; background: var(--cc-surface);
  padding: 18px 20px; box-shadow: 0 16px 34px -30px var(--cc-shadow);
}
.cc-card h3 { margin: 0 0 4px 0; font-size: 16px; font-weight: 720; color: var(--cc-ink); letter-spacing: -0.01em; }
.cc-card .cc-hint { color: var(--cc-muted); font-size: 13px; margin: 0 0 14px 0; line-height: 1.5; }
.cc-empty {
  border: 1px dashed color-mix(in srgb, var(--cc-line) 90%, transparent);
  border-radius: 14px; padding: 28px 22px; text-align: center;
  color: var(--cc-muted); background: var(--cc-surface-2); font-size: 13.5px; line-height: 1.55;
}
.cc-empty strong { display: block; color: var(--cc-ink); font-size: 14.5px; margin-bottom: 4px; }

/* ---- input panels ---- */
.cc-panel {
  border: 1px solid var(--cc-line) !important; border-radius: 20px !important;
  background: var(--cc-surface) !important; padding: 8px 12px 14px !important;
  box-shadow: 0 16px 34px -30px var(--cc-shadow); min-height: 100%;
}
.cc-panel-head { margin: 6px 2px 12px; }
.cc-panel-head h3 { margin: 0; font-size: 17px; font-weight: 740; color: var(--cc-ink); letter-spacing: -0.015em; }
.cc-panel-head .cc-hint { margin: 4px 0 0; color: var(--cc-muted); font-size: 13px; }
.cc-field textarea, .cc-field input[type="text"], .cc-field input[type="url"] {
  background: var(--cc-soft) !important; color: var(--cc-ink) !important;
  border: 1px solid var(--cc-line) !important; border-radius: 12px !important;
}
.cc-field textarea::placeholder, .cc-field input::placeholder { color: var(--cc-muted) !important; opacity: .9; }
/* Single flat action bar — kill Gradio's nested block/column chrome inside it. */
.cc-cta {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 16px !important;
  flex-wrap: wrap !important;
  border: 1px solid var(--cc-line) !important;
  border-radius: 18px !important;
  background: var(--cc-surface) !important;
  padding: 16px 18px !important;
  box-shadow: 0 16px 34px -30px var(--cc-shadow);
  margin: 4px 0 2px !important;
}
.cc-cta > div,
.cc-cta .block,
.cc-cta .form,
.cc-cta .wrap,
.cc-cta .panel-wrap,
.cc-cta .svelte-1p9262q,
.cc-cta .styler {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}
.cc-cta .gap { gap: 10px !important; }
.cc-cta-copy { flex: 1 1 280px; min-width: 220px; }
.cc-cta-copy h3 { margin: 0; font-size: 16px; font-weight: 740; color: var(--cc-ink); letter-spacing: -0.01em; }
.cc-cta-copy p { margin: 4px 0 0; font-size: 13px; color: var(--cc-muted); line-height: 1.45; max-width: 52ch; }
.cc-cta-actions {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 10px !important;
  flex: 0 0 auto !important;
}

button.cc-run {
  background: linear-gradient(135deg, var(--cc-accent), var(--cc-accent-2)) !important;
  border: none !important; color: #fff !important; font-weight: 720 !important;
  box-shadow: 0 14px 28px -16px color-mix(in srgb, var(--cc-accent) 80%, transparent) !important;
  min-height: 44px !important; min-width: 168px !important;
  padding: 0 20px !important; border-radius: 12px !important;
}
button.cc-clear {
  background: transparent !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink-2) !important;
  font-weight: 650 !important;
  min-height: 44px !important;
  min-width: 88px !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
button.cc-clear:hover {
  background: var(--cc-soft) !important;
  border-color: color-mix(in srgb, var(--cc-accent) 40%, var(--cc-line)) !important;
  color: var(--cc-ink) !important;
}

/* ---- horizontal progress stepper ---- */
.cc-progress { margin-top: 4px; }
.cc-progress-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px;
}
.cc-progress-top .cc-progress-label { font-size: 13px; color: var(--cc-muted); }
.cc-progress-top .cc-progress-count { font-size: 13px; font-weight: 700; color: var(--cc-ink); }
.cc-stages {
  display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0;
  position: relative;
}
@media (max-width: 980px) {
  .cc-stages { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
}
@media (max-width: 640px) {
  .cc-stages { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
}
.cc-stage {
  position: relative; padding: 0 8px; text-align: center;
}
.cc-stage::before {
  content: ""; position: absolute; top: 15px; left: 0; right: 0; height: 2px;
  background: var(--cc-line); z-index: 0;
}
.cc-stage:first-child::before { left: 50%; }
.cc-stage:last-child::before { right: 50%; }
.cc-stage .cc-dot {
  position: relative; z-index: 1; margin: 0 auto 8px;
  width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
  font-size: 12px; font-weight: 750; background: var(--cc-soft); color: var(--cc-muted);
  border: 2px solid var(--cc-line);
}
.cc-stage .cc-ttl { font-weight: 680; font-size: 12.5px; color: var(--cc-ink); line-height: 1.25; }
.cc-stage .cc-blurb { display: none; }
.cc-stage .cc-pill {
  margin-top: 6px; display: inline-block;
  font-size: 10px; font-weight: 750; letter-spacing: .05em;
  padding: 3px 8px; border-radius: 999px; background: var(--cc-soft); color: var(--cc-muted);
}
.cc-stage.done .cc-dot { background: color-mix(in srgb, var(--cc-ok) 18%, transparent); color: var(--cc-ok); border-color: var(--cc-ok); }
.cc-stage.done .cc-pill { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); }
.cc-stage.done::before { background: color-mix(in srgb, var(--cc-ok) 55%, var(--cc-line)); }
.cc-stage.active .cc-dot {
  background: color-mix(in srgb, var(--cc-accent) 18%, transparent); color: var(--cc-accent);
  border-color: var(--cc-accent); animation: cc-pulse 1.2s infinite;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--cc-accent) 16%, transparent);
}
.cc-stage.active .cc-pill { background: color-mix(in srgb, var(--cc-accent) 16%, transparent); color: var(--cc-accent); }
.cc-stage.active .cc-ttl { color: var(--cc-accent); }
@keyframes cc-pulse { 0%,100% { opacity: 1 } 50% { opacity: .55 } }
.cc-live {
  margin-top: 14px; border-radius: 12px; padding: 11px 13px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  color: var(--cc-ink-2); font-size: 13px;
  display: flex; align-items: center; gap: 8px;
}
.cc-live .cc-blink { color: var(--cc-accent); animation: cc-pulse 1.1s infinite; font-weight: 700; }

/* ---- results ---- */
.cc-meter { margin: 4px 0 18px; }
.cc-meter .cc-meter-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.cc-meter .cc-score { font-size: 34px; font-weight: 800; letter-spacing: -0.03em; color: var(--cc-ink); }
.cc-meter .cc-score small { font-size: 14px; color: var(--cc-muted); font-weight: 600; }
.cc-meter .cc-meter-label { font-size: 12px; color: var(--cc-muted); font-weight: 650; text-align: right; }
.cc-bar { height: 10px; border-radius: 999px; background: var(--cc-soft); overflow: hidden; }
.cc-bar > span {
  display: block; height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--cc-accent), #06b6d4);
}
.cc-stats { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.cc-chip {
  font-size: 12px; font-weight: 650; padding: 5px 10px; border-radius: 999px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-chip.covered { background: color-mix(in srgb, var(--cc-ok) 16%, transparent); color: var(--cc-ok); border-color: color-mix(in srgb, var(--cc-ok) 38%, transparent); }
.cc-chip.reframeable { background: color-mix(in srgb, var(--cc-warn) 16%, transparent); color: var(--cc-warn); border-color: color-mix(in srgb, var(--cc-warn) 38%, transparent); }
.cc-chip.out { background: color-mix(in srgb, var(--cc-bad) 16%, transparent); color: var(--cc-bad); border-color: color-mix(in srgb, var(--cc-bad) 38%, transparent); }
.cc-section-title {
  font-size: 12px; font-weight: 750; text-transform: uppercase; letter-spacing: .08em;
  color: var(--cc-muted); margin: 22px 0 10px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.cc-section-title .cc-count {
  font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: none;
  padding: 3px 9px; border-radius: 999px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-section-lead {
  margin: -4px 0 12px; color: var(--cc-muted); font-size: 13px; line-height: 1.5;
}
.cc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.cc-table th {
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--cc-muted); padding: 8px 10px; border-bottom: 1px solid var(--cc-line);
}
.cc-table td { padding: 11px 10px; border-bottom: 1px solid var(--cc-line); vertical-align: top; color: var(--cc-ink-2); }

/* Suggested resume rewrites */
.cc-bullets { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.cc-bullets li {
  display: grid; grid-template-columns: 28px 1fr; gap: 12px; align-items: start;
  border: 1px solid var(--cc-line); border-radius: 14px; padding: 14px 15px;
  background: var(--cc-surface-2);
}
.cc-bullets .cc-idx {
  width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center;
  font-size: 12px; font-weight: 750; color: var(--cc-accent);
  background: color-mix(in srgb, var(--cc-accent) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--cc-accent) 28%, transparent);
}
.cc-bullets .cc-bullet-body { min-width: 0; }
.cc-bullets li p { margin: 0 0 10px; color: var(--cc-ink); font-size: 14px; line-height: 1.55; font-weight: 600; }
.cc-cite {
  display: flex; align-items: flex-start; gap: 8px; flex-wrap: wrap;
  font-size: 12.5px; line-height: 1.45; color: var(--cc-ink-2);
  padding: 8px 10px; border-radius: 10px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
}
.cc-cite .cc-cite-label {
  flex: 0 0 auto; font-size: 10.5px; font-weight: 750; letter-spacing: .06em;
  text-transform: uppercase; color: var(--cc-muted); padding-top: 1px;
}
.cc-cite .cc-cite-fact { color: var(--cc-ink-2); font-weight: 550; }
.cc-cite b { color: var(--cc-ink); font-weight: 650; }

/* Interview talking points — same card weight as rewrites */
.cc-talks { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.cc-talks li {
  display: grid; grid-template-columns: 28px 1fr; gap: 12px; align-items: start;
  border: 1px solid var(--cc-line); border-radius: 14px; padding: 13px 14px;
  background: var(--cc-surface-2);
}
.cc-talks .cc-idx {
  width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center;
  font-size: 12px; font-weight: 750; color: var(--cc-ok);
  background: color-mix(in srgb, var(--cc-ok) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--cc-ok) 28%, transparent);
}
.cc-talks .cc-talk-text { color: var(--cc-ink); font-size: 13.5px; line-height: 1.55; padding-top: 4px; }

.cc-list { margin: 0; padding-left: 18px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.65; }

/* Do not claim — caution block with readable body text */
.cc-note {
  border: 1px solid color-mix(in srgb, var(--cc-warn) 38%, transparent);
  background: color-mix(in srgb, var(--cc-warn) 12%, transparent); color: var(--cc-warn);
  border-radius: 12px; padding: 11px 13px; font-size: 13px; margin-top: 10px;
}
.cc-note .cc-list { color: var(--cc-ink-2); }
.cc-caution {
  border: 1px solid color-mix(in srgb, var(--cc-bad) 36%, transparent);
  background: color-mix(in srgb, var(--cc-bad) 10%, transparent);
  border-radius: 14px; padding: 14px 15px; margin-top: 4px;
}
.cc-caution .cc-caution-head {
  display: flex; align-items: center; gap: 8px; margin: 0 0 8px;
  color: var(--cc-bad); font-size: 13px; font-weight: 720;
}
.cc-caution .cc-caution-head .cc-caution-mark {
  width: 22px; height: 22px; border-radius: 7px; display: grid; place-items: center;
  font-size: 12px; font-weight: 800;
  background: color-mix(in srgb, var(--cc-bad) 16%, transparent);
  border: 1px solid color-mix(in srgb, var(--cc-bad) 32%, transparent);
}
.cc-caution .cc-caution-lead {
  margin: 0 0 10px; color: var(--cc-ink-2); font-size: 13px; line-height: 1.5;
}
.cc-caution .cc-list {
  margin: 0; padding-left: 18px; color: var(--cc-ink); font-size: 13.5px; line-height: 1.65;
}
.cc-caution .cc-list li { margin: 0 0 4px; }

.cc-qa { display: flex; flex-direction: column; gap: 10px; }
.cc-qa-item {
  border: 1px solid var(--cc-line); border-radius: 14px; padding: 14px 15px; background: var(--cc-surface-2);
}
.cc-qa-item .cc-q { margin: 0 0 6px; font-weight: 680; color: var(--cc-ink); font-size: 13.5px; }
.cc-qa-item .cc-a { margin: 0 0 8px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.55; }

/* Top-level workflow tabs — full-width panels so content never shrinks the page */
.cc-main-tabs,
.cc-main-tabs > .tabs,
.cc-main-tabs .tabs {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
.cc-main-tabs > .tab-nav,
.cc-main-tabs .tabs > .tab-nav {
  gap: 4px !important;
  flex-wrap: wrap !important;
  width: 100% !important;
  border-bottom: 1px solid var(--cc-line) !important;
  margin-bottom: 14px !important;
}
.cc-main-tabs .tab-nav button,
.cc-main-tabs button[role="tab"] {
  font-weight: 650 !important;
  font-size: 13.5px !important;
  border-radius: 10px 10px 0 0 !important;
}
.cc-main-tabs .tabitem,
.cc-main-tabs [role="tabpanel"],
.cc-result-tabs .tabitem,
.cc-result-tabs [role="tabpanel"] {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
.cc-result-tabs {
  margin: 12px 0 14px;
  width: 100% !important;
}

/* Decision dock — step-by-step HITL */
.cc-review {
  border: 1px solid var(--cc-line); border-radius: 18px; background: var(--cc-surface);
  padding: 18px 18px 16px; box-shadow: 0 16px 34px -30px var(--cc-shadow);
  margin-top: 6px;
}
.cc-review .cc-panel-head { margin: 0 0 12px; }
.cc-review .cc-panel-head h3 { margin: 0; font-size: 17px; font-weight: 740; color: var(--cc-ink); }
.cc-review .cc-panel-head .cc-hint { margin: 4px 0 0; color: var(--cc-muted); font-size: 13px; line-height: 1.5; max-width: 70ch; }

.cc-review-steps {
  display: flex; flex-direction: column; gap: 6px;
  margin: 0 0 16px; padding: 10px 12px;
  border-radius: 14px; background: var(--cc-soft);
  border: 1px solid var(--cc-line);
}
.cc-review-step {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px; color: var(--cc-muted); line-height: 1.4;
}
.cc-review-step.active { color: var(--cc-ink); font-weight: 650; }
.cc-review-step.done { color: var(--cc-ink-2); }
.cc-review-step-n {
  flex: 0 0 22px; height: 22px; border-radius: 999px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 740;
  background: var(--cc-surface); border: 1px solid var(--cc-line); color: var(--cc-muted);
}
.cc-review-step.active .cc-review-step-n {
  background: var(--cc-accent); border-color: transparent; color: #fff;
}
.cc-review-step.done .cc-review-step-n {
  background: color-mix(in srgb, var(--cc-good, #22c55e) 18%, transparent);
  border-color: transparent; color: var(--cc-ink);
}
.cc-review-step-t { flex: 1; }
.cc-review-step-pill {
  font-size: 10px; font-weight: 720; letter-spacing: 0.04em;
  padding: 2px 7px; border-radius: 999px;
  background: var(--cc-surface); border: 1px solid var(--cc-line); color: var(--cc-muted);
}
.cc-review-step.active .cc-review-step-pill {
  background: color-mix(in srgb, var(--cc-accent) 16%, transparent);
  border-color: transparent; color: var(--cc-accent);
}

.cc-review-choice {
  border: 1px solid var(--cc-line); border-radius: 14px;
  padding: 12px 14px 14px; margin: 0 0 10px; background: var(--cc-surface-2, var(--cc-surface));
}
.cc-review-choice-a {
  border-color: color-mix(in srgb, var(--cc-accent) 35%, var(--cc-line));
  background: color-mix(in srgb, var(--cc-accent) 6%, transparent);
}
.cc-choice-label {
  display: flex; gap: 10px; align-items: flex-start;
  margin: 0 0 10px; font-size: 13px; line-height: 1.5; color: var(--cc-ink-2);
}
.cc-choice-n {
  flex: 0 0 26px; height: 26px; border-radius: 8px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 780;
  background: var(--cc-soft); border: 1px solid var(--cc-line); color: var(--cc-ink);
}
.cc-review-choice-a .cc-choice-n {
  background: var(--cc-accent); border-color: transparent; color: #fff;
}
.cc-choice-label strong { color: var(--cc-ink); }
.cc-choice-label em { font-style: normal; font-weight: 680; color: var(--cc-accent); }

.cc-review-actions {
  display: flex !important; flex-wrap: wrap !important; align-items: center !important;
  gap: 10px !important; margin-top: 4px !important;
}
.cc-review-actions > div,
.cc-review-actions .block,
.cc-review-actions .form,
.cc-review-actions .wrap {
  background: transparent !important; border: none !important; box-shadow: none !important;
  padding: 0 !important; margin: 0 !important; min-width: 0 !important;
}
button.cc-approve {
  background: linear-gradient(135deg, var(--cc-accent), var(--cc-accent-2)) !important;
  border: none !important; color: #fff !important; font-weight: 720 !important;
  min-height: 42px !important; border-radius: 12px !important;
  box-shadow: 0 12px 24px -14px color-mix(in srgb, var(--cc-accent) 75%, transparent) !important;
}
button.cc-revise, button.cc-reject, button.cc-refresh {
  background: var(--cc-soft) !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink-2) !important; font-weight: 650 !important;
  min-height: 42px !important; border-radius: 12px !important;
  box-shadow: none !important;
}
button.cc-revise {
  background: color-mix(in srgb, var(--cc-accent) 12%, var(--cc-soft)) !important;
  border-color: color-mix(in srgb, var(--cc-accent) 40%, var(--cc-line)) !important;
  color: var(--cc-ink) !important; font-weight: 700 !important;
}
button.cc-reject {
  color: var(--cc-bad) !important;
  border-color: color-mix(in srgb, var(--cc-bad) 35%, var(--cc-line)) !important;
  background: color-mix(in srgb, var(--cc-bad) 8%, transparent) !important;
}
button.cc-refresh {
  min-height: 34px !important; font-size: 12.5px !important; margin-left: auto !important;
}
.cc-review-status { margin-top: 8px; }
.cc-foot { color: var(--cc-muted); font-size: 12px; margin: 8px 0 18px; text-align: center; }

/* ---- alerts / status under the CTA (always visible when set) ---- */
.cc-alert {
  border-radius: 14px; padding: 12px 14px; margin: 8px 0 4px;
  font-size: 13.5px; line-height: 1.5; border: 1px solid transparent;
}
.cc-alert.error {
  background: color-mix(in srgb, var(--cc-bad) 12%, transparent);
  border-color: color-mix(in srgb, var(--cc-bad) 40%, transparent);
  color: var(--cc-ink);
}
.cc-alert.error strong { color: var(--cc-bad); display: block; margin-bottom: 2px; }
.cc-alert.info {
  background: color-mix(in srgb, var(--cc-accent) 10%, transparent);
  border-color: color-mix(in srgb, var(--cc-accent) 34%, transparent);
  color: var(--cc-ink-2);
}
.cc-status-line {
  margin: 6px 0 2px; font-size: 13.5px; color: var(--cc-ink-2); min-height: 1.4em;
}
"""
