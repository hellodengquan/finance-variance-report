"""财务差异报告生成器"""

from .models import (
    FinancialData,
    VarianceResult,
    AnomalyItem,
    ReportConfig
)

from .report_generator import FinanceVarianceReportGenerator

__version__ = "1.0.0"

__all__ = [
    "FinancialData",
    "VarianceResult",
    "AnomalyItem",
    "ReportConfig",
    "FinanceVarianceReportGenerator"
]
