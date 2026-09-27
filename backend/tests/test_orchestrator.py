import asyncio

import httpx
import pytest
import respx

from app.config import Settings
from app.recon import orchestrator
from app.recon.base import Output, Pipeline, Pivot, SkipPipeline
from app.recon.classify import InputType, classify
from app.recon.pipelines.network import RipeStat
from app.recon.pipelines.registration import Rdap


class _Fake(Pipeline):
    category = "test"
    accepts = frozenset({InputType.DOMAIN})

    def __init__(self, name, behaviour, key_fields=()):
        self.name = self.label = name
        self.behaviour = behaviour
        self.key_fields = key_fields
        self.calls = 0

    async def run(self, target, settings):
        self.calls += 1
        if self.behaviour == "ok":
            return Output(summary={"hello": target.value}, pivots=[Pivot("ip", "192.0.2.1")])
        if self.behaviour == "skip":
            raise SkipPipeline("nothing")
        if self.behaviour == "slow":
            await asyncio.sleep(5)
        raise RuntimeError("boom")


@pytest.fixture
def fakes(monkeypatch):
    items = [
        _Fake("good", "ok"),
        _Fake("bad", "error"),
        _Fake("skip", "skip"),
        _Fake("slow", "slow"),
        _Fake("keyed", "ok", key_fields=("shodan_api_key",)),
    ]
    monkeypatch.setattr(orchestrator, "ALL", items)
    return items


async def _collect(target, settings, **kw):
    return [ev async for ev in orchestrator.sweep(classify(target), settings, **kw)]


async def test_sweep_isolates_failures(fakes):
    settings = Settings(_env_file=None, pipeline_timeout_s=0.2)
    events = await _collect("example.com", settings)

    assert events[0]["event"] == "plan"
    plan = {p["name"]: p["status"] for p in events[0]["data"]["pipelines"]}
    assert plan == {"good": "pending", "bad": "pending", "skip": "pending", "slow": "pending", "keyed": "skipped"}

    results = {e["data"]["name"]: e["data"] for e in events if e["event"] == "result"}
    assert results["good"]["status"] == "ok"
    assert results["good"]["pivots"] == [{"type": "ip", "value": "192.0.2.1", "label": ""}]
    assert results["bad"]["status"] == "error" and "boom" in results["bad"]["error"]
    assert results["skip"]["status"] == "skipped"
    assert results["slow"]["error"] == "Timed out"
    assert "keyed" not in results  # never runs without its key

    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["counts"] == {"ok": 1, "error": 2, "skipped": 2}


async def test_results_are_cached(fakes):
    settings = Settings(_env_file=None, pipeline_timeout_s=0.2)
    await _collect("example.com", settings, only=["good"])
    events = await _collect("example.com", settings, only=["good"])
    result = next(e["data"] for e in events if e["event"] == "result")
    assert result["cached"] is True
    assert fakes[0].calls == 1

    await _collect("example.com", settings, only=["good"], use_cache=False)
    assert fakes[0].calls == 2


@respx.mock
async def test_rdap_domain_summary():
    respx.get("https://rdap.org/domain/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": ["active"],
                "events": [
                    {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
                    {"eventAction": "expiration", "eventDate": "2030-08-13T04:00:00Z"},
                ],
                "nameservers": [{"ldhName": "A.IANA-SERVERS.NET"}],
                "entities": [
                    {"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]]}
                ],
                "secureDNS": {"delegationSigned": True},
            },
        )
    )
    out = await Rdap().run(classify("example.com"), Settings(_env_file=None))
    assert out.summary["registrar"] == "Example Registrar"
    assert out.summary["nameservers"] == ["a.iana-servers.net"]
    assert out.summary["expires"].startswith("2030")
    assert out.summary["dnssec"] is True


@respx.mock
async def test_rdap_not_found():
    respx.get("https://rdap.org/domain/nope.example").mock(return_value=httpx.Response(404))
    out = await Rdap().run(classify("nope.example"), Settings(_env_file=None))
    assert out.summary == {"found": False}


@respx.mock
async def test_ripestat_ip_pivots_to_asn():
    base = "https://stat.ripe.net/data/{}/data.json"
    respx.get(base.format("prefix-overview")).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"resource": "8.8.8.0/24", "announced": True, "asns": [{"asn": 15169, "holder": "GOOGLE"}]}},
        )
    )
    respx.get(base.format("abuse-contact-finder")).mock(
        return_value=httpx.Response(200, json={"data": {"abuse_contacts": ["abuse@example.net"]}})
    )
    respx.get(base.format("routing-status")).mock(return_value=httpx.Response(500))
    out = await RipeStat().run(classify("8.8.8.8"), Settings(_env_file=None))
    assert out.summary["asns"] == ["AS15169 GOOGLE"]
    assert {(p.type, p.value) for p in out.pivots} == {("asn", "AS15169"), ("cidr", "8.8.8.0/24")}
