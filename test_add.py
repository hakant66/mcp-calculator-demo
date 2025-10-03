import asyncio
import logging
import argparse
from typing import Any
from fastmcp import Client

# --- Logging setup -----------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,  # Change to INFO to reduce verbosity or DEBUG for detailed debug info
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


async def call_add(url: str, a: int, b: int, timeout_s: float = 10.0) -> Any:
    """
    Connect to the MCP server at `url` and call the 'add' tool with {'a': a, 'b': b}.
    Returns the raw result (often a CallToolResult).
    """
    log.debug("Preparing Client with URL: %s", url)
    client = Client(url)

    try:
        async with client:
            log.debug("Client connected. Calling tool 'add' with a=%s, b=%s", a, b)
            result = await asyncio.wait_for(
                client.call_tool("add", {"a": a, "b": b}),
                timeout=timeout_s,
            )
            log.debug("Raw result received from server: %r", result)
            return result

    except asyncio.TimeoutError:
        log.error("Timed out after %.1f seconds waiting for tool response.", timeout_s)
        raise
    except Exception as e:
        log.exception("Error while calling 'add' tool: %s", e)
        raise


def coerce_sum_from_result(result: Any) -> int:
    """
    Extract an integer sum from common FastMCP return shapes:

    - CallToolResult with:
        .data == 46
        .structured_content == {'result': 46}
        .content[0].text == "46" (optional)
    - plain int/float
    - dict with keys like 'result' / 'sum' / 'total'
    - numeric string
    """
    log.debug("Coercing sum from result: %r", result)

    # 1) FastMCP CallToolResult object
    #    We avoid importing its class; just duck-type by attributes.
    if hasattr(result, "data"):
        val = getattr(result, "data")
        try:
            return int(val)
        except (TypeError, ValueError):
            pass

    if hasattr(result, "structured_content"):
        sc = getattr(result, "structured_content") or {}
        if isinstance(sc, dict) and "result" in sc:
            try:
                return int(sc["result"])
            except (TypeError, ValueError):
                pass

    if hasattr(result, "content"):
        # Optional fallback: first text item, if present
        try:
            content = getattr(result, "content") or []
            if content and isinstance(content[0], dict):
                # some clients use dicts
                txt = content[0].get("text")
            else:
                # fastmcp.TextContent object with .text
                txt = getattr(content[0], "text", None) if content else None
            if isinstance(txt, str):
                return int(txt.strip())
        except Exception:
            pass

    # 2) Primitive numeric
    if isinstance(result, (int, float)):
        return int(result)

    # 3) Dict shapes
    if isinstance(result, dict):
        for key in ("result", "sum", "total", "value"):
            if key in result:
                try:
                    return int(result[key])
                except (TypeError, ValueError):
                    continue

    # 4) Numeric string
    if isinstance(result, str):
        try:
            return int(result.strip())
        except ValueError:
            pass

    raise ValueError(
        "Could not determine numeric sum from server response. "
        f"Got: {type(result).__name__} -> {result!r}"
    )


async def main_async(url: str, a: int, b: int, timeout_s: float) -> None:
    log.info("Calling MCP 'add' tool at %s with a=%d, b=%d", url, a, b)
    result = await call_add(url, a, b, timeout_s=timeout_s)


    # Print the server’s wrapped result directly (uses CallToolResult.data if present)
    print(getattr(result, "data", result))

    # (Optional) quick sanity check:
    # assert getattr(result, "data", None) == a + b, "Server sum mismatch"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test calling the 'add' tool on an MCP server."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/mcp",
        help="MCP server URL (default: %(default)s)",
    )
    parser.add_argument("--a", type=int, default=145, help="First addend (default: %(default)s)")
    parser.add_argument("--b", type=int, default=87, help="Second addend (default: %(default)s)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Timeout in seconds for the tool call (default: %(default)s)",
    )
    return parser


def run_entry() -> None:
    args = build_arg_parser().parse_args()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Spyder/Jupyter etc.
            log.debug("Detected running event loop; scheduling task via create_task().")
            loop.create_task(main_async(args.url, args.a, args.b, args.timeout))
        else:
            log.debug("No running event loop; using loop.run_until_complete().")
            loop.run_until_complete(main_async(args.url, args.a, args.b, args.timeout))
    except RuntimeError:
        log.debug("No current event loop; using asyncio.run().")
        asyncio.run(main_async(args.url, args.a, args.b, args.timeout))


if __name__ == "__main__":
    run_entry()
