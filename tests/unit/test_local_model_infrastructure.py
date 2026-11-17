"""Unit tests for P3 Order 6: Local Intelligence Infrastructure & Model Registry."""

from __future__ import annotations

from life_graph.services.local_model_registry import (
    LOCAL_MODEL_REGISTRY,
    RTX_5080_VRAM_GB,
    evaluate_gpu_scheduler_justification,
    probe_ollama_models,
    select_backend_for_task,
)


def test_registry_covers_all_required_task_capabilities_and_vram_limits():
    all_caps = set()
    for spec in LOCAL_MODEL_REGISTRY.values():
        all_caps |= set(spec.capabilities)
    for required in (
        "reasoning",
        "extraction",
        "coding",
        "embeddings",
        "reranking",
        "vision",
        "speech_indic",
    ):
        assert required in all_caps

    assert LOCAL_MODEL_REGISTRY["qwen3:14b"].fits_rtx_5080_vram is True
    assert LOCAL_MODEL_REGISTRY["bge-m3:latest"].fits_rtx_5080_vram is True
    assert LOCAL_MODEL_REGISTRY["qwen3-coder:30b"].fits_rtx_5080_vram is False


def test_personal_data_never_routes_to_cloud_even_when_gpu_is_busy():
    # Personal memory extraction while GPU is busy -> queues locally, NEVER routes to cloud
    decision = select_backend_for_task(
        task_kind="personal_memory_extraction",
        capability="extraction",
        personal_data=True,
        vram_free_gb=2.0,
        user_active_on_gpu=True,
        cloud_models_available=("openrouter/free-model",),
    )
    assert decision.action == "queue_local"
    assert decision.local_only is True
    assert decision.backend == "local_queue"
    assert "personal data never leaves the local machine" in decision.explanation

    # Non-personal coding task while GPU is busy -> routes to free cloud model with clear explanation
    cloud_dec = select_backend_for_task(
        task_kind="code_refactor",
        capability="coding",
        personal_data=False,
        vram_free_gb=2.0,
        user_active_on_gpu=True,
        cloud_models_available=("openrouter/qwen-coder:free",),
    )
    assert cloud_dec.action == "run_cloud"
    assert cloud_dec.local_only is False
    assert cloud_dec.model_id == "openrouter/qwen-coder:free"
    assert "owner is actively using" in cloud_dec.explanation

    # Personal task when VRAM is available -> runs locally on preferred model
    local_dec = select_backend_for_task(
        task_kind="personal_memory_judge",
        capability="reranking",
        personal_data=True,
        preferred_model="qwen3:4b",
        vram_free_gb=RTX_5080_VRAM_GB,
    )
    assert local_dec.action == "run_local"
    assert local_dec.model_id == "qwen3:4b"
    assert local_dec.local_only is True


def test_gpu_scheduler_justification_and_ollama_probe():
    just = evaluate_gpu_scheduler_justification()
    assert just["co_resident_fits_in_16gb"] is True
    assert just["primary_extractor_plus_embedder_vram_gb"] <= RTX_5080_VRAM_GB
    assert just["complex_gpu_scheduler_justified"] is False

    probe = probe_ollama_models()
    assert "reachable" in probe
    assert "installed_models" in probe
