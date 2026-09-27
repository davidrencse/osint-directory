import asyncio
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core import store
from app.recon import orchestrator
from app.recon.classify import ClassifyError, classify
from app.recon.pipelines import ALL
from app.recon.scope import in_scope

router = APIRouter(prefix="/api/recon", tags=["recon"])


def _checked_target(target: str, authorized: bool):
    if not authorized:
        raise HTTPException(
            400, "Confirm you are authorized to run reconnaissance against this target."
        )
    try:
        t = classify(target)
    except ClassifyError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not in_scope(t, store.scope_list()):
        raise HTTPException(403, f"'{t.value}' is outside the configured scope allowlist.")
    return t


@router.get("/pipelines")
def list_pipelines():
    s = get_settings()
    return [p.describe(s) for p in ALL]


@router.get("/classify")
def classify_input(target: str):
    try:
        t = classify(target)
    except ClassifyError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**t.as_dict(), "in_scope": in_scope(t, store.scope_list())}


@router.get("/stream")
async def stream(
    target: str,
    authorized: bool = False,
    pipelines: str | None = Query(None, description="Comma-separated pipeline names"),
    fresh: bool = False,
):
    """Server-Sent Events: one `plan` event, one `result` per pipeline, then `done`."""
    t = _checked_target(target, authorized)
    only = [p for p in (pipelines or "").split(",") if p] or None
    settings = get_settings()
    await asyncio.to_thread(
        store.audit, "recon", t.value, {"type": t.type.value, "pipelines": only, "fresh": fresh}
    )

    async def events():
        async for ev in orchestrator.sweep(t, settings, only, use_cache=not fresh):
            yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'], default=str)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/run")
async def run_all(target: str, authorized: bool = False, pipelines: str | None = None, fresh: bool = False):
    """Non-streaming variant: waits for every pipeline and returns one JSON report."""
    t = _checked_target(target, authorized)
    only = [p for p in (pipelines or "").split(",") if p] or None
    settings = get_settings()
    await asyncio.to_thread(store.audit, "recon", t.value, {"type": t.type.value, "pipelines": only})
    report: dict = {"results": []}
    async for ev in orchestrator.sweep(t, settings, only, use_cache=not fresh):
        if ev["event"] == "plan":
            report.update(ev["data"])
        elif ev["event"] == "result":
            report["results"].append(ev["data"])
        else:
            report["summary"] = ev["data"]
    return report
