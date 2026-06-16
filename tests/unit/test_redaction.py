"""Unit tests for trace redaction helpers."""

from harness_foundry.tracing.redaction import redact_dict, redact_secrets


def test_redact_secrets_preserves_prefixes() -> None:
    text = "api_key: abc12345 token=abcdefgh secret = qwertyui"

    redacted = redact_secrets(text)

    assert redacted == "api_key: ***REDACTED*** token=***REDACTED*** secret = ***REDACTED***"


def test_redact_secrets_removes_google_api_key_assignment() -> None:
    text = "GOOGLE_API_KEY=super-secret-value"

    assert redact_secrets(text) == "***REDACTED***"


def test_redact_dict_recursively_redacts_nested_values() -> None:
    payload = {
        "message": "token: abcdefgh",
        "nested": {
            "api_key": "api_key=my-secret-key",
            "list": ["safe", "secret: abcdefgh"],
        },
        "count": 3,
    }

    assert redact_dict(payload) == {
        "message": "token: ***REDACTED***",
        "nested": {
            "api_key": "api_key=***REDACTED***",
            "list": ["safe", "secret: ***REDACTED***"],
        },
        "count": 3,
    }
