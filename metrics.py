"""지표 계산 로직 (docs/rules.md 기준). 화면 코드(app.py)와 분리한다."""
import io
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
BASE_DATE = pd.Timestamp("2026-09-30")
PRODUCT_GROUPS = ["종신", "건강", "연금", "저축"]


# ---------------------------------------------------------------- 데이터 로드
TABLES = {  # 파일 이름: (표시명, 필수 열)
    "branches": ("지점", ["branch_id", "branch_name", "region"]),
    "agents": ("설계사", ["agent_id", "agent_name", "branch_id", "appoint_date", "status", "db_source"]),
    "products": ("상품", ["product_id", "product_name", "product_group"]),
    "contracts": ("신계약", ["contract_id", "contract_date", "agent_id", "product_id", "monthly_premium",
                             "status", "cancel_date", "is_replacement"]),
    "targets": ("목표", ["year_month", "branch_id", "target_count", "target_premium"]),
}
ALLOWED = {  # (파일, 열): 허용 값
    ("agents", "status"): ["재직", "해촉"],
    ("contracts", "status"): ["유지", "해지", "실효"],
    ("products", "product_group"): PRODUCT_GROUPS,
}
DATES = {"agents": ["appoint_date"], "contracts": ["contract_date", "cancel_date"]}
NUMBERS = {"contracts": ["monthly_premium", "is_replacement"], "targets": ["target_count", "target_premium"]}


def read_csv(source) -> pd.DataFrame:
    """CSV 읽기. 엑셀에서 저장한 CP949 파일도 받는다."""
    raw = source.read_bytes() if isinstance(source, Path) else source
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc, dtype={"year_month": str})
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949로 저장해 주세요).")


def read_tables(data_dir: Path = DATA_DIR) -> dict:
    return {name: read_csv(data_dir / f"{name}.csv") for name in TABLES}


def validate_tables(raw: dict) -> list:
    """필수 열, 날짜·숫자 형식, 허용 값, ID 연결을 검사해 오류 문구 목록을 돌려준다."""
    errors = []
    for name, (label, cols) in TABLES.items():
        df = raw[name]
        missing = [c for c in cols if c not in df.columns]
        if missing:
            errors.append(f"{name}.csv({label}): 필수 열이 없습니다: {', '.join(missing)}")
        elif df.empty:
            errors.append(f"{name}.csv({label}): 데이터 행이 없습니다.")
    if errors:
        return errors  # 열이 맞아야 아래 검사가 의미 있다

    for name, cols in DATES.items():
        for c in cols:
            bad = pd.to_datetime(raw[name][c], errors="coerce").isna() & raw[name][c].notna()
            if bad.any():
                errors.append(f"{name}.csv: {c} 열에 날짜가 아닌 값이 {bad.sum()}개 있습니다 (예: {raw[name].loc[bad, c].iloc[0]}).")
    for name, cols in NUMBERS.items():
        for c in cols:
            bad = pd.to_numeric(raw[name][c], errors="coerce").isna()
            if bad.any():
                errors.append(f"{name}.csv: {c} 열에 숫자가 아닌 값이나 빈 칸이 {bad.sum()}개 있습니다.")
    bad_ym = ~raw["targets"]["year_month"].astype(str).str.fullmatch(r"\d{4}-\d{2}")
    if bad_ym.any():
        errors.append(f"targets.csv: year_month는 2026-09 형식이어야 합니다 (예: {raw['targets'].loc[bad_ym, 'year_month'].iloc[0]}).")
    for (name, c), allowed in ALLOWED.items():
        bad = sorted(set(raw[name][c].dropna().astype(str)) - set(allowed))
        if bad:
            errors.append(f"{name}.csv: {c} 열에 허용되지 않은 값이 있습니다: {', '.join(bad[:5])} (허용: {', '.join(allowed)})")

    links = [("agents", "branch_id", "branches"), ("targets", "branch_id", "branches"),
             ("contracts", "agent_id", "agents"), ("contracts", "product_id", "products")]
    for name, c, ref in links:
        unknown = sorted(set(raw[name][c].dropna()) - set(raw[ref][c]))
        if unknown:
            errors.append(f"{name}.csv: {ref}.csv에 없는 {c}가 있습니다: {', '.join(map(str, unknown[:5]))}")
    return errors


