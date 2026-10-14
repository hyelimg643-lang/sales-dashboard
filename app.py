"""영업 성과 분석 대시보드 (PoC · 더미데이터). 실행: streamlit run app.py"""
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import metrics as m
import report as rp

SERIES = "#157f8d"      # 포인트 청록 (추이 선, 본인 비중)
BAR = "#8d9aaa"         # 실적·예측 막대 기본색
LOW = "#ee8a86"         # 기준 미달 막대
CRITICAL = "#d03a3a"    # 기준 미달 글자, 고위험
TARGET = "#8a939d"      # 목표 점선
COMPARE = "#a9b4c0"     # 비교 계열 (전사 평균)
WARNING = "#d9822b"     # 관찰 등급 글자색
TEALS = ["#157f8d", "#4ea7b3", "#85c3cc", "#b6dce1"]  # 비중 큰 순서대로 진한 청록
LOW_RATE = 90.0


def show(fig):
    """흰 카드 위에 바로 그리도록 차트 배경을 투명하게."""
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, width="stretch")

st.set_page_config(page_title="영업 성과 분석 대시보드", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #f7f9fa; border-right: 1px solid #e0e6eb; }
[class*="st-key-card"] { background: #ffffff; border-color: #e0e6eb !important; border-radius: 10px !important; }
.page-title { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin: 0 0 4px; }
.page-title .t { font-size: 24px; font-weight: 700; color: #15232d; }
.page-title .badge { font-size: 12px; color: #4a5a67; border: 1px solid #e0e6eb; border-radius: 999px; padding: 2px 10px; background: #fff; }
/* 탭을 아이콘 알약 버튼으로 */
.stTabs [role="tablist"] { gap: 8px; flex-wrap: wrap; border-bottom: 0 !important; box-shadow: none !important; }
.stTabs [data-testid="stTab"] { background: #ffffff; border: 1px solid #e0e6eb; border-radius: 8px; padding: 6px 16px !important; height: auto; }
.stTabs [data-testid="stTab"]::after, .stTabs [data-testid="stTab"]::before { display: none !important; }
.stTabs [data-testid="stTab"][aria-selected="true"] { background: #157f8d; border-color: #157f8d; }
.stTabs [data-testid="stTab"][aria-selected="true"] * { color: #ffffff !important; font-weight: 600; }
.kpi { display: flex; flex-direction: column; gap: 4px; padding: 2px 2px 4px; }
.kpi .k { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #4a5a67; font-weight: 500; }
.kpi .ic { width: 26px; height: 26px; border-radius: 7px; background: #e1f1f3; color: #157f8d; display: grid; place-items: center; }
.kpi .ic svg { width: 15px; height: 15px; }
.kpi .v { font-size: 28px; font-weight: 700; color: #15232d; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; line-height: 1.3; }
.kpi .s { font-size: 12.5px; color: #7d8b97; }
.kpi .up { color: #1e9a5a; font-weight: 600; } .kpi .down { color: #d03a3a; font-weight: 600; }
.card-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }
.card-head h4 { margin: 0; padding: 0; font-size: 16px; font-weight: 600; }
.hint { font-size: 12px; color: #0f6370; background: #e1f1f3; border: 1px solid #b6dce1; border-radius: 6px; padding: 2px 8px; }
</style>
""", unsafe_allow_html=True)

ICONS = {
    "doc": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM9 12h6M9 16h4"/></svg>',
    "coin": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/></svg>',
    "pct": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M19 5 5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/></svg>',
    "user": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>',
}


# ---------------------------------------------------------------- 표시 형식
def fmt_won(v):
    return "-" if v is None else f"{v:,.0f}원"


def fmt_pct(v):
    return "-" if v is None else f"{v:.1f}%"


def change_html(v):
    """전월 대비 증감: 올라가면 초록 ▲, 내려가면 빨강 ▼."""
    if v is None:
        return "전월 대비 -"
    cls, arrow = ("up", "▲") if v >= 0 else ("down", "▼")
    return f'전월 대비 <span class="{cls}">{v:+.1f}% {arrow}</span>'


_card_no = [0]


def card():
    """흰 배경 카드 (CSS가 key로 찾는다)."""
    _card_no[0] += 1
    return st.container(border=True, key=f"card{_card_no[0]}")


def kpi_card(icon, label, value, sub, value_color=None):
    with card():
        style = f' style="color:{value_color}"' if value_color else ""
        icon_html = f'<span class="ic">{ICONS[icon]}</span>' if icon else ""
        st.markdown(f'<div class="kpi"><span class="k">{icon_html}{label}</span>'
                    f'<span class="v"{style}>{value}</span><span class="s">{sub}</span></div>',
                    unsafe_allow_html=True)


def card_head(title, hint=None):
    hint_html = f'<span class="hint">{hint}</span>' if hint else ""
    st.markdown(f'<div class="card-head"><h4>{title}</h4>{hint_html}</div>', unsafe_allow_html=True)


@st.cache_data
def get_data():
    return m.load_data()


data = get_data()
months = m.month_list(data["contracts"])

# ---------------------------------------------------------------- 사이드바 (모든 탭 공통)
st.markdown('<div class="page-title"><div class="t">영업 성과 분석 대시보드</div><div class="badge">PoC · 더미데이터</div></div>',
            unsafe_allow_html=True)

with st.sidebar:
    ym = st.selectbox("기준 월", months, index=months.index("2026-09"))
    branch_names = ["전체"] + data["branches"]["branch_name"].tolist()
    branch_name = st.selectbox("지점", branch_names, index=0)
    st.markdown("상품군")
    groups = [g for g in m.PRODUCT_GROUPS if st.checkbox(g, value=True, key=f"pg_{g}")]
    st.caption("필터는 모든 탭에 공통 적용")
    st.markdown("등급 (② 위험 설계사)")
    grades = [g for g in m.GRADES if st.checkbox(g, value=(g != "정상"), key=f"grade_{g}")]

branch_ids = None
if branch_name != "전체":
    branch_ids = data["branches"].loc[data["branches"]["branch_name"] == branch_name, "branch_id"].tolist()
group_filter = None if len(groups) == len(m.PRODUCT_GROUPS) else groups

tab1, tab2, tab3, tab4 = st.tabs([":material/monitoring: 성과 대시보드", ":material/warning: 위험 설계사",
                                  ":material/history: 실적 예측", ":material/description: 월간 보고서"])

# ---------------------------------------------------------------- ① 성과 대시보드
with tab1:
    if not groups:
        st.warning("상품군을 하나 이상 선택하세요.")
        st.stop()  # 상품군이 없으면 모든 탭이 계산할 대상이 없다

    k = m.kpi_summary(data, ym, branch_ids, group_filter)

    # 1. KPI 카드 4개
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("doc", "신계약 건수", f"{k['count']:,}건", change_html(k["count_change"]))
    with c2:
        kpi_card("coin", "신계약 보험료", fmt_won(k["premium"]), change_html(k["premium_change"]))
    with c3:
        kpi_card("pct", "목표 달성률(건수)", fmt_pct(k["count_rate"]),
                 "목표 -" if k["target_count"] is None else f"목표 {k['target_count']:,}건")
    with c4:
        kpi_card("user", "가동률", fmt_pct(k["activity_rate"]), f"{k['working_agents']} / {k['active_agents']}명")
    if group_filter is not None:
        st.caption("※ 목표는 상품군 구분 없이 지점 전체 기준이므로, 상품군을 일부만 선택하면 달성률이 낮게 보입니다.")

    left, right = st.columns([3, 2])

    # 2. 월별 신계약 추이 (24개월)
    with left, card():
        head, toggle = st.columns([3, 2])
        with head:
            card_head("월별 신계약 추이 (24개월)")
        measure = toggle.radio("지표", ["건수", "보험료"], horizontal=True, label_visibility="collapsed")
        trend = m.monthly_trend(data, ym, 24, branch_ids, group_filter)
        unit = "건" if measure == "건수" else "원"
        fig = go.Figure(go.Scatter(
            x=trend["연월"], y=trend[measure], mode="lines", fill="tozeroy",
            line=dict(color=SERIES, width=2), fillcolor="rgba(21,127,141,0.07)",
            hovertemplate=f"%{{x}}<br>{measure} %{{y:,.0f}}{unit}<extra></extra>",
        ))
        # 최고점 표시 (12·1월이면 성수기로 표기)
        peak = trend.loc[trend[measure].idxmax()]
        peak_txt = "12~1월 성수기" if peak["연월"][5:] in ("12", "01") else f"최고 {peak['연월']}"
        fig.add_annotation(x=peak["연월"], y=peak[measure], text=peak_txt, showarrow=False, yshift=14,
                           font=dict(size=11, color="#4a5a67"))
        fig.update_layout(
            height=320, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
            yaxis=dict(title=None, tickformat=",", rangemode="tozero"),
            xaxis=dict(title=None, type="category", tickangle=0, nticks=8),
        )
        show(fig)

    # 3. 상품군별 비중 (당월)
    with right, card():
        card_head("상품군별 비중 (당월)", "가로 막대")
        share = m.product_group_share(data, ym, branch_ids, group_filter)
        rank = share["비중"].rank(ascending=False, method="first").astype(int) - 1
        fig = go.Figure(go.Bar(
            y=share["상품군"], x=share["비중"], orientation="h",
            marker=dict(color=[TEALS[min(r, 3)] for r in rank], cornerradius=4),
            text=[f"{v:.1f}%" for v in share["비중"]], textposition="outside",
            customdata=share[["건수", "보험료"]],
            hovertemplate="%{y}<br>비중 %{x:.1f}%<br>%{customdata[0]:,}건 · %{customdata[1]:,}원<extra></extra>",
        ))
        fig.update_layout(
            height=320, margin=dict(l=10, r=40, t=10, b=10), bargap=0.45,
            yaxis=dict(autorange="reversed", title=None),
            xaxis=dict(title=None, ticksuffix="%", range=[0, max(share["비중"].max() * 1.25, 1)]),
        )
        show(fig)

    # 4. 지점별 실적 vs 목표 (당월)
    with card():
        card_head("지점별 실적 vs 목표 (당월)", f"막대=실적, 점선=목표, {LOW_RATE:.0f}% 미만은 빨간색")
        bp = m.branch_performance(data, ym, branch_ids, group_filter)
        low = [r is not None and r < LOW_RATE for r in bp["건수 달성률"]]
        fig = go.Figure()
        fig.add_bar(
            x=bp["지점"], y=bp["건수"], name="실적", showlegend=False,
            marker=dict(color=[LOW if l else BAR for l in low], cornerradius=4),
            text=[f"{r:.1f}%" if l else "" for r, l in zip(bp["건수 달성률"], low)],
            textposition="outside", textfont=dict(color=CRITICAL),
            customdata=list(zip(bp["목표 건수"], [fmt_pct(r) for r in bp["건수 달성률"]])),
            hovertemplate="%{x}<br>실적 %{y}건 / 목표 %{customdata[0]}건<br>달성률 %{customdata[1]}<extra></extra>",
        )
        # 지점별 목표: 막대 폭만큼의 점선
        for i, t in enumerate(bp["목표 건수"]):
            if t is None or t != t:
                continue
            fig.add_shape(type="line", x0=i - 0.45, x1=i + 0.45, y0=t, y1=t,
                          line=dict(color=TARGET, width=2, dash="dash"))
        # 범례: 막대 색이 지점마다 달라서 실적 범례는 기본색으로 따로 그린다
        ymax = max(bp["건수"].max(), bp["목표 건수"].max()) * 1.2
        fig.update_layout(
            height=340, margin=dict(l=10, r=10, t=10, b=10), bargap=0.45,
            yaxis=dict(title=None, range=[0, ymax]), xaxis=dict(title=None),
            legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
        )
        show(fig)

        with st.expander("표로 보기"):
            table = bp.copy()
            for col in ["건수 달성률", "보험료 달성률"]:
                table[col] = [("▼ " if r is not None and r < LOW_RATE else "") + fmt_pct(r) for r in table[col]]
            for col in ["보험료", "목표 보험료"]:
                table[col] = table[col].map(lambda v: f"{v:,.0f}")
            st.dataframe(table, hide_index=True, width="stretch")

# ---------------------------------------------------------------- ② 위험 설계사
with tab2:
    risk = m.risk_scores(data, ym, branch_ids)
    counts = risk["등급"].value_counts().reindex(m.GRADES, fill_value=0)

    # 1. 등급별 인원 카드
    cards = [
        ("고위험 (60점↑)", "고위험", "코칭·교육 대상"),
        ("관찰 (30~59점)", "관찰", "지점장 모니터링"),
        ("정상", "정상", f"재직 {len(risk)}명 중"),
    ]
    colors = {"고위험": CRITICAL, "관찰": WARNING, "정상": None}
    for col, (label, grade, note) in zip(st.columns(3), cards):
        with col:
            kpi_card(None, label, f"{counts[grade]}명", note, colors[grade])

    # 2. 위험 설계사 목록 (점수 높은 순)
    with card():
        card_head("위험 설계사 목록 (점수 높은 순)", "행 클릭 → 아래 상세 표시 · CSV 다운로드")
        listed = risk[risk["등급"].isin(grades)].reset_index(drop=True)
        cols = ["설계사", "지점", "점수", "등급", "해당 사유", "직전3M→최근3M", "유지율"]
        view = listed[cols].copy()
        view["유지율"] = view["유지율"].map(fmt_pct)
        styled = view.style.map(
            lambda g: f"color: {CRITICAL}; font-weight: 600" if g == "고위험"
            else (f"color: {WARNING}" if g == "관찰" else ""),
            subset=["등급"],
        )
        st.caption("행을 클릭하면 아래에 상세가 표시됩니다.")
        event = st.dataframe(
            styled, hide_index=True, width="stretch", height=min(38 + 35 * len(view), 600),
            on_select="rerun", selection_mode="single-row", key="risk_table",
        )
        st.download_button(
            "CSV 다운로드", view.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"위험설계사_{ym}.csv", mime="text/csv",
        )
        if not grades:
            st.info("사이드바에서 등급을 하나 이상 선택하세요.")

    # 3. 선택한 설계사 상세
    rows = event.selection.rows if event else []
    if rows and rows[0] < len(listed):
        sel = listed.iloc[rows[0]]
        left, right = st.columns(2)
        with left, card():
            card_head(f"{sel['설계사']}: 월별 판매 건수 (12개월)", "막대 그래프")
            mc = m.agent_monthly_counts(data, sel["agent_id"], ym)
            fig = go.Figure(go.Bar(
                x=mc["연월"], y=mc["건수"], marker=dict(color=BAR, cornerradius=4),
                hovertemplate="%{x}<br>%{y}건<extra></extra>",
            ))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), bargap=0.35,
                              xaxis=dict(type="category", title=None), yaxis=dict(title=None, dtick=1))
            show(fig)
            st.caption(f"{sel['지점']} · 점수 {sel['점수']}점 · {sel['해당 사유'] or '해당 사유 없음'}")
        with right, card():
            card_head(f"{sel['설계사']}: 상품군 구성 vs 전사 평균", "비교 막대")
            mix = m.agent_group_mix(data, sel["agent_id"], ym)
            fig = go.Figure()
            for name, color in [("본인", SERIES), ("전사 평균", COMPARE)]:
                fig.add_bar(x=mix["상품군"], y=mix[name], name=name,
                            marker=dict(color=color, cornerradius=4),
                            text=[f"{v:.1f}%" for v in mix[name]], textposition="outside",
                            hovertemplate=f"%{{x}}<br>{name} %{{y:.1f}}%<extra></extra>")
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                              barmode="group", bargap=0.35, bargroupgap=0.1,
                              yaxis=dict(title=None, ticksuffix="%", range=[0, max(mix[["본인", "전사 평균"]].max()) * 1.2]),
                              xaxis=dict(title=None),
                              legend=dict(orientation="h", y=1.1, x=1, xanchor="right"))
            show(fig)
            st.caption("기준 월까지 전체 기간 계약 건수 기준")
    else:
        st.caption("표에서 설계사를 선택하면 월별 판매 건수와 상품군 구성이 표시됩니다.")

# ---------------------------------------------------------------- ③ 실적 예측
with tab3:
    fc, seasonal = m.next_quarter_forecast(data, ym, branch_ids)
    if fc is None:
        st.info("다음 분기 계절지수에 필요한 전년 같은 달 실적이 없어 예측할 수 없습니다. 기준 월을 2025-09 이후로 선택하세요.")
    else:
        quarter = pd.Period(seasonal["월"].iloc[0], "M")
        q_label = f"{quarter.year}년 {quarter.quarter}분기" if quarter.month in (1, 4, 7, 10) else \
            f"{seasonal['월'].iloc[0]} ~ {seasonal['월'].iloc[-1]}"
        low = [r is not None and r < m.FORECAST_GAP_RATE for r in fc["예측 달성률"]]

        # 1. 지점별 다음 분기 예측 vs 목표
        with card():
            card_head(f"지점별 다음 분기({q_label}) 예측 vs 목표",
                      f"막대=예측, 점선=목표(가정), {m.FORECAST_GAP_RATE:.0f}% 미만은 빨간색")
            fig = go.Figure()
            fig.add_bar(
                x=fc["지점"], y=fc["예측"], showlegend=False,
                marker=dict(color=[LOW if l else BAR for l in low], cornerradius=4),
                text=[f"⚠ {r:.1f}%" if l else "" for r, l in zip(fc["예측 달성률"], low)],
                textposition="outside", textfont=dict(color=CRITICAL),
                customdata=list(zip(fc["목표(가정)"], [fmt_pct(r) for r in fc["예측 달성률"]])),
                hovertemplate="%{x}<br>예측 %{y:.1f}건 / 목표 %{customdata[0]:.0f}건<br>달성률 %{customdata[1]}<extra></extra>",
            )
            for i, t in enumerate(fc["목표(가정)"]):
                if pd.notna(t):
                    fig.add_shape(type="line", x0=i - 0.45, x1=i + 0.45, y0=t, y1=t,
                                  line=dict(color=TARGET, width=2, dash="dash"))
            fig.update_layout(
                height=340, margin=dict(l=10, r=10, t=10, b=10), bargap=0.45,
                yaxis=dict(title=None, range=[0, max(fc["예측"].max(), fc["목표(가정)"].max()) * 1.2]),
                xaxis=dict(title=None), legend=dict(orientation="h", y=1.08, x=1, xanchor="right"),
            )
            show(fig)

        # 2. 예측 표
        table = pd.DataFrame({
            "지점": fc["지점"],
            "예측": fc["예측"].map(lambda v: f"{v:.1f}"),
            "목표(가정)": fc["목표(가정)"].map(lambda v: "-" if pd.isna(v) else f"{v:,.0f}"),
            "예측 달성률": fc["예측 달성률"].map(fmt_pct),
            "판정": fc["판정"],
        })
        st.dataframe(
            table.style.map(lambda v: f"color: {CRITICAL}; font-weight: 600" if v.startswith("⚠") else "",
                            subset=["판정"]),
            hide_index=True, width="stretch",
        )

        # 3. 계산 근거
        with st.expander("계산 근거"):
            st.markdown(
                "- 월 예측 = 지점별 최근 3개월 월평균 건수 × 계절지수\n"
                f"- 계절지수 = 전년 같은 달 전사 건수 ÷ {m.SEASONAL_BASE_YEAR}년 1~12월 전사 월평균 건수\n"
                "- 다음 분기 예측 = 3개월 예측의 합, 목표(가정) = 최근 3개월 목표 평균 × 3\n"
                f"- 예측 달성률이 {m.FORECAST_GAP_RATE:.0f}% 미만이면 \"괴리 예상\""
            )
            st.markdown("**계절지수**")
            st.dataframe(
                pd.DataFrame({"월": seasonal["월"], "계절지수": seasonal["계절지수"].map(lambda v: f"{v:.3f}")}),
                hide_index=True,
            )
            st.markdown("**지점별 최근 3개월 평균과 월별 예측**")
            detail = fc[["지점", "최근 3개월 평균"] + [f"{f} 예측" for f in seasonal["월"]] + ["예측"]].copy()
            for col in detail.columns[1:]:
                detail[col] = detail[col].map(lambda v: f"{v:.1f}")
            st.dataframe(detail, hide_index=True, width="stretch")
        st.caption("※ 예측은 지점 전체 건수 기준이며 상품군 필터는 적용하지 않습니다.")

# ---------------------------------------------------------------- ④ 월간 보고서
with tab4:
    c1, c2, _ = st.columns([1, 1, 3], vertical_alignment="bottom")
    report_ym = c1.selectbox("보고 월", months, index=months.index(ym), key="report_ym")
    if c2.button("보고서 생성", type="primary"):
        st.session_state["report"] = (report_ym, rp.build_report(data, report_ym))
    st.caption("보고서는 양식대로 전 지점·전 상품군 기준으로 작성되며, 사이드바의 지점·상품군 필터는 적용하지 않습니다.")

    saved = st.session_state.get("report")
    if saved and saved[0] == report_ym:
        with card():
            card_head("미리보기 (docs/report_template.md 구성)", "마크다운 렌더링")
            # 미리보기에서는 제목 크기만 두 단계 줄인다 (다운로드 파일은 양식 그대로)
            st.markdown(re.sub(r"^(#+) ", r"\1## ", saved[1], flags=re.M))
        st.download_button(
            "⬇ 보고서 다운로드 (.md)", saved[1].encode("utf-8"),
            file_name=f"영업성과보고서_{report_ym}.md", mime="text/markdown",
        )
    else:
        st.info("보고 월을 고르고 \"보고서 생성\"을 누르세요.")
