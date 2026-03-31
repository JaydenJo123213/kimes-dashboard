# KIMES 방문 데이터 변환 에이전트 — 통합 설계서

> Claude Code 구현 시 참조할 계획서 (v2.0)  
> 변경: Google Sheets / Looker Studio 제거 → 로컬 Python 서버 + HTML 대시보드

---

## 1. 작업 컨텍스트

### 배경 및 목적

KIMES 전시회 입장 시 각 홀 입구의 QR 스캐너가 방문객 데이터를 수집한다. 수집된 원시 데이터는 CSV 파일로 로컬에 저장되며, 이를 파이썬 스크립트로 집계하여 브라우저에서 바로 볼 수 있는 HTML 대시보드로 시각화한다.

### 입력

- 로컬에 저장된 QR 스캐너 CSV 파일 (예: `QR스캐너_kimes_전체데이터.csv`)
- 주요 컬럼:

| 컬럼명 | 역할 |
|--------|------|
| 스캔기업명 | 홀 식별 (`A홀0319` 패턴) |
| QR코드번호 | 방문객 고유 식별자 |
| 방문시간 | ISO 8601 형식 (`2026-03-19T14:28:17`) |
| 직업분류 | 의사 판별 (`"의사"`) |
| 연령, 성별, 구분 | 참관객 속성 |

### 출력

| 산출물 | 형식 | 위치 |
|--------|------|------|
| 집계 데이터 | JSON | `/output/dashboard_data.json` |
| HTML 대시보드 | HTML (단일 파일) | `/dashboard/index.html` |
| 실행 로그 | JSONL | `run_log.jsonl` |

### 주요 제약조건

- **로컬 실행**: Mac 환경, Python HTTP 서버로 브라우저에서 열기
- **외부 서비스 없음**: Google Sheets, Looker Studio 연결 없음
- **홀 식별 규칙**: `스캔기업명`이 `[홀명][날짜4자리]` 패턴(예: `A홀0319`)인 경우만 홀 데이터로 인식. 일반 기업명은 집계에서 제외
- **의사 판별**: `직업분류 == "의사"`
- **실행 트리거**: 수동 실행 (`python run.py --input [파일경로]`)

### 용어 정의

| 용어 | 정의 |
|------|------|
| 스캔 1건 | QR 스캐너가 방문객 배지를 읽은 1회 이벤트 |
| 홀 스캔 | `스캔기업명`이 `[홀명][날짜]` 패턴인 스캔 |
| 순 방문객 | 동일 `QR코드번호`의 중복을 제거한 고유 방문객 |
| 의사 방문객 | `직업분류 == "의사"`인 방문객 |

---

## 2. 워크플로우 정의

### 전체 흐름

```
[시작] python run.py --input [CSV 파일 경로]
  │
  ▼
[1단계] CSV 로드 및 유효성 검사
  │   성공 기준: 필수 컬럼 존재, 1행 이상
  │   실패: 에스컬레이션 (실행 중단, 오류 메시지 출력)
  │
  ▼
[2단계] 홀 데이터 필터링
  │   스캔기업명 정규식 패턴 매칭 → 홀 스캔만 추출
  │   성공 기준: 홀 스캔 1건 이상
  │   실패: 스킵 + 로그 (경고 출력 후 계속)
  │
  ▼
[3단계] hall_code / scan_date 파싱
  │   스캔기업명 → hall_code, scan_date 컬럼 추가
  │   성공 기준: 모든 홀 스캔 행에 추출 성공
  │   실패: 재시도 1회 → 실패 행 스킵 + 로그
  │
  ▼
[4단계] 집계 계산
  │   ├─ summary_cards: 전체 스캔 수, 순방문객 수, 의사 수/비율
  │   ├─ hall_chart: 홀별 스캔 수 (막대 차트용)
  │   └─ hourly_chart: 시간대별 스캔 수 (라인 차트용)
  │   성공 기준: 3종 집계 객체 생성, 값 존재
  │   실패: 에스컬레이션
  │
  ▼
[5단계] dashboard_data.json 저장
  │   /output/dashboard_data.json 덮어쓰기
  │   성공 기준: 파일 생성, JSON 유효
  │   실패: 에스컬레이션
  │
  ▼
[6단계] HTML 대시보드 생성
  │   /dashboard/index.html 덮어쓰기
  │   dashboard_data.json을 fetch로 읽는 정적 HTML
  │   성공 기준: 파일 생성
  │   실패: 에스컬레이션
  │
  ▼
[7단계] 로컬 HTTP 서버 실행
  │   python -m http.server (또는 별도 serve.py)
  │   브라우저 자동 오픈: http://localhost:8000/dashboard/
  │
  ▼
[8단계] 실행 로그 기록
  │   run_log.jsonl에 결과 append
  │
  ▼
[완료] 브라우저에서 대시보드 확인
```

