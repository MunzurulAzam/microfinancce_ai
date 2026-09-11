"""Explicit read-only warehouse smoke check, with a downloadable report artifact."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv


def main():
    load_dotenv()
    from reports.service import create_report
    from reports.pdf import render_pdf
    parser = argparse.ArgumentParser()
    parser.add_argument('--period', default='2026-08')
    args = parser.parse_args()
    report = create_report(args.period, with_summary=False)['report']
    folder = Path('output/pdf'); folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'Group Performance Report - {report["period_label"]}.pdf'
    path.write_bytes(render_pdf(report))
    print(json.dumps({'report_id':report['report_id'], 'metrics':report['metrics'],
                      'countries':[{k:c[k] for k in ('country','branches','borrowers','par_percent','par_reconciled')} for c in report['countries']],
                      'warnings':report['availability']['warnings'], 'pdf':str(path.resolve())}, indent=2))


if __name__ == '__main__':
    main()
