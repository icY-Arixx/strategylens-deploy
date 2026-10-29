from app.domain.models import Condition, Conflict, METRIC_INFO


def detect_conflicts(conditions: list[Condition]) -> list[Conflict]:
    groups = {}
    for c in conditions:
        if c.enabled:
            groups.setdefault(c.metric, []).append(c)
    conflicts = []
    for metric, group in groups.items():
        lower, upper = float("-inf"), float("inf")
        lower_closed, upper_closed = False, False
        for c in group:
            if c.operator in (">", ">=", "=="):
                closed = c.operator != ">"
                if c.value > lower:
                    lower, lower_closed = c.value, closed
                elif c.value == lower:
                    lower_closed = lower_closed and closed
            if c.operator in ("<", "<=", "=="):
                closed = c.operator != "<"
                if c.value < upper:
                    upper, upper_closed = c.value, closed
                elif c.value == upper:
                    upper_closed = upper_closed and closed
        if lower > upper or (lower == upper and not (lower_closed and upper_closed)):
            conflicts.append(Conflict(metric=metric, condition_ids=[c.condition_id for c in group],
                                      reason=f"{METRIC_INFO[metric][0]} 的启用条件没有公共可行范围"))
    return conflicts
