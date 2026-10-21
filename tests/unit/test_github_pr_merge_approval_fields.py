from life_graph.services.github_pr import merge_approval_fields


def test_merge_approval_fields_basic():
    """Basic happy path: all fields present and valid."""
    payload = {
        "pr_url": "https://github.com/owner/repo/pull/42",
        "instruction": "Do something",
        "branch": "feature-branch",
        "base_branch": "main",
        "head_commit": "abcdef123456",
    }
    result = merge_approval_fields(payload)
    # title contains number and first line of instruction
    assert result["title"] == "Merge PR #42: Do something"
    # detail contains url, branch, base_branch, head_commit first 8 chars
    assert "https://github.com/owner/repo/pull/42" in result["detail"]
    assert "squash-merge feature-branch into main" in result["detail"]
    assert "verified commit abcdef12" in result["detail"]
    # payload contains original keys and pr_number
    assert result["payload"]["pr_number"] == "42"
    for key in payload:
        assert result["payload"][key] == payload[key]


def test_merge_approval_fields_missing_pr_url_and_instruction():
    """When pr_url is missing, number is '?' and title uses empty instruction."""
    payload = {
        "instruction": "Update",
    }
    result = merge_approval_fields(payload)
    assert result["title"].startswith("Merge PR #?: Update")
    # pr_number should be '?' in payload
    assert result["payload"]["pr_number"] == "?"


def test_merge_approval_fields_title_truncation():
    """Instruction longer than 90 chars gets truncated in the title."""
    long_instr = "a" * 120
    payload = {
        "pr_url": "https://github.com/owner/repo/pull/99",
        "instruction": long_instr,
    }
    result = merge_approval_fields(payload)
    # title should contain first 90 'a's
    expected_title = "Merge PR #99: " + "a" * 90
    assert result["title"] == expected_title


def test_merge_approval_fields_head_commit_various_lengths():
    """Verify head_commit slicing: short, missing, and normal."""
    # Normal length
    payload = {
        "pr_url": "https://github.com/owner/repo/pull/1",
        "branch": "b",
        "base_branch": "m",
        "head_commit": "abcdef123",
    }
    result = merge_approval_fields(payload)
    assert "verified commit abcdef12" in result["detail"]
    # Short length
    payload["head_commit"] = "abc"
    result = merge_approval_fields(payload)
    assert "verified commit abc" in result["detail"]
    # Missing head_commit
    payload.pop("head_commit")
    result = merge_approval_fields(payload)
    assert "verified commit " in result["detail"]


def test_merge_approval_fields_missing_branch_and_base_branch():
    """When branch or base_branch missing, detail shows None."""
    payload = {
        "pr_url": "https://github.com/owner/repo/pull/5",
        "instruction": "Fix bug",
    }
    result = merge_approval_fields(payload)
    assert "squash-merge None into None" in result["detail"]
    assert result["payload"]["pr_number"] == "5"
