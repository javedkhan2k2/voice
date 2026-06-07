"""Inference layer: VoiceConversionEngine interface and the WorkerAdapter that backs it.

Public API (imported by services/):
  engine.py         — VoiceConversionEngine ABC, data types, CancelToken, exceptions
  worker_adapter.py — WorkerAdapter: manages the worker subprocess and IPC

Internal helpers (not for layers above services/):
  ipc.py            — length-prefixed JSON framing (read_msg / write_msg)
  shm_buffer.py     — ShmBuffer: shared-memory PCM transfer helper
"""
