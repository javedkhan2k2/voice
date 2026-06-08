# Accessibility checklist (Phase 2 M6)

Applies to every view in `src/voiceconv/app/views/`. Automated coverage lives in
`tests/app/test_accessibility.py`; items marked **(manual)** require a human pass
with a screen reader and keyboard only.

## Per-view requirements

1. **Screen-reader labels** — every interactive widget (line edit, combo box,
   checkbox, push button, list, table, progress bar) sets a non-empty
   `accessibleName`. Where a control repeats per row (Queue actions/progress),
   the name includes the source filename so it is unambiguous in a list.
   *Tested:* presence asserted for all controls in all six tabs.

2. **Keyboard navigation (manual)** — every action is reachable with Tab/Shift+Tab
   and activatable with Space/Enter. Primary buttons expose Alt-key mnemonics
   (`&` in the label); mnemonics within a view do not collide
   (e.g. Convert `&C` vs `Ca&ncel`). *Partially tested:* mnemonic distinctness on
   the Convert buttons.

3. **Focus indicators (manual)** — the default Qt focus rectangle is preserved
   (no stylesheet removes outline/focus). Verify a visible focus ring on each
   control while tabbing.

4. **No colour-only status cues** — Queue job status is rendered as **text**
   (`QUEUED`/`RUNNING`/`DONE`/`CANCELLED`/`FAILED`) plus a tooltip; colour is a
   secondary cue only. Status colours are darkened to meet WCAG AA contrast on
   the light table background. *Tested:* status item text equals the status name
   for every `JobStatus`.

5. **High-DPI / contrast (manual)** — layouts use Qt logical pixels (DPI-scaled
   automatically); no hard-coded font sizes drive primary content. Verify at
   150%/200% scaling and under a high-contrast theme.

## Manual audit log

Run before tagging Phase 2 exit. Record date + OS + screen reader (Narrator/NVDA):

- [ ] Tab-only walkthrough of all six tabs reaches every control in logical order.
- [ ] Narrator announces a meaningful name for every focused control.
- [ ] Alt-mnemonics activate the labelled buttons.
- [ ] 200% display scaling: no clipped text or overlapping controls.
- [ ] High-contrast theme: all text and status cues remain legible.
