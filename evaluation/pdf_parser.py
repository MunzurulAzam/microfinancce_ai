"""Universal statement parser — M-Pesa/mobile money, US, UK/EU, South Asian, African and Middle-East bank formats."""

import pdfplumber
import re
from datetime import date
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta


CURRENCY_HINTS: dict[str, list[str]] = {
    'KES': ['ksh', 'kes', 'ksh.', 'k.s.h', 'kenya shilling'],
    'TZS': ['tsh', 'tzs', 'tsh.', 'tanzania shilling', 'shilingi'],
    'UGX': ['ugx', 'ush', 'uganda shilling', 'ugsh'],
    'GHS': ['ghs', 'gh₵', 'ghc', 'cedis', 'ghana cedi'],
    'RWF': ['rwf', 'frw', 'rwanda franc'],
    'ETB': ['etb', 'birr', 'ethiopia birr'],
    'ZMW': ['zmw', 'zambian kwacha'],
    'MZN': ['mzn', 'mozambique metical'],
    'NGN': ['ngn', '₦', 'naira', 'nigeria'],
    'ZAR': ['zar', 'rand', 'south africa'],
    'EGP': ['egp', 'egyptian pound', 'e£'],
    'GHS': ['ghs', 'cedis'],
    'BDT': ['bdt', '৳', 'taka', 'bangladeshi'],
    'INR': ['inr', '₹', 'rupee', 'indian rupee', 'rs.', 'rs '],
    'PKR': ['pkr', 'pakistani rupee'],
    'LKR': ['lkr', 'sri lanka rupee'],
    'NPR': ['npr', 'nepalese rupee'],
    'MMK': ['mmk', 'myanmar kyat'],
    'PHP': ['php', '₱', 'philippine peso'],
    'IDR': ['idr', 'rupiah'],
    'THB': ['thb', '฿', 'baht'],
    'VND': ['vnd', '₫', 'dong'],
    'AED': ['aed', 'dirham', 'uae'],
    'SAR': ['sar', 'riyal', 'saudi'],
    'QAR': ['qar', 'qatari riyal'],
    'KWD': ['kwd', 'kuwaiti dinar'],
    'BHD': ['bhd', 'bahraini dinar'],
    'EUR': ['eur', '€', 'euro'],
    'GBP': ['gbp', '£', 'pound sterling', 'british pound'],
    'CHF': ['chf', 'swiss franc'],
    'SEK': ['sek', 'swedish krona'],
    'NOK': ['nok', 'norwegian krone'],
    'DKK': ['dkk', 'danish krone'],
    'PLN': ['pln', 'zloty', 'polish'],
    'USD': ['usd', 'us$', 'u.s. dollar', 'dollar'],
    'CAD': ['cad', 'canadian dollar'],
    'MXN': ['mxn', 'mexican peso'],
    'BRL': ['brl', 'r$', 'real', 'brazilian'],
    'JPY': ['jpy', '¥', 'yen'],
    'CNY': ['cny', 'yuan', 'rmb', 'renminbi'],
    'KRW': ['krw', '₩', 'won'],
    'AUD': ['aud', 'a$', 'australian dollar'],
}

MPESA_IDENTITY_KEYWORDS = [
    'm-pesa', 'mpesa', 'safaricom', 'vodacom m-pesa',
    'airtel money', 'airtel networks', 'balance statement for the period',
    'tigo pesa', 'mtn money', 'mtn momo',
    'lipa na m-pesa', 'lipa na mpesa', 'bonga points', 'm-shwari',
    'fuliza', 'till number',
    'mobile money statement', 'mobile banking statement',
    'money deposit', 'money sent', 'money credited', 'money debited',
]

BANK_IDENTITY_KEYWORDS = {
    'Chase':           ['jpmorgan chase', 'chase bank', 'chase.com'],
    'Bank of America': ['bank of america', 'bankofamerica'],
    'Wells Fargo':     ['wells fargo'],
    'Citi':            ['citibank', 'citi bank'],
    'Barclays':        ['barclays'],
    'HSBC':            ['hsbc'],
    'Revolut':         ['revolut'],
    'Monzo':           ['monzo'],
    'Starling':        ['starling bank'],
    'HDFC':            ['hdfc bank'],
    'SBI':             ['state bank of india', 'sbi'],
    'ICICI':           ['icici bank'],
    'DBBL':            ['dutch-bangla bank', 'dbbl'],
    'BRAC Bank':       ['brac bank'],
    'Islami Bank':     ['islami bank'],
    'Dutch Bangla':    ['dutch bangla'],
    'AB Bank':         ['ab bank'],
    'UCB':             ['united commercial bank', 'ucb'],
    'Standard Chartered': ['standard chartered'],
    'GTBank':          ['guaranty trust', 'gtbank'],
    'Zenith':          ['zenith bank'],
    'Access Bank':     ['access bank'],
    'FNB':             ['first national bank', 'fnb'],
    'Absa':            ['absa', 'amalgamated banks'],
    'Airtel Money':    ['airtel networks', 'airtel money', 'airtel mobile'],
    'MTN Mobile Money': ['mtn momo', 'mtn mobile money', 'mtn money'],
    'Tigo Pesa':       ['tigo pesa', 'tigo cash'],
    'M-Pesa (Safaricom)': ['safaricom', 'm-pesa'],
}


