# 영업 성과 분석 대시보드 (PoC · 더미데이터)

## 실행 방법
1. Python 3.10 이상을 준비한다.
2. 이 폴더에서 패키지를 설치한다.
   ```
   pip install -r requirements.txt
   ```
3. 앱을 실행한다.
   ```
   streamlit run app.py
   ```
4. 브라우저가 자동으로 열리지 않으면 http://localhost:8501 에 접속한다.

## 데이터 올리기
- 사이드바 맨 위 **데이터 올리기**에서 CSV나 엑셀(.xlsx)을 올리면 그 데이터로 모든 탭을 다시 계산한다.
- CSV는 파일 이름이 `agents`, `branches`, `contracts`, `products`, `targets` 중 하나여야 한다. 엑셀은 같은 이름의 파일(첫 시트를 읽음)이거나, 시트 이름이 위 이름인 통합 문서 한 개면 된다.
- 올리지 않은 표는 `data/`의 기본 더미데이터를 쓴다. **엑셀 양식**(시트 5개)과 **CSV 양식**(5개 묶음)을 내려받아 열 구성을 맞춘다.
- 필수 열, 날짜·숫자 형식, 허용 값(재직/해촉, 유지/해지/실효, 종신/건강/연금/저축), ID 연결을 검사해 문제가 있으면 화면에 이유를 보여준다.
- UTF-8과 엑셀 기본 저장(CP949) CSV 모두 읽는다. 엑셀이 연월(2026-09)을 날짜로 바꿔 저장해도 연월로 되돌린다. 올린 파일은 저장되지 않는다.
- 웹 공유 페이지에는 올리기 기능이 없다. 새 데이터로 웹 페이지를 갱신하려면 `data/`를 바꾸고 `python web/build_web.py`를 다시 실행한다.

## 설계사 조회
- **설계사 조회** 탭에서 설계사 한 명을 고르면 당월 실적(전월 대비), 누적 유지율, 위험점수와 조건별 근거(docs/rules.md 2장), 12개월 판매 추이, 상품군 구성, 최근 계약 10건을 본다.
- 설계사별 목표는 데이터에 없어서 표시하지 않는다 (목표는 지점 단위).

## 보고서 파일 내보내기
- **월간 보고서** 탭에서 보고서를 만든 뒤 PDF, 워드(.docx), 마크다운(.md)으로 내려받는다.
- PDF는 `fonts/`의 나눔고딕(SIL OFL 1.1)을 넣어 만들기 때문에 어느 컴퓨터에서 열어도 한글이 깨지지 않는다.
- 화면 없이 만들려면: `python make_report.py 2026-09 --out reports` (월을 빼면 지난달, 없으면 데이터의 마지막 월)

## 인터넷 주소로 공유 (Streamlit Community Cloud)
이 저장소는 그대로 배포할 수 있게 준비되어 있다 (`requirements.txt`, `.streamlit/config.toml`, 상대 경로).
1. https://share.streamlit.io 에 GitHub 계정으로 로그인한다.
2. **Create app → Deploy a public app from GitHub**를 고른다.
3. Repository `hyelimg643-lang/sales-dashboard`, Branch `main`, Main file path `app.py`를 넣는다.
4. 원하는 주소(App URL)를 정하고 **Deploy**를 누른다. 몇 분 뒤 `https://<정한 이름>.streamlit.app` 으로 열린다.
- 비공개 저장소에서 배포한 앱은 기본으로 초대한 사람만 볼 수 있다. 앱 화면 오른쪽 위 **Share**에서 볼 사람 이메일을 추가한다.
- `main`에 새로 올리면 앱이 자동으로 갱신된다.

## 구성
- `app.py`: 화면 (사이드바 필터, 탭 4개)
- `metrics.py`: 지표 계산 로직 (docs/rules.md 기준)
- `report.py`: 월간 보고서 마크다운 생성 (docs/report_template.md 구성)
- `export.py`: 보고서 PDF·워드 변환, `make_report.py`: 보고서 파일 일괄 생성
- `fonts/`: PDF용 나눔고딕 (SIL OFL 1.1)
- `data/`: 더미데이터 CSV 5개
- `docs/`: 규칙·화면 구성·보고서 양식

## 진행 상황
- ① 성과 대시보드: 완료 (2026-09 검증 포인트 일치)
- ② 위험 설계사: 완료 (고위험 5명·관찰 6명, rules.md 기대 결과 일치)
- ③ 실적 예측: 완료 (가상1지점 77.5% 괴리 예상, 보고서 예시 일치)
- ④ 월간 보고서: 완료 (2026-09 보고서가 report_template.md 2부와 일치)

## 웹 공유 페이지
- 앱과 같은 탭 5개(설계사 조회 포함)를 담는다. 보고서 PDF·워드·마크다운과 위험 설계사 CSV는 claude.ai 아티팩트의 파일 저장 기능으로 내려받는다 (저장 기능이 없는 화면에서는 복사 버튼).
- 데이터 올리기는 앱 전용이다 (웹 페이지는 미리 계산한 결과를 담기 때문).
- `python web/build_web.py`를 실행하면 `web/dashboard.html`이 만들어진다 (앱과 같은 계산 결과를 담은 설치 없는 단일 HTML).
- 데이터나 계산을 바꾼 뒤에는 다시 실행해서 페이지를 갱신한다 (`pip install markdown` 필요).
