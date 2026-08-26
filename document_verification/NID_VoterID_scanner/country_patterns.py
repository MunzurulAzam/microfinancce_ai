import re
from typing import Optional

COUNTRY_REGISTRY = [
    {
        'name': 'Uganda',
        'code': 'UG',
        'id_type': 'National Identification Number (NIN)',
        'pattern': re.compile(r'\bC[MF][A-Z0-9]{12}\b', re.IGNORECASE),
        'keywords': ['uganda', 'national identification', 'nira', 'republic of uganda',
                     'ugandan', 'kampala'],
        'voter_keywords': ['electoral commission', 'voter', 'ugandan voter'],
    },
    {
        'name': 'Kenya',
        'code': 'KE',
        'id_type': 'National Identity Card',
        'pattern': re.compile(r'\b\d{7,8}\b'),
        'keywords': ['kenya', 'republic of kenya', 'kenyan', 'nairobi', 'huduma'],
        'voter_keywords': ['independent electoral', 'iebc', 'kenyan voter'],
    },
    {
        'name': 'Tanzania',
        'code': 'TZ',
        'id_type': 'NIDA National ID',
        'pattern': re.compile(r'\b\d{8}-\d{5}-\d{5}-\d{2}\b|\b\d{20}\b'),
        'keywords': ['tanzania', 'jamhuri ya muungano', 'nida', 'tanzanian',
                     'dodoma', 'dar es salaam'],
        'voter_keywords': ['zanzibar', 'tanzanian voter'],
    },
    {
        'name': 'Zambia',
        'code': 'ZM',
        'id_type': 'National Registration Card (NRC)',
        'pattern': re.compile(r'\b\d{6}/\d{2}/\d\b'),
        'keywords': ['zambia', 'republic of zambia', 'nrc', 'zambian', 'lusaka'],
        'voter_keywords': ['zambia electoral', 'zambian voter'],
    },
    {
        'name': 'Bangladesh',
        'code': 'BD',
        'id_type': 'National Identity Card (NID)',
        'pattern': re.compile(r'\b(\d{17}|\d{10})\b'),
        'keywords': ['bangladesh', 'peoples republic', 'nid', 'dhaka',
                     'election commission bangladesh', 'nirbachon'],
        'voter_keywords': ['voter id', 'voter card'],
    },
    {
        'name': 'Rwanda',
        'code': 'RW',
        'id_type': 'National Identity Card',
        'pattern': re.compile(r'\b1\d{15}\b'),
        'keywords': ['rwanda', 'repubulika', 'kigali', 'rwandan'],
        'voter_keywords': [],
    },
    {
        'name': 'Ethiopia',
        'code': 'ET',
        'id_type': 'National Identity Card',
        'pattern': re.compile(r'\bETH\d{9}\b', re.IGNORECASE),
        'keywords': ['ethiopia', 'federal democratic', 'addis ababa', 'ethiopian'],
        'voter_keywords': [],
    },
    {
        'name': 'Ghana',
        'code': 'GH',
        'id_type': 'Ghana Card (National ID)',
        'pattern': re.compile(r'\bGHA-\d{9}-\d\b', re.IGNORECASE),
        'keywords': ['ghana', 'republic of ghana', 'ghanaian', 'accra', 'nia'],
        'voter_keywords': ['electoral commission', 'ghanaian voter'],
    },
    {
        'name': 'Nigeria',
        'code': 'NG',
        'id_type': 'National Identity Card (NIN)',
        'pattern': re.compile(r'\b\d{11}\b'),
        'keywords': ['nigeria', 'federal republic of nigeria', 'nigerian', 'abuja', 'nimc'],
        'voter_keywords': ['inec', 'nigerian voter', 'permanent voter'],
    },
]

GENERIC_FALLBACK = {
    'name': 'Unknown',
    'code': 'XX',
    'id_type': 'Identity Document',
    'pattern': re.compile(r'\b[A-Z0-9][A-Z0-9\-/]{5,24}\b'),
    'keywords': [],
    'voter_keywords': [],
}


def detect_country(extracted_text: str) -> dict:
    if not extracted_text:
        return GENERIC_FALLBACK

    text_lower = extracted_text.lower()
    best_score = 0
    best_country = GENERIC_FALLBACK

    for country in COUNTRY_REGISTRY:
        score = sum(1 for kw in country['keywords'] if kw in text_lower)
        score += sum(1 for kw in country['voter_keywords'] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_country = country

    return best_country


def validate_id_number(id_number: str, country: dict) -> bool:
    if not id_number:
        return False
    cleaned = (
        id_number.strip()
        .replace(' ', '')
        .replace('–', '-')
        .replace('—', '-')
    )
    return bool(country['pattern'].fullmatch(cleaned)) or bool(country['pattern'].search(cleaned))


def get_country_by_code(code: str) -> Optional[dict]:
    for c in COUNTRY_REGISTRY:
        if c['code'].upper() == code.upper():
            return c
    return None
