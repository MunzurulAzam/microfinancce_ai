import pdfplumber
import re

def extract_financial_metrics(file_path):
    """
    Universal Parsing Engine: Extracts financial metrics from any transaction PDF.
    Prioritizes summary sections and uses date-anchored scanning for tables.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            all_text = ""
            all_rows = []
            
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"
                
                # Table Extraction
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean_row = [str(cell).strip() if cell else "" for cell in row]
                        if any(clean_row):
                            all_rows.append(clean_row)

            # --- STEP 1: SUMMARY EXTRACTION (Highest Accuracy) ---
            # Improved patterns to handle optional currency codes (Ugx, BDT, etc.)
            # Match "Total Credit", then optional ":" or spaces, then optional currency code, then the number
            currency_code_pattern = r'(?:[A-Z]{2,3}|৳|\$|Rs\.?|U\.?S\.?D\.?)?\s*'
            
            credit_regex = rf'(?:Total\s+Credit|Total\s+Deposit|Cash\s+In|Total\s+In)\s*[:\s]*{currency_code_pattern}([\d,]+\.?\d*)'
            debit_regex = rf'(?:Total\s+Debit|Total\s+Withdrawal|Cash\s+Out|Total\s+Out|Total\s+Fee)\s*[:\s]*{currency_code_pattern}([\d,]+\.?\d*)'
            balance_regex = rf'(?:Closing\s+Balance|Available\s+Balance|Balance\s+as\s+of)\s*[:\s]*{currency_code_pattern}([\d,]+\.?\d*)'

            summary_credit = _find_by_regex(credit_regex, all_text)
            summary_debit = _find_by_regex(debit_regex, all_text)
            summary_balance = _find_by_regex(balance_regex, all_text)

            # Check if we have both credit and debit in the summary
            if summary_credit is not None and summary_debit is not None:
                return round(summary_credit, 2), round(summary_debit, 2), round(summary_balance if summary_balance is not None else 0.0, 2)

            # --- STEP 2: TABLE HEURISTICS (Fallback) ---
            total_credit = 0.0
            total_debit = 0.0
            balances = []
            
            credit_idx = -1
            debit_idx = -1
            balance_idx = -1
            amount_idx = -1
            type_idx = -1
            
            # Identify columns using strict multi-keyword matching
            for row in all_rows[:20]: # Search headers in first 20 rows
                rl = [c.lower() for c in row]
                for j, cell in enumerate(rl):
                    if balance_idx == -1 and any(k in cell for k in ['balance', 'available', 'স্থিতি']):
                        balance_idx = j
                    elif amount_idx == -1 and any(k in cell for k in ['amount', 'transaction amount', 'পরিমাণ']):
                        amount_idx = j
                    elif credit_idx == -1 and any(k == cell or k in cell for k in ['credit', 'deposit', 'received', 'জমা']):
                        credit_idx = j
                    elif debit_idx == -1 and any(k == cell or k in cell for k in ['debit', 'withdrawal', 'out', 'payment', 'খরচ']):
                        debit_idx = j
                    elif type_idx == -1 and any(k in cell for k in ['status', 'type', 'description', 'particulars']):
                        if any(k in cell for k in ['credit', 'debit', 'received', 'payment']):
                            type_idx = j

            # Process rows with Date Anchoring
            date_pattern = re.compile(r'\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4}')

            for row in all_rows:
                row_str = " ".join(row)
                if not date_pattern.search(row_str):
                    continue

                row_vals = []
                for i, cell in enumerate(row):
                    v = _parse_val(cell)
                    if v > 0:
                        clean_digit_only = re.sub(r'[^\d]', '', cell)
                        if len(clean_digit_only) <= 11:
                            row_vals.append((i, v))

                if not row_vals: continue

                if type_idx != -1 and amount_idx != -1 and amount_idx < len(row) and type_idx < len(row):
                    t = row[type_idx].lower()
                    v = _parse_val(row[amount_idx])
                    if any(k in t for k in ['credit', 'received', 'in', 'deposit', 'successful']):
                        if any(k in t for k in ['received', 'cash in', 'deposit']): total_credit += v
                        elif any(k in t for k in ['payment', 'sent', 'cash out', 'withdraw']): total_debit += v
                else:
                    if credit_idx != -1 and credit_idx < len(row):
                        v = _parse_val(row[credit_idx])
                        if v: total_credit += v
                    if debit_idx != -1 and debit_idx < len(row):
                        v = _parse_val(row[debit_idx])
                        if v: total_debit += v

                if balance_idx != -1 and balance_idx < len(row):
                    v = _parse_val(row[balance_idx])
                    if v: balances.append(v)
                elif row_vals:
                    balances.append(row_vals[-1][1])

            final_credit = summary_credit if summary_credit is not None else total_credit
            final_debit = summary_debit if summary_debit is not None else total_debit
            avg_balance = sum(balances) / len(balances) if balances else (summary_balance if summary_balance is not None else 0.0)

            return round(final_credit, 2), round(final_debit, 2), round(avg_balance, 2)

    except Exception as e:
        print(f"Universal Parser Error: {e}")
        return 0.0, 0.0, 0.0

def _find_by_regex(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return _parse_val(match.group(1))
    return None

def _parse_val(val_str):
    if not val_str: return 0.0
    # Common format: removes currency symbols and handles commas/spaces
    # Special case: Ugx, BDT, etc. usually separated by space
    clean = re.sub(r'[^\d.]', '', val_str.replace(',', '').replace(' ', ''))
    try:
        if clean.count('.') > 1: return 0.0
        if clean.endswith('.'): clean = clean[:-1]
        return float(clean) if clean else 0.0
    except ValueError:
        return 0.0



