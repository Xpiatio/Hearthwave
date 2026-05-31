import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ComputeBackend:
    provider: str
    device_label: str
    ort_providers: list[str] = field(default_factory=list)


def detect() -> ComputeBackend:
    # CUDA / ROCm — single torch import attempt reused for both probes
    try:
        import torch
        try:
            if torch.cuda.is_available():
                b = ComputeBackend(
                    provider="CUDAExecutionProvider",
                    device_label="NVIDIA GPU (CUDA)",
                    ort_providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                )
                logger.info("Hardware backend selected: %s", b.device_label)
                return b
        except Exception:
            pass

        # ROCm
        try:
            if torch.version.hip is not None:
                b = ComputeBackend(
                    provider="ROCMExecutionProvider",
                    device_label="AMD GPU (ROCm)",
                    ort_providers=["ROCMExecutionProvider", "CPUExecutionProvider"],
                )
                logger.info("Hardware backend selected: %s", b.device_label)
                return b
        except Exception:
            pass
    except ImportError:
        pass

    # OpenVINO (standalone import — covers CPU/GPU/VPU targets other than NPU)
    try:
        import openvino  # noqa: F401
        try:
            b = ComputeBackend(
                provider="OpenVINOExecutionProvider",
                device_label="Intel OpenVINO",
                ort_providers=["OpenVINOExecutionProvider", "CPUExecutionProvider"],
            )
            logger.info("Hardware backend selected: %s", b.device_label)
            return b
        except Exception:
            pass
    except ImportError:
        pass

    # NPU via ORT OpenVINO provider with an NPU device string
    try:
        import onnxruntime
        try:
            if "OpenVINOExecutionProvider" in onnxruntime.get_available_providers():
                # ORT exposes the active OpenVINO device through provider options;
                # the string "NPU" appears when the OpenVINO runtime enumerates a
                # dedicated Neural Processing Unit.
                try:
                    all_providers = onnxruntime.get_all_providers()
                except AttributeError:
                    all_providers = []
                device_ids = [p for p in all_providers if "NPU" in str(p)]
                if device_ids:
                    b = ComputeBackend(
                        provider="OpenVINOExecutionProvider",
                        device_label="Neural Processing Unit (NPU)",
                        ort_providers=["OpenVINOExecutionProvider", "CPUExecutionProvider"],
                    )
                    logger.info("Hardware backend selected: %s", b.device_label)
                    return b
        except Exception:
            pass
    except ImportError:
        pass

    # CPU fallback
    b = ComputeBackend(
        provider="CPUExecutionProvider",
        device_label="CPU (quantized)",
        ort_providers=["CPUExecutionProvider"],
    )
    logger.info("Hardware backend selected: %s", b.device_label)
    return b
