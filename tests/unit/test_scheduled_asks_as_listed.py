import uuid

from life_graph.services.scheduled_asks import as_listed


def test_as_listed_with_full_props_and_active_true():
    """When job has full properties and is active, all fields are populated correctly."""
    job_id = uuid.uuid4()
    job = {
        "id": job_id,
        "properties": {
            "ask": "Summarise my week",
            "when": "every Monday at 9",
            "session_id": str(uuid.uuid4()),
        },
        "cron_expression": "0 9 * * MON",
        "is_active": True,
        "next_run_at": "2024-01-01T09:00:00Z",
        "last_run_at": "2023-12-25T09:00:00Z",
        "last_run_status": "completed",
    }
    last_reply = "Here is your summary."

    result = as_listed(job, last_reply)

    assert result["id"] == str(job_id)
    assert result["ask"] == "Summarise my week"
    assert result["when"] == "every Monday at 9"
    assert result["cron"] == "0 9 * * MON"
    assert result["active"] is True
    assert result["next_run_at"] == "2024-01-01T09:00:00Z"
    assert result["last_run_at"] == "2023-12-25T09:00:00Z"
    assert result["last_run_status"] == "completed"
    assert result["last_reply"] == last_reply
    assert result["session_id"] == job["properties"]["session_id"]


def test_as_listed_without_properties_and_inactive():
    """When job lacks properties, description is used and active defaults to False."""
    job_id = uuid.uuid4()
    description = "Ask to check the weather"
    job = {
        "id": job_id,
        "description": description,
        # No properties key
        "cron_expression": None,
        "is_active": None,
    }

    result = as_listed(job)

    assert result["id"] == str(job_id)
    assert result["ask"] == description
    assert result["when"] is None
    assert result["cron"] is None
    assert result["active"] is False
    assert result["last_reply"] is None
    assert result["session_id"] is None


def test_as_listed_empty_ask_fallbacks_to_description():
    """If the ask property is an empty string, the function falls back to description."""
    job_id = uuid.uuid4()
    description = "Describe the sunrise"
    job = {
        "id": job_id,
        "properties": {
            "ask": "",  # empty string is falsy
            "when": "every day at 6",
        },
        "description": description,
        "cron_expression": "0 6 * * *",
        "is_active": False,
    }

    result = as_listed(job)

    assert result["ask"] == description
    assert result["when"] == "every day at 6"
    assert result["cron"] == "0 6 * * *"
    assert result["active"] is False
