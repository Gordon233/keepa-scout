import pytest

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_eligibility_found(client):
    resp = await client.get("/eligibility/B00TEST001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["asin"] == "B00TEST001"
    assert data["eligible"] is True
    assert "checks" in data

@pytest.mark.asyncio
async def test_eligibility_not_found(client):
    resp = await client.get("/eligibility/DOESNOTEXIST")
    assert resp.status_code == 404

@pytest.mark.asyncio
async def test_batch_eligibility(client):
    resp = await client.post("/eligibility/batch", json={"asins": ["B00TEST001", "NOPE"]})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["found"] is True
    assert results[1]["found"] is False
