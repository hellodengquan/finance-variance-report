from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import re
import math


class PeriodParser:
    """多期日期解析器，支持多种格式"""

    QUARTER_PATTERN = re.compile(
        r'(\d{4})\s*年\s*第\s*([1-4])\s*季度',
        re.IGNORECASE
    )
    MONTH_PATTERN = re.compile(
        r'(\d{1,2})\s*月'
    )
    YEAR_MONTH_PATTERN = re.compile(
        r'(\d{4})[\-/_年](\d{1,2})'
    )

    @staticmethod
    def parse(period_str: str) -> Tuple[float, str]:
        """
        解析期间字符串，返回(排序键, 标准化名称)

        支持格式：
        - "1月", "2月" ... "12月"
        - "2024年第1季度", "2024年第2季度" ...
        - "2024-01", "2024_01", "2024/01", "2024年01月"
        - "Q1 2024", "2024 Q1"
        """
        s = str(period_str).strip()

        m = PeriodParser.QUARTER_PATTERN.search(s)
        if m:
            year = int(m.group(1))
            quarter = int(m.group(2))
            sort_key = year * 100 + quarter * 25
            std_name = f"{year}年第{quarter}季度"
            return (sort_key, std_name)

        m = PeriodParser.YEAR_MONTH_PATTERN.search(s)
        if m:
            year = int(m.group(1))
            month = int(m.group(2))
            sort_key = year * 100 + month
            std_name = f"{year}年{month}月"
            return (sort_key, std_name)

        m = PeriodParser.MONTH_PATTERN.search(s)
        if m:
            month = int(m.group(1))
            sort_key = float(month)
            std_name = f"{month}月"
            return (sort_key, std_name)

        try:
            sort_key = float(s)
            return (sort_key, s)
        except (ValueError, TypeError):
            return (hash(s) % 100000, s)

    @staticmethod
    def sort_periods(periods: List[str]) -> List[str]:
        """对期间列表进行智能排序"""
        parsed = [(PeriodParser.parse(p)[0], p) for p in periods]
        parsed.sort(key=lambda x: x[0])
        return [p[1] for p in parsed]


@dataclass
class FinancialData:
    """财务数据基类"""
    data: pd.DataFrame
    periods: List[str] = field(default_factory=list)
    account_codes: List[str] = field(default_factory=list)
    account_names: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        raw_periods = [col for col in self.data.columns if col not in ['科目编码', '科目名称']]
        self.periods = PeriodParser.sort_periods(raw_periods)

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
            val = self.data.loc[mask, period].values[0]
            if pd.isna(val):
                return 0.0
            return float(val)
        return 0.0

    def get_period_values(self, period: str) -> Dict[str, float]:
        """获取指定期间所有科目的数值"""
        values = dict(zip(
            self.data['科目编码'].astype(str),
            self.data[period].astype(float)
        ))
        return {k: (0.0 if pd.isna(v) else float(v)) for k, v in values.items()}


@dataclass
class VarianceResult:
    """差异计算结果"""
    account_code: str
    account_name: str
    period: str
    budget: float
    actual: float
    absolute_variance: float
    relative_variance: Optional[float]
    cumulative_budget: float
    cumulative_actual: float
    cumulative_variance: float
    cumulative_relative_variance: Optional[float]


@dataclass
class AnomalyItem:
    """异常项"""
    account_code: str
    account_name: str
    period: str
    absolute_variance: float
    relative_variance: Optional[float]
    impact_score: float
    cause_placeholder: str
    variance_type: str


@dataclass
class ExcelColorConfig:
    """Excel单元格颜色三档阈值配置"""

    level1_threshold: float = 0.05
    level2_threshold: float = 0.10
    level3_threshold: float = 0.20

    favorable_level1_bg: str = "#E2EFDA"
    favorable_level1_font: str = "#375623"
    favorable_level2_bg: str = "#C6EFCE"
    favorable_level2_font: str = "#006100"
    favorable_level3_bg: str = "#70AD47"
    favorable_level3_font: str = "#FFFFFF"

    unfavorable_level1_bg: str = "#FCE4D6"
    unfavorable_level1_font: str = "#833C0B"
    unfavorable_level2_bg: str = "#FFC7CE"
    unfavorable_level2_font: str = "#9C0006"
    unfavorable_level3_bg: str = "#FF0000"
    unfavorable_level3_font: str = "#FFFFFF"

    neutral_bg: str = "#FFFFFF"
    neutral_font: str = "#000000"

    def get_format_key(self, relative_variance: Optional[float]) -> str:
        """根据相对差异获取格式键"""
        if relative_variance is None or math.isnan(relative_variance):
            return 'neutral'

        abs_val = abs(relative_variance)
        if relative_variance >= 0:
            if abs_val >= self.level3_threshold:
                return 'favorable_level3'
            elif abs_val >= self.level2_threshold:
                return 'favorable_level2'
            elif abs_val >= self.level1_threshold:
                return 'favorable_level1'
            else:
                return 'neutral'
        else:
            if abs_val >= self.level3_threshold:
                return 'unfavorable_level3'
            elif abs_val >= self.level2_threshold:
                return 'unfavorable_level2'
            elif abs_val >= self.level1_threshold:
                return 'unfavorable_level1'
            else:
                return 'neutral'


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

    cause_templates_path: Optional[str] = None

    excel_color_config: ExcelColorConfig = field(default_factory=ExcelColorConfig)

    separate_anomaly_groups: bool = True
