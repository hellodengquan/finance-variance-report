import math
import pandas as pd
from typing import List, Dict, Optional
from .models import FinancialData, VarianceResult, ReportConfig


class VarianceCalculator:
    """差异计算引擎"""

    def __init__(self, budget_data: FinancialData, actual_data: FinancialData,
                 config: Optional[ReportConfig] = None):
        self.budget_data = budget_data
        self.actual_data = actual_data
        self.config = config or ReportConfig()

        self._validate_periods()

    def _validate_periods(self) -> None:
        """验证期间一致性"""
        if set(self.budget_data.periods) != set(self.actual_data.periods):
            raise ValueError(
                f"预算数据和实际数据的期间不一致\n"
                f"预算期间: {sorted(self.budget_data.periods)}\n"
                f"实际期间: {sorted(self.actual_data.periods)}"
            )

    def _get_target_periods(self) -> List[str]:
        """获取需要计算的期间范围"""
        all_periods = self.budget_data.periods

        if self.config.start_period and self.config.end_period:
            start_idx = all_periods.index(self.config.start_period)
            end_idx = all_periods.index(self.config.end_period)
            return all_periods[start_idx:end_idx + 1]
        elif self.config.start_period:
            start_idx = all_periods.index(self.config.start_period)
            return all_periods[start_idx:]
        elif self.config.end_period:
            end_idx = all_periods.index(self.config.end_period)
            return all_periods[:end_idx + 1]

        return all_periods

    @staticmethod
    def safe_divide(numerator: float, denominator: float) -> Optional[float]:
        """
        安全除法，避免ZeroDivisionError

        - denominator == 0 and numerator > 0: 返回 +inf
        - denominator == 0 and numerator < 0: 返回 -inf
        - denominator == 0 and numerator == 0: 返回 None
        - 正常情况: 返回 numerator / denominator
        """
        if denominator == 0:
            if numerator > 0:
                return float('inf')
            elif numerator < 0:
                return float('-inf')
            else:
                return None
        return numerator / denominator

    @staticmethod
    def format_relative_variance_pct(rel_var: Optional[float]) -> Optional[float]:
        """格式化相对差异为百分比（保留2位小数），处理None和inf情况"""
        if rel_var is None:
            return None
        if math.isinf(rel_var):
            return float('inf') if rel_var > 0 else float('-inf')
        return round(rel_var * 100, 2)

    def calculate_variances(self) -> List[VarianceResult]:
        """计算所有科目和期间的差异"""
        target_periods = self._get_target_periods()
        results = []

        for account_code in self.budget_data.account_codes:
            account_name = self.budget_data.account_names[account_code]

            cum_budget = 0.0
            cum_actual = 0.0

            for period in target_periods:
                budget = self.budget_data.get_value(account_code, period)
                actual = self.actual_data.get_value(account_code, period)

                cum_budget += budget
                cum_actual += actual

                abs_variance = actual - budget
                rel_variance = self.safe_divide(abs_variance, budget)

                cum_variance = cum_actual - cum_budget
                cum_rel_variance = self.safe_divide(cum_variance, cum_budget)

                results.append(VarianceResult(
                    account_code=account_code,
                    account_name=account_name,
                    period=period,
                    budget=budget,
                    actual=actual,
                    absolute_variance=abs_variance,
                    relative_variance=rel_variance,
                    cumulative_budget=cum_budget,
                    cumulative_actual=cum_actual,
                    cumulative_variance=cum_variance,
                    cumulative_relative_variance=cum_rel_variance
                ))

        return results

    def to_dataframe(self, results: List[VarianceResult]) -> pd.DataFrame:
        """将计算结果转换为DataFrame"""
        data = []
        for r in results:
            data.append({
                '科目编码': r.account_code,
                '科目名称': r.account_name,
                '期间': r.period,
                '预算金额': r.budget,
                '实际金额': r.actual,
                '绝对差异': r.absolute_variance,
                '相对差异(%)': self.format_relative_variance_pct(r.relative_variance),
                '累计预算': r.cumulative_budget,
                '累计实际': r.cumulative_actual,
                '累计偏离': r.cumulative_variance,
                '累计相对偏离(%)': self.format_relative_variance_pct(r.cumulative_relative_variance)
            })

        return pd.DataFrame(data)

    def get_summary_by_account(self, results: List[VarianceResult]) -> pd.DataFrame:
        """按科目汇总差异"""
        df = self.to_dataframe(results)

        summary = df.groupby(['科目编码', '科目名称']).agg({
            '预算金额': 'sum',
            '实际金额': 'sum',
            '绝对差异': 'sum',
            '累计偏离': 'last'
        }).reset_index()

        rel_vars = []
        for _, row in summary.iterrows():
            rv = self.safe_divide(row['绝对差异'], row['预算金额'])
            rel_vars.append(self.format_relative_variance_pct(rv))
        summary['相对差异(%)'] = rel_vars

        summary = summary.sort_values('绝对差异', key=lambda x: x.abs(), ascending=False)
        return summary

    def get_summary_by_period(self, results: List[VarianceResult]) -> pd.DataFrame:
        """按期间汇总差异"""
        df = self.to_dataframe(results)

        summary = df.groupby('期间').agg({
            '预算金额': 'sum',
            '实际金额': 'sum',
            '绝对差异': 'sum',
            '累计偏离': 'last'
        }).reset_index()

        from .models import PeriodParser
        summary['_sort_key'] = summary['期间'].apply(lambda x: PeriodParser.parse(x)[0])
        summary = summary.sort_values('_sort_key').drop(columns=['_sort_key']).reset_index(drop=True)

        rel_vars = []
        for _, row in summary.iterrows():
            rv = self.safe_divide(row['绝对差异'], row['预算金额'])
            rel_vars.append(self.format_relative_variance_pct(rv))
        summary['相对差异(%)'] = rel_vars

        return summary
