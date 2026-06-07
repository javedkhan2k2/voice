# Phase 4 — Packaging, Installer, Hardening & Beta

Turns the working app into a distributable Windows 11 product. Architecture/packaging notes:
`docs/architecture.md`. This is the GA-readiness phase.

> Prerequisite: **Phases 1–3 exit criteria met.** Feature-complete app with safeguards and offline
> guarantee in place; only distribution, hardening, and sign-off remain.

## Scope

In scope:

- **Runtime bundling:** embedded CPython + pinned wheels (incl. PyTorch CUDA/CPU) reproducibly packaged.
- **Install-time weight fetch:** download model weights + runtime at install time, **checksum-verified**
  against a manifest; runtime stays fully offline thereafter.
- **Installer:** Inno Setup producing a standard installed app (Start-menu entry, uninstaller).
- **Build strategy:** single GPU+CPU build vs base (CPU) install + optional GPU pack — decide and implement.
- **Hardening:** crash handling/reporting (local only), performance tuning, VRAM lifecycle under repeated
  jobs.
- **Beta:** clean-VM install matrix and beta sign-off.

Out of scope: auto-update service, app store distribution, non-Windows installers (portability preserved,
not built).

## Milestone breakdown

| # | Milestone | Outcome |
|---|---|---|
| M1 | **Runtime bundling** | Reproducible embedded-Python + pinned-wheel bundle (GPU and CPU variants); ffmpeg binary bundled. |
| M2 | **Install-time weight fetch + manifest** | Weights/runtime fetched once at install with checksum verification; explicit consent + disclosure; runtime offline afterward. |
| M3 | **Inno Setup installer** | Install / uninstall / update flows; Start-menu + uninstaller; clean removal (except user-chosen data). |
| M4 | **Build-strategy decision** | Single GPU+CPU installer vs base + optional GPU pack, implemented and documented. |
| M5 | **Crash handling + perf tuning** | Local crash reports (no audio); VRAM released across repeated jobs; throughput tuned and measured. |
| M6 | **Clean-VM install matrix + beta** | Tested on fresh Win 11 (GPU present/absent, varied drivers); post-install offline verification; beta sign-off. |

Dependency order: M1 → M2 → M3 → M4; M5 parallel after M1; M6 last.

## Acceptance criteria

- A clean Windows 11 machine installs the app and runs a conversion **fully offline** post-install.
- Install-time weight fetch is checksum-verified and clearly disclosed/consented; a tampered/missing
  weight is detected and surfaced.
- Install, uninstall, and update all work; uninstall leaves no residue except user-chosen data.
- The app runs on machines **with and without** an NVIDIA GPU (CPU fallback completes with a clear notice).
- VRAM is released across repeated jobs; no leak-driven crash over a long session.
- Installer size and download strategy are documented and acceptable.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Package size (PyTorch + CUDA + weights) | Huge download, drop-off | Base (CPU) + optional GPU pack; compress; document expectations. |
| CUDA/driver variance across machines | Install/run failures | Hardware probe + clear messaging; robust CPU fallback; test matrix in M6. |
| Unsigned installer → SmartScreen warning | Trust/adoption hit | Pursue a code-signing certificate; document if unavailable (ties to commercial-intent decision). |
| Dependency-tree license obligations at GA | Distribution/legal risk | Full license audit before GA (PyTorch, ffmpeg, encoders/vocoders, model weights + training-data attribution). |
| Install-time fetch fails offline-only environments | Cannot install | Offer an optional fully-bundled (large) installer variant — TODO decision. |

## Test strategy

- **Clean-VM matrix:** fresh Win 11 images — GPU present / GPU absent / older driver — for install, run,
  uninstall, update.
- **Offline verification:** post-install conversion under a network monitor asserts zero outbound traffic.
- **Integrity:** corrupt/missing weight detected by checksum; surfaced cleanly.
- **Endurance:** repeated-job session to confirm VRAM/memory stability.
- **Uninstall:** filesystem diff confirms clean removal (minus user-chosen data).

## Exit criteria

- All acceptance criteria pass across the clean-VM matrix.
- Offline-after-install guarantee verified at the network layer.
- Full dependency + weight + training-data **license audit complete and cleared** for the distribution
  model chosen (open-source vs proprietary).
- Code-signing resolved (cert obtained, or absence documented with mitigation).
- Beta sign-off recorded; known limitations documented.

## Phase 4 TODOs

- Decide build strategy: single GPU+CPU installer vs base + optional GPU pack.
- Decide whether to also offer a fully-bundled offline installer (no install-time fetch).
- Obtain a code-signing certificate (depends on commercial-intent decision).
- Finalize the **app's own license** (open-source vs proprietary) — gates the dependency audit and the
  seed-VC reconsideration from Phase 0.
- Select Python/PyTorch/CUDA pinned versions and the wheel/runtime bundling tool.
