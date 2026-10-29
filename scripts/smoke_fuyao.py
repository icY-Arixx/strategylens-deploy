"""Opt-in LIVE probe. No key => not_verified, no external financial request.

Run from project root: python -m scripts.smoke_fuyao [--full] [--output artifacts/live-smoke.json]
"""
import argparse
import json
import os
import time
from pathlib import Path

from app.adapters.financial_base import DataProviderError
from app.adapters.fuyao_financial import FuyaoFinancialDataProvider
from app.domain.models import now
from app.domain.strategy_engine import StrategyEngine
from app.services.strategy_compiler import StrategyCompiler
from app.store.sqlite_store import SQLiteStore


def main(argv=None):
    parser = argparse.ArgumentParser(description="Official Fuyao LIVE smoke; explicit sample or full universe.")
    parser.add_argument("--full", action="store_true", help="Fetch ALL official constituents, never truncate silently")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    report = {"test_type":"LIVE", "started_at":now().isoformat(), "universe":"000300.SH",
              "scope":"full_official_constituents" if args.full else "explicit_smoke_sample_first_1_official_member",
              "status":"not_verified", "successful_capabilities":[], "full_universe_measured":False}
    code = 2
    if not os.getenv("HITHINK_FINANCE_API_KEY", "").strip():
        report["reason"] = "HITHINK_FINANCE_API_KEY not configured; no live financial request was made"
    else:
        provider = FuyaoFinancialDataProvider()
        try:
            if args.full:
                snapshot = provider.fetch_snapshot(provider.universe)
            else:
                if not provider.ready:
                    raise ValueError("FUYAO_REPORT must be explicitly configured")
                members, evidence = provider.get_constituents()
                snapshot = provider.collect_members(members[:1], evidence)
                snapshot.parameters["scope"] = report["scope"]
                snapshot.parameters["official_universe_size"] = len(members)
            store = SQLiteStore(Path(__file__).resolve().parents[1] / "data" / "live-smoke.sqlite3")
            sealed = store.save_snapshot(snapshot)
            strategy = StrategyCompiler().compile("fixed four-condition smoke")
            strategy.universe = provider.universe
            results = StrategyEngine().evaluate(strategy, snapshot.stocks)
            failures = [i for i in snapshot.issues if i.category != "missing_data"]
            report.update(status="partial_failure" if failures else "completed", snapshot_id=sealed.snapshot_id,
                          processed_count=len(results), official_universe_size=len(snapshot.universe_evidence.raw_value),
                          full_universe_measured=args.full, issues=[i.model_dump(mode="json") for i in snapshot.issues],
                          selected_count=sum(r.status=="selected" for r in results),
                          excluded_count=sum(r.status=="excluded" for r in results),
                          unknown_count=sum(r.status=="unknown" for r in results), report_period=provider.report)
            successful = {"constituents"}
            if snapshot.calendar_evidence:
                successful.add("calendar")
            for stock in snapshot.stocks:
                for obs in stock.observations.values():
                    ev = obs.evidence
                    if ev and ev.request_id and (not ev.error or ev.error.category == "missing_data"):
                        successful.add(ev.field)
            report["successful_capabilities"] = sorted(successful)
            code = 1 if failures else 0
        except DataProviderError as exc:
            report.update(status="failed", issue=exc.issue.model_dump(mode="json"))
            code = 1
        except ValueError:
            report.update(status="failed", reason="Explicit financial report/configuration required or snapshot invalid")
            code = 1
        finally:
            provider.close()
    report["elapsed_seconds"] = round(time.perf_counter()-started,3)
    report["completed_at"] = now().isoformat()
    content = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(content,encoding="utf-8")
    print(content)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