def prepare_data(raw: dict) -> dict:
    """원본 표 5개에 지점·상품군·연월을 붙여 계산용 데이터로 만든다."""
    branches = raw["branches"].copy()
    agents = raw["agents"].copy()
    products = raw["products"].copy()
    targets = raw["targets"].copy()
    contracts = raw["contracts"].copy()
    targets["year_month"] = targets["year_month"].astype(str)

    agents["appoint_date"] = pd.to_datetime(agents["appoint_date"])
    contracts["contract_date"] = pd.to_datetime(contracts["contract_date"])
    contracts["cancel_date"] = pd.to_datetime(contracts["cancel_date"])
    contracts["year_month"] = contracts["contract_date"].dt.strftime("%Y-%m")
    contracts = (
        contracts.merge(agents[["agent_id", "agent_name", "branch_id"]], on="agent_id", how="left")
        .merge(products[["product_id", "product_group"]], on="product_id", how="left")
        .merge(branches[["branch_id", "branch_name"]], on="branch_id", how="left")
    )
    agents = agents.merge(branches[["branch_id", "branch_name"]], on="branch_id", how="left")
    targets = targets.merge(branches[["branch_id", "branch_name"]], on="branch_id", how="left")

    return {
        "branches": branches,
        "agents": agents,
        "products": products,
        "targets": targets,
        "contracts": contracts,
    }


def load_data(data_dir: Path = DATA_DIR) -> dict:
    """data/ 폴더의 CSV 5개를 읽어 계산용 데이터로 만든다."""
    return prepare_data(read_tables(data_dir))


def month_list(contracts: pd.DataFrame) -> list:
    return sorted(contracts["year_month"].unique())


def prev_month(ym: str) -> str:
    return (pd.Period(ym, "M") - 1).strftime("%Y-%m")


# ---------------------------------------------------------------- 필터
def filter_contracts(contracts, branch_ids=None, groups=None):
    df = contracts
    if branch_ids is not None:
        df = df[df["branch_id"].isin(branch_ids)]
    if groups is not None:
        df = df[df["product_group"].isin(groups)]
    return df


def filter_targets(targets, branch_ids=None):
    if branch_ids is None:
        return targets
    return targets[targets["branch_id"].isin(branch_ids)]


def active_agents(agents, ym: str, branch_ids=None):
    """해당 월 재직 설계사: status=재직 이고 그 달 말일까지 위촉된 설계사."""
    month_end = pd.Period(ym, "M").end_time
    df = agents[(agents["status"] == "재직") & (agents["appoint_date"] <= month_end)]
    if branch_ids is not None:
        df = df[df["branch_id"].isin(branch_ids)]
    return df


# ---------------------------------------------------------------- 공통 계산
def safe_rate(num, den):
    """분모가 0이면 None (화면에서 '-')."""
    if den is None or den == 0 or pd.isna(den):
        return None
    return num / den * 100


def month_summary(data, ym, branch_ids=None, groups=None) -> dict:
    """한 달의 건수·보험료·목표·가동률."""
    c = filter_contracts(data["contracts"], branch_ids, groups)
    cm = c[c["year_month"] == ym]
    t = filter_targets(data["targets"], branch_ids)
    tm = t[t["year_month"] == ym]

    act = active_agents(data["agents"], ym, branch_ids)
    working = cm[cm["agent_id"].isin(act["agent_id"])]["agent_id"].nunique()

    count = len(cm)
    premium = int(cm["monthly_premium"].sum())
    target_count = int(tm["target_count"].sum()) if len(tm) else None
    target_premium = int(tm["target_premium"].sum()) if len(tm) else None
    return {
        "count": count,
        "premium": premium,
        "target_count": target_count,
        "target_premium": target_premium,
        "count_rate": safe_rate(count, target_count),
        "premium_rate": safe_rate(premium, target_premium),
        "working_agents": working,
        "active_agents": len(act),
        "activity_rate": safe_rate(working, len(act)),
    }


