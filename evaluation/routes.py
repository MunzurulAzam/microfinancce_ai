from flask import Blueprint, request, jsonify
import os
import math
from werkzeug.utils import secure_filename
from evaluation.pdf_parser import parse_statement

evaluation_bp = Blueprint('evaluation', __name__)

UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def _sanitize(obj):
    """Recursively walk a dict/list and replace any float Infinity or NaN with 0.0 so that Flask's jsonify produces valid JSON."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return 0.0
    return obj


@evaluation_bp.route('/evaluate', methods=['POST'])
def evaluate_applicant():
    try:
        applicant_name      = request.form.get('applicantName', 'Unknown')
        business_type       = request.form.get('businessType', 'General')
        business_age        = float(request.form.get('businessAge', 0))
        self_declared_income= float(request.form.get('monthlyIncome', 0))
        rent_amount         = float(request.form.get('rentAmount', 0))

        if 'bankStatement' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['bankStatement']
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False,
                            'error': 'Invalid file format. Only PDF is accepted.'}), 400

        filename  = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        try:
            m = parse_statement(file_path)
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        total_credit        = m['total_credit']
        total_debit         = m['total_debit']
        avg_balance         = m['avg_balance']
        period_months       = m['period_months']
        period_start        = m['period_start']
        period_end          = m['period_end']
        monthly_avg_credit  = m['monthly_avg_credit']
        monthly_avg_debit   = m['monthly_avg_debit']
        currency            = m['currency']
        bank_name           = m.get('bank_name', 'Unknown Bank')
        is_mpesa            = m['is_mpesa']
        tx_summary          = m.get('transaction_summary', {})

        income_match = False
        margin = 0.20

        if monthly_avg_credit > 0:
            lower = (1 - margin) * monthly_avg_credit
            upper = (1 + margin) * monthly_avg_credit
            if lower <= self_declared_income <= upper:
                income_match = True
            elif self_declared_income <= monthly_avg_credit:
                income_match = True

        status = 'Verified' if income_match else 'Needs Review'

        is_eligible      = False
        suggested_amount = 0.0
        eligibility_reason = ''

        if status == 'Verified':
            if business_age < 1:
                eligibility_reason = 'Business age is less than 1 year.'
            elif avg_balance <= 0 and monthly_avg_credit <= 0:
                eligibility_reason = 'Average monthly balance / income is too low.'
            else:
                is_eligible = True
                base = (monthly_avg_credit if self_declared_income <= 0
                        else min(self_declared_income, monthly_avg_credit))

                if business_age < 2:
                    multiplier = 2
                elif business_age < 5:
                    multiplier = 3
                else:
                    multiplier = 5

                suggested_amount   = base * multiplier
                eligibility_reason = 'Applicant meets financial and stability criteria.'
        else:
            eligibility_reason = 'Income verification failed or needs manual review.'

        safe_credit      = monthly_avg_credit if math.isfinite(monthly_avg_credit) else 0.0
        safe_debit       = monthly_avg_debit  if math.isfinite(monthly_avg_debit)  else 0.0
        safe_tc          = total_credit        if math.isfinite(total_credit)        else 0.0
        safe_td          = total_debit         if math.isfinite(total_debit)         else 0.0
        safe_bal         = avg_balance         if math.isfinite(avg_balance)         else 0.0

        response_body = {
            'success': True,
            'data': {
                'applicantName': applicant_name,
                'businessType':  business_type,

                'statementPeriod': {
                    'months':    period_months,
                    'startDate': period_start,
                    'endDate':   period_end,
                    'currency':  currency,
                    'bankName':  bank_name,
                    'isMpesa':   is_mpesa,
                },

                'metrics': {
                    'totalCredit':           safe_tc,
                    'totalDebit':            safe_td,
                    'averageMonthlyBalance': safe_bal,
                },

                'monthlyAverages': {
                    'avgMonthlyCredit': safe_credit,
                    'avgMonthlyDebit':  safe_debit,
                },

                'transactionSummary': tx_summary,

                'validation': {
                    'incomeMatch': income_match,
                    'status':      status,
                    'message': (
                        f"Monthly income ({currency} {self_declared_income:,.0f}) vs "
                        f"avg monthly credit ({currency} {safe_credit:,.0f}): "
                        f"{'Matched' if income_match else 'Threshold mismatch'}"
                    ),
                },

                'loanPrediction': {
                    'isEligible':      is_eligible,
                    'suggestedAmount': round(suggested_amount, 2),
                    'reason':          eligibility_reason,
                },
            }
        }

        return jsonify(_sanitize(response_body))

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
