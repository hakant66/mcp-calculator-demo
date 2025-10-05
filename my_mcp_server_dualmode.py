# -*- coding: utf-8 -*-
"""
MCP server that can run in two modes:
  1) MCP over stdio  →  `python my_mcp_server.py --mode stdio`
  2) HTTP (FastAPI)  →  `python my_mcp_server.py --mode http --host 0.0.0.0 --port 8000`

Env:
  MCP_LOG_LEVEL = DEBUG|INFO|WARNING|ERROR (default DEBUG)

Requires:
  fastmcp
  pydantic>=2
  # only for --mode http:
  fastapi
  uvicorn[standard]
"""

import argparse
import logging
import os
import signal
import sys
import time
import traceback
import uuid
from typing import Tuple

from pydantic import Field, ValidationError
from fastmcp import FastMCP

# -----------------------------
# Logging
# -----------------------------
LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("calculator_mcp")

# -----------------------------
# Helpers
# -----------------------------
def _validate_add_args(a: int, b: int) -> None:
    LIMIT = 10**18
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both 'a' and 'b' must be integers.")
    if abs(a) > LIMIT or abs(b) > LIMIT:
        raise ValueError(f"Input out of bounds. |a|, |b| must be ≤ {LIMIT}.")

def _time_call() -> Tuple[float, callable]:
    start = time.perf_counter()
    def done() -> float:
        return time.perf_counter() - start
    return start, done

# -----------------------------
# MCP server (stdio)
# -----------------------------
mcp = FastMCP(name="Calculator_Server")

@mcp.tool(
    title="Add two numbers",
    description="Adds two integer numbers together and returns the result."
)
def add(
    a: int = Field(description="The first number to add"),
    b: int = Field(description="The second number to add"),
) -> int:
    call_id = str(uuid.uuid4())
    logger.debug(f"[{call_id}] add() invoked with a={a}, b={b}")
    _, done = _time_call()
    try:
        _validate_add_args(a, b)
        result = a + b
        duration = done()
        logger.info(f"[{call_id}] add() success result={result} in {duration:.6f}s")
        return result
    except (TypeError, ValueError) as e:
        duration = done()
        logger.warning(f"[{call_id}] add() validation error after {duration:.6f}s: {e}")
        raise ValueError(f"Invalid input: {e}") from e
    except ValidationError as e:
        duration = done()
        logger.warning(f"[{call_id}] add() pydantic validation error after {duration:.6f}s: {e}")
        raise ValueError(f"Validation failed: {e}") from e
    except Exception as e:
        duration = done()
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"[{call_id}] add() unexpected error after {duration:.6f}s:\n{tb}")
        raise RuntimeError("An unexpected error occurred while adding the numbers.") from e

def _install_signal_handlers():
    def _handler(signum, _frame):
        name = signal.Signals(signum).name
        logger.info(f"Received {name}. Shutting down gracefully…")
        for h in logger.handlers:
            try:
                h.flush()
            except Exception:
                pass
        sys.exit(0)
    try:
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)
    except Exception as e:
        logger.debug(f"Signal handlers not installed: {e}")

# -----------------------------
# HTTP app (optional mode)
# -----------------------------
def build_http_app():
    """
    Builds a small FastAPI app that exposes the same 'add' capability plus health.
    Only imported if --mode http to avoid optional deps when running stdio.
    """
    from fastapi import FastAPI, Query
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Calculator_Server HTTP")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "Calculator_Server"}

    @app.get("/api/add")
    def add_http(
        a: int = Query(..., description="The first number"),
        b: int = Query(..., description="The second number"),
    ):
        call_id = str(uuid.uuid4())
        logger.debug(f"[{call_id}] /api/add a={a}, b={b}")
        _, done = _time_call()
        try:
            _validate_add_args(a, b)
            result = a + b
            duration = done()
            logger.info(f"[{call_id}] /api/add success result={result} in {duration:.6f}s")
            return {"result": result, "call_id": call_id, "duration_s": duration}
        except (TypeError, ValueError) as e:
            duration = done()
            logger.warning(f"[{call_id}] /api/add validation error after {duration:.6f}s: {e}")
            return JSONResponse(status_code=400, content={"error": str(e), "call_id": call_id})
        except Exception as e:
            duration = done()
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error(f"[{call_id}] /api/add unexpected error after {duration:.6f}s:\n{tb}")
            return JSONResponse(status_code=500, content={"error": "internal error", "call_id": call_id})

    return app

# -----------------------------
# Entrypoint
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Calculator MCP server (stdio or HTTP).")
    p.add_argument("--mode", choices=["stdio", "http"], default="stdio",
                   help="Run as MCP over stdio (default) or expose as an HTTP server.")
    p.add_argument("--host", default="127.0.0.1", help="HTTP host (when --mode http).")
    p.add_argument("--port", type=int, default=8000, help="HTTP port (when --mode http).")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    logger.info(f"Starting Calculator_Server in mode={args.mode}")
    logger.debug(f"Effective LOG_LEVEL={logging.getLevelName(logger.level)}")
    _install_signal_handlers()

    if args.mode == "stdio":
        # Pure MCP over stdio (for editors/agents)
        try:
            mcp.run(transport="stdio")
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.critical(f"Fatal MCP stdio error:\n{tb}")
            sys.exit(1)

    elif args.mode == "http":
        # Simple HTTP wrapper using FastAPI + Uvicorn
        try:
            app = build_http_app()
            import uvicorn
            uvicorn.run(app, host=args.host, port=args.port, log_level=LOG_LEVEL.lower())
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.critical(f"Fatal HTTP error:\n{tb}")
            sys.exit(1)
