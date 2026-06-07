# Phase 0 — Zero-Shot Voice-Conversion Model Bake-Off

Research/decision task (no implementation code). Selects the default voice-conversion (VC) engine for v1
and the alternative(s) kept behind the `VoiceConversionEngine` adapter. Product scope: `docs/spec.md`.
Architecture: `docs/architecture.md`.

## Decision context (hard constraints from the plan)

- **Audio-to-audio VC**, not TTS — source speech → target voice.
- **Zero-shot from a short reference clip** (seconds, not a training corpus).
- **Strictly local / offline at runtime**; weights may be fetched once at install time.
- **NVIDIA GPU preferred, CPU fallback** must at least complete.
- **License must permit bundled redistribution** in a Windows installer (this is the make-or-break gate;
  commercial intent is still unconfirmed — see `docs/architecture.md` open decisions — so we optimize for
  the strictest case: redistribution in a possibly-commercial closed-source app).
- **Python/PyTorch** runtime (matches the chosen stack).

> The license gate applies to **three layers**, not just the repo: (a) the model **code**, (b) the
> distributed **weights/checkpoints**, and (c) the **training data** those checkpoints were derived from.
> A permissive code license with a non-commercial checkpoint is still a blocker.

## Candidates

| Model | Repo | Code license | Native task |
|---|---|---|---|
| OpenVoice V2 | myshell-ai/OpenVoice | **MIT (code + weights)** | TTS + tone-color cloning; supports A2A VC |
| FreeVC | OlaWod/FreeVC | MIT (code) | One-shot any-to-any VC |
| kNN-VC | bshall/knn-vc | MIT (code) | Any-to-any VC via kNN matching |
| seed-VC | Plachtaa/seed-vc | **GPLv3** | Zero-shot VC + real-time + singing |

## License analysis (the deciding factor)

| Model | Code | Weights | Training-data inheritance | Bundling verdict |
|---|---|---|---|---|
| **OpenVoice V2** | MIT | **MIT (explicit, since Apr 2024)** | Vendor states MIT on the release | **Cleanest.** Lowest legal risk for bundling. |
| **FreeVC** | MIT | Author publishes checkpoints; **license not explicitly stated** | Checkpoints trained on **VCTK 0.92 → ODC-By v1.0** (commercial OK *with attribution*) | Usable, but **requires attribution + confirming checkpoint terms** before bundling. |
| **kNN-VC** | MIT | Prematched HiFi-GAN vocoder | Vocoder trained on **LibriSpeech → CC BY 4.0** (commercial OK *with attribution*) | Usable with attribution; but see task-fit problem below. |
| **seed-VC** | **GPLv3** | GPLv3 | n/a — code license dominates | **Blocked for closed-source/proprietary bundling.** GPLv3 would force the *entire app* to be GPL. Only viable if the product commits to open-source/GPL. |

Shared upstream dependency: **OpenVoice V2, FreeVC and kNN-VC all rely on Microsoft's WavLM** (or a
similar SSL encoder) for content features. WavLM **code is MIT** (microsoft/unilm); the **weight license
should be confirmed on the HuggingFace model card** before bundling (treated as MIT in practice — residual
TODO, low risk).

## Technical comparison

| Criterion | OpenVoice V2 | FreeVC | kNN-VC | seed-VC |
|---|---|---|---|---|
| Short-clip zero-shot (a few sec) | Yes | Yes (one-shot) | **Weak — wants minutes of target audio** for best quality | Yes (1–30 s) |
| Quality (subjective, short ref) | Good, multilingual | Good, English-centric | High *with enough reference* | **State-of-the-art** |
| CUDA support | Yes | Yes | Yes | Yes |
| CPU fallback viability | Workable (light) | Workable (light) | Workable (light) | **Poor — diffusion is heavy on CPU** |
| Approx. VRAM | ~2–4 GB | ~2–4 GB | ~2–3 GB | ~4–6 GB (real-time variant lighter) |
| Real-time future fit | Not designed for it | Not designed for it | Not designed for it | **Native real-time (~300 ms)** |
| Maintenance / community | Active, large | Stable (2023), low activity | Stable (2023) | Active |
| Python/PyTorch | Yes (needs MeloTTS only for TTS path, not VC) | Yes (older pins likely) | Yes (minimal deps) | Yes (modern) |

## Scoring

Weighted for v1 priorities. License is weighted heaviest because it is the stated make-or-break gate.
Scale 1–5 (5 best). Weighted total = Σ(score × weight).

