"""영업 성과 분석 대시보드의 핵심 로직을 원본 그대로 txt 한 파일로 추출한다.

실행: python exports/extract_core_logic.py [프로젝트 폴더] [출력 파일]
- 파일 전체를 넣는 경우와, app.py처럼 화면 코드와 섞인 파일은 로직 함수만 줄 단위로 그대로 잘라 넣는다.
- 추출한 내용이 원본 바이트와 같은지 확인하고, 인증정보로 보이는 값이 있으면 가린다.
"""
import ast
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else ROOT / "exports" / "core_logic.txt")

WHOLE_FILES = [  # 파일 전체가 계산·데이터 처리 로직인 파일
    "metrics.py",        # 데이터 로드·검증, 지표, 위험점수, 예측
    "report.py",         # 월간 보고서 생성
    "export.py",         # 보고서 PDF·워드 변환
    "make_report.py",    # 보고서 파일 일괄 생성
    "web/build_web.py",  # 웹 페이지용 계산 결과 생성
]
APP_FUNCTIONS = ["fmt_won", "fmt_pct", "get_data", "template_zip", "template_xlsx", "report_files"]

SECRET = re.compile(r"""(?i)((?:api[_-]?key|secret|token|passw(?:or)?d|credential)\s*[=:]\s*)(["'])([^"']+)\2""")


def mask(text):
    hits = []

    def sub(mo):
        hits.append(mo.group(0)[:40])
        return f"{mo.group(1)}{mo.group(2)}***MASKED***{mo.group(2)}"
    return SECRET.sub(sub, text), hits


def app_segments(path):
    """app.py에서 로직 함수(데코레이터 포함)만 원본 줄 그대로 잘라낸다."""
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    segs = []
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in APP_FUNCTIONS:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            segs.append((node.name, start, node.end_lineno, "".join(lines[start - 1:node.end_lineno])))
    return segs


def main():
    parts, checks, masked = [], [], []
    for rel in WHOLE_FILES:
        raw = (ROOT / rel).read_bytes()
        text = raw.decode("utf-8")
        checks.append((rel, "전체", text == raw.decode("utf-8")))
        text, hits = mask(text)
        masked += [(rel, h) for h in hits]
        parts.append((f"{rel} (전체, {len(text.splitlines())}줄, sha256 {hashlib.sha256(raw).hexdigest()[:16]})", text))

    app = ROOT / "app.py"
    app_lines = app.read_text(encoding="utf-8").splitlines(keepends=True)
    for name, a, b, seg in app_segments(app):
        checks.append((f"app.py:{name}", f"{a}-{b}줄", seg == "".join(app_lines[a - 1:b])))
        seg, hits = mask(seg)
        masked += [(f"app.py:{name}", h) for h in hits]
        parts.append((f"app.py → {name} ({a}~{b}줄, 원본 그대로)", seg))

    bar = "=" * 100
    head = [
        "영업 성과 분석 대시보드 PoC — 핵심 로직 원본 추출",
        f"추출 시각: {datetime.now():%Y-%m-%d %H:%M}  /  추출 대상 폴더: {ROOT.name}",
        "규칙: 코드는 새로 쓰거나 고치거나 요약하지 않고 원본 그대로 옮김. 화면 디자인·스타일 코드(CSS, 테마, 화면 배치)와 설명 문서는 제외.",
        f"인증정보: {'가린 값 ' + str(len(masked)) + '개' if masked else '코드에 API 키·비밀번호 등 인증정보 없음 (가린 값 0개)'}",
        "",
        "포함 목록:",
        *[f"  {i + 1}. {title}" for i, (title, _) in enumerate(parts)],
        "",
    ]
    body = []
    for title, text in parts:
        body += [bar, f"### {title}", bar, text.rstrip("\n"), ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(head + body) + "\n", encoding="utf-8")

    ok = all(c[2] for c in checks)
    print(f"{OUT}  ({OUT.stat().st_size:,} bytes)")
    print("원본 일치 검사:", "모두 일치" if ok else [c for c in checks if not c[2]])
    print("가린 인증정보:", masked or "없음")


if __name__ == "__main__":
    main()
