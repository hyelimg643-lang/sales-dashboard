"""월간 보고서 마크다운 생성 (docs/report_template.md 구성·문구 스타일). 계산은 metrics.py를 쓴다."""
import pandas as pd

import metrics as m

LOW_RATE = 90.0


def _pct(v):
    return "-" if v is None or pd.isna(v) else f"{v:.1f}%"


def _signed_pct(v):
    return "-" if v is None else f"{v:+.1f}%"


def _won(v):
    return "-" if v is None or pd.isna(v) else f"{v:,.0f}"


def _mark(rate):
    """달성률 90% 미만이면 ▼ 표시."""
    return ("▼ " if rate is not None and not pd.isna(rate) and rate < LOW_RATE else "") + _pct(rate)


def _quarter_label(months: list) -> tuple:
    """(제목용 라벨, 문장용 짧은 라벨). 분기 시작 월이 아니면 기간으로 표시."""
    p = pd.Period(months[0], "M")
    if p.month in (1, 4, 7, 10):
        return f"{p.year}년 {p.quarter}분기", f"{p.quarter}분기"
    return f"{months[0]} ~ {months[-1]}", "다음 분기"


def _short_id(agent_id: str) -> str:
    return agent_id.lstrip("A")


def _risk_table(rows: pd.DataFrame) -> list:
    lines = ["| 설계사 | 지점 | 점수 | 해당 사유 |", "|---|---|---:|---|"]
    if rows.empty:
        lines.append("| 해당 없음 | | | |")
    for _, r in rows.iterrows():
        lines.append(f"| {r['설계사']} | {r['지점']} | {r['점수']} | {r['해당 사유']} |")
    return lines


def _summary_sentences(k, share, bp, high) -> list:
    # 1. 전월 대비 실적 변화와 주된 원인 상품군
    if k["count_change"] is None:
        s1 = f"신계약 건수는 {k['count']}건이다."
    else:
        up = k["count_change"] >= 0
        movers = share[share["증감"] > 0] if up else share[share["증감"] < 0]
        movers = movers.sort_values("증감", ascending=not up).head(2)
        verb = "증가" if up else "감소"
        s1 = f"신계약 건수는 전월 대비 {abs(k['count_change']):.1f}% {verb}했으며"
        if movers.empty:
            s1 += "."
        else:
            names = "과 ".join(f"{g}({d:+d}건)" for g, d in zip(movers["상품군"], movers["증감"]))
            s1 += f", {names}이 {verb}를 이끌었다."

    # 2. 목표 미달 지점 (건수 달성률 90% 미만)
    low = bp[[r is not None and r < LOW_RATE for r in bp["건수 달성률"]]]
    if low.empty:
        s2 = f"모든 지점이 건수 달성률 {LOW_RATE:.0f}% 이상으로 목표 수준을 유지했다."
    else:
        parts = [f"{r['지점']}은 건수 달성률 {_pct(r['건수 달성률'])}, 보험료 달성률 {_pct(r['보험료 달성률'])}"
                 for _, r in low.iterrows()]
        s2 = ", ".join(parts) + "로 목표에 크게 못 미쳤다."

    # 3. 고위험 설계사 수와 조치 필요 사항
    if high.empty:
        s3 = "고위험 설계사는 없다."
    else:
        no_sales = int(high["cond_no_sales"].sum())
        s3 = f"고위험 설계사는 {len(high)}명이며, "
        if no_sales:
            who = f"{no_sales}명 모두" if no_sales == len(high) else f"이 중 {no_sales}명은"
            s3 += f"{who} 최근 2개월 동안 신계약이 없어 즉시 면담이 필요하다."
        else:
            s3 += "코칭·교육 배정이 필요하다."
    return [s1, s2, s3]


def _action_items(ym, high, watch, fc, q_short) -> list:
    next_month = (pd.Period(ym, "M") + 1).month
    items = []
    if high.empty:
        items.append("고위험 설계사는 없으므로 관찰 대상 설계사를 지점장이 월 단위로 점검한다.")
    else:
        items.append(f"고위험 설계사 {len(high)}명은 {next_month}월 둘째 주까지 지점장 면담과 코칭 교육을 배정한다.")

    gap = fc[fc["판정"] != "정상"] if fc is not None else pd.DataFrame()
    if gap.empty:
        items.append(f"{q_short} 괴리 예상 지점은 없으므로 현재 활동 수준을 유지한다.")
    watch_counts = watch.groupby("지점").size()
    max_watch = watch_counts.max() if len(watch_counts) else 0
    for _, g in gap.iterrows():
        mine = watch[watch["지점"] == g["지점"]]
        if mine.empty:
            items.append(f"{g['지점']}은 {q_short} 괴리가 예상되므로 지점 단위 활동 점검이 필요하다.")
            continue
        ids = "·".join(_short_id(a) for a in sorted(mine["agent_id"]))
        most = "으로 가장 많고" if len(mine) == max_watch else "이고"
        items.append(f"{g['지점']}은 관찰 대상 설계사가 {len(mine)}명({ids}){most} "
                     f"{q_short} 괴리가 예상되므로 지점 단위 활동 점검이 필요하다.")
    return items


