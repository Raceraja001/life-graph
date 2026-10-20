from life_graph.services.sources import check_findings

# Helper to create a simple finding dict


def make_finding(source: str = "", detail: str = "", **kwargs) -> dict:
    data = {"source": source, "detail": detail}
    data.update(kwargs)
    return data


# 1. Non‑dict items are passed through unchanged and are not counted as findings


def test_non_dict_item_passed_through():
    findings = [123, make_finding("", "")]
    marked, stats = check_findings(findings, tool_results=[])
    assert marked[0] == 123
    assert marked[1] == {"source": "", "detail": "", "unverified": True}
    assert stats["findings"] == 1  # only dict items count
    assert stats["unverified_findings"] == 1
    assert stats["fetched"] == 0
    assert stats["unverified"] is True


# 2. A finding whose source URL is fetched is not marked unverified


def test_finding_with_fetched_source_is_verified():
    tool_results = ["https://example.com"]
    finding = make_finding(source="https://example.com")
    marked, stats = check_findings([finding], tool_results=tool_results)
    assert "unverified" not in marked[0]
    assert stats["unverified_findings"] == 0
    assert stats["unverified"] is False


# 3. A finding whose source URL is not fetched is marked unverified


def test_finding_with_unfetched_source_is_unverified():
    finding = make_finding(source="https://unfetched.com")
    marked, stats = check_findings([finding], tool_results=[])
    assert marked[0]["unverified"] is True
    assert stats["unverified_findings"] == 1
    assert stats["unverified"] is True


# 4. A finding whose detail contains a fetched URL is verified even if source is empty


def test_finding_with_fetched_detail_is_verified():
    tool_results = ["https://detail.com"]
    finding = make_finding(source="", detail="See https://detail.com for info")
    marked, stats = check_findings([finding], tool_results=tool_results)
    assert "unverified" not in marked[0]
    assert stats["unverified_findings"] == 0


# 5. When multiple URLs are cited, only one matching is enough to avoid unverified


def test_finding_with_multiple_urls_one_matches():
    tool_results = ["https://match.com"]
    finding = make_finding(source="https://match.com", detail="Or https://other.com")
    marked, stats = check_findings([finding], tool_results=tool_results)
    assert "unverified" not in marked[0]
    assert stats["unverified_findings"] == 0


# 6. If a finding cites no URLs, it is marked unverified


def test_finding_with_no_urls_is_unverified():
    finding = make_finding(source="", detail="")
    marked, stats = check_findings([finding], tool_results=[])
    assert marked[0]["unverified"] is True
    assert stats["unverified_findings"] == 1


# 7. Normalisation removes duplicates and counting fetched URLs correctly


def test_fetched_urls_are_normalised_and_unique():
    tool_results = [
        "https://example.com/path",
        "https://www.example.com/path/",
        "https://example.com/path?query=1",
        "https://example.com/path?query=1.",  # trailing punctuation
    ]
    marked, stats = check_findings([], tool_results=tool_results)
    # All variants should normalise to the same host/path? query
    assert stats["fetched"] == 2
    assert stats["unverified"] is False
