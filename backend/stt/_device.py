"""Runtime probe for an available ROCm/HIP GPU usable by torch.

Isolated so the worker's backend selection can be unit-tested by stubbing torch.
"""
import logging

logger = logging.getLogger(__name__)


def rocm_available() -> bool:
    """True when torch is importable, built with HIP, and a GPU is visible.
    Never raises — any failure means 'no usable ROCm GPU'."""
    try:
        import torch
        return bool(getattr(torch.version, "hip", None)) and torch.cuda.is_available()
    except Exception as exc:  # ImportError, driver errors, etc.
        logger.info("ROCm GPU not available: %s", exc)
        return False
