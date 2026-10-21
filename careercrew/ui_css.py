"""Styling only. Not part of the logic; skip during the code talk.

CareerCrew Gradio custom CSS — clean light theme.
"""

CUSTOM_CSS = """
/* Always light, calm, minimal */
:root,
.gradio-container,
body.dark,
.dark {
  --cc-bg: #f7f8fa;
  --cc-surface: #ffffff;
  --cc-surface-2: #fafbfc;
  --cc-line: #e2e5eb;
  --cc-ink: #1a1d24;
  --cc-ink-2: #3d4450;
  --cc-muted: #6b7280;
  --cc-soft: #f0f2f5;
  --cc-accent: #2563eb;
  --cc-ok: #15803d;
  --cc-warn: #b45309;
  --cc-bad: #b91c1c;
  color-scheme: light !important;
}

.gradio-container {
  width: min(1120px, calc(100vw - 32px)) !important;
  max-width: 1120px !important;
  min-width: min(1120px, calc(100vw - 32px)) !important;
  margin: 0 auto !important;
  padding: 16px 0 28px !important;
  box-sizing: border-box !important;
  background: var(--cc-bg) !important;
  color: var(--cc-ink) !important;
}
footer { display: none !important; }
.contain {
  gap: 12px !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}

[data-testid="block-info"] {
  background: transparent !important; border: none !important;
  color: var(--cc-muted) !important; font-size: 12px !important;
  font-weight: 500 !important; padding: 0 !important; margin-bottom: 4px !important;
}

/* ---- brand bar ---- */
.cc-topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 4px 0 8px;
}
.cc-brand { display: flex; align-items: center; gap: 10px; }
.cc-mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--cc-accent);
  color: #fff; display: grid; place-items: center; font-weight: 700; font-size: 14px;
}
.cc-brand-name { font-size: 17px; font-weight: 700; color: var(--cc-ink); }
.cc-brand-tag { font-size: 12px; color: var(--cc-muted); margin-top: 1px; }
.cc-status-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;
  border: 1px solid var(--cc-line); background: var(--cc-surface); color: var(--cc-ink-2);
}
.cc-status-chip .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--cc-ok); }
.cc-status-chip.warn .dot { background: var(--cc-warn); }

.cc-hero {
  border: 1px solid var(--cc-line); border-radius: 10px; padding: 18px 20px;
  background: var(--cc-surface);
}
.cc-hero h1 {
  margin: 0 0 6px 0; font-size: 24px; line-height: 1.25;
  font-weight: 700; color: var(--cc-ink);
}
.cc-hero .cc-sub {
  margin: 0; color: var(--cc-ink-2); font-size: 14px; line-height: 1.5; max-width: 62ch;
}

.cc-badge {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600;
  border: 1px solid transparent;
}
.cc-badge.on  { background: #ecfdf5; color: var(--cc-ok); border-color: #bbf7d0; }
.cc-badge.off { background: #fffbeb; color: var(--cc-warn); border-color: #fde68a; }
.cc-badge.ghost { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); }
.cc-badge.covered { background: #ecfdf5; color: var(--cc-ok); border-color: #bbf7d0; }
.cc-badge.reframeable { background: #fffbeb; color: var(--cc-warn); border-color: #fde68a; }
.cc-badge.out { background: #fef2f2; color: var(--cc-bad); border-color: #fecaca; }
.cc-badge.src { background: var(--cc-soft); color: var(--cc-ink-2); border-color: var(--cc-line); font-family: ui-monospace, monospace; }

.cc-card {
  border: 1px solid var(--cc-line); border-radius: 10px; background: var(--cc-surface);
  padding: 16px 18px;
}
.cc-card h3 { margin: 0 0 4px 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); }
.cc-card .cc-hint { color: var(--cc-muted); font-size: 13px; margin: 0 0 12px 0; line-height: 1.5; }
.cc-empty {
  border: 1px dashed var(--cc-line);
  border-radius: 8px; padding: 22px 18px; text-align: center;
  color: var(--cc-muted); background: var(--cc-surface-2); font-size: 13.5px; line-height: 1.5;
}
.cc-empty strong { display: block; color: var(--cc-ink); font-size: 14px; margin-bottom: 4px; }

/* ---- input panels ---- */
.cc-panel {
  border: 1px solid var(--cc-line) !important; border-radius: 10px !important;
  background: var(--cc-surface) !important; padding: 8px 12px 12px !important;
  min-height: 100%; box-shadow: none !important;
}
.cc-panel-head { margin: 4px 2px 10px; }
.cc-panel-head h3 { margin: 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); }
.cc-panel-head .cc-hint { margin: 3px 0 0; color: var(--cc-muted); font-size: 13px; line-height: 1.45; }
.cc-field textarea, .cc-field input[type="text"], .cc-field input[type="url"] {
  background: #fff !important; color: var(--cc-ink) !important;
  border: 1px solid var(--cc-line) !important; border-radius: 8px !important;
}
.cc-field textarea::placeholder, .cc-field input::placeholder { color: var(--cc-muted) !important; opacity: .9; }

.cc-cta {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 12px !important;
  flex-wrap: wrap !important;
  border: 1px solid var(--cc-line) !important;
  border-radius: 10px !important;
  background: var(--cc-surface) !important;
  padding: 12px 14px !important;
  box-shadow: none !important;
  margin: 2px 0 !important;
}
.cc-cta > div,
.cc-cta .block,
.cc-cta .form,
.cc-cta .wrap,
.cc-cta .panel-wrap,
.cc-cta .styler {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  min-width: 0 !important;
}
.cc-cta .gap { gap: 8px !important; }
.cc-cta-copy { flex: 1 1 260px; min-width: 200px; }
.cc-cta-copy h3 { margin: 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); }
.cc-cta-copy p { margin: 3px 0 0; font-size: 13px; color: var(--cc-muted); line-height: 1.45; max-width: 52ch; }
.cc-cta-actions {
  display: flex !important;
  align-items: center !important;
  justify-content: flex-end !important;
  gap: 8px !important;
  flex: 0 0 auto !important;
}

button.cc-run {
  background: var(--cc-accent) !important;
  border: none !important; color: #fff !important; font-weight: 650 !important;
  box-shadow: none !important;
  min-height: 40px !important; min-width: 148px !important;
  padding: 0 16px !important; border-radius: 8px !important;
}
button.cc-clear {
  background: #fff !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink-2) !important;
  font-weight: 600 !important;
  min-height: 40px !important;
  min-width: 80px !important;
  border-radius: 8px !important;
  box-shadow: none !important;
}
button.cc-clear:hover {
  background: var(--cc-soft) !important;
  color: var(--cc-ink) !important;
}

/* ---- progress stepper ---- */
.cc-progress { margin-top: 2px; }
.cc-progress-top {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px;
}
.cc-progress-top .cc-progress-label { font-size: 13px; color: var(--cc-muted); }
.cc-progress-top .cc-progress-count { font-size: 13px; font-weight: 650; color: var(--cc-ink); }
.cc-stages {
  display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0;
  position: relative;
}
@media (max-width: 720px) {
  .cc-stages { gap: 14px 0; }
  .cc-stage::before { display: none; }
  .cc-stage .cc-ttl { font-size: 11px; }
}
.cc-stage { position: relative; padding: 0 6px; text-align: center; }
.cc-stage::before {
  content: ""; position: absolute; top: 14px; left: 0; right: 0; height: 2px;
  background: var(--cc-line); z-index: 0;
}
.cc-stage:first-child::before { left: 50%; }
.cc-stage:last-child::before { right: 50%; }
.cc-stage .cc-dot {
  position: relative; z-index: 1; margin: 0 auto 6px;
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
  font-size: 12px; font-weight: 700; background: #fff; color: var(--cc-muted);
  border: 2px solid var(--cc-line);
}
.cc-stage .cc-ttl { font-weight: 650; font-size: 12px; color: var(--cc-ink); line-height: 1.25; }
.cc-stage .cc-blurb { display: none; }
.cc-stage .cc-pill {
  margin-top: 5px; display: inline-block;
  font-size: 10px; font-weight: 700; letter-spacing: .04em;
  padding: 2px 7px; border-radius: 6px; background: var(--cc-soft); color: var(--cc-muted);
}
.cc-stage.done .cc-dot { background: #ecfdf5; color: var(--cc-ok); border-color: var(--cc-ok); }
.cc-stage.done .cc-pill { background: #ecfdf5; color: var(--cc-ok); }
.cc-stage.done::before { background: #86efac; }
.cc-stage.active .cc-dot {
  background: #eff6ff; color: var(--cc-accent); border-color: var(--cc-accent);
}
.cc-stage.active .cc-pill { background: #eff6ff; color: var(--cc-accent); }
.cc-stage.active .cc-ttl { color: var(--cc-accent); }
.cc-live {
  margin-top: 12px; border-radius: 8px; padding: 10px 12px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
  color: var(--cc-ink-2); font-size: 13px;
  display: flex; align-items: center; gap: 8px;
}
.cc-live .cc-blink { color: var(--cc-accent); font-weight: 700; }

/* ---- results ---- */
.cc-meter { margin: 4px 0 16px; }
.cc-meter .cc-meter-top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.cc-meter .cc-score { font-size: 30px; font-weight: 750; color: var(--cc-ink); }
.cc-meter .cc-score small { font-size: 13px; color: var(--cc-muted); font-weight: 600; }
.cc-meter .cc-meter-label { font-size: 12px; color: var(--cc-muted); font-weight: 600; text-align: right; }
.cc-bar { height: 8px; border-radius: 999px; background: var(--cc-soft); overflow: hidden; }
.cc-bar > span {
  display: block; height: 100%; border-radius: 999px; background: var(--cc-accent);
}
.cc-stats { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.cc-chip {
  font-size: 12px; font-weight: 600; padding: 4px 9px; border-radius: 6px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-chip.covered { background: #ecfdf5; color: var(--cc-ok); border-color: #bbf7d0; }
.cc-chip.reframeable { background: #fffbeb; color: var(--cc-warn); border-color: #fde68a; }
.cc-chip.out { background: #fef2f2; color: var(--cc-bad); border-color: #fecaca; }
.cc-section-title {
  font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
  color: var(--cc-muted); margin: 18px 0 8px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.cc-section-title .cc-count {
  font-size: 11px; font-weight: 650; letter-spacing: 0; text-transform: none;
  padding: 2px 8px; border-radius: 6px;
  background: var(--cc-soft); color: var(--cc-ink-2); border: 1px solid var(--cc-line);
}
.cc-section-lead {
  margin: -2px 0 10px; color: var(--cc-muted); font-size: 13px; line-height: 1.45;
}
.cc-table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.cc-table th {
  text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--cc-muted); padding: 8px 8px; border-bottom: 1px solid var(--cc-line);
}
.cc-table td { padding: 10px 8px; border-bottom: 1px solid var(--cc-line); vertical-align: top; color: var(--cc-ink-2); }

.cc-bullets { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.cc-bullets li {
  display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: start;
  border: 1px solid var(--cc-line); border-radius: 8px; padding: 12px;
  background: var(--cc-surface-2);
}
.cc-bullets .cc-idx {
  width: 26px; height: 26px; border-radius: 6px; display: grid; place-items: center;
  font-size: 12px; font-weight: 700; color: var(--cc-accent);
  background: #eff6ff; border: 1px solid #bfdbfe;
}
.cc-bullets .cc-bullet-body { min-width: 0; }
.cc-bullets li p { margin: 0 0 8px; color: var(--cc-ink); font-size: 13.5px; line-height: 1.5; font-weight: 600; }
.cc-cite {
  display: flex; align-items: flex-start; gap: 8px; flex-wrap: wrap;
  font-size: 12.5px; line-height: 1.45; color: var(--cc-ink-2);
  padding: 7px 9px; border-radius: 6px;
  background: var(--cc-soft); border: 1px solid var(--cc-line);
}
.cc-cite .cc-cite-label {
  flex: 0 0 auto; font-size: 10px; font-weight: 700; letter-spacing: .05em;
  text-transform: uppercase; color: var(--cc-muted); padding-top: 1px;
}
.cc-cite .cc-cite-fact { color: var(--cc-ink-2); }
.cc-cite b { color: var(--cc-ink); font-weight: 650; }

.cc-talks { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.cc-talks li {
  display: grid; grid-template-columns: 26px 1fr; gap: 10px; align-items: start;
  border: 1px solid var(--cc-line); border-radius: 8px; padding: 12px;
  background: var(--cc-surface-2);
}
.cc-talks .cc-idx {
  width: 26px; height: 26px; border-radius: 6px; display: grid; place-items: center;
  font-size: 12px; font-weight: 700; color: var(--cc-ok);
  background: #ecfdf5; border: 1px solid #bbf7d0;
}
.cc-talks .cc-talk-text { color: var(--cc-ink); font-size: 13.5px; line-height: 1.5; padding-top: 3px; }

.cc-list { margin: 0; padding-left: 18px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.6; }

.cc-note {
  border: 1px solid #fde68a; background: #fffbeb; color: var(--cc-warn);
  border-radius: 8px; padding: 10px 12px; font-size: 13px; margin-top: 8px;
}
.cc-note .cc-list { color: var(--cc-ink-2); }
.cc-caution {
  border: 1px solid #fecaca; background: #fef2f2;
  border-radius: 8px; padding: 12px; margin-top: 4px;
}
.cc-caution .cc-caution-head {
  display: flex; align-items: center; gap: 8px; margin: 0 0 6px;
  color: var(--cc-bad); font-size: 13px; font-weight: 700;
}
.cc-caution .cc-caution-head .cc-caution-mark {
  width: 20px; height: 20px; border-radius: 5px; display: grid; place-items: center;
  font-size: 11px; font-weight: 800; background: #fee2e2; border: 1px solid #fecaca;
}
.cc-caution .cc-caution-lead {
  margin: 0 0 8px; color: var(--cc-ink-2); font-size: 13px; line-height: 1.45;
}
.cc-caution .cc-list {
  margin: 0; padding-left: 18px; color: var(--cc-ink); font-size: 13.5px; line-height: 1.6;
}
.cc-caution .cc-list li { margin: 0 0 3px; }

.cc-qa { display: flex; flex-direction: column; gap: 8px; }
.cc-qa-item {
  border: 1px solid var(--cc-line); border-radius: 8px; padding: 12px; background: var(--cc-surface-2);
}
.cc-qa-item .cc-q { margin: 0 0 5px; font-weight: 650; color: var(--cc-ink); font-size: 13.5px; }
.cc-qa-item .cc-a { margin: 0 0 6px; color: var(--cc-ink-2); font-size: 13.5px; line-height: 1.5; }

/* Tabs — stable width */
.cc-main-tabs,
.cc-main-tabs > .tabs,
.cc-main-tabs .tabs {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
.cc-main-tabs > .tab-nav,
.cc-main-tabs .tabs > .tab-nav {
  gap: 2px !important;
  flex-wrap: wrap !important;
  width: 100% !important;
  border-bottom: 1px solid var(--cc-line) !important;
  margin-bottom: 12px !important;
  background: transparent !important;
}
.cc-main-tabs .tab-nav button,
.cc-main-tabs button[role="tab"] {
  font-weight: 600 !important;
  font-size: 13.5px !important;
  border-radius: 6px 6px 0 0 !important;
  color: var(--cc-ink-2) !important;
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
  margin: 10px 0 12px;
  width: 100% !important;
}

/* Decision dock */
.cc-review {
  border: 1px solid var(--cc-line); border-radius: 10px; background: var(--cc-surface);
  padding: 14px 16px; margin-top: 4px; box-shadow: none;
}
.cc-review .cc-panel-head { margin: 0 0 10px; }
.cc-review .cc-panel-head h3 { margin: 0; font-size: 15px; font-weight: 700; color: var(--cc-ink); }
.cc-review .cc-panel-head .cc-hint { margin: 3px 0 0; color: var(--cc-muted); font-size: 13px; line-height: 1.45; max-width: 70ch; }

.cc-review-steps {
  display: flex; flex-direction: column; gap: 4px;
  margin: 0 0 12px; padding: 8px 10px;
  border-radius: 8px; background: var(--cc-soft);
  border: 1px solid var(--cc-line);
}
.cc-review-step {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--cc-muted); line-height: 1.4;
}
.cc-review-step.active { color: var(--cc-ink); font-weight: 650; }
.cc-review-step.done { color: var(--cc-ink-2); }
.cc-review-step-n {
  flex: 0 0 20px; height: 20px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700;
  background: #fff; border: 1px solid var(--cc-line); color: var(--cc-muted);
}
.cc-review-step.active .cc-review-step-n {
  background: var(--cc-accent); border-color: var(--cc-accent); color: #fff;
}
.cc-review-step.done .cc-review-step-n {
  background: #ecfdf5; border-color: #bbf7d0; color: var(--cc-ok);
}
.cc-review-step-t { flex: 1; }
.cc-review-step-pill {
  font-size: 10px; font-weight: 700; letter-spacing: 0.03em;
  padding: 2px 6px; border-radius: 6px;
  background: #fff; border: 1px solid var(--cc-line); color: var(--cc-muted);
}
.cc-review-step.active .cc-review-step-pill {
  background: #eff6ff; border-color: #bfdbfe; color: var(--cc-accent);
}

.cc-review-choice {
  border: 1px solid var(--cc-line); border-radius: 8px;
  padding: 10px 12px 12px; margin: 0 0 8px; background: var(--cc-surface-2);
}
.cc-review-choice-a {
  border-color: #bfdbfe;
  background: #f8fbff;
}
.cc-choice-label {
  display: flex; gap: 8px; align-items: flex-start;
  margin: 0 0 8px; font-size: 13px; line-height: 1.45; color: var(--cc-ink-2);
}
.cc-choice-n {
  flex: 0 0 24px; height: 24px; border-radius: 6px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 750;
  background: var(--cc-soft); border: 1px solid var(--cc-line); color: var(--cc-ink);
}
.cc-review-choice-a .cc-choice-n {
  background: var(--cc-accent); border-color: var(--cc-accent); color: #fff;
}
.cc-choice-label strong { color: var(--cc-ink); }
.cc-choice-label em { font-style: normal; font-weight: 650; color: var(--cc-accent); }

.cc-review-actions {
  display: flex !important; flex-wrap: wrap !important; align-items: center !important;
  gap: 8px !important; margin-top: 2px !important;
}
.cc-review-actions > div,
.cc-review-actions .block,
.cc-review-actions .form,
.cc-review-actions .wrap {
  background: transparent !important; border: none !important; box-shadow: none !important;
  padding: 0 !important; margin: 0 !important; min-width: 0 !important;
}
button.cc-approve {
  background: var(--cc-accent) !important;
  border: none !important; color: #fff !important; font-weight: 650 !important;
  min-height: 40px !important; border-radius: 8px !important;
  box-shadow: none !important;
}
button.cc-revise, button.cc-reject, button.cc-refresh {
  background: #fff !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink-2) !important; font-weight: 600 !important;
  min-height: 40px !important; border-radius: 8px !important;
  box-shadow: none !important;
}
button.cc-revise {
  border-color: #bfdbfe !important;
  color: var(--cc-accent) !important; font-weight: 650 !important;
  background: #eff6ff !important;
}
button.cc-reject {
  color: var(--cc-bad) !important;
  border-color: #fecaca !important;
  background: #fef2f2 !important;
}
button.cc-refresh {
  min-height: 32px !important; font-size: 12.5px !important; margin-left: auto !important;
}
.cc-review-status { margin-top: 6px; }
.cc-foot { color: var(--cc-muted); font-size: 12px; margin: 6px 0 12px; text-align: center; }

.cc-alert {
  border-radius: 8px; padding: 10px 12px; margin: 6px 0 2px;
  font-size: 13.5px; line-height: 1.45; border: 1px solid transparent;
}
.cc-alert.error {
  background: #fef2f2; border-color: #fecaca; color: var(--cc-ink);
}
.cc-alert.error strong { color: var(--cc-bad); display: block; margin-bottom: 2px; }
.cc-alert.info {
  background: #eff6ff; border-color: #bfdbfe; color: var(--cc-ink-2);
}
.cc-status-line {
  margin: 4px 0 2px; font-size: 13.5px; color: var(--cc-ink-2); min-height: 1.4em;
}

/* Soften Gradio chrome toward the same light look */
.gradio-container .block,
.gradio-container .form,
.gradio-container .panel {
  background: transparent !important;
}

/* ------------------------------------------------------------------ */
/* Light mode is not optional.                                        */
/* Gradio adds a "dark" class to <body> whenever the OS prefers dark,  */
/* which swaps its whole palette (navy upload zones, dark inputs).     */
/* The companion script in LIGHT_MODE_JS strips that class; these      */
/* overrides cover the window before it runs and any stray dark scope. */
/* ------------------------------------------------------------------ */
html,
body,
body.dark,
.dark,
:root.dark,
:root .dark {
  color-scheme: light !important;
  --body-background-fill: #f7f8fa !important;
  --body-text-color: #1a1d24 !important;
  --body-text-color-subdued: #3d4450 !important;
  --background-fill-primary: #ffffff !important;
  --background-fill-secondary: #fafbfc !important;
  --border-color-primary: #e2e5eb !important;
  --border-color-accent: #bfdbfe !important;
  --border-color-accent-subdued: #bfdbfe !important;
  --block-background-fill: #ffffff !important;
  --block-border-color: #e2e5eb !important;
  --block-info-text-color: #6b7280 !important;
  --block-label-background-fill: #fafbfc !important;
  --block-label-border-color: #e2e5eb !important;
  --block-label-text-color: #6b7280 !important;
  --block-title-text-color: #3d4450 !important;
  --panel-background-fill: #ffffff !important;
  --panel-border-color: #e2e5eb !important;
  --input-background-fill: #ffffff !important;
  --input-background-fill-focus: #ffffff !important;
  --input-background-fill-hover: #ffffff !important;
  --input-border-color: #e2e5eb !important;
  --input-border-color-focus: #bfdbfe !important;
  --input-border-color-hover: #d1d5db !important;
  --input-placeholder-color: #9ca3af !important;
  --code-background-fill: #f0f2f5 !important;
  --checkbox-background-color: #ffffff !important;
  --checkbox-border-color: #d1d5db !important;
  --checkbox-label-background-fill: #ffffff !important;
  --checkbox-label-border-color: #e2e5eb !important;
  --checkbox-label-text-color: #1a1d24 !important;
  --color-accent: #2563eb !important;
  --color-accent-soft: #eff6ff !important;
  --table-border-color: #e2e5eb !important;
  --table-even-background-fill: #ffffff !important;
  --table-odd-background-fill: #fafbfc !important;
  --table-text-color: #3d4450 !important;
  --stat-background-fill: linear-gradient(to right, #60a5fa, #2563eb) !important;
  --button-secondary-background-fill: #ffffff !important;
  --button-secondary-background-fill-hover: #f0f2f5 !important;
  --button-secondary-border-color: #e2e5eb !important;
  --button-secondary-text-color: #3d4450 !important;
  --error-background-fill: #fef2f2 !important;
  --error-text-color: #b91c1c !important;
  --link-text-color: #2563eb !important;
  --accordion-text-color: #1a1d24 !important;
}

body {
  background: var(--cc-bg) !important;
  color: var(--cc-ink) !important;
}
gradio-app {
  background: var(--cc-bg) !important;
}

/* ---- Gradio file uploader: light, dashed, quiet ---- */
.gradio-container .cc-field.block,
.gradio-container .cc-field {
  background: #ffffff !important;
  border: 1px solid var(--cc-line) !important;
  border-radius: 8px !important;
  padding: 10px 12px !important;
  color: var(--cc-ink) !important;
}
.gradio-container .cc-field button.upload-container,
.gradio-container button.upload-container {
  background: var(--cc-surface-2) !important;
  border: 1px dashed var(--cc-line) !important;
  border-radius: 8px !important;
  color: var(--cc-muted) !important;
  box-shadow: none !important;
  transition: background .15s ease, border-color .15s ease;
}
.gradio-container button.upload-container:hover,
.gradio-container button.upload-container:focus-visible {
  background: #eff6ff !important;
  border-color: #bfdbfe !important;
  color: var(--cc-accent) !important;
}
.gradio-container .cc-field [data-testid="upload-text"],
.gradio-container .cc-field [data-testid="upload-text"] span {
  color: var(--cc-muted) !important;
}
.gradio-container .cc-field button.upload-container:hover [data-testid="upload-text"],
.gradio-container .cc-field button.upload-container:hover [data-testid="upload-text"] span {
  color: var(--cc-accent) !important;
}
.gradio-container .cc-field [data-testid="upload-text"] .or { color: #9ca3af !important; }
.gradio-container .cc-field [data-testid="block-label"],
.gradio-container [data-testid="block-label"] {
  background: transparent !important;
  border: none !important;
  color: var(--cc-muted) !important;
  font-size: 12px !important;
  font-weight: 600 !important;
}
.gradio-container .cc-field .file-preview,
.gradio-container .file-preview {
  background: var(--cc-surface-2) !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink) !important;
}

/* ---- Accordion, tabs, slider, chatbot ---- */
.gradio-container .cc-panel .label-wrap,
.gradio-container details > summary {
  background: transparent !important;
  color: var(--cc-ink-2) !important;
  font-size: 13px !important;
  font-weight: 600 !important;
}
.gradio-container .cc-main-tabs button[role="tab"],
.gradio-container .cc-result-tabs button[role="tab"] {
  color: var(--cc-muted) !important;
  background: transparent !important;
}
.gradio-container .cc-main-tabs button[role="tab"][aria-selected="true"],
.gradio-container .cc-result-tabs button[role="tab"][aria-selected="true"] {
  color: var(--cc-accent) !important;
}
.gradio-container .cc-main-tabs .tab-nav,
.gradio-container .cc-result-tabs .tab-nav {
  border-bottom: 1px solid var(--cc-line) !important;
  background: transparent !important;
}
.gradio-container input[type="range"] { accent-color: var(--cc-accent); }
.gradio-container .cc-panel button:not(.cc-run):not(.cc-clear),
.gradio-container .cc-panel button.secondary {
  background: #ffffff !important;
  border: 1px solid var(--cc-line) !important;
  color: var(--cc-ink-2) !important;
  box-shadow: none !important;
}
.gradio-container .cc-panel button:not(.cc-run):not(.cc-clear):hover {
  background: var(--cc-soft) !important;
  color: var(--cc-ink) !important;
}
.gradio-container .chatbot,
.gradio-container .bubble-wrap {
  background: #ffffff !important;
  border-color: var(--cc-line) !important;
  color: var(--cc-ink) !important;
}
.gradio-container .message.user {
  background: #eff6ff !important;
  color: var(--cc-ink) !important;
  border-color: #bfdbfe !important;
}
.gradio-container .message.bot {
  background: var(--cc-surface-2) !important;
  color: var(--cc-ink) !important;
  border-color: var(--cc-line) !important;
}
"""

