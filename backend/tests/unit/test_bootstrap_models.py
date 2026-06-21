import bootstrap_models as bm


def test_cpu_final_uses_ct2_repo_and_plain_dir():
    repo, local = bm.final_target("distil-large-v3", "cpu")
    assert repo == "Systran/faster-distil-whisper-large-v3"
    assert local.replace("\\", "/").endswith("Models/STT/distil-large-v3")


def test_gpu_final_uses_hf_repo_and_hf_dir():
    repo, local = bm.final_target("distil-large-v3", "gpu")
    assert repo == "distil-whisper/distil-large-v3"
    assert local.replace("\\", "/").endswith("Models/STT/distil-large-v3-hf")


def test_unknown_final_model_raises():
    import pytest
    with pytest.raises(KeyError):
        bm.final_target("nope", "gpu")
