from src.handlers import process

class Boom(Exception):
    pass

def test_process_partial_batch(monkeypatch):
    def ok_apply(payload):
        return None
    def bad_apply(payload):
        raise Boom("fail")

    monkeypatch.setattr(process, "apply_event", lambda p: ok_apply(p) if p.get("id") == "ok" else bad_apply(p))

    event = {
        "Records": [
            {"messageId": "m1", "body": "{\"id\": \"ok\"}"},
            {"messageId": "m2", "body": "{\"id\": \"bad\"}"},
        ]
    }

    res = process.handler(event, None)
    assert res["batchItemFailures"] == [{"itemIdentifier": "m2"}]