### LLM 판단 vs 코드 처리

| 처리 내용 | 담당 주체 | 이유 |
|-----------|-----------|------|
| CSV 파싱, 집계 계산 | 코드 (pandas) | 반복 처리, 정량 계산 |
| 홀 패턴 규칙 적용 | 코드 (정규식) | 결정론적 규칙 |
| JSON 직렬화 | 코드 | 정형 변환 |
| HTML/JS 차트 렌더링 | 코드 (Chart.js) | 정적 렌더링 |
| 실행 결과 요약 출력 | 에이전트 (LLM) | 자연어 요약 |
| 예외 상황 판단 | 에이전트 (LLM) | 패턴 미매칭 처리 방식 결정 |

### 분기 조건

```
스캔기업명 패턴 매칭 (정규식: ^[A-Z가-힣]+홀\d{4}$)
  ├─ 매칭 (예: A홀0319)    → 홀 스캔으로 집계
  ├─ 미매칭 (예: 한국이앤엑스) → 집계 제외, 카운트만 로그 기록
  └─ 빈 값 / null           → 스킵 + 로그

직업분류 값
  ├─ "의사"                 → 의사 통계 포함
  └─ 기타 / 빈 값           → 의사 통계 제외
```

### 성공 기준 및 실패 처리 요약

| 단계 | 성공 기준 | 검증 방법 | 실패 처리 |
|------|-----------|-----------|-----------|
| CSV 로드 | 필수 컬럼 존재, 1행 이상 | 스키마 검증 | 에스컬레이션 (실행 중단) |
| 홀 필터링 | 홀 스캔 1건 이상 | 규칙 기반 | 스킵 + 로그 |
| 파싱 | hall_code, scan_date 추출 성공 | 규칙 기반 | 재시도 1회 → 실패 행 스킵 |
| 집계 | 3종 집계 객체 생성, 값 존재 | 규칙 기반 | 에스컬레이션 |
| JSON 저장 | 파일 생성, JSON 유효 | 파일 존재 + json.loads | 에스컬레이션 |
| HTML 생성 | 파일 생성 | 파일 존재 | 에스컬레이션 |

---

## 3. 구현 스펙

### 폴더 구조

```
~/Desktop/claude_agent/kimes-visit-data/
  ├── CLAUDE.md                          # 메인 에이전트 지침
  ├── run.py                             # 실행 진입점: 파싱 → 집계 → 출력 → 서버 실행
  ├── serve.py                           # HTTP 서버 + 브라우저 자동 오픈
  ├── run_log.jsonl                      # 실행 이력 로그
  ├── /output
  │   └── dashboard_data.json            # 집계 결과 JSON (HTML이 fetch로 읽음)
  ├── /dashboard
  │   └── index.html                     # HTML 대시보드 (단일 파일, Chart.js 사용)
  └── /.claude
      └── /skills
          ├── /csv-parser
          │   ├── SKILL.md
          │   └── /scripts
          │       └── parse_csv.py       # CSV 로드, 스키마 검증, 홀 필터링, 파싱
          ├── /aggregator
          │   ├── SKILL.md
          │   └── /scripts
          │       └── aggregate.py       # 3종 집계 계산 → dashboard_data.json 저장
          └── /html-builder
              ├── SKILL.md
              └── /scripts
                  └── build_html.py      # index.html 생성 (템플릿 기반)
```

### CLAUDE.md 핵심 섹션 목록

- 작업 개요 및 목적
- 실행 명령 및 인수 설명 (`--input`, `--no-server` 옵션)
- 스킬 호출 순서
- 실패 시 에스컬레이션 기준
- 실행 결과 요약 출력 형식

### 에이전트 구조

**단일 에이전트** — 워크플로우가 순차적이며 컨텍스트 윈도우 초과 우려 없음

