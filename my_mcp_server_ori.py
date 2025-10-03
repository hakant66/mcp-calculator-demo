# -*- coding: utf-8 -*-
"""
Created on Wed Oct  1 16:08:46 2025
@author: hakan

This script exposes a minimal MCP (Model Context Protocol) server using FastMCP.
Workflow overview:
1) Start an MCP server instance with a descriptive name.
2) Register one or more "tools" (capabilities) on that server.
3) Run the server over a chosen transport (here: stdio) so an MCP client can
   discover the tools, validate parameters, and invoke them.
4) When the client calls a tool, FastMCP handles I/O and type validation,
   calls your Python function, and returns the result back to the client.

Typical lifecycle when used by an MCP client:
- Client connects -> requests the tool schema (introspection).
- Client sends a tool invocation with typed args -> FastMCP validates via Pydantic.
- Your function executes -> return value serialized -> response sent to client.
"""

from fastmcp import FastMCP
from pydantic import Field

# 1) Create the MCP server instance.
#    - The name is what clients will see in registries/UX; pick something descriptive.
mcp = FastMCP(name="Calculator_Server")

# 2) Define a Tool
#    - @mcp.tool registers this function as an MCP "tool".
#    - 'title' and 'description' are surfaced to clients for discovery/UX.
@mcp.tool(
    title="Add two numbers",
    description="Adds two integer numbers together and returns the result."
)
def add(
        # Pydantic Field() lets you add per-parameter metadata seen by clients.
        # Clients can show this as inline help and use it to validate input.
        a: int = Field(description="The first number to add"), 
        b: int = Field(description="The second number to add")) -> int:
    """Adds two integer numbers together."""
    return a + b

# 3) Define the server execution entrypoint
if __name__ == "__main__":
    # transport="stdio":
    # - Uses standard input/output for request/response frames.
    # - Common for desktop MCP clients and editor integrations (simple, robust).
    # Alternative transports (if supported) might include sockets or HTTP.
    #
    # When this runs:
    # - The server advertises its tools (including schema derived from annotations/Field).
    # - On invocation, FastMCP:
    #     * parses JSON-RPC/MCP message
    #     * validates args against the Pydantic types
    #     * calls your Python function
    #     * returns the result or a structured error
    mcp.run(transport="stdio")