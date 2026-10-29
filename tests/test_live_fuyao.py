"""Real network test, NEVER counted as an offline fixture success."""
import os

import pytest

from scripts.smoke_fuyao import main


@pytest.mark.live
@pytest.mark.skipif(os.getenv("RUN_FUYAO_LIVE") != "1" or not os.getenv("HITHINK_FINANCE_API_KEY"),
                    reason="LIVE未启用或缺少HITHINK_FINANCE_API_KEY；真实线上请求未验证")
def test_official_live_single_member_smoke(tmp_path):
    assert main(["--output",str(tmp_path/"live-smoke.json")]) == 0
