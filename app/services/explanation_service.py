"""Deterministic templates only; never asks an LLM for financial conclusions."""
from app.domain.models import METRIC_INFO, Condition, Observation


def check_reason(c: Condition, observation: Observation | None, status: str) -> str:
    label = METRIC_INFO[c.metric][0]
    if status == "unknown":
        detail = observation.missing_reason if observation else "Provider 未返回该指标"
        return f"{label}数据不足：{detail or '数值缺失'}；不能判定是否满足条件"
    relation = "满足" if status == "pass" else "不满足"
    return f"{label}实际 {observation.value:g}{c.unit}，{relation} {c.operator} {c.value:g}{c.unit}"


def stock_explanation(checks, status: str) -> str:
    if status == "selected":
        return f"全部 {len(checks)} 个启用条件通过"
    failed = [METRIC_INFO[c.metric][0] for c in checks if c.status == "fail"]
    unknown = [METRIC_INFO[c.metric][0] for c in checks if c.status == "unknown"]
    parts = []
    if failed:
        parts.append("未通过：" + "、".join(failed))
    if unknown:
        parts.append("数据不足：" + "、".join(unknown))
    return "；".join(parts)
