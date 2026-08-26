"""Small HMAC result-token format for tamper detection."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json


PREFIX = "SET2"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_result(payload: dict, secret: str) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    encoded = _b64encode(body)
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{PREFIX}.{encoded}.{_b64encode(signature)}"


def verify_result(token: str, secret: str) -> dict:
    try:
        prefix, encoded, supplied = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("malformed result token") from exc
    if prefix != PREFIX:
        raise ValueError("unsupported result token")
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    try:
        supplied_signature = _b64decode(supplied)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("malformed result signature") from exc
    if not hmac.compare_digest(expected, supplied_signature):
        raise ValueError("invalid result signature")
    try:
        payload = json.loads(_b64decode(encoded))
    except (UnicodeDecodeError, ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise ValueError("malformed result payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("result payload must be an object")
    return payload
