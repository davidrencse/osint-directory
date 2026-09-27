"""Fan a target out to every applicable pipeline and yield results as they finish."""

import asyncio
import time
from collections.abc import AsyncIterator, Iterable

import httpx

from app.config import Settings
from app.core import store
from app.recon.base import Pipeline, SkipPipeline, query_type, query_value
from app.recon.classify import Target
from app.recon.pipelines import ALL


def plan(target: Target, settings: Settings, only: Iterable[str] | None = None) -> list[dict]:
    wanted = set(only) if only else None
    rows = []
    for p in ALL:
        if not p.applies_to(target) or (wanted is not None and p.name not in wanted):
            continue
        row = p.describe(settings)
        row["status"] = "pending" if p.enabled(settings) else "skipped"
        if not p.enabled(settings):
            row["error"] = f"No API key ({', '.join(p.key_fields)})"
        rows.append(row)
    return rows


def _cache_key(p: Pipeline, target: Target) -> str:
    return f"recon:{p.name}:{query_type(target, p)}:{query_value(target, p)}"


async def run_pipeline(p: Pipeline, target: Target, settings: Settings, use_cache: bool = True) -> dict:
    base = {"name": p.name, "label": p.label, "category": p.category, "homepage": p.homepage}
    key = _cache_key(p, target)
    if use_cache:
        cached = await asyncio.to_thread(store.cache_get, key)
        if cached is not None:
            return {**cached, "cached": True}

    started = time.perf_counter()
    try:
        out = await asyncio.wait_for(
            p.run(target, settings), timeout=p.timeout_s or settings.pipeline_timeout_s
        )
    except SkipPipeline as exc:
        result = {**base, "status": "skipped", "error": str(exc) or "Nothing to do"}
    except TimeoutError:
        result = {**base, "status": "error", "error": "Timed out"}
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        hint = {
            401: "the API key was rejected",
            402: "your plan does not include this lookup",
            403: "access denied or quota used up",
            429: "rate limited, try again shortly",
        }.get(code, "")
        result = {**base, "status": "error", "error": f"HTTP {code}: {hint}" if hint else f"HTTP {code}"}
    except Exception as exc:  # a broken source must never take down the whole sweep
        result = {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}"[:500]}
    else:
        result = {
            **base,
            "status": "ok",
            "summary": out.summary,
            "data": out.data,
            "source_url": out.source_url,
            "pivots": [pv.as_dict() for pv in out.pivots],
        }
    result["took_ms"] = round((time.perf_counter() - started) * 1000)
    result["cached"] = False
    if result["status"] == "ok":
        await asyncio.to_thread(store.cache_set, key, result, settings.recon_cache_ttl_s)
    return result


async def sweep(
    target: Target,
    settings: Settings,
    only: Iterable[str] | None = None,
    use_cache: bool = True,
) -> AsyncIterator[dict]:
    """Yields {'event': 'plan'|'result'|'done', 'data': ...}."""
    rows = plan(target, settings, only)
    yield {"event": "plan", "data": {"target": target.as_dict(), "pipelines": rows}}

    by_name = {p.name: p for p in ALL}
    runnable = [by_name[r["name"]] for r in rows if r["status"] == "pending"]
    started = time.perf_counter()
    tasks = [asyncio.create_task(run_pipeline(p, target, settings, use_cache)) for p in runnable]
    counts = {"ok": 0, "error": 0, "skipped": len(rows) - len(runnable)}
    try:
        for fut in asyncio.as_completed(tasks):
            result = await fut
            counts[result["status"]] += 1
            yield {"event": "result", "data": result}
    finally:
        for t in tasks:
            t.cancel()
    yield {
        "event": "done",
        "data": {"counts": counts, "took_ms": round((time.perf_counter() - started) * 1000)},
    }
