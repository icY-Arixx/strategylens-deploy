"""Official REST envelope and conservative pacing. No SDK or unofficial endpoint."""
import os
import math
import re
import threading
import time
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, StrictInt, ValidationError

from app.adapters.financial_base import DataProviderError
from app.domain.models import DataIssue

PROVIDER = "同花顺扶摇 / official REST"
BASE_URL = "https://fuyao.aicubes.cn"
ALLOWED_ENDPOINTS = {"/api/a-share-index/constituents/ths-stock-list", "/api/a-share/calendar/trading-days",
                     "/api/a-share/financials/indicators", "/api/a-share/valuations/snapshot",
                     "/api/a-share/prices/historical"}


class ApiEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    code: StrictInt
    message: str
    request_id: str | None = None
    data: dict[str, Any] | None


class FuyaoClient:
    def __init__(self, api_key: str | None = None, *, transport=None, timeout: float = 20,
                 min_interval: float = 1, sleeper=time.sleep, monotonic=time.monotonic):
        self._secret = SecretStr(api_key if api_key is not None else os.getenv("HITHINK_FINANCE_API_KEY", ""))
        if (not math.isfinite(timeout) or not math.isfinite(min_interval) or timeout <= 0
                or min_interval < 0 or (transport is None and min_interval < .25)):
            raise ValueError("timeout必须为正；真实请求间隔至少0.25秒，默认1秒")
        self._http = httpx.Client(base_url=BASE_URL, transport=transport, timeout=timeout, follow_redirects=False)
        self._interval, self._sleep, self._clock = min_interval, sleeper, monotonic
        self._next = 0.0
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self._secret.get_secret_value().strip())

    def redact(self, value):
        if isinstance(value, str):
            secret = self._secret.get_secret_value()
            return value.replace(secret, "[REDACTED]") if secret else value
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, dict):
            return {self.redact(key): self.redact(item) for key, item in value.items()}
        return value

    def fail(self, category, endpoint, *, code=None, request_id=None):
        messages = {
            "authentication_error": "扶摇凭证缺失或无效；不会回退Mock",
            "permission_error": "扶摇未授权此能力",
            "upstream_error": "扶摇服务调用失败或触发限流；未自动连续重试",
            "timeout": "扶摇请求超时",
            "missing_data": "扶摇当前没有可用数据",
            "invalid_payload": "扶摇响应不符合已核验契约",
        }
        raise DataProviderError(DataIssue(category=category, provider=PROVIDER, endpoint=endpoint,
                                         message=messages[category], business_code=code, request_id=request_id)) from None

    def get(self, endpoint: str, params=None) -> tuple[dict, str | None]:
        if endpoint not in ALLOWED_ENDPOINTS:
            self.fail("invalid_payload", "unsupported_endpoint")
        if not self.configured:
            self.fail("authentication_error", endpoint)
        with self._lock:
            delay = max(0, self._next - self._clock())
            if delay:
                self._sleep(delay)
            self._next = self._clock() + self._interval
        response, failure = None, None
        try:
            response = self._http.get(endpoint, params=params, headers={"X-api-key": self._secret.get_secret_value()})
        except httpx.TimeoutException:
            failure = "timeout"
        except httpx.HTTPError:
            failure = "upstream_error"
        if failure:
            self.fail(failure, endpoint)
        if response.status_code == 401:
            self.fail("authentication_error", endpoint)
        if response.status_code == 403:
            self.fail("permission_error", endpoint)
        if response.status_code == 429:
            self.fail("upstream_error", endpoint, code=4001)
        if not 200 <= response.status_code < 300:
            self.fail("upstream_error", endpoint)
        envelope = None
        try:
            envelope = ApiEnvelope.model_validate(response.json())
        except (ValueError, ValidationError):
            pass
        if envelope is None:
            self.fail("invalid_payload", endpoint)
        # Never forward upstream message/error bodies. IDs are character/length bounded.
        rid = self.redact(envelope.request_id)
        rid = rid if rid and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", rid) else None
        if envelope.code != 0:
            category = {2001: "authentication_error", 2003: "permission_error", 5002: "timeout",
                        3001: "missing_data", 3002: "missing_data", 3004: "missing_data"}.get(envelope.code, "upstream_error")
            self.fail(category, endpoint, code=envelope.code, request_id=rid)
        if envelope.data is None:
            self.fail("invalid_payload", endpoint, request_id=rid)
        return self.redact(envelope.data), rid

    def close(self):
        self._http.close()
