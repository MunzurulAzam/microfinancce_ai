

import pymssql

from ask_ai.config import COUNTRIES_BY_CODE, SYNC_QUERY_TIMEOUT


def connect(profile):
    """Open a new MSSQL connection for a given country profile dict."""
    return pymssql.connect(
        server=profile['server'],
        port=profile['port'],
        user=profile['user'],
        password=profile['password'],
        database=profile['database'],
        login_timeout=60,
        timeout=SYNC_QUERY_TIMEOUT,   # per-query timeout (keyset pages stay small)
        as_dict=True,
    )


def connect_country(country_code):
    """Convenience: open a connection by country code, e.g. connect_country('KY')."""
    profile = COUNTRIES_BY_CODE.get(country_code.upper())
    if not profile:
        raise ValueError(
            f"Unknown country '{country_code}'. "
            f"Known: {', '.join(COUNTRIES_BY_CODE)}"
        )
    return connect(profile)
