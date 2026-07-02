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


def test_final_target_turbo_cpu_uses_community_ct2():
    # Verified 2026-07-01: repo downloads, loads in faster-whisper 1.2.1,
    # and transcribes (community CT2 conversion of openai/whisper-large-v3-turbo).
    import bootstrap_models as bm
    repo, local = bm.final_target("large-v3-turbo", "cpu")
    assert repo == "deepdml/faster-whisper-large-v3-turbo-ct2"
    assert local.replace("\\", "/").endswith("Models/STT/large-v3-turbo")


def test_final_target_turbo_gpu_uses_openai_hf():
    import bootstrap_models as bm
    repo, local = bm.final_target("large-v3-turbo", "gpu")
    assert repo == "openai/whisper-large-v3-turbo"
    assert local.replace("\\", "/").endswith("Models/STT/large-v3-turbo-hf")
