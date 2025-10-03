# -*- coding: utf-8 -*-
"""
Created on Wed Oct  1 16:08:46 2025
@author: hakan

MCP server with robust logging, debugging, and error handling.

What’s new:
- Structured logging with env-configurable level (MCP_LOG_LEVEL).
- Log level is controlled by MCP_LOG_LEVEL (e.g., DEBUG, INFO, WARNING).
- Defensive validation (bounds + type checks are explained in logs).
- Try/except around tool logic with helpful error messages for clients.
- Execution timing + per-call correlation IDs for easier tracing.
- Graceful shutdown on SIGINT/SIGTERM with final log flush.
"""

import logging
import os
import signal
import sys
import time
import traceback
import uuid
from typing import Tuple

from fastmcp import FastMCP
from pydantic import Field, ValidationError

# -----------------------------------------------------------------------------
# Logging setup
# -----------------------------------------------------------------------------
LOG_LEVEL = os.getenv("MCP_LOG_LEVEL", "DEBUG").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout, 
    # """  stream=sys.stderr,  # send logs to stderr so they don’t interfere with MCP I/O """
)
logger = logging.getLogger("calculator_mcp")

# -----------------------------------------------------------------------------
# Utility: input validation and timing helpers
# -----------------------------------------------------------------------------
def _validate_add_args(a: int, b: int) -> None:
    """
    Extra guardrails beyond Pydantic type coercion:
    - Ensure arguments are in a "reasonable" range to avoid pathological inputs.
    - Adjust limits as needed for your use-case.
    """
    LIMIT = 10**18
    if not isinstance(a, int) or not isinstance(b, int):
        # Shouldn’t happen if the client respects schema, but log defensively.
        raise TypeError("Both 'a' and 'b' must be integers.")
    if abs(a) > LIMIT or abs(b) > LIMIT:
        raise ValueError(f"Input out of bounds. |a|, |b| must be ≤ {LIMIT}.")


def _time_call() -> Tuple[float, callable]:
    """Simple wall-clock timer for execution duration."""
    start = time.perf_counter()

    def done() -> float:
        return time.perf_counter() - start

    return start, done


# -----------------------------------------------------------------------------
# MCP server
# -----------------------------------------------------------------------------
mcp = FastMCP(name="Calculator_Server")

#  Register the tool with rich error handling and tracing.
@mcp.tool(
    title="Add two numbers",
    description="Adds two integer numbers together and returns the result."
)
def add(
    a: int = Field(description="The first number to add"),
    b: int = Field(description="The second number to add"),
) -> int:
    """
    Adds two integers with:
    - Argument validation
    - Error handling that returns clean messages to the client
    - Debug logs including a correlation ID and timing
    """
    call_id = str(uuid.uuid4())
    logger.debug(f"[{call_id}] add() invoked with a={a}, b={b}")
    _, done = _time_call()

    try:
        # Defensive validation (pydantic handles types, we add bounds, etc.)
        _validate_add_args(a, b)

        result = a + b
        duration = done()
        logger.info(f"[{call_id}] add() success result={result} in {duration:.6f}s")
        return result

    except (TypeError, ValueError) as e:
        # User/validation error: log as WARNING and surface a clear message.
        duration = done()
        logger.warning(
            f"[{call_id}] add() validation error after {duration:.6f}s: {e}"
        )
        # Raising ValueError keeps the error structured for the MCP client.
        raise ValueError(f"Invalid input: {e}") from e

    except ValidationError as e:
        # Pydantic-specific validation details (should be rare here).
        duration = done()
        logger.warning(
            f"[{call_id}] add() pydantic validation error after {duration:.6f}s: {e}"
        )
        raise ValueError(f"Validation failed: {e}") from e

    except Exception as e:
        # Unexpected error: log full traceback for debugging, return generic msg.
        duration = done()
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error(f"[{call_id}] add() unexpected error after {duration:.6f}s:\n{tb}")
        # Avoid leaking sensitive internals to clients
        raise RuntimeError("An unexpected error occurred while adding the numbers.") from e


# -----------------------------------------------------------------------------
# Graceful shutdown handling
# -----------------------------------------------------------------------------
def _install_signal_handlers():
    def _handler(signum, _frame):
        name = signal.Signals(signum).name
        logger.info(f"Received {name}. Shutting down Calculator_Server gracefully…")
        # If FastMCP has its own shutdown lifecycle, call it here.
        # We exit after flushing log handlers.
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
        # Not all environments allow installing signal handlers (e.g., Windows, restricted runtimes).
        logger.debug(f"Signal handlers not installed: {e}")


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting Calculator_Server (transport=stdio)…")
    logger.debug(f"Effective LOG_LEVEL={logging.getLevelName(logger.level)}")
    _install_signal_handlers()

    # The 'stdio' transport mode allows the server to communicate via stdin/stdout.
    # Common for desktop MCP clients and editor integrations.
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.critical(f"Fatal server error:\n{tb}")
        sys.exit(1)