CREDIT_VOCAB = [
    'money in', 'received', 'paid in', 'deposit', 'deposits',
    'cash in', 'transfer in', 'received from', 'customer transfer',
    'reversal', 'refund', 'salary', 'wages', 'payroll',
    'loan disbursement', 'inward', 'incoming', 'loaded',
    'top up', 'topup', 'recharge', 'credit', 'cr',
    'payments in', 'payment received', 'interest credit',
    'dividend', 'cashback', 'bonus', 'reimburse',
]

DEBIT_VOCAB = [
    'money out', 'sent', 'withdrawn', 'withdrawal', 'cash out',
    'buy goods', 'pay bill', 'paybill', 'airtime', 'send money',
    'lipa na mpesa', 'lipa na m-pesa', 'debit', 'dr',
    'outward', 'outgoing', 'payment', 'fees', 'charge', 'charges',
    'fuliza', 'tax', 'merchant payment', 'business payment',
    'till', 'agent', 'transfer out', 'payments out',
    'purchase', 'pos', 'atm', 'eft', 'standing order',
    'direct debit', 'bill payment', 'utility', 'insurance',
    'mortgage', 'loan repayment', 'interest debit',
]

MONTH_NAMES = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _parse_amount(val: str) -> float:
    if not val:
        return 0.0
    s = str(val).strip()

    s = re.sub(r'^\((.+)\)$', r'\1', s)

    s = re.sub(
        r'(?i)\b(cr|dr|credit|debit|ksh\.?|tsh\.?|ugx|ush|shs|ghs|rwf|etb|zmw|mzn'
        r'|ngn|zar|egp|bdt|inr|pkr|lkr|npr|mmk|php|idr|thb|vnd'
        r'|aed|sar|qar|kwd|bhd|eur|gbp|chf|sek|nok|dkk|pln'
        r'|usd|cad|mxn|brl|jpy|cny|krw|aud|kes|tzs|rs\.?)\b', '', s
    )
    s = re.sub(r'[€£¥₹₺₦₱₫฿₩৳\$]', '', s)
    s = s.strip()

    has_dot   = '.' in s
    has_comma = ',' in s

    if has_comma and has_dot:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')

    elif has_comma and not has_dot:
        after_last_comma = re.sub(r'[^\d]', '', s.rsplit(',', 1)[-1])
        if len(after_last_comma) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')

    elif has_dot and not has_comma:
        dot_parts = s.split('.')
        if len(dot_parts) > 2:
            s = s.replace('.', '')

    s = s.replace(' ', '')

    clean = re.sub(r'[^\d.]', '', s)
    try:
        if clean.count('.') > 1:
            return 0.0
        if clean.endswith('.'):
            clean = clean[:-1]
        if not clean:
            return 0.0
        digit_count = len(clean.replace('.', ''))
        if digit_count > 13:
            return 0.0
        result = float(clean)
        import math
        if not math.isfinite(result):
            return 0.0
        return result
    except ValueError:
        return 0.0


def _has_cr_suffix(cell: str) -> bool:
    return bool(re.search(r'\bCr\.?\s*$', cell, re.IGNORECASE))


def _has_dr_suffix(cell: str) -> bool:
    return bool(re.search(r'\bDr\.?\s*$', cell, re.IGNORECASE))


def _has_plus_prefix(cell: str) -> bool:
    return cell.strip().startswith('+')


def _has_minus_prefix(cell: str) -> bool:
    return cell.strip().startswith('-')


