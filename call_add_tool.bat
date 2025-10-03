@echo off
setlocal
set "A=%~1"
set "B=%~2"
if "%A%"=="" set "A=145"
if "%B%"=="" set "B=87"

set "PYFILE=%TEMP%\fastmcp_call_%RANDOM%.py"
> "%PYFILE%" (
  echo import asyncio
  echo from fastmcp import Client
  echo
  echo async def main():
  echo(    client = Client("http://127.0.0.1:8000/mcp")
  echo(    async with client:
  echo(        result = await client.call_tool("add", {"a": %A%, "b": %B%})
  echo(        print(result)
  echo
  echo asyncio.run(main())
)

python "%PYFILE%"
set "ERR=%ERRORLEVEL%"
del "%PYFILE%" 2>nul
exit /b %ERR%
