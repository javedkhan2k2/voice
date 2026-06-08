# Offline runtime invariant (Phase 3 M5)

VoiceBuilder converts audio **fully on the local device**. No code in the
conversion path may open a network connection. This is a non-negotiable
invariant (`CLAUDE.md`) and is enforced at the **socket layer**, not merely by
configuration.

## Enforcement

`services/offline_check.py`:

- **`block_network()`** — a context manager that replaces
  `socket.socket.__init__` so any socket creation inside the block raises
  `AssertionError`. Restored on exit.
- **`check_offline_invariant(fn)`** — runs `fn()` under `block_network()`. The
  integration test `tests/integration/test_offline.py::test_full_conversion_opens_no_sockets`
  wraps a real mock-engine conversion in this and asserts zero sockets open.
- **`verify_offline() -> OfflineCheckResult`** — a deterministic self-check:
  (1) a *positive control* confirms the guard actually blocks a deliberate
  socket attempt (so it isn't a silent no-op), then (2) a clean run completes
  under the guard. Returns `{ok, detail}` instead of raising.

## Surfacing in the UI

- **Status bar** (main window) shows a persistent `Offline — no network used`
  indicator next to the device info.
- **Settings → Privacy** states the guarantee and offers a **"Verify offline"**
  button. It calls `SettingsViewModel.verify_offline()`, which runs the
  self-check and emits `offline_verified(ok, detail)`; the view shows the result.

## Scope and limits

- The socket guard patches **only the calling (main) process**. Subprocesses
  spawned inside the guarded region — bundled **ffmpeg** for decode/encode and
  the **inference worker** — are separate processes and are not patched.
- Their offline behaviour rests on the architecture: no network code exists in
  the conversion path, ffmpeg is invoked on local files/pipes only, and the
  worker runs local model inference. The guard verifies the orchestration
  (services/main process) layer, which is where any accidental network call
  would most plausibly be introduced.
- This is honest scoping: we assert the invariant where we can enforce it in
  code, and rely on design + review for the subprocesses. A full external
  verification (OS-level network monitor on a clean VM) is part of Phase 4 beta
  hardening.

## Tests

`tests/integration/test_offline.py` — the guard catches socket usage, the
context manager blocks then restores, `verify_offline()` reports ok and leaves
sockets usable, and a full conversion opens no sockets (ffmpeg-guarded).
`tests/app/test_settings_vm.py` — the VM emits `offline_verified`.
