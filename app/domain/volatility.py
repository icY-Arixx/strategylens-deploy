"""60 simple daily returns from 61 aligned closes; sample stdev, percentage points."""
import math
import statistics


class InsufficientHistory(ValueError):
    pass


def annualized_volatility(closes: list[float]) -> float:
    if len(closes) != 61:
        raise InsufficientHistory("需要61个完整交易日收盘价，形成60个日收益率")
    if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0 for p in closes):
        raise ValueError("收盘价必须为有限正数，不允许补0或跳过缺失日")
    returns = [closes[i] / closes[i-1] - 1 for i in range(1, 61)]
    return statistics.stdev(returns) * math.sqrt(252) * 100
