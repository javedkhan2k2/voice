"""GPU / device detection shim."""

from __future__ import annotations


def detect_device() -> dict:
    """Probe the available compute device.

    Returns a dict with keys:
    - ``device``: ``"cuda"`` or ``"cpu"``
    - ``vram_mb``: int (VRAM in MiB) or ``None`` for CPU
    - ``note``: human-readable description string
    """
    try:
        import torch  # type: ignore[import]

        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "device": "cuda",
                "vram_mb": props.total_memory // (1024 * 1024),
                "note": props.name,
            }
        return {"device": "cpu", "vram_mb": None, "note": "No CUDA GPU detected"}
    except ImportError:
        return {
            "device": "cpu",
            "vram_mb": None,
            "note": "PyTorch not installed — running in mock mode",
        }
