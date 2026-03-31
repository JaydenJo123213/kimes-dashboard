"""
csv-parser skill
CSV 로드 → 스키마 검증 → 홀 필터링 → hall_code / scan_date 파싱
Returns: (hall_df, meta) or raises SystemExit on escalation
"""

import re
import sys
import pandas as pd

HALL_PATTERN = re.compile(r'^([A-Z가-힣]+홀)(\d{4})$')
REQUIRED_COLUMNS = ['스캔기업명', 'QR코드번호', '방문시간', '직업분류']


def load_csv(path: str) -> pd.DataFrame:
    for enc in ('utf-8-sig', 'utf-8', 'euc-kr', 'cp949'):
        try:
            df = pd.read_csv(path, encoding=enc)
            return df
        except (UnicodeDecodeError, Exception):
            continue
    print(f"[ERROR] CSV 파일을 읽을 수 없습니다: {path}", file=sys.stderr)
    sys.exit(1)


def validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[ERROR] 필수 컬럼 없음: {missing}", file=sys.stderr)
        sys.exit(1)
    if len(df) == 0:
        print("[ERROR] CSV 데이터가 비어 있습니다.", file=sys.stderr)
        sys.exit(1)


def filter_and_parse(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    total_rows = len(df)

    mask = df['스캔기업명'].astype(str).str.match(HALL_PATTERN, na=False)
    hall_df = df[mask].copy()
    excluded_rows = total_rows - len(hall_df)

    excluded_names = (
        df[~mask & df['스캔기업명'].notna()]['스캔기업명']
        .value_counts()
        .head(10)
        .to_dict()
    )

    if len(hall_df) == 0:
        print("[WARN] 홀 스캔 데이터가 없습니다. 집계를 건너뜁니다.", file=sys.stderr)

    # hall_code / scan_date 파싱
    def parse_hall(name):
        m = HALL_PATTERN.match(str(name))
        if m:
            return m.group(1), m.group(2)
        return None, None

    hall_df[['hall_code', 'scan_date_raw']] = hall_df['스캔기업명'].apply(
        lambda x: pd.Series(parse_hall(x))
    )

    # scan_date: MMDD → 2026-MM-DD
    def to_date(mmdd):
        if mmdd and len(str(mmdd)) == 4:
            return f"2026-{str(mmdd)[:2]}-{str(mmdd)[2:]}"
        return None

    hall_df['scan_date'] = hall_df['scan_date_raw'].apply(to_date)

    # 파싱 실패 행 스킵
    failed = hall_df['hall_code'].isna().sum()
    if failed > 0:
        print(f"[WARN] hall_code 파싱 실패 행 {failed}건 스킵", file=sys.stderr)
        hall_df = hall_df[hall_df['hall_code'].notna()]

    meta = {
        'total_rows': total_rows,
        'hall_scan_rows': len(hall_df),
        'excluded_rows': excluded_rows,
        'excluded_names_sample': excluded_names,
    }

    return hall_df, meta