def kpi_summary(data, ym, branch_ids=None, groups=None) -> dict:
    """당월 KPI와 전월 대비 증감."""
    cur = month_summary(data, ym, branch_ids, groups)
    pm = prev_month(ym)
    has_prev = pm in set(data["contracts"]["year_month"])
    prev = month_summary(data, pm, branch_ids, groups) if has_prev else None
    cur["prev"] = prev
    cur["count_change"] = safe_rate(cur["count"] - prev["count"], prev["count"]) if prev else None
    cur["premium_change"] = safe_rate(cur["premium"] - prev["premium"], prev["premium"]) if prev else None
    if prev and cur["activity_rate"] is not None and prev["activity_rate"] is not None:
        cur["activity_change"] = cur["activity_rate"] - prev["activity_rate"]
    else:
        cur["activity_change"] = None
    return cur


def monthly_trend(data, end_ym, months=24, branch_ids=None, groups=None) -> pd.DataFrame:
    """기준 월까지 최근 N개월 월별 건수·보험료."""
    all_months = [m for m in month_list(data["contracts"]) if m <= end_ym][-months:]
    c = filter_contracts(data["contracts"], branch_ids, groups)
    agg = c.groupby("year_month").agg(건수=("contract_id", "count"), 보험료=("monthly_premium", "sum"))
    agg = agg.reindex(all_months, fill_value=0)
    agg.index.name = "연월"
    return agg.reset_index()


def product_group_share(data, ym, branch_ids=None, groups=None) -> pd.DataFrame:
    """당월 상품군별 건수·비중·전월 건수·보험료."""
    c = filter_contracts(data["contracts"], branch_ids, groups)
    order = [g for g in PRODUCT_GROUPS if groups is None or g in groups]
    cur = c[c["year_month"] == ym].groupby("product_group")
    prev = c[c["year_month"] == prev_month(ym)].groupby("product_group")["contract_id"].count()
    df = pd.DataFrame({
        "건수": cur["contract_id"].count(),
        "보험료": cur["monthly_premium"].sum(),
    }).reindex(order, fill_value=0)
    df["전월 건수"] = prev.reindex(order, fill_value=0)
    df["증감"] = df["건수"] - df["전월 건수"]
    total = df["건수"].sum()
    df["비중"] = df["건수"] / total * 100 if total else 0.0
    df.index.name = "상품군"
    return df.reset_index()


def branch_performance(data, ym, branch_ids=None, groups=None) -> pd.DataFrame:
    """당월 지점별 실적 vs 목표."""
    c = filter_contracts(data["contracts"], branch_ids, groups)
    cm = c[c["year_month"] == ym].groupby("branch_id").agg(
        건수=("contract_id", "count"), 보험료=("monthly_premium", "sum"))
    t = filter_targets(data["targets"], branch_ids)
    tm = t[t["year_month"] == ym].set_index("branch_id")

    b = data["branches"]
    if branch_ids is not None:
        b = b[b["branch_id"].isin(branch_ids)]
    df = b.set_index("branch_id")[["branch_name", "region"]].join(cm).join(
        tm[["target_count", "target_premium"]])
    df[["건수", "보험료"]] = df[["건수", "보험료"]].fillna(0).astype(int)
    df["건수 달성률"] = [safe_rate(a, t) for a, t in zip(df["건수"], df["target_count"])]
    df["보험료 달성률"] = [safe_rate(a, t) for a, t in zip(df["보험료"], df["target_premium"])]
    df = df.rename(columns={
        "branch_name": "지점", "region": "권역",
        "target_count": "목표 건수", "target_premium": "목표 보험료",
    })
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- 위험점수 (rules.md 4장)
RISK_RULES = [  # (컬럼, 점수, 사유) — 표시 순서도 이 순서
    ("cond_drop", 30, "판매 급감"),
    ("cond_retention", 25, "유지율 저하"),
    ("cond_no_sales", 25, "연속 무실적"),
    ("cond_concentration", 10, "상품 편중"),
    ("cond_early_cancel", 10, "조기해지 다발"),
]
GRADES = ["고위험", "관찰", "정상"]


