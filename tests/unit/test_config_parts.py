"""Settings is one class made of per-domain parts (life_graph/config/).

Split from one 1,100-line class on 2026-11-18 without renaming anything; the
split was checked to give the same fields, defaults, derived values and the
same values loaded from a real .env. These tests keep it that way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_settings import BaseSettings

from life_graph.config import Settings, settings
from life_graph.config.agents import AgentSettings
from life_graph.config.assistant import AssistantSettings
from life_graph.config.browser import BrowserSettings
from life_graph.config.core import CoreSettings
from life_graph.config.drivers import DriverSettings
from life_graph.config.llm import LLMSettings
from life_graph.config.memory import MemorySettings
from life_graph.config.research import ResearchSettings
from life_graph.config.storage import StorageSettings

if TYPE_CHECKING:
    from pydantic import BaseModel

PARTS = (
    CoreSettings,
    StorageSettings,
    MemorySettings,
    LLMSettings,
    ResearchSettings,
    DriverSettings,
    AgentSettings,
    AssistantSettings,
    BrowserSettings,
)


def test_settings_is_made_of_every_part() -> None:
    assert set(PARTS) <= set(Settings.__mro__)
    assert isinstance(settings, Settings)


@pytest.mark.parametrize("part", PARTS, ids=lambda p: p.__name__)
def test_a_part_is_a_plain_model_not_settings(part: type[BaseModel]) -> None:
    # A part that were BaseSettings could be instantiated on its own and read
    # the environment without the LIFE_GRAPH_ prefix.
    assert not issubclass(part, BaseSettings)


def test_every_field_is_defined_in_exactly_one_part() -> None:
    owners: dict[str, list[str]] = {}
    for part in PARTS:
        for name in part.__annotations__:
            if name in part.model_fields:
                owners.setdefault(name, []).append(part.__name__)
    assert {n for n, o in owners.items() if len(o) > 1} == set()
    assert set(owners) == set(Settings.model_fields)


def test_the_env_prefix_and_dotenv_stay_on_settings() -> None:
    assert Settings.model_config["env_prefix"] == "LIFE_GRAPH_"
    assert Settings.model_config["env_file"] == ".env"
    assert Settings.model_config["extra"] == "ignore"


@pytest.mark.parametrize("part", PARTS, ids=lambda p: p.__name__)
def test_a_field_from_each_part_is_read_from_its_env_name(
    part: type[BaseModel], monkeypatch: pytest.MonkeyPatch
) -> None:
    name = next(
        n for n, f in part.model_fields.items() if f.annotation in ("str", str) and n.islower()
    )
    monkeypatch.setenv(f"LIFE_GRAPH_{name.upper()}", "set-by-env")
    assert getattr(Settings(_env_file=None), name) == "set-by-env"


def test_derived_values_still_work_across_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIFE_GRAPH_SERVICE_API_KEYS", "a, b")
    monkeypatch.setenv("LIFE_GRAPH_DEV_CLOUD_MODELS", "m1,m2")
    monkeypatch.setenv("LIFE_GRAPH_TENANT_PLANS", '{"t": "pro"}')
    s = Settings(_env_file=None)
    assert s.service_api_keys_list == ["a", "b"]
    assert s.dev_cloud_models_list == ["m1", "m2"]
    assert s.get_plan_limits("t")["requests_per_min"] == 300
