"""웹 공유용 정적 페이지 생성: 앱과 같은 계산(metrics.py, report.py) 결과를 HTML에 넣는다.

실행: python web/build_web.py  →  web/dashboard.html
필요 패키지: pandas, markdown
"""
import json
import re
import sys
from itertools import product
from pathlib import Path

import base64

import markdown
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import metrics as m  # noqa: E402
import export as ex  # noqa: E402
import report as rp  # noqa: E402

LOW_RATE = 90.0


def pct(v):
    return "-" if v is None or pd.isna(v) else f"{v:.1f}%"


def signed(v):
    return "-" if v is None else f"{v:+.1f}%"


def num(v):
    return None if v is None or pd.isna(v) else float(v)


def build():
    data = m.load_data()
    months = m.month_list(data["contracts"])
    branches = data["branches"]
    bkeys = ["ALL"] + branches["branch_id"].tolist()
    masks = ["".join(bits) for bits in product("10", repeat=4) if "1" in bits]

    def b_ids(b):
        return None if b == "ALL" else [b]

    def g_filter(mask):
        gs = [g for g, bit in zip(m.PRODUCT_GROUPS, mask) if bit == "1"]
        return None if len(gs) == 4 else gs

    # ① 성과 대시보드
    trend, perf = {}, {}
    for b, mask in product(bkeys, masks):
        t = m.monthly_trend(data, months[-1], 24, b_ids(b), g_filter(mask))
        trend[f"{b}|{mask}"] = {"count": t["건수"].astype(int).tolist(), "premium": t["보험료"].astype(int).tolist()}
        for ym in months:
            k = m.kpi_summary(data, ym, b_ids(b), g_filter(mask))
            share = m.product_group_share(data, ym, b_ids(b), g_filter(mask))
            bp = m.branch_performance(data, ym, b_ids(b), g_filter(mask))
            perf[f"{ym}|{b}|{mask}"] = {
                "kpi": [
                    f"{k['count']:,}건", f"전월 대비 {signed(k['count_change'])}",
                    f"{k['premium']:,}원", f"전월 대비 {signed(k['premium_change'])}",
                    pct(k["count_rate"]), "목표 -" if k["target_count"] is None else f"목표 {k['target_count']:,}건",
                    pct(k["activity_rate"]), f"{k['working_agents']} / {k['active_agents']}명",
                ],
                "share": [[r["상품군"], round(float(r["비중"]), 4), pct(r["비중"]), int(r["건수"]), int(r["보험료"])]
                          for _, r in share.iterrows()],
                "branch": [[r["지점"], int(r["건수"]), num(r["목표 건수"]), pct(r["건수 달성률"]),
                            r["건수 달성률"] is not None and r["건수 달성률"] < LOW_RATE]
                           for _, r in bp.iterrows()],
            }

    # ② 위험 설계사 (전 지점으로 계산, 화면에서 지점으로 거른다)
    risk = {}
    bid = data["agents"].set_index("agent_id")["branch_id"]
    for ym in months:
        r = m.risk_scores(data, ym)
        rows = []
        for _, a in r.iterrows():
            rows.append([a["agent_id"], a["설계사"], bid[a["agent_id"]], a["지점"], int(a["점수"]), a["등급"],
                         a["해당 사유"], a["직전3M→최근3M"], pct(a["유지율"])])
        risk[ym] = rows

    # 설계사별 월·상품군 건수 (상세 차트와 전사 평균 비교용)
    c = data["contracts"]
    cnt = c.groupby(["agent_id", "year_month", "product_group"]).size()
    agent_mg = {}
    for aid in data["agents"]["agent_id"]:
        agent_mg[aid] = [[int(cnt.get((aid, ym, g), 0)) for g in m.PRODUCT_GROUPS] for ym in months]

    # 설계사 조회: 월별 건수·보험료·유지 건수(누적 유지율 계산용), 위험 조건, 계약 목록
    ag = data["agents"].sort_values("agent_id")
    agents = [[r.agent_id, r.agent_name, r.branch_id, r.branch_name, r.status,
               r.appoint_date.strftime("%Y-%m-%d"), r.db_source] for r in ag.itertuples()]
    by = c.assign(kept=(c["status"] == "유지").astype(int)).groupby(["agent_id", "year_month"]).agg(
        n=("contract_id", "size"), prem=("monthly_premium", "sum"), kept=("kept", "sum"))
    agent_month = {aid: [[int(by.loc[(aid, ym)].n), int(by.loc[(aid, ym)].prem), int(by.loc[(aid, ym)].kept)]
                         if (aid, ym) in by.index else [0, 0, 0] for ym in months] for aid in ag["agent_id"]}
    risk_chk = {}
    for ym in months:
        r = m.risk_scores(data, ym)
        risk_chk[ym] = {a["agent_id"]: [[x["해당"] == "해당", x["현재 값"]] for _, x in m.risk_checklist(a).iterrows()]
                        for _, a in r.iterrows()}
    names = data["products"].set_index("product_id")["product_name"]
    agent_contracts = {aid: [] for aid in ag["agent_id"]}
    for r in c.sort_values(["contract_date", "contract_id"], ascending=False).itertuples():
        agent_contracts[r.agent_id].append([r.contract_date.strftime("%Y-%m-%d"), names[r.product_id], r.product_group,
                                            int(r.monthly_premium), r.status, int(r.is_replacement)])
    sample = m.risk_checklist(m.risk_scores(data, months[-1]).iloc[0])  # 조건 이름·기준·배점은 metrics.py에서 가져온다
    chk_rule = [[x["조건"], x["기준"], int(x["점수"].split(" / ")[1])] for _, x in sample.iterrows()]

    # ③ 실적 예측
    forecast = {}
    for ym in months:
        fc, seasonal = m.next_quarter_forecast(data, ym)
        if fc is None:
            forecast[ym] = None
            continue
        bid = dict(zip(branches["branch_name"], branches["branch_id"]))
        future = list(seasonal["월"])
        forecast[ym] = {
            "months": future,
            "seasonal": [f"{v:.3f}" for v in seasonal["계절지수"]],
            "rows": [[bid[r["지점"]], r["지점"], round(float(r["예측"]), 4), f"{r['예측']:.1f}", float(r["목표(가정)"]),
                      f"{r['목표(가정)']:,.0f}", pct(r["예측 달성률"]), r["판정"], f"{r['최근 3개월 평균']:.1f}",
                      [f"{r[f'{f} 예측']:.1f}" for f in future]] for _, r in fc.iterrows()],
        }

    # ④ 월간 보고서
    reports = {}
    for ym in months:
        md = rp.build_report(data, ym)
        # 굵은 소제목 바로 아래 목록도 목록으로 렌더링되도록 빈 줄을 넣는다 (미리보기용)
        md_view = re.sub(r"(\*\*[^\n]*\*\*)\n(- )", r"\1\n\n\2", md)
        reports[ym] = {"md": md, "html": markdown.markdown(md_view, extensions=["tables"]),
                       "pdf": base64.b64encode(ex.report_pdf(md)).decode(),
                       "docx": base64.b64encode(ex.report_docx(md)).decode()}

    payload = {
        "months": months,
        "branches": [[r.branch_id, r.branch_name] for r in branches.itertuples()],
        "groups": m.PRODUCT_GROUPS,
        "trend": trend, "perf": perf, "risk": risk, "agentMG": agent_mg,
        "forecast": forecast, "reports": reports,
        "agents": agents, "agentMonth": agent_month, "riskChk": risk_chk, "chkRule": chk_rule,
        "agentContracts": agent_contracts,
        "gapRate": m.FORECAST_GAP_RATE,
    }
    tpl = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    out = tpl.replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    (ROOT / "web" / "dashboard.html").write_text(out, encoding="utf-8")
    print(f"web/dashboard.html {len(out.encode()) / 1e6:.2f} MB")


if __name__ == "__main__":
    build()
