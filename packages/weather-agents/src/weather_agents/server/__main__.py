"""Run the server over stdio: `python -m weather_agents.server`."""

from weather_agents.server.app import mcp

if __name__ == "__main__":
    mcp.run()
