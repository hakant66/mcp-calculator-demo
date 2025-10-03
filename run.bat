python - << "PY"
import asyncio
from fastmcp import Client

async def main():
    client = Client("http://127.0.0.1:8000/mcp")
    async with client:
        # use your tool’s real param names (e.g., a/b)
        result = await client.call_tool("add", {"a": 145, "b": 87})
        print(result)
asyncio.run(main())
PY
