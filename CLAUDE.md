# KIMES 방문 데이터 대시보드 에이전트

## 작업 개요
KIMES 전시회 QR 스캐너 CSV 데이터를 집계하여 로컬 브라우저에서 볼 수 있는 HTML 대시보드를 생성한다.

## 실행 명령

```bash
# 기본 실행 (집계 + HTML 생성 + 서버 시작)
python run.py --input '/path/to/QR스캐너_kimes_전체데이터.csv'

# 서버 없이 파일만 생성
python run.py --input '/path/to/file.csv' --no-server

# 포트 변경
python run.py --input '/path/to/file.csv' --port 8080

# 서버만 재시작 (재집계 없음)
python serve.py
```

## 스킬 호출 순서

1. `csv-parser` → CSV 로드, 스키마 검증, 홀 필터링, hall_code/scan_date 파싱
2. `aggregator` → summary_cards, hall_chart, hourly_chart, date_chart 집계 → dashboard_data.json 저장
3. `html-builder` → dashboard/index.html 생성

## 실패 시 에스컬레이션 기준

| 단계 | 처리 |
|------|------|
| CSV 로드 실패 (파일 없음, 인코딩 불가) | 실행 중단 + 오류 메시지 |
| 필수 컬럼 없음 | 실행 중단 + 컬럼 목록 출력 |
| 홀 스캔 0건 | 경고 출력 후 계속 (빈 집계) |
| 집계 결과 비어 있음 | 실행 중단 |
| JSON/HTML 저장 실패 | 실행 중단 |

## 출력 형식 요약

```
[완료] 대시보드 생성 성공!
  전체 스캔:  73,082
  순 방문객:  24,100
  의사 수:    4,820 (20.0%)
```

## 홀 패턴 규칙
- 정규식: `^[A-Z가-힣]+홀\d{4}$`
- 예시: `A홀0319`, `GB홀0321`
- 미매칭(일반 기업명)은 집계 제외, 로그에만 기록

## 파일 구조
```
entrance chart/
  run.py              ← 진입점
  serve.py            ← 서버 단독 실행
  run_log.jsonl       ← 실행 이력
  output/
    dashboard_data.json
  dashboard/
    index.html
  .claude/skills/
    csv-parser/scripts/parse_csv.py
    aggregator/scripts/aggregate.py
    html-builder/scripts/build_html.py
```
