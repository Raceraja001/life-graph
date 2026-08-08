from life_graph.config import Settings


def test_mcp_servers_list_parses_valid_json():
    s = Settings(mcp_servers='[{"name": "x", "command": "echo", "args": ["hi"]}]')
    assert s.mcp_servers_list == [{"name": "x", "command": "echo", "args": ["hi"]}]


def test_mcp_servers_list_empty_string_returns_empty_list():
    s = Settings(mcp_servers="")
    assert s.mcp_servers_list == []


def test_mcp_servers_list_malformed_json_returns_empty_list():
    s = Settings(mcp_servers="not json")
    assert s.mcp_servers_list == []


def test_mcp_servers_list_default_is_empty():
    s = Settings()
    assert s.mcp_servers_list == []