| Criterion (weight) | OpenVoice V2 | FreeVC | kNN-VC | seed-VC |
|---|---|---|---|---|
| License/bundling fit (×3) | 5 | 4 | 4 | 1 |
| Short-clip zero-shot fit (×2) | 4 | 4 | 2 | 5 |
| Quality (×2) | 3.5 | 3.5 | 4 | 5 |
| CPU fallback (×1) | 3.5 | 4 | 4 | 2 |
| VRAM footprint (×1) | 4 | 4 | 4 | 3 |
| Real-time future fit (×1) | 2 | 2 | 2 | 5 |
| Maturity/maintenance (×1) | 4 | 3 | 3 | 4 |
| **Weighted total (max 55)** | **42** | **39** | **35** | **34** |

## Recommendation

**Default v1 engine: OpenVoice V2.** It is the only candidate with an **explicit, permissive license on
both code and weights**, which directly satisfies the hard distribution gate at the lowest legal risk. It
is multilingual, actively maintained, light enough for a CPU fallback, and works zero-shot from a short
reference clip.

**Alternative kept behind the adapter: FreeVC.** It is the most purpose-built any-to-any VC model and a
strong quality contender. Implement it as a second `VoiceConversionEngine` so the default is a config
flip, not a rewrite. **Before bundling FreeVC weights**, confirm the checkpoint license and add VCTK
(ODC-By) attribution.

**Mandatory early validation:** OpenVoice V2's core strength is the TTS + tone-color pipeline; its
audio-to-audio VC quality versus FreeVC's can only be settled by **listening tests on representative
source/target pairs**. Run that A/B during early Phase 1 (M1) on the Phase-0 sample set. If FreeVC's VC
quality is clearly better and its checkpoint terms clear, switch the default to FreeVC. The engine
abstraction makes this reversible.

**Deferred — seed-VC.** Technically the strongest (best quality *and* the only native real-time path,
which matches our future real-time goal), but **GPLv3 blocks proprietary bundling**. Revisit only if the
product explicitly commits to an open-source/GPL license. If that decision lands, seed-VC likely becomes
the preferred engine — so keep the adapter boundary clean to allow the swap.

**Future "high-fidelity mode" — kNN-VC.** Excellent quality, but it needs a larger target reference pool
(minutes), which conflicts with the short-clip flow. Good candidate for a later opt-in mode for users who
can supply more target audio.

## Residual TODOs before locking the bundle

- Confirm **WavLM-Large weight license** on its HuggingFace model card (low risk; treated as MIT).
- Confirm **FreeVC checkpoint license** and required **VCTK ODC-By attribution** text.
- Confirm **kNN-VC prematched-HiFiGAN / LibriSpeech CC BY 4.0** attribution text (if kNN-VC is ever shipped).
- If commercial intent is confirmed, run a full **license audit of the whole dependency tree**
  (PyTorch, ffmpeg, encoders, vocoders) before GA.
- Decide the **open-source vs proprietary** licensing of this app itself — this single decision
  determines whether seed-VC is on or off the table.
- Pin **Python + PyTorch + CUDA** versions compatible with the chosen engine(s) (updates `pyproject.toml`).

## Sources

- FreeVC — [OlaWod/FreeVC](https://github.com/OlaWod/FreeVC) (MIT code; depends on WavLM, HiFi-GAN; checkpoints trained on VCTK)
- OpenVoice V2 — [myshell-ai/OpenVoice](https://github.com/myshell-ai/OpenVoice), [HF: myshell-ai/OpenVoiceV2](https://huggingface.co/myshell-ai/OpenVoiceV2) (MIT code + weights since Apr 2024)
- seed-VC — [Plachtaa/seed-vc](https://github.com/Plachtaa/seed-vc) (GPLv3; real-time ~300 ms; diffusion)
- kNN-VC — [bshall/knn-vc](https://github.com/bshall/knn-vc), [LICENSE](https://github.com/bshall/knn-vc/blob/master/LICENSE) (MIT code; needs larger reference pool)
- WavLM — [microsoft/unilm wavlm](https://github.com/microsoft/unilm/tree/master/wavlm), [HF: microsoft/wavlm-large](https://huggingface.co/microsoft/wavlm-large) (MIT code; confirm weight license)
- VCTK 0.92 — [Edinburgh DataShare](https://datashare.ed.ac.uk/handle/10283/3443?show=full) (ODC-By v1.0)