### 스킬 파일 목록

| 스킬명 | 역할 | 트리거 조건 |
|--------|------|-------------|
| `csv-parser` | CSV 로드 → 스키마 검증 → 홀 필터링 → hall_code/scan_date 파싱 | 실행 시작 시 첫 번째로 호출 |
| `aggregator` | 파싱된 DataFrame → 3종 집계 → `dashboard_data.json` 저장 | csv-parser 성공 후 호출 |
| `html-builder` | `index.html` 생성 (Chart.js 기반 대시보드 단일 파일) | aggregator 성공 후 호출 |

### 스킬별 주요 처리 로직

#### csv-parser
- 인코딩 자동 감지 (UTF-8 / EUC-KR 대응)
- 필수 컬럼 존재 여부 스키마 검증
- `스캔기업명` 정규식 `^[A-Z가-힣]+홀\d{4}$` 로 홀 스캔 추출
- `hall_code` = 홀명 부분 (예: `A홀`, `B홀`, `GB홀`)
- `scan_date` = 날짜 4자리 → `2026-MM-DD` 변환
- 미매칭 행 수, 제외된 기업명 목록 로그 기록

#### aggregator
- **summary_cards**: 전체 스캔 수, 순방문객 수(QR 중복제거), 의사 수, 의사 비율(%)
- **hall_chart**: `hall_code` 기준 스캔 수 집계 → `{labels: [...], values: [...]}` 형태
- **hourly_chart**: `방문시간`에서 hour 추출 → 시간대별 스캔 수 → `{labels: [...], values: [...]}` 형태
- 결과를 `dashboard_data.json` 단일 파일로 저장

#### html-builder
- `index.html` 단일 파일 생성 (외부 CDN: Chart.js)
- 시작 시 `fetch('../output/dashboard_data.json')` 으로 데이터 로드
- 로컬 서버 없이도 더블클릭으로 열리도록 fallback 처리 포함
- 브라우저 새로고침 시 최신 JSON 반영

### 주요 산출물 파일 형식

#### dashboard_data.json

```json
{
  "generated_at": "2026-03-20T15:30:00",
  "summary_cards": {
    "total_scans": 58400,
    "unique_visitors": 24100,
    "doctor_count": 4820,
    "doctor_ratio": 20.0
  },
  "hall_chart": {
    "labels": ["A홀", "B홀", "C홀", "D홀", "E홀", "GB홀"],
    "values": [12300, 9800, 11200, 8700, 10400, 6000]
  },
  "hourly_chart": {
    "labels": ["9시", "10시", "11시", "12시", "13시", "14시", "15시", "16시", "17시"],
    "values": [1200, 4500, 6800, 5200, 7100, 8400, 9200, 7800, 3200]
  }
}
```

#### run_log.jsonl

```json
{"run_at": "2026-03-20T15:30:00", "status": "success", "input_file": "QR스캐너_kimes_전체데이터.csv", "input_rows": 71220, "hall_scan_rows": 58400, "excluded_rows": 12820, "unique_visitors": 24100, "doctor_count": 4820}
```

### HTML 대시보드 화면 구성

```
┌─────────────────────────────────────────────────────┐
│  KIMES 2026 방문객 현황          최종 업데이트: 15:30 │
├──────────────┬──────────────┬──────────────┬────────┤
│  전체 스캔   │  순 방문객   │   의사 수    │ 의사   │
│   58,400     │   24,100     │    4,820     │ 20.0%  │
├──────────────┴──────────────┴──────────────┴────────┤
│  [홀별 입장객 막대 차트 - Chart.js Bar]             │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [시간대별 입장 추이 라인 차트 - Chart.js Line]     │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 4. 환경 설정

| 항목 | 내용 |
|------|------|
| 실행 환경 | Mac, Python 3.x |
| 의존 라이브러리 | `pandas`, `openpyxl`, `python-dotenv` |
| 외부 CDN (HTML) | Chart.js (`https://cdn.jsdelivr.net/npm/chart.js`) |
| 실행 명령 | `python run.py --input [파일경로]` |
| 서버만 실행 | `python serve.py` (집계 재실행 없이 브라우저만 열기) |
| Sleep 방지 | `caffeinate` 적용 가능 |

---

*설계 완료 (v2.0) — Claude Code에서 이 문서를 참조하여 구현 시작*
