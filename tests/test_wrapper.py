"""Basic tests using a fake client so we do not hit real APIs."""

from __future__ import annotations

from llm_cost_tracker import track
from llm_cost_tracker.store import Store


class FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeResponse:
    def __init__(self, input_tokens, output_tokens):
        self.usage = FakeUsage(input_tokens, output_tokens)


class FakeMessages:
    def create(self, *, model, max_tokens, messages):
        return FakeResponse(input_tokens=10, output_tokens=20)


class FakeAnthropic:
    def __init__(self):
        self.messages = FakeMessages()


def test_wrapper_logs_call(tmp_path):
    db = tmp_path / "test.db"
    store = Store(db)
    client = track(FakeAnthropic(), tags={"feature": "test"}, store=store)
    resp = client.messages.create(model="claude-sonnet-4-5", max_tokens=512, messages=[])
    assert resp.usage.input_tokens == 10
    rows = store.query("SELECT * FROM llm_calls")
    assert len(rows) == 1
    assert rows[0]["model"] == "claude-sonnet-4-5"
    assert rows[0]["input_tokens"] == 10
    assert rows[0]["output_tokens"] == 20
    assert rows[0]["cost_usd"] is not None