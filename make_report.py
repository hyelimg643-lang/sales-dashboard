"""월간 보고서 파일(.md, .pdf, .docx)을 만든다. 매월 자동 보고에서 쓴다.

실행: python make_report.py [YYYY-MM] [--out 폴더]
월을 빼면 지난달 보고서를 만들고, 데이터에 지난달이 없으면 데이터의 마지막 월로 만든다.
"""
import argparse
from datetime import date
from pathlib import Path

import export as ex
import metrics as m
import report as rp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("month", nargs="?", help="보고 월 (예: 2026-09)")
    ap.add_argument("--out", default="reports", help="저장 폴더 (기본: reports)")
    args = ap.parse_args()

    data = m.load_data()
    months = m.month_list(data["contracts"])
    wanted = args.month or m.prev_month(date.today().strftime("%Y-%m"))
    ym = wanted if wanted in months else months[-1]
    if ym != wanted:
        print(f"안내: 데이터에 {wanted}이(가) 없어 마지막 월 {ym}로 작성합니다.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md = rp.build_report(data, ym)
    base = out / f"영업성과보고서_{ym}"
    base.with_suffix(".md").write_text(md, encoding="utf-8")
    base.with_suffix(".pdf").write_bytes(ex.report_pdf(md))
    base.with_suffix(".docx").write_bytes(ex.report_docx(md))
    print(f"보고 월 {ym}")
    for ext in (".md", ".pdf", ".docx"):
        print(base.with_suffix(ext))


if __name__ == "__main__":
    main()