def build_report(data, ym: str) -> str:
    """선택한 월의 전 지점 보고서 마크다운."""
    p = pd.Period(ym, "M")
    k = m.kpi_summary(data, ym)
    prev = k["prev"]
    share = m.product_group_share(data, ym)
    bp = m.branch_performance(data, ym)
    risk = m.risk_scores(data, ym)
    high = risk[risk["등급"] == "고위험"]
    watch = risk[risk["등급"] == "관찰"]
    fc, seasonal = m.next_quarter_forecast(data, ym)
    q_label, q_short = _quarter_label(list(seasonal["월"]))

    L = [
        f"# {p.year}년 {p.month}월 영업성과 보고서",
        "",
        f"- 작성기준일: {p.end_time.strftime('%Y-%m-%d')}",
        f"- 대상: 전 지점 ({len(data['branches'])}개), 재직 설계사 {k['active_agents']}명",
        "- 작성: 하이브리드사업부 (자동 생성)",
        "",
        "## 1. 요약",
        "",
        "| 구분 | 당월 | 전월 | 증감 | 목표 | 달성률 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if prev:
        # 가동률 증감은 표시값(소수 1자리) 기준 차이
        act_change = round(k["activity_rate"], 1) - round(prev["activity_rate"], 1)
        L += [
            f"| 신계약 건수 | {k['count']:,}건 | {prev['count']:,}건 | {_signed_pct(k['count_change'])} "
            f"| {k['target_count']:,}건 | {_pct(k['count_rate'])} |",
            f"| 신계약 보험료(월납) | {k['premium']:,}원 | {prev['premium']:,}원 | {_signed_pct(k['premium_change'])} "
            f"| {k['target_premium']:,}원 | {_pct(k['premium_rate'])} |",
            f"| 가동률 | {_pct(k['activity_rate'])} | {_pct(prev['activity_rate'])} | {act_change:+.1f}%p | - | - |",
        ]
    else:
        L += [
            f"| 신계약 건수 | {k['count']:,}건 | - | - | {k['target_count']:,}건 | {_pct(k['count_rate'])} |",
            f"| 신계약 보험료(월납) | {k['premium']:,}원 | - | - | {k['target_premium']:,}원 | {_pct(k['premium_rate'])} |",
            f"| 가동률 | {_pct(k['activity_rate'])} | - | - | - | - |",
        ]
    L += ["", "**주요 내용**"]
    L += [f"- {s}" for s in _summary_sentences(k, share, bp, high)]

    # 2. 지점별 실적
    L += [
        "", "## 2. 지점별 실적", "",
        "| 지점 | 권역 | 건수 | 목표 | 달성률 | 보험료(원) | 목표(원) | 달성률 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in bp.iterrows():
        L.append(f"| {r['지점']} | {r['권역']} | {r['건수']} | {r['목표 건수']:.0f} | {_mark(r['건수 달성률'])} "
                 f"| {_won(r['보험료'])} | {_won(r['목표 보험료'])} | {_mark(r['보험료 달성률'])} |")
    L.append(f"| **합계** | | **{k['count']}** | **{k['target_count']}** | **{_pct(k['count_rate'])}** "
             f"| **{_won(k['premium'])}** | **{_won(k['target_premium'])}** | **{_pct(k['premium_rate'])}** |")
    L += ["", f"※ 달성률 {LOW_RATE:.0f}% 미만 지점은 ▼ 표시"]

    # 3. 상품군별 실적
    L += [
        "", "## 3. 상품군별 실적", "",
        "| 상품군 | 건수 | 비중 | 전월 건수 | 증감 | 보험료(원) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in share.iterrows():
        L.append(f"| {r['상품군']} | {r['건수']} | {_pct(r['비중'])} | {r['전월 건수']} | {r['증감']:+d} "
                 f"| {_won(r['보험료'])} |")
    L.append(f"| **합계** | **{share['건수'].sum()}** | **100.0%** | **{share['전월 건수'].sum()}** "
             f"| **{share['증감'].sum():+d}** | **{_won(share['보험료'].sum())}** |")

    # 4. 위험 설계사 현황
    L += ["", "## 4. 위험 설계사 현황", "", "**고위험 (60점 이상) — 코칭·교육 대상**", ""]
    L += _risk_table(high)
    L += ["", "**관찰 (30~59점) — 지점장 모니터링**", ""]
    L += _risk_table(watch)

    # 5. 다음 분기 예측
    L += ["", f"## 5. 다음 분기({q_label}) 실적 예측", ""]
    if fc is None:
        L.append("전년 같은 달 실적이 없어 계절지수를 구할 수 없으므로 예측을 생략한다.")
    else:
        L += ["| 지점 | 예측 건수 | 목표(가정) | 예측 달성률 | 판정 |", "|---|---:|---:|---:|---|"]
        for _, r in fc.iterrows():
            L.append(f"| {r['지점']} | {r['예측']:.1f} | {r['목표(가정)']:.0f} | {_pct(r['예측 달성률'])} | {r['판정']} |")
        idx = ", ".join(f"{pd.Period(mo, 'M').month}월 {v:.3f}" for mo, v in zip(seasonal["월"], seasonal["계절지수"]))
        L += ["", f"※ 계절지수: {idx} ({m.SEASONAL_BASE_YEAR}년 실적 기준)"]

    # 6. 조치 제안
    L += ["", "## 6. 조치 제안"]
    L += [f"- {s}" for s in _action_items(ym, high, watch, fc, q_short)]
    return "\n".join(L) + "\n"
