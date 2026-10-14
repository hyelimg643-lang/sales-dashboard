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

## 구성
- `app.py`: 화면 (사이드바 필터, 탭 4개)
- `metrics.py`: 지표 계산 로직 (docs/rules.md 기준)
- `report.py`: 월간 보고서 마크다운 생성 (docs/report_template.md 구성)
- `data/`: 더미데이터 CSV 5개
- `docs/`: 규칙·화면 구성·보고서 양식

## 진행 상황
- ① 성과 대시보드: 완료 (2026-09 검증 포인트 일치)
- ② 위험 설계사: 완료 (고위험 5명·관찰 6명, rules.md 기대 결과 일치)
- ③ 실적 예측: 완료 (가상1지점 77.5% 괴리 예상, 보고서 예시 일치)
- ④ 월간 보고서: 완료 (2026-09 보고서가 report_template.md 2부와 일치)

## 웹 공유 페이지
- `python web/build_web.py`를 실행하면 `web/dashboard.html`이 만들어진다 (앱과 같은 계산 결과를 담은 설치 없는 단일 HTML).
- 데이터나 계산을 바꾼 뒤에는 다시 실행해서 페이지를 갱신한다 (`pip install markdown` 필요).
