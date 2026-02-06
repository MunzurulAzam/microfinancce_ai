from flask import Blueprint, request, jsonify
import os
from werkzeug.utils import secure_filename
from services.pdf_parser import extract_financial_metrics

evaluation_bp = Blueprint('evaluation', __name__)

# Configure upload folder
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@evaluation_bp.route('/evaluate', methods=['POST'])
def evaluate_applicant():
    """
    Endpoint to handle data entry and PDF upload for evaluation.
    """
    try:
        # 1. Get Section A data (Manual Input)
        applicant_name = request.form.get('applicantName')
        business_type = request.form.get('businessType')
        business_age = request.form.get('businessAge')
        self_declared_income = float(request.form.get('monthlyIncome', 0))
        rent_amount = float(request.form.get('rentAmount', 0))

        # 2. Handle Section B (Document Upload)
        if 'bankStatement' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['bankStatement']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # 3. Parse PDF
            total_credit, total_debit, avg_balance = extract_financial_metrics(file_path)
            
            # Clean up: delete temp file
            os.remove(file_path)
            
            # 4. Validation & Logic
            # Cross-check if Self-Declared Monthly Income matches roughly with Total_Credit_Sum
            # Rough match: let's say within 20% margin, or if self-declared is not significantly higher than credit
            income_match = False
            margin = 0.2 # 20%
            if total_credit > 0:
                # If total_credit is for a month, it should be close to monthly income
                # Note: extract_financial_metrics might return total for several months, 
                # but for simplicity we'll treat it as a proxy for the statement period's activity.
                if (1 - margin) * total_credit <= self_declared_income <= (1 + margin) * total_credit:
                    income_match = True
                elif self_declared_income <= total_credit:
                    income_match = True # Under-declaring is also fine for validation
            
            status = "Verified" if income_match else "Needs Review"
            
            # 5. Loan Prediction Logic
            is_eligible = False
            suggested_amount = 0.0
            eligibility_reason = ""

            if status == "Verified":
                if float(business_age) < 1:
                    eligibility_reason = "Business age is less than 1 year."
                elif avg_balance <= 0:
                    eligibility_reason = "Average monthly balance is too low."
                else:
                    is_eligible = True
                    # Suggesed amount based on 3x of monthly income or average balance (whichever is lower)
                    # capped for conservative estimation
                    base_resource = min(self_declared_income, avg_balance)
                    
                    # Multiplier based on business stability
                    age = float(business_age)
                    if age < 2:
                        multiplier = 2
                    elif age < 5:
                        multiplier = 3
                    else:
                        multiplier = 5
                    
                    suggested_amount = base_resource * multiplier
                    eligibility_reason = "Applicant meets financial and stability criteria."
            else:
                eligibility_reason = "Income verification failed or needs manual review."

            return jsonify({
                'success': True,
                'data': {
                    'applicantName': applicant_name,
                    'businessType': business_type,
                    'metrics': {
                        'totalCredit': total_credit,
                        'totalDebit': total_debit,
                        'averageMonthlyBalance': avg_balance
                    },
                    'validation': {
                        'incomeMatch': income_match,
                        'status': status,
                        'message': f"Income vs Credit validation: {'Matched' if income_match else 'Threshold mismatch'}"
                    },
                    'loanPrediction': {
                        'isEligible': is_eligible,
                        'suggestedAmount': round(suggested_amount, 2),
                        'reason': eligibility_reason
                    }
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid file format. Only PDF allowed.'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
