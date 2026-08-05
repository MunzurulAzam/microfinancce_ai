"""
Performance calculations — now powered by MSSQL (via mssql_data_service).
CSV/data_processor dependency removed.
"""

from portfolio.data_service import (
    get_top_performers,
    get_risk_analysis,
    get_quick_insights,
)


def get_business_performance():
    """
    Business performance by loan purpose — from MSSQL.
    Kept as stub; returns empty list (loan purpose not part of bulk query yet).
    """
    return []
