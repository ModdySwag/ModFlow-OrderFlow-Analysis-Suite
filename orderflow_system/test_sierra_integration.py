"""The Sierra Chart integration: free path first, plans as published, workflow that adapts.

These lock the promises the view makes: the free option is a real plan listed first, paid tiers are
quoted with a read-date and a source link, the workflow changes with the plan, and link opening is
allow-listed to the vendor's own https pages.
"""
from __future__ import annotations

from orderflow_system.desktop import platforms as plat


def test_free_plan_is_first_and_free():
    assert plat.PLANS[0]["id"] == "free"
    assert plat.PLANS[0]["price"] == "0"
    assert plat.PLANS[0]["kind"] == "free"
    assert plat.PLANS[0]["highlight"] is True


def test_paid_tiers_are_published_with_a_date_and_a_source():
    paid = [p for p in plat.PLANS if p["kind"] != "free"]
    assert len(paid) >= 4
    assert all(p["price"].isdigit() and p["period"] for p in paid)
    assert plat.PRICES_AS_OF, "prices must carry the date they were read"
    assert any(l["id"] == "pricing" for l in plat.LINKS)


def test_caveats_state_the_exchange_fee_fact():
    joined = " ".join(plat.CAVEATS).lower()
    assert "exchange" in joined and "separate" in joined


def test_workflow_adapts_to_the_plan():
    free = plat.workflow("free")
    paid = plat.workflow("p10")
    assert free["plan_kind"] == "free" and paid["plan_kind"] == "integrated"
    assert len(paid["steps"]) > len(free["steps"]), "the paid path adds the activation step"
    assert any("delayed" in s.lower() for s in free["suite_changes"])
    assert any("real-time" in s.lower() for s in paid["suite_changes"])


def test_unknown_plan_falls_back_to_free():
    assert plat.workflow("nonsense")["plan"] == "free"


def test_links_are_https_on_the_vendor_host():
    for link in plat.LINKS:
        ok, reason = plat.validate_url(link["url"])
        assert ok, f"{link['id']}: {reason}"


def test_open_url_refuses_everything_else():
    for url in ("http://www.sierrachart.com/x", "https://example.com/", "", "javascript:alert(1)"):
        ok, _ = plat.validate_url(url)
        assert ok is False, url
    assert plat.open_url("https://example.com/")["ok"] is False


def test_dtc_defaults_carry_the_plan_fields():
    block = plat.dtc_defaults()
    assert block["plan"] == "free" and block["integrated"] is False
    assert block["enabled"] is False and block["username"] == "" and block["password"] == ""
