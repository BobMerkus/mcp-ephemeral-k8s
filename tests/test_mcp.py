from mcp_ephemeral_k8s.app.mcp import mcp


def test_tool_functionality():
    # Pass the server directly to the Client constructor
    assert mcp is not None
