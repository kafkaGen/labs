import json
from pathlib import Path

import pytest

from weather_agents.mcp_client.config import StdioServerConfig, load_config
from weather_agents.mcp_client.errors import ConfigError

SHIPPED_CONFIG = Path(__file__).parents[2] / "mcp.stdio.json"


def write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps(payload))
    return path


def test_a_stdio_entry_loads_with_its_command_args_and_env(tmp_path):
    entry = {"command": "uv", "args": ["run", "server"], "env": {"A": "1"}}
    servers = load_config(write(tmp_path, {"mcpServers": {"weather": entry}}))
    assert servers == {
        "weather": StdioServerConfig(command="uv", args=["run", "server"], env={"A": "1"})
    }


def test_type_defaults_to_stdio_and_may_be_given(tmp_path):
    payload = {
        "mcpServers": {
            "plain": {"command": "a"},
            "typed": {"type": "stdio", "command": "b"},
        }
    }
    servers = load_config(write(tmp_path, payload))
    assert servers["plain"].type == "stdio"
    assert servers["typed"].type == "stdio"
    assert servers["plain"].args == []
    assert servers["plain"].env is None


def test_an_unsupported_type_names_the_server_and_the_supported_types(tmp_path):
    payload = {"mcpServers": {"web": {"type": "http", "url": "http://127.0.0.1:8000/mcp"}}}
    with pytest.raises(
        ConfigError, match="server 'web': type 'http' is not supported, supported: stdio"
    ):
        load_config(write(tmp_path, payload))


def test_a_type_that_is_not_a_string_is_unsupported_too(tmp_path):
    payload = {"mcpServers": {"odd": {"type": ["stdio"], "command": "a"}}}
    with pytest.raises(ConfigError, match="server 'odd': type"):
        load_config(write(tmp_path, payload))


def test_an_unknown_key_names_the_server_and_the_key(tmp_path):
    payload = {"mcpServers": {"weather": {"command": "a", "cwd": "/tmp"}}}
    with pytest.raises(ConfigError, match="server 'weather': cwd"):
        load_config(write(tmp_path, payload))


def test_a_missing_command_names_the_server_and_the_field(tmp_path):
    with pytest.raises(ConfigError, match="server 'weather': command"):
        load_config(write(tmp_path, {"mcpServers": {"weather": {"args": []}}}))


def test_an_entry_that_is_not_an_object_names_the_server(tmp_path):
    with pytest.raises(ConfigError, match="server 'weather': entry must be an object"):
        load_config(write(tmp_path, {"mcpServers": {"weather": "uv run server"}}))


def test_a_missing_file_names_the_path(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(ConfigError, match=f"cannot read {missing}"):
        load_config(missing)


def test_invalid_json_names_the_path(tmp_path):
    path = tmp_path / "mcp.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError, match=f"{path} is not valid JSON"):
        load_config(path)


def test_a_file_without_mcp_servers_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="no 'mcpServers' object"):
        load_config(write(tmp_path, {"servers": {}}))


def test_the_shipped_stdio_config_loads():
    servers = load_config(SHIPPED_CONFIG)
    assert list(servers) == ["open-meteo"]
    assert servers["open-meteo"].command == "uv"
    assert servers["open-meteo"].args[-2:] == ["-m", "weather_agents.server"]