def month_range(end_ym: str, n: int, offset: int = 0) -> list:
    """end_ym에서 offset개월 앞을 끝으로 하는 n개월 목록 (오래된 순)."""
    end = pd.Period(end_ym, "M") - offset
    return [(end - i).strftime("%Y-%m") for i in range(n - 1, -1, -1)]


def risk_grade(score: int) -> str:
    if score >= 60:
        return "고위험"
    if score >= 30:
        return "관찰"
    return "정상"


def risk_scores(data, ym: str = "2026-09", branch_ids=None) -> pd.DataFrame:
    """재직 설계사별 위험점수·등급·사유 (점수 높은 순).

    기간은 기준 월을 당월로 보고 계산한다 (2026-09이면 rules.md 1장과 같다).
    유지율·조기해지율·편중도는 기준 월까지의 전체 기간 계약으로 계산한다.
    """
    month_end = pd.Period(ym, "M").end_time
    agents = active_agents(data["agents"], ym, branch_ids).copy()
    c = data["contracts"]
    c = c[(c["contract_date"] <= month_end) & c["agent_id"].isin(agents["agent_id"])]

    recent3, prev3, recent2 = month_range(ym, 3), month_range(ym, 3, 3), month_range(ym, 2)
    by_agent = c.groupby("agent_id")
    early = (c["status"].isin(["해지", "실효"])
             & ((c["cancel_date"] - c["contract_date"]).dt.days <= 90))
    group_counts = c.groupby(["agent_id", "product_group"]).size().unstack(fill_value=0)

    s = pd.DataFrame(index=agents["agent_id"])
    s["recent3"] = c[c["year_month"].isin(recent3)].groupby("agent_id").size()
    s["prev3"] = c[c["year_month"].isin(prev3)].groupby("agent_id").size()
    s["recent2"] = c[c["year_month"].isin(recent2)].groupby("agent_id").size()
    s["total"] = by_agent.size()
    s["kept"] = c[c["status"] == "유지"].groupby("agent_id").size()
    s["early"] = c[early].groupby("agent_id").size()
    s["top_group"] = group_counts.max(axis=1)
    s = s.fillna(0).astype(int)

    has = s["total"] > 0
    s["유지율"] = (s["kept"] / s["total"] * 100).where(has)
    s["조기해지율"] = (s["early"] / s["total"] * 100).where(has)
    s["편중도"] = (s["top_group"] / s["total"] * 100).where(has)

    # 위촉 후 3개월 미만이면 "감소" 조건 제외
    appoint = agents.set_index("agent_id")["appoint_date"]
    is_new = appoint > (month_end - pd.DateOffset(months=3))

    s["cond_drop"] = (s["prev3"] >= 1) & (s["recent3"] <= s["prev3"] * 0.7) & ~is_new
    s["cond_retention"] = s["유지율"] < 80
    s["cond_no_sales"] = s["recent2"] == 0
    s["cond_concentration"] = s["편중도"] >= 70
    s["cond_early_cancel"] = s["조기해지율"] >= 10

    s["점수"] = sum(s[col] * pts for col, pts, _ in RISK_RULES)
    s["등급"] = s["점수"].map(risk_grade)
    s["해당 사유"] = [
        ", ".join(reason for col, _, reason in RISK_RULES if row[col])
        for _, row in s.iterrows()
    ]

    info = agents.set_index("agent_id")[["agent_name", "branch_name"]]
    s = info.join(s).rename(columns={"agent_name": "설계사", "branch_name": "지점"})
    s["직전3M→최근3M"] = s["prev3"].astype(str) + " → " + s["recent3"].astype(str) + "건"
    s = s.reset_index().sort_values(["점수", "agent_id"], ascending=[False, True])
    return s.reset_index(drop=True)