def _extract_all_dates(text: str) -> list[date]:
    found: list[date] = []

    for m in re.finditer(r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b', text):
        try:
            found.append(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            pass

    for m in re.finditer(r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b', text):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass

    for m in re.finditer(
        r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b',
        text, re.IGNORECASE
    ):
        try:
            mon = MONTH_NAMES[m.group(2).lower()[:3]]
            found.append(date(int(m.group(3)), mon, int(m.group(1))))
        except ValueError:
            pass

    for m in re.finditer(
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b',
        text, re.IGNORECASE
    ):
        try:
            mon = MONTH_NAMES[m.group(1).lower()[:3]]
            found.append(date(int(m.group(3)), mon, int(m.group(2))))
        except ValueError:
            pass

    return [d for d in found if 2010 <= d.year <= 2030]


def _months_between(start: date, end: date) -> float:
    """Fractional months between two dates. Minimum 1.0, Maximum 6.0."""
    delta = relativedelta(end, start)
    months = delta.years * 12 + delta.months + delta.days / 30.0
    return max(1.0, min(6.0, round(months, 1)))


def _detect_currency(text: str) -> str:
    lower = text.lower()
    for code, hints in CURRENCY_HINTS.items():
        for h in hints:
            if h in lower:
                return code
    return 'USD'


def _detect_bank_name(text: str) -> str:
    lower = text.lower()
    for name, hints in BANK_IDENTITY_KEYWORDS.items():
        for h in hints:
            if h in lower:
                return name
    return 'Unknown Bank'


def _is_mpesa(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in MPESA_IDENTITY_KEYWORDS)


def _detect_period(text: str):
    """Returns (start_str, end_str, months_float)."""
    explicit = re.search(
        r'(?:statement\s*period|period|from|date\s*range|for\s+the\s+period)\s*[:\-]?\s*'
        r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}\s+\w+\s+\d{4})'
        r'\s*(?:to|through|–|-|until|thru)\s*'
        r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{1,2}\s+\w+\s+\d{4})',
        text, re.IGNORECASE
    )
    if explicit:
        try:
            s = date_parser.parse(explicit.group(1), dayfirst=True).date()
            e = date_parser.parse(explicit.group(2), dayfirst=True).date()
            return str(s), str(e), _months_between(s, e)
        except Exception:
            pass

    all_dates = _extract_all_dates(text)
    if len(all_dates) >= 2:
        s, e = min(all_dates), max(all_dates)
        return str(s), str(e), _months_between(s, e)

    return '', '', 1.0


_AMT = r'(?:[A-Z]{2,4}\.?|[€£¥₹₺₦₱₫฿₩৳\$])?\s*([\d,\.\s]+)'


def _extract_summary(text: str) -> dict:

    def _find(patterns: list[str]) -> float | None:
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if m:
                v = _parse_amount(m.group(1))
                if v > 0:
                    return v
        return None

    credit_pats = [
        rf'(?:Total\s+Credit[s]?|Total\s+Deposit[s]?'
        rf'|Total\s+Money\s+In|Total\s+In|Cash\s+In'
        rf'|Payments?\s+In|Total\s+Received|Total\s+Inflow[s]?'
        rf'|Total\s+CR|Sum\s+of\s+Credit[s]?|Credit\s+Total|Inward\s+Total'
        rf'|Total\s+Amount\s+Credited'
        rf'|Total\s+Money\s+Credited'
        rf'|Total\s+Airtime\s+Credited'
        rf'|Amount\s+Credited|Credited\s+Amount'
        rf')\s*[:\-]?\s*{_AMT}',
    ]
    debit_pats = [
        rf'(?:Total\s+Debit[s]?|Total\s+Withdrawal[s]?'
        rf'|Total\s+Money\s+Out|Total\s+Out|Cash\s+Out'
        rf'|Payments?\s+Out|Total\s+Sent|Total\s+Outflow[s]?'
        rf'|Total\s+DR|Sum\s+of\s+Debit[s]?|Debit\s+Total|Outward\s+Total'
        rf'|Total\s+Amount\s+Debited|Total\s+Fee[s]?'
        rf'|Total\s+Money\s+Debited'
        rf'|Amount\s+Debited|Debited\s+Amount'
        rf')\s*[:\-]?\s*{_AMT}',
    ]
    balance_pats = [
        rf'(?:Closing\s+Balance|Available\s+Balance|Balance\s+[Bb]rought\s+[Ff]orward'
        rf'|Account\s+Balance|Balance\s+[Aa]s\s+[Oo]f|Ending\s+Balance'
        rf'|Ledger\s+Balance|Current\s+Balance|Net\s+Balance'
        rf'|Opening\s+Balance'
        rf')\s*[:\-]?\s*{_AMT}',
    ]

    return {
        'credit':  _find(credit_pats),
        'debit':   _find(debit_pats),
        'balance': _find(balance_pats),
    }


