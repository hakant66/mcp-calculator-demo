# server.py — MCP-style adapter (validation, guardrails, and upstream calls)
# Run with: uvicorn server:app --port 8788 --reload

import os, asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr
import httpx
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Statista MCP Demo")

BASE_URL = os.getenv("BASE_URL", "https://api.example.com")
API_KEY = os.getenv("STATISTA_API_KEY", "")
MAX_PER_PAGE = int(os.getenv("MAX_PER_PAGE", "100"))
PROJECTION_ALLOW = set((os.getenv("PROJECTION_ALLOWLIST",
                                  "id,name,domain,industry,employees,country,updated_at")).split(","))

def headers():
    h = {}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

# --------- Schemas (tool parameters) ---------
class UsageLimitsReq(BaseModel):
    pass

class SearchCompaniesReq(BaseModel):
    domain: Optional[str] = None
    country: Optional[constr(min_length=2, max_length=2)] = None
    industry: Optional[str] = None
    employees_min: Optional[int] = Field(default=None, ge=1)
    sort: Optional[str] = Field(default=None, pattern=r"^-?updated_at$")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=25, ge=1, le=100)
    fields: Optional[List[str]] = Field(default=None, max_items=30)

class GetCompanyReq(BaseModel):
    company_id: constr(regex=r"^[A-Za-z0-9_-]{6,}$")
    fields: Optional[List[str]] = Field(default=None, max_items=30)

class BulkEnrichReq(BaseModel):
    domains: List[str] = Field(min_items=1, max_items=1000)
    fields: Optional[List[str]] = Field(default=None, max_items=30)

class DeltaReq(BaseModel):
    company_id: constr(regex=r"^[A-Za-z0-9_-]{6,}$")
    since: constr(min_length=10)

# --------- Helpers ---------
async def backoff_request(client, method: str, url: str, **kwargs):
    delay = 0.5
    for _ in range(3):
        resp = await client.request(method, url, **kwargs)
        if resp.status_code != 429 and resp.status_code < 500:
            return resp
        retry_after = float(resp.headers.get("retry-after", delay))
        await asyncio.sleep(retry_after)
        delay *= 2
    return await client.request(method, url, **kwargs)

def sanitize_fields(fields: Optional[List[str]]):
    if not fields:
        return None
    return [f for f in fields if f in PROJECTION_ALLOW]

# --------- Tools (endpoints) ---------
@app.post("/tools/getUsageLimits")
async def get_usage_limits(_: UsageLimitsReq):
    async with httpx.AsyncClient(headers=headers(), timeout=20) as client:
        r = await backoff_request(client, "GET", f"{BASE_URL}/me/limits")
        try:
            data = r.json()
        except Exception:
            raise HTTPException(status_code=502, detail="Invalid upstream response")
        return {"data": data, "source": {"endpoint": "/me/limits", "status": r.status_code}}

@app.post("/tools/searchCompanies")
async def search_companies(req: SearchCompaniesReq):
    params = req.dict(exclude_none=True)
    if "fields" in params:
        proj = sanitize_fields(params["fields"])
        if proj:
            params["fields"] = ",".join(proj)
        else:
            params.pop("fields", None)
    params["per_page"] = min(params.get("per_page", 25), MAX_PER_PAGE)
    async with httpx.AsyncClient(headers=headers(), timeout=20) as client:
        r = await backoff_request(client, "GET", f"{BASE_URL}/companies", params=params)
        data = r.json()
        return {"data": data, "source": {"endpoint": "/companies", "params": params}}

@app.post("/tools/getCompanyById")
async def get_company(req: GetCompanyReq):
    params = {}
    proj = sanitize_fields(req.fields)
    if proj:
        params["fields"] = ",".join(proj)
    async with httpx.AsyncClient(headers=headers(), timeout=20) as client:
        r = await backoff_request(client, "GET", f"{BASE_URL}/companies/{req.company_id}", params=params)
        data = r.json()
        return {"data": data, "source": {"endpoint": f"/companies/{req.company_id}", "params": params}}

@app.post("/tools/bulkEnrich")
async def bulk_enrich(req: BulkEnrichReq):
    body = {"domains": req.domains}
    proj = sanitize_fields(req.fields)
    if proj:
        body["fields"] = proj
    async with httpx.AsyncClient(headers={**headers(), "Content-Type": "application/json"}, timeout=60) as client:
        r = await backoff_request(client, "POST", f"{BASE_URL}/companies/bulk", json=body)
        data = r.json()
        return {"data": data, "source": {"endpoint": "/companies/bulk"}}

@app.post("/tools/getDeltaUpdates")
async def delta(req: DeltaReq):
    params = {"since": req.since}
    async with httpx.AsyncClient(headers=headers(), timeout=20) as client:
        r = await backoff_request(client, "GET", f"{BASE_URL}/companies/{req.company_id}/updates", params=params)
        data = r.json()
        return {"data": data, "source": {"endpoint": f"/companies/{req.company_id}/updates", "params": params}}
