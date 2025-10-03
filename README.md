# MCP Calculator Demo

A minimal MCP server exposing an `add(a, b)` tool, plus a Python client,
curl/Postman examples, and troubleshooting notes.

## Quick Start
fastmcp run calculator_server.py --transport http --host 127.0.0.1 --port 8000
python test_add.py --url http://127.0.0.1:8000/mcp --a 31 --b 69

## What is MCP (in this setup)?
- MCP server exposes tools (e.g., `add(a, b)`)
- MCP client connects to the server, calls `tools/call`, and prints results
- Streamable HTTP transport returns results via Server-Sent Events (SSE)
  
Part 1 — MCP Server (mcp_calculator_server)
Purpose: Expose an `add` tool with logging, input validation, error handling, correlation IDs, timing, and graceful shutdown.
Key components:
1. Logging controlled by MCP_LOG_LEVEL
2. Input validation & timing helpers
3. MCP server and tool registration with FastMCP
4. Graceful shutdown handlers
5. Entry point to run server
Run server:
- stdio: python mcp_calculator_server.py
- HTTP: fastmcp run mcp_calculator_server.py --transport http --host 127.0.0.1 --port 8000

  
Part 2 — MCP Client (Caller)
Purpose: Connect to MCP server and call `add(a, b)`
Key components:
- Logging & CLI argument parsing
- Connect with Client(url)
- Call tool with client.call_tool('add', {...})
- Print result with getattr(result, 'data', result)
Run client:
python test_add.py --url http://127.0.0.1:8000/mcp --a 31 --b 69

Calling Without Python (curl / Postman)
Lifecycle: initialize → initialized → tools/call → (optional) DELETE /mcp
curl example:
- POST initialize with Accept: application/json, text/event-stream
- POST notifications/initialized with MCP-Session-Id
- POST tools/call {"a":31,"b":69}
  
Postman setup:
- Headers: Content-Type, Accept, MCP-Session-Id
- Body: raw JSON (initialize, initialized, tools/call)
- Use Tests tab to store MCP-Session-Id
  
Common Errors & Fixes
- 406 Not Acceptable → missing Accept: text/event-stream
- 400 Missing session ID → missing MCP-Session-Id header
- 'Received request before initialization complete' → forgot initialized step
- Only :ping events → read POST body as SSE or use Prefer: respond-async
- Postman 'Invalid HTTP request' → disable HTTP/2 and system proxy
- Python client shows CallToolResult → print getattr(result, 'data', result)
  
Hardening & Extensibility
- Validation: adjust _validate_add_args
- Schema: return richer structures
- Add more tools with @mcp.tool
- Observability: logs include correlation IDs & timing
- Transports: stdio (local) or http (Postman/curl/testing)
  
Quick Start (copy/paste)
Server (HTTP):
set MCP_LOG_LEVEL=INFO
fastmcp run mcp_calculator_server.py --transport http --host 127.0.0.1 --port 8000
Client:
python test_add.py --url http://127.0.0.1:8000/mcp --a 31 --b 69
Postman tools/call:
Headers: Content-Type, Accept, MCP-Session-Id
Body JSON: {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"add","arguments":{"a":31,"b":69},"_meta":{"progressToken":1}}}

Step-by-Step Checklist
1. Start MCP server (stdio or HTTP).
2. Confirm server logs show 'mcp_calculator_server' started.
3. Run initialize (curl/Postman/Python Client).
4. Capture MCP-Session-Id from response.
5. Send notifications/initialized with same session id.
6. Send tools/call with arguments (a, b).
7. Confirm numeric result is returned.
8. DELETE /mcp to close session.
9. Check server logs for correlation ID, timings, errors.
10. For production: set MCP_LOG_LEVEL=INFO or WARNING.