def _identify_columns(rows: list[list[str]]) -> dict:
    """Scan the first 30 rows to identify column roles by header keywords."""
    h = {k: -1 for k in ('date', 'credit', 'debit', 'balance', 'amount', 'type', 'sign')}

    role_kw = {
        'date':    {'date', 'txn date', 'transaction date', 'value date',
                    'posting date', 'datetime', 'date & time', 'date/time'},
        'credit':  {'credit', 'credits', 'deposit', 'deposits',
                    'money in', 'paid in', 'payments in', 'cr', 'inflow',
                    'received',
                    'credited',
                    'amount(zmw)',
                    },
        'debit':   {'debit', 'debits', 'withdrawal', 'withdrawals',
                    'money out', 'payments out', 'dr', 'outflow', 'withdrawn',
                    'debited',
                    },
        'balance': {'balance', 'running balance', 'available balance',
                    'closing balance', 'net balance', 'ledger balance'},
        'amount':  {'amount', 'transaction amount', 'value', 'amt',
                    'debit/credit amount'},
        'type':    {'type', 'transaction type', 'txn type', 'description',
                    'narration', 'particulars', 'details', 'remarks',
                    'reference', 'ref'},
        'sign':    {'cr/dr', 'dr/cr', 'indicator', 'sign', 'credit/debit'},
    }

    for row in rows[:30]:
        rl = [str(c).lower().strip() for c in row]
        for j, cell in enumerate(rl):
            for role, kw_set in role_kw.items():
                if h[role] == -1:
                    if cell in kw_set or any(kw in cell for kw in kw_set):
                        h[role] = j
                        break

    return h


def _parse_transaction_rows(
    rows: list[list[str]],
    h: dict,
    all_text: str
) -> tuple[float, float, list[float], dict]:
    """Parse all transaction rows and return: (total_credit, total_debit, balances_list, transaction_counts)"""
    total_credit = 0.0
    total_debit = 0.0
    balances: list[float] = []
    tx_counts: dict[str, int] = {}

    date_pat = re.compile(r'\d{1,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}')

    for row in rows:
        row_str = ' '.join(row)

        if not date_pat.search(row_str):
            continue

        c_idx = h['credit']
        d_idx = h['debit']
        b_idx = h['balance']
        a_idx = h['amount']
        t_idx = h['type']
        s_idx = h['sign']

        if c_idx != -1 or d_idx != -1:
            cv = _parse_amount(row[c_idx]) if c_idx != -1 and c_idx < len(row) else 0.0
            dv = _parse_amount(row[d_idx]) if d_idx != -1 and d_idx < len(row) else 0.0
            if cv > 0:
                total_credit += cv
            if dv > 0:
                total_debit += dv

        elif a_idx != -1 and a_idx < len(row):
            raw_cell = row[a_idx]
            v = _parse_amount(raw_cell)

            if _has_cr_suffix(raw_cell):
                if v > 0:
                    total_credit += v
            elif _has_dr_suffix(raw_cell):
                if v > 0:
                    total_debit += v

            elif _has_plus_prefix(raw_cell):
                if v > 0:
                    total_credit += v
            elif _has_minus_prefix(raw_cell):
                if v > 0:
                    total_debit += v

            elif s_idx != -1 and s_idx < len(row):
                sign_cell = row[s_idx].strip().lower()
                if sign_cell in ('cr', 'c', '+', 'credit', 'in'):
                    if v > 0:
                        total_credit += v
                elif sign_cell in ('dr', 'd', '-', 'debit', 'out'):
                    if v > 0:
                        total_debit += v

            elif t_idx != -1 and t_idx < len(row):
                desc = row[t_idx].lower()
                if re.search(r'\bcr\b', desc):
                    if v > 0:
                        total_credit += v
                elif re.search(r'\bdr\b', desc):
                    if v > 0:
                        total_debit += v
                elif any(kw in desc for kw in CREDIT_VOCAB):
                    if v > 0:
                        total_credit += v
                    cat = _classify_tx(desc)
                    tx_counts[cat] = tx_counts.get(cat, 0) + 1
                elif any(kw in desc for kw in DEBIT_VOCAB):
                    if v > 0:
                        total_debit += v
                    cat = _classify_tx(desc)
                    tx_counts[cat] = tx_counts.get(cat, 0) + 1

        else:
            nums = []
            for cell in row:
                raw = cell.strip()
                if re.search(r'\d{2,4}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', raw):
                    continue
                v = _parse_amount(raw)
                digs = re.sub(r'[^\d]', '', raw)
                if v > 0 and 1 <= len(digs) <= 12:
                    nums.append(v)
            if len(nums) >= 2:
                total_credit += nums[-2]
                balances.append(nums[-1])
            elif len(nums) == 1:
                balances.append(nums[0])

        if b_idx != -1 and b_idx < len(row):
            bv = _parse_amount(row[b_idx])
            if bv > 0:
                balances.append(bv)

    return total_credit, total_debit, balances, tx_counts


