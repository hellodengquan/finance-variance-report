"""财务差异报告生成器"""

from .models import (
    FinancialData,
    VarianceResult,
    AnomalyItem,
    ReportConfig,
    ExcelColorConfig,
    PeriodParser
)

from .report_generator import FinanceVarianceReportGenerator

__version__ = "1.1.0"

__all__ = [
    "FinancialData",
    "VarianceResult",
    "AnomalyItem",
    "ReportConfig",
    "ExcelColorConfig",
    "PeriodParser",
    "FinanceVarianceReportGenerator"
]
