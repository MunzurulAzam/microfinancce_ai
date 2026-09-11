from io import BytesIO
from flask import Blueprint, jsonify, request, send_file
from reports.service import create_report, load_report, ReportError, period_catalog, enrich_period_error

reports_bp = Blueprint('reports', __name__)


def error_response(error):
    return jsonify(error.payload()), error.status


@reports_bp.route('/reports/group-performance', methods=['POST'])
def group_performance():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response(ReportError('Request body must be a JSON object.'))
    if 'summary' in data and not isinstance(data['summary'], bool):
        return error_response(ReportError('summary must be a boolean.'))
    try:
        return jsonify(create_report(data.get('period'), data.get('country'), data.get('summary', True)))
    except ReportError as error:
        return error_response(enrich_period_error(error, data.get('country')))


@reports_bp.get('/reports/group-performance/periods')
def group_performance_periods():
    try:
        return jsonify(period_catalog(request.args.get('country')))
    except ReportError as error:
        return error_response(error)


@reports_bp.route('/reports/<report_id>/pdf', methods=['GET'])
def download_pdf(report_id):
    try:
        report = load_report(report_id)
    except ReportError as error:
        return error_response(error)
    from reports.pdf import render_pdf
    response = send_file(BytesIO(render_pdf(report)), mimetype='application/pdf', as_attachment=True,
                         download_name=f"Group Performance Report - {report['period_label']}.pdf")
    response.headers['Cache-Control'] = 'private, no-store'
    return response
