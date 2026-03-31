"""
run.py — KIMES 방문 데이터 대시보드 실행 진입점

사용법:
  python run.py --input [CSV 파일 경로]
  python run.py --input [CSV 파일 경로] --no-server
  python run.py --input [CSV 파일 경로] --port 8080
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 스킬 경로 등록
SKILL_BASE = Path(__file__).parent / '.claude' / 'skills'
for skill_dir in ['csv-parser', 'aggregator', 'html-builder']:
    sys.path.insert(0, str(SKILL_BASE / skill_dir / 'scripts'))

from parse_csv import load_csv, validate_schema, filter_and_parse
from aggregate import aggregate, save_json
from build_html import build

LOG_PATH = Path(__file__).parent / 'run_log.jsonl'


def write_log(entry: dict) -> None:
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description='KIMES 방문 데이터 대시보드 생성기')
    parser.add_argument('--input', required=True, help='입력 CSV 파일 경로')
    parser.add_argument('--no-server', action='store_true', help='HTTP 서버 실행 안 함')
    parser.add_argument('--port', type=int, default=8000, help='HTTP 서버 포트 (기본: 8000)')
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    run_at = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    print(f"\n{'='*52}")
    print(f"  KIMES 방문 데이터 대시보드 생성기")
    print(f"  입력: {input_path.name}")
    print(f"{'='*52}\n")

    # ── 1단계: CSV 로드 & 검증
    print("[1/6] CSV 로드 및 유효성 검사...")
    df = load_csv(str(input_path))
    validate_schema(df)
    print(f"      총 {len(df):,}행 로드 완료")

    # ── 2~3단계: 홀 필터링 & 파싱
    print("[2/6] 홀 데이터 필터링 및 파싱...")
    hall_df, meta = filter_and_parse(df)
    print(f"      홀 스캔: {meta['hall_scan_rows']:,}행 / 제외: {meta['excluded_rows']:,}행")

    # ── 4~5단계: 집계 & JSON 저장
    # (원본 df도 함께 전달 → 날짜별 등록유형은 전체 스캔 기준)
    print("[3/6] 집계 계산...")
    data = aggregate(hall_df, df)
    s = data['summary_cards']
    print(f"      전체 스캔: {s['total_scans']:,} | 순 방문객: {s['unique_visitors']:,} | 의사: {s['doctor_count']:,} ({s['doctor_ratio']}%)")

    print("[4/6] dashboard_data.json 저장...")
    save_json(data)

    # ── 6단계: HTML 생성
    print("[5/6] HTML 대시보드 생성...")
    build()

    # ── 로그 기록
    log_entry = {
        'run_at': run_at,
        'status': 'success',
        'input_file': input_path.name,
        'input_rows': meta['total_rows'],
        'hall_scan_rows': meta['hall_scan_rows'],
        'excluded_rows': meta['excluded_rows'],
        'unique_visitors': s['unique_visitors'],
        'doctor_count': s['doctor_count'],
        'doctor_ratio': s['doctor_ratio'],
    }
    write_log(log_entry)

    print("\n[완료] 대시보드 생성 성공!")
    print(f"  전체 스캔:  {s['total_scans']:,}")
    print(f"  순 방문객:  {s['unique_visitors']:,}")
    print(f"  의사 수:    {s['doctor_count']:,} ({s['doctor_ratio']}%)")

    # ── 7단계: HTTP 서버
    if not args.no_server:
        print(f"\n[6/6] HTTP 서버 시작 → http://localhost:{args.port}/dashboard/")
        from serve import serve
        serve(port=args.port, open_browser=True)
    else:
        print("\n[6/6] --no-server 옵션: 서버 실행 건너뜀")
        print(f"      나중에 실행: python serve.py")


if __name__ == '__main__':
    main()