def _classify_tx(desc: str) -> str:
    d = desc.lower()
    if any(k in d for k in ['salary', 'wages', 'payroll']):          return 'Salary'
    if any(k in d for k in ['send money', 'transfer', 'sent to']):   return 'Transfer Out'
    if any(k in d for k in ['received', 'paid in', 'deposit']):      return 'Received'
    if any(k in d for k in ['buy goods', 'till', 'merchant', 'pos']): return 'Purchase'
    if any(k in d for k in ['pay bill', 'paybill', 'utility']):      return 'Bill Payment'
    if any(k in d for k in ['airtime', 'recharge', 'topup']):        return 'Airtime'
    if any(k in d for k in ['withdraw', 'cash out', 'atm', 'agent']): return 'Withdrawal'
    if any(k in d for k in ['loan', 'fuliza', 'credit facility']):   return 'Loan/Credit'
    if any(k in d for k in ['interest']):                             return 'Interest'
    if any(k in d for k in ['insurance']):                            return 'Insurance'
    if any(k in d for k in ['tax', 'levy', 'excise']):               return 'Tax'
    if any(k in d for k in ['refund', 'reversal', 'cashback']):      return 'Refund'
    return 'Other'


class UniversalStatementParser:
    """Parse any PDF bank / mobile-money statement from anywhere in the world."""

    def parse(self, file_path: str) -> dict:
        try:
            all_text, all_rows = self._read_pdf(file_path)
        except Exception as e:
            print(f"[Parser] PDF read error: {e}")
            return self._empty()

        is_mobile = _is_mpesa(all_text)
        currency = _detect_currency(all_text)
        bank_name = _detect_bank_name(all_text)
        period_start, period_end, period_months = _detect_period(all_text)

        summary = _extract_summary(all_text)
        total_credit = summary['credit']
        total_debit  = summary['debit']
        avg_balance_raw = summary['balance']

        if total_credit is not None and total_debit is not None:
            avg_balance = avg_balance_raw or 0.0
            tx_counts = {}
        else:
            h = _identify_columns(all_rows)
            tc, td, bals, tx_counts = _parse_transaction_rows(all_rows, h, all_text)
            total_credit = tc if total_credit is None else total_credit
            total_debit  = td if total_debit  is None else total_debit
            avg_balance = (sum(bals) / len(bals)) if bals else (avg_balance_raw or 0.0)

        total_credit = round(total_credit or 0.0, 2)
        total_debit  = round(total_debit  or 0.0, 2)
        avg_balance  = round(avg_balance,          2)

        monthly_avg_credit = round(total_credit / period_months, 2)
        monthly_avg_debit  = round(total_debit  / period_months, 2)

        return {
            'total_credit':       total_credit,
            'total_debit':        total_debit,
            'avg_balance':        avg_balance,
            'period_months':      period_months,
            'period_start':       period_start,
            'period_end':         period_end,
            'monthly_avg_credit': monthly_avg_credit,
            'monthly_avg_debit':  monthly_avg_debit,
            'currency':           currency,
            'bank_name':          bank_name,
            'is_mpesa':           is_mobile,
            'transaction_summary': tx_counts,
        }

    def _read_pdf(self, file_path: str) -> tuple[str, list]:
        all_text = ''
        all_rows = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                all_text += (page.extract_text() or '') + '\n'
                for table in page.extract_tables():
                    for row in table:
                        clean = [str(c).strip() if c else '' for c in row]
                        if any(clean):
                            all_rows.append(clean)
        return all_text, all_rows

    def _empty(self) -> dict:
        return {
            'total_credit': 0.0, 'total_debit': 0.0, 'avg_balance': 0.0,
            'period_months': 1.0, 'period_start': '', 'period_end': '',
            'monthly_avg_credit': 0.0, 'monthly_avg_debit': 0.0,
            'currency': 'USD', 'bank_name': 'Unknown', 'is_mpesa': False,
            'transaction_summary': {},
        }


_parser = UniversalStatementParser()


def parse_statement(file_path: str) -> dict:
    return _parser.parse(file_path)


def parse_mpesa_statement(file_path: str) -> dict:
    """Alias of parse_statement — kept for backward compatibility."""
    return parse_statement(file_path)


def extract_financial_metrics(file_path: str) -> tuple[float, float, float]:
    """Legacy convenience wrapper. Returns (total_credit, total_debit, avg_balance)."""
    r = parse_statement(file_path)
    return r['total_credit'], r['total_debit'], r['avg_balance']
