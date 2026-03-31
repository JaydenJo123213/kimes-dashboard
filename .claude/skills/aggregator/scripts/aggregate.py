"""
aggregator skill
파싱된 DataFrame → 3종 집계 → dashboard_data.json 저장
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

OUTPUT_PATH = Path(__file__).parents[4] / 'output' / 'dashboard_data.json'


EVENT_DATES = ('2026-03-19', '2026-03-20', '2026-03-21', '2026-03-22')


def aggregate(hall_df: pd.DataFrame, full_df: pd.DataFrame = None) -> dict:
    # ── 3/19~3/22 필터 + 참가업체 제외
    hall_df = hall_df[hall_df['scan_date'].isin(EVENT_DATES)].copy()
    hall_df = hall_df[hall_df['직업분류'].astype(str).str.strip() != '참가업체']

    total_scans = len(hall_df)
    unique_visitors = hall_df['QR코드번호'].nunique()

    doctor_mask = hall_df['직업분류'].astype(str).str.strip() == '의사'
    doctor_count = hall_df[doctor_mask]['QR코드번호'].nunique()
    doctor_ratio = round(doctor_count / unique_visitors * 100, 1) if unique_visitors else 0.0

    hall_df['hour'] = pd.to_datetime(hall_df['방문시간'], errors='coerce').dt.hour
    dates = sorted(hall_df['scan_date'].dropna().unique().tolist())

    # 홀별 × 날짜별 스캔 수 (grouped bar)
    hall_labels = sorted(hall_df['hall_code'].dropna().unique().tolist())
    hall_by_date = {}
    for d in dates:
        day_df = hall_df[hall_df['scan_date'] == d]
        counts = day_df.groupby('hall_code').size()
        hall_by_date[d] = [int(counts.get(h, 0)) for h in hall_labels]

    # 시간대별 × 날짜별 스캔 수 (multi-line)
    valid_hourly = hall_df.dropna(subset=['hour'])
    all_hours = sorted(valid_hourly['hour'].astype(int).unique().tolist())
    hourly_by_date = {}
    for d in dates:
        day_df = valid_hourly[valid_hourly['scan_date'] == d]
        counts = day_df.groupby(day_df['hour'].astype(int)).size()
        hourly_by_date[d] = [int(counts.get(h, 0)) for h in all_hours]

    # 등록 유형 분류 (QR코드번호 앞 2자리 기준)
    def reg_type(qr):
        p = str(qr)[:2]
        if p in ('96', '86'):
            return '사전등록'
        if p == '76':
            return '현장등록'
        return '기타'

    REG_TYPES = ['사전등록', '현장등록', '기타']

    def reg_counts_unique(df):
        """QR코드번호 중복 제거 후 등록유형별 순방문객 수"""
        deduped = df.drop_duplicates(subset='QR코드번호').copy()
        deduped['reg_type'] = deduped['QR코드번호'].apply(reg_type)
        c = deduped['reg_type'].value_counts()
        return {t: int(c.get(t, 0)) for t in REG_TYPES}

    # 날짜별 등록유형: 전체 스캔 기준, 방문시간에서 날짜 추출, 3/19~3/22만, QR 중복 제거
    if full_df is not None:
        fdf = full_df.copy()
        fdf['visit_date'] = pd.to_datetime(fdf['방문시간'], errors='coerce').dt.strftime('%Y-%m-%d')
        fdf = fdf[fdf['visit_date'].isin(EVENT_DATES)]
        fdf = fdf[fdf['직업분류'].astype(str).str.strip() != '참가업체']
        event_dates_full = sorted(fdf['visit_date'].dropna().unique().tolist())
        date_reg = {d: reg_counts_unique(fdf[fdf['visit_date'] == d]) for d in event_dates_full}
        date_reg_dates = event_dates_full
    else:
        date_reg = {d: reg_counts_unique(hall_df[hall_df['scan_date'] == d]) for d in dates}
        date_reg_dates = dates

    # 직업분류별 × 날짜별 순방문객 수 (중복 제거, 전체)
    hall_df['직업분류_clean'] = hall_df['직업분류'].fillna('미분류')
    top_jobs = hall_df['직업분류_clean'].value_counts().index.tolist()  # 전체
    job_by_date = {}
    for j in top_jobs:
        job_by_date[j] = {}
        for d in dates:
            subset = hall_df[(hall_df['scan_date'] == d) & (hall_df['직업분류_clean'] == j)]
            cnt = int(subset['QR코드번호'].nunique())
            job_by_date[j][d] = cnt
    job_totals = {j: int(hall_df[hall_df['직업분류_clean'] == j]['QR코드번호'].nunique()) for j in top_jobs}
    job_chart = {
        'labels': top_jobs,
        'dates': dates,
        'by_date': job_by_date,
        'totals': job_totals,
    }

    # 홀별 등록유형: hall_df 기준, QR 중복 제거
    hall_df['reg_type'] = hall_df['QR코드번호'].apply(reg_type)
    hall_reg = {h: reg_counts_unique(hall_df[hall_df['hall_code'] == h]) for h in hall_labels}

    # 홀별 × 날짜별 등록유형 (서브행용)
    hall_date_reg = {}
    for h in hall_labels:
        hall_date_reg[h] = {}
        for d in dates:
            subset = hall_df[(hall_df['hall_code'] == h) & (hall_df['scan_date'] == d)]
            hall_date_reg[h][d] = reg_counts_unique(subset)

    # 전체 합계: 출입구 스캔 기준 전체 기간 중복 제거 (순방문객 카드와 동일 기준)
    total_reg = reg_counts_unique(hall_df)

    # ── 해외 바이어: 국적이 대한민국 아니고 빈값/null 제외
    overseas_section = None
    if '국적' in hall_df.columns:
        nat_col = hall_df['국적'].astype(str).str.strip()
        overseas_mask = nat_col.notna() & (nat_col != '') & (nat_col != 'nan') & (nat_col != '대한민국')
        ov_df = hall_df[overseas_mask].copy()
        ov_unique = int(ov_df['QR코드번호'].nunique())
        ov_by_date = {d: int(ov_df[ov_df['scan_date'] == d]['QR코드번호'].nunique()) for d in dates}
        ov_by_hall = {h: int(ov_df[ov_df['hall_code'] == h]['QR코드번호'].nunique()) for h in hall_labels}
        ov_deduped = ov_df.drop_duplicates(subset='QR코드번호').copy()
        nat_counts = (
            ov_deduped['국적'].astype(str).str.strip()
            .value_counts()
            .to_dict()
        )
        ov_deduped['직업분류_clean'] = ov_deduped['직업분류'].fillna('미분류')
        ov_jobs = ov_deduped['직업분류_clean'].value_counts().to_dict()
        overseas_section = {
            'unique_visitors': ov_unique,
            'by_date': {d: int(v) for d, v in ov_by_date.items()},
            'by_hall': {h: int(v) for h, v in ov_by_hall.items()},
            'nationality_counts': {k: int(v) for k, v in nat_counts.items()},
            'job_counts': {k: int(v) for k, v in ov_jobs.items()},
            'dates': dates,
            'halls': hall_labels,
        }

    data = {
        'generated_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'summary_cards': {
            'total_scans': int(total_scans),
            'unique_visitors': int(unique_visitors),
            'doctor_count': int(doctor_count),
            'doctor_ratio': float(doctor_ratio),
        },
        'hall_chart': {
            'labels': hall_labels,
            'dates': dates,
            'by_date': hall_by_date,
        },
        'hourly_chart': {
            'labels': [f'{h}시' for h in all_hours],
            'dates': dates,
            'by_date': hourly_by_date,
        },
        'job_chart': job_chart,
        'reg_table': {
            'reg_types': REG_TYPES,
            'total': total_reg,
            'by_date': date_reg,
            'by_hall': hall_reg,
            'by_hall_date': hall_date_reg,
            'dates': date_reg_dates,
            'hall_dates': dates,
            'halls': hall_labels,
        },
        'overseas_buyers': overseas_section,
    }

    if not data['summary_cards']['total_scans']:
        print("[ERROR] 집계 결과가 비어 있습니다.", file=sys.stderr)
        sys.exit(1)

    return data


def save_json(data: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # 유효성 검증
    json.loads(OUTPUT_PATH.read_text(encoding='utf-8'))
    print(f"[OK] dashboard_data.json 저장: {OUTPUT_PATH}")
