from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class FinancialData:
    """财务数据基类"""
    data: pd.DataFrame
    periods: List[str] = field(default_factory=list)
    account_codes: List[str] = field(default_factory=list)
    account_names: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.periods:
            self.periods = [col for col in self.data.columns if col not in ['科目编码', '科目名称']]
        if not self.account_codes:
            self.account_codes = self.data['科目编码'].astype(str).tolist()
        if not self.account_names:
            self.account_names = dict(zip(
                self.data['科目编码'].astype(str),
                self.data['科目名称']
            ))

    def get_value(self, account_code: str, period: str) -> float:
        """获取指定科目、指定期间的数值"""
        mask = self.data['科目编码'].astype(str) == account_code
        if mask.any():
            return float(self.data.loc[mask, period].values[0])
        return 0.0

    def get_period_values(self, period: str) -> Dict[str, float]:
        """获取指定期间所有科目的数值"""
        return dict(zip(
            self.data['科目编码'].astype(str),
            self.data[period].astype(float)
        ))


@dataclass
class VarianceResult:
    """差异计算结果"""
    account_code: str
    account_name: str
    period: str
    budget: float
    actual: float
    absolute_variance: float
    relative_variance: float
    cumulative_budget: float
    cumulative_actual: float
    cumulative_variance: float
    cumulative_relative_variance: float


@dataclass
class AnomalyItem:
    """异常项"""
    account_code: str
    account_name: str
    period: str
    absolute_variance: float
    relative_variance: float
    impact_score: float
    cause_placeholder: str
    variance_type: str


@dataclass
class ReportConfig:
    """报告配置"""
    title: str = "财务差异分析报告"
    company_name: str = "示例公司"
    start_period: Optional[str] = None
    end_period: Optional[str] = None
    anomaly_threshold: float = 0.10
    top_n_anomalies: int = 10
    include_cumulative: bool = True
    currency: str = "CNY"
    currency_symbol: str = "¥"
