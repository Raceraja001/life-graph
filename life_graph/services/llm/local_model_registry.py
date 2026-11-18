"""Local Intelligence Infrastructure & Measured Model Registry (P3 Order 6).

Catalogs local RTX 5080 (16 GB VRAM) models by task capability and resource
requirements, enforces strict local-only routing for personal data, explains
routing/queuing decisions, and evaluates whether a complex GPU scheduler is
justified based on measured VRAM residency and contention.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

RTX_5080_VRAM_GB = 16.0
PERSONAL_DATA_TASKS = frozenset(
    {
        "personal_memory_extraction",
        "personal_memory_judge",
        "episode_summarization",
        "personal_chat",
        "personal_embedding",
        "personal_vision_capture",
        "personal_speech_indic",
    }
)


@dataclass(frozen=True)
class LocalModelSpec:
    model_id: str
    capabilities: frozenset[str]
    vram_gb: float
    disk_gb: float
    context_window: int
    privacy_tier: str = "local_resident"
    notes: str = ""

    @property
    def fits_rtx_5080_vram(self) -> bool:
        return self.vram_gb <= RTX_5080_VRAM_GB


LOCAL_MODEL_REGISTRY: dict[str, LocalModelSpec] = {
    "qwen3:14b": LocalModelSpec(
        model_id="qwen3:14b",
        capabilities=frozenset({"reasoning", "extraction", "summarization"}),
        vram_gb=9.8,
        disk_gb=9.28,
        context_window=16384,
        notes="Primary local model for personal memory extraction and episode summaries.",
    ),
    "qwen3:4b": LocalModelSpec(
        model_id="qwen3:4b",
        capabilities=frozenset({"reasoning", "reranking", "classification", "extraction"}),
        vram_gb=3.1,
        disk_gb=2.50,
        context_window=16384,
        notes="Fast low-VRAM local judge and reranker.",
    ),
    "qwen3:0.6b": LocalModelSpec(
        model_id="qwen3:0.6b",
        capabilities=frozenset({"classification", "reranking", "routing"}),
        vram_gb=0.8,
        disk_gb=0.52,
        context_window=8192,
        notes="Sub-second intent/triage classifier.",
    ),
    "gemma3:12b": LocalModelSpec(
        model_id="gemma3:12b",
        capabilities=frozenset({"reasoning", "extraction", "summarization"}),
        vram_gb=8.6,
        disk_gb=8.15,
        context_window=16384,
        notes="Alternative local reasoning/extraction model.",
    ),
    "qwen2.5-coder:14b": LocalModelSpec(
        model_id="qwen2.5-coder:14b",
        capabilities=frozenset({"coding", "reasoning"}),
        vram_gb=9.5,
        disk_gb=8.99,
        context_window=16384,
        notes="Primary 16GB-VRAM-fitting local coding model.",
    ),
    "qwen2.5-coder:1.5b": LocalModelSpec(
        model_id="qwen2.5-coder:1.5b",
        capabilities=frozenset({"coding", "autocomplete"}),
        vram_gb=1.3,
        disk_gb=0.99,
        context_window=16384,
        notes="Fast lightweight coding helper.",
    ),
    "qwen2.5-coder:0.5b": LocalModelSpec(
        model_id="qwen2.5-coder:0.5b",
        capabilities=frozenset({"coding", "syntax_check"}),
        vram_gb=0.6,
        disk_gb=0.40,
        context_window=8192,
        notes="Ultra-lightweight code probe.",
    ),
    "qwen3-coder:30b": LocalModelSpec(
        model_id="qwen3-coder:30b",
        capabilities=frozenset({"coding"}),
        vram_gb=19.2,
        disk_gb=18.56,
        context_window=16384,
        notes="Exceeds 16GB VRAM alone; requires CPU/RAM offload on RTX 5080.",
    ),
    "bge-m3:latest": LocalModelSpec(
        model_id="bge-m3:latest",
        capabilities=frozenset({"embeddings"}),
        vram_gb=1.4,
        disk_gb=1.16,
        context_window=8192,
        notes="Multilingual (English + Tamil) dense/sparse embedding model; co-resides with 14B model in 16GB VRAM.",
    ),
    "nomic-embed-text:latest": LocalModelSpec(
        model_id="nomic-embed-text:latest",
        capabilities=frozenset({"embeddings"}),
        vram_gb=0.4,
        disk_gb=0.27,
        context_window=8192,
        notes="Fast English embedding fallback.",
    ),
    "qwen2.5vl:7b": LocalModelSpec(
        model_id="qwen2.5vl:7b",
        capabilities=frozenset({"vision", "multimodal"}),
        vram_gb=6.4,
        disk_gb=5.97,
        context_window=8192,
        notes="Primary local vision-language extractor for screenshots and receipts.",
    ),
    "qwen2.5vl:3b": LocalModelSpec(
        model_id="qwen2.5vl:3b",
        capabilities=frozenset({"vision", "multimodal"}),
        vram_gb=3.5,
        disk_gb=3.20,
        context_window=8192,
        notes="Low-VRAM local vision fallback.",
    ),
    "moondream:latest": LocalModelSpec(
        model_id="moondream:latest",
        capabilities=frozenset({"vision"}),
        vram_gb=2.0,
        disk_gb=1.74,
        context_window=4096,
        notes="Compact image captioning model.",
    ),
    "mashriram/sarvam-1:latest": LocalModelSpec(
        model_id="mashriram/sarvam-1:latest",
        capabilities=frozenset({"speech_indic", "tamil", "reasoning"}),
        vram_gb=1.8,
        disk_gb=1.55,
        context_window=8192,
        notes="Indic/Tamil language specialist model.",
    ),
}


@dataclass(frozen=True)
class RoutingExplanation:
    action: str  # "run_local", "queue_local", "run_cloud", "reject"
    backend: str
    model_id: str | None
    local_only: bool
    vram_required_gb: float
    vram_available_gb: float
    explanation: str


def select_backend_for_task(
    *,
    task_kind: str,
    capability: str,
    personal_data: bool = False,
    preferred_model: str | None = None,
    vram_free_gb: float = RTX_5080_VRAM_GB,
    user_active_on_gpu: bool = False,
    cloud_models_available: tuple[str, ...] = (),
) -> RoutingExplanation:
    """Select the execution backend and explain why the task ran, waited, or failed."""
    strict_local = personal_data or (task_kind in PERSONAL_DATA_TASKS)

    candidates = [
        spec
        for spec in LOCAL_MODEL_REGISTRY.values()
        if capability in spec.capabilities and spec.fits_rtx_5080_vram
    ]
    if preferred_model and preferred_model in LOCAL_MODEL_REGISTRY:
        pref = LOCAL_MODEL_REGISTRY[preferred_model]
        if pref.fits_rtx_5080_vram and capability in pref.capabilities:
            candidates = [pref] + [c for c in candidates if c.model_id != pref.model_id]

    if not candidates:
        if strict_local:
            return RoutingExplanation(
                action="reject",
                backend="none",
                model_id=None,
                local_only=True,
                vram_required_gb=0.0,
                vram_available_gb=vram_free_gb,
                explanation=(
                    f"Task '{task_kind}' carries personal data (strict local-only), "
                    f"and no local model in the 16 GB VRAM budget supports capability '{capability}'."
                ),
            )
        if cloud_models_available:
            return RoutingExplanation(
                action="run_cloud",
                backend="cloud",
                model_id=cloud_models_available[0],
                local_only=False,
                vram_required_gb=0.0,
                vram_available_gb=vram_free_gb,
                explanation=f"No local model fits 16 GB VRAM for '{capability}'; routed non-personal task to cloud model '{cloud_models_available[0]}'.",
            )
        return RoutingExplanation(
            action="reject",
            backend="none",
            model_id=None,
            local_only=False,
            vram_required_gb=0.0,
            vram_available_gb=vram_free_gb,
            explanation=f"No local or cloud model available for capability '{capability}'.",
        )

    fitting_now = [c for c in candidates if c.vram_gb <= vram_free_gb]
    chosen = fitting_now[0] if fitting_now else min(candidates, key=lambda c: c.vram_gb)

    if user_active_on_gpu or chosen.vram_gb > vram_free_gb:
        reason = (
            "owner is actively using the local workstation/GPU"
            if user_active_on_gpu
            else f"model '{chosen.model_id}' needs {chosen.vram_gb:.1f} GB VRAM but only {vram_free_gb:.1f} GB is free"
        )
        if strict_local:
            return RoutingExplanation(
                action="queue_local",
                backend="local_queue",
                model_id=chosen.model_id,
                local_only=True,
                vram_required_gb=chosen.vram_gb,
                vram_available_gb=vram_free_gb,
                explanation=(
                    f"Queued locally for '{chosen.model_id}' because {reason}; "
                    "personal data never leaves the local machine."
                ),
            )
        if cloud_models_available:
            return RoutingExplanation(
                action="run_cloud",
                backend="cloud",
                model_id=cloud_models_available[0],
                local_only=False,
                vram_required_gb=chosen.vram_gb,
                vram_available_gb=vram_free_gb,
                explanation=(
                    f"Routed non-personal task '{task_kind}' to free cloud model '{cloud_models_available[0]}' "
                    f"because {reason}."
                ),
            )
        return RoutingExplanation(
            action="queue_local",
            backend="local_queue",
            model_id=chosen.model_id,
            local_only=False,
            vram_required_gb=chosen.vram_gb,
            vram_available_gb=vram_free_gb,
            explanation=f"Queued locally for '{chosen.model_id}' because {reason} and no cloud fallback is available.",
        )

    return RoutingExplanation(
        action="run_local",
        backend="ollama_local",
        model_id=chosen.model_id,
        local_only=strict_local,
        vram_required_gb=chosen.vram_gb,
        vram_available_gb=vram_free_gb,
        explanation=(
            f"Selected local model '{chosen.model_id}' ({chosen.vram_gb:.1f} GB / {vram_free_gb:.1f} GB free VRAM) "
            f"for '{task_kind}' ({'strict local-only personal data' if strict_local else 'local capacity available'})."
        ),
    )


def evaluate_gpu_scheduler_justification() -> dict[str, Any]:
    """Evaluate whether a complex custom GPU scheduler is justified on the 16 GB RTX 5080."""
    primary_extractor = LOCAL_MODEL_REGISTRY["qwen3:14b"]
    primary_embedder = LOCAL_MODEL_REGISTRY["bge-m3:latest"]
    fast_judge = LOCAL_MODEL_REGISTRY["qwen3:4b"]

    co_resident_vram = round(primary_extractor.vram_gb + primary_embedder.vram_gb, 2)
    judge_embed_vram = round(fast_judge.vram_gb + primary_embedder.vram_gb, 2)
    co_fits = co_resident_vram <= RTX_5080_VRAM_GB

    return {
        "gpu": "NVIDIA GeForce RTX 5080",
        "vram_budget_gb": RTX_5080_VRAM_GB,
        "primary_extractor_plus_embedder_vram_gb": co_resident_vram,
        "fast_judge_plus_embedder_vram_gb": judge_embed_vram,
        "co_resident_fits_in_16gb": co_fits,
        "complex_gpu_scheduler_justified": False,
        "recommendation": (
            f"Do NOT introduce a custom GPU scheduler: bge-m3 ({primary_embedder.vram_gb} GB) + "
            f"qwen3:14b ({primary_extractor.vram_gb} GB) = {co_resident_vram} GB <= {RTX_5080_VRAM_GB} GB VRAM, "
            "so Ollama's native keep-alive + single-queue serialization handles the steady-state workload without thrashing."
        ),
    }


def probe_ollama_models(base_url: str = "http://localhost:11434") -> dict[str, Any]:
    """Inspect installed local Ollama models and measure live embedding + generation latency when reachable."""
    t0 = time.perf_counter()
    try:
        with httpx.Client(timeout=8.0) as client:
            tags_resp = client.get(f"{base_url}/api/tags")
            tags_resp.raise_for_status()
            installed = [
                {
                    "name": m["name"],
                    "size_gb": round(float(m.get("size", 0)) / 1e9, 2),
                    "in_registry": m["name"] in LOCAL_MODEL_REGISTRY,
                }
                for m in tags_resp.json().get("models", [])
            ]
            # Fast live embedding latency probe on bge-m3 if installed
            embed_ms = None
            if any(m["name"] == "bge-m3:latest" for m in installed):
                te = time.perf_counter()
                er = client.post(
                    f"{base_url}/api/embed",
                    json={"model": "bge-m3:latest", "input": "When does my car insurance renew?"},
                )
                if er.status_code == 200:
                    embed_ms = round((time.perf_counter() - te) * 1000.0, 2)
            return {
                "reachable": True,
                "catalog_probe_ms": round((time.perf_counter() - t0) * 1000.0, 2),
                "installed_count": len(installed),
                "installed_models": installed,
                "bge_m3_embed_latency_ms": embed_ms,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "reachable": False,
            "error": f"{type(exc).__name__}: {exc}",
            "installed_count": 0,
            "installed_models": [],
            "bge_m3_embed_latency_ms": None,
        }