# Gradio re-applies the "dark" class to <body> whenever the OS is in dark
# mode (matchMedia listener inside its bundle). The app is light-only, so we
# strip the class and keep it stripped. A stylesheet is also injected with the
# light palette scoped to .dark, which covers the first paint before the
# observer runs.
LIGHT_MODE_JS = """
() => {
  const forceLight = () => {
    const html = document.documentElement;
    const body = document.body;
    if (!html || !body) return;
    if (html.classList.contains("dark")) html.classList.remove("dark");
    if (body.classList.contains("dark")) body.classList.remove("dark");
    html.style.colorScheme = "light";
    body.style.colorScheme = "light";
    body.style.background = "#f7f8fa";
    body.style.color = "#1a1d24";
  };

  forceLight();
  document.addEventListener("DOMContentLoaded", forceLight);

  // Gradio keeps a media-query listener that flips the class back.
  const watch = new MutationObserver(forceLight);
  const start = () => {
    if (!document.body) return setTimeout(start, 10);
    forceLight();
    watch.observe(document.body, { attributes: true, attributeFilter: ["class", "style"] });
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  };
  start();

  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => forceLight();
  if (mq.addEventListener) mq.addEventListener("change", onChange);
  else if (mq.addListener) mq.addListener(onChange);
}
"""