def agent_monthly_counts(data, agent_id: str, ym: str, months: int = 12) -> pd.DataFrame:
    """설계사의 최근 N개월 월별 판매 건수."""
    ms = month_range(ym, months)
    c = data["contracts"]
    cnt = c[c["agent_id"] == agent_id].groupby("year_month").size().reindex(ms, fill_value=0)
    return pd.DataFrame({"연월": ms, "건수": cnt.values})


def agent_group_mix(data, agent_id: str, ym: str) -> pd.DataFrame:
    """설계사 본인 상품군 비중 vs 전사 평균 비중 (기준 월까지 전체 기간)."""
    c = data["contracts"]
    c = c[c["contract_date"] <= pd.Period(ym, "M").end_time]
    share = lambda df: (df["product_group"].value_counts(normalize=True) * 100).reindex(
        PRODUCT_GROUPS, fill_value=0.0)
    return pd.DataFrame({
        "상품군": PRODUCT_GROUPS,
        "본인": share(c[c["agent_id"] == agent_id]).values,
        "전사 평균": share(c).values,
    })


# ---------------------------------------------------------------- 예측 (rules.md 5장)
FORECAST_GAP_RATE = 80.0
SEASONAL_BASE_YEAR = "2025"


def seasonal_index(data, target_ym: str):
    """계절지수 = 전년 같은 달 전사 건수 ÷ 2025년 1~12월 전사 월평균 건수.

    전년 같은 달 데이터가 없으면 None.
    """
    monthly = data["contracts"].groupby("year_month").size()
    base = monthly[monthly.index.str.startswith(SEASONAL_BASE_YEAR)].mean()
    year_ago = (pd.Period(target_ym, "M") - 12).strftime("%Y-%m")
    if year_ago not in monthly.index:
        return None
    return monthly[year_ago] / base


def next_quarter_forecast(data, ym: str = "2026-09", branch_ids=None):
    """기준 월 다음 3개월의 지점별 예측 건수와 목표 대비 판정.

    반환: (지점별 표, 계절지수 표). 계절지수를 구할 수 없으면 (None, 계절지수 표).
    """
    future = [(pd.Period(ym, "M") + i).strftime("%Y-%m") for i in (1, 2, 3)]
    seasonal = pd.DataFrame({"월": future, "계절지수": [seasonal_index(data, f) for f in future]})
    if seasonal["계절지수"].isna().any():
        return None, seasonal

    recent3 = month_range(ym, 3)
    c = data["contracts"]
    recent_avg = c[c["year_month"].isin(recent3)].groupby("branch_id").size() / 3
    t = data["targets"]
    target_avg = t[t["year_month"].isin(recent3)].groupby("branch_id")["target_count"].mean()

    b = data["branches"]
    if branch_ids is not None:
        b = b[b["branch_id"].isin(branch_ids)]
    df = b.set_index("branch_id")[["branch_name"]].rename(columns={"branch_name": "지점"})
    df["최근 3개월 평균"] = recent_avg.reindex(df.index, fill_value=0)
    for f, idx in zip(seasonal["월"], seasonal["계절지수"]):
        df[f"{f} 예측"] = df["최근 3개월 평균"] * idx
    df["예측"] = df[[f"{f} 예측" for f in future]].sum(axis=1)
    df["목표(가정)"] = target_avg.reindex(df.index) * 3
    df["예측 달성률"] = [safe_rate(p, t) for p, t in zip(df["예측"], df["목표(가정)"])]
    df["판정"] = ["⚠ 괴리 예상" if r is not None and r < FORECAST_GAP_RATE else "정상"
                for r in df["예측 달성률"]]
    return df.reset_index(drop=True), seasonal
