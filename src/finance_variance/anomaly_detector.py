import pandas as pd
from typing import List, Dict, Optional
from .models import VarianceResult, AnomalyItem, ReportConfig


class AnomalyDetector:
    """异常检测和排序模块"""

    CAUSE_TEMPLATES = {
        'revenue_positive': [
            "【待核实】市场需求超预期增长，销售表现优于预算",
            "【待核实】新产品/服务推广效果显著，带动收入增长",
            "【待核实】主要客户订单增加或新增大客户",
            "【待核实】产品定价策略调整带来溢价",
            "【待核实】季节性因素或行业周期影响"
        ],
        'revenue_negative': [
            "【待核实】市场竞争加剧，销售未达预期",
            "【待核实】产品交付延迟或质量问题导致收入确认延后",
            "【待核实】主要客户需求下降或流失",
            "【待核实】促销活动效果不及预期",
            "【待核实】宏观经济环境或政策变化影响"
        ],
        'cost_positive': [
            "【待核实】原材料采购价格上涨超出预期",
            "【待核实】业务规模扩张导致相关成本增加",
            "【待核实】低效运营或浪费导致成本超支",
            "【待核实】意外支出或一次性费用发生",
            "【待核实】供应商议价能力变化或合同条款调整"
        ],
        'cost_negative': [
            "【待核实】成本控制措施见效，采购价格下降",
            "【待核实】业务量低于预期导致变动成本减少",
            "【待核实】运营效率提升带来成本节约",
            "【待核实】预算编制偏保守，实际支出优化",
            "【待核实】费用延后确认或计入期间调整"
        ]
    }

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()

    def detect_anomalies(self, variance_results: List[VarianceResult],
                         variance_df: Optional[pd.DataFrame] = None) -> List[AnomalyItem]:
        """
        检测异常项并按影响排序

        Args:
            variance_results: 差异计算结果列表
            variance_df: 差异数据DataFrame（可选，用于计算整体影响）

        Returns:
            按影响分数排序的异常项列表
        """
        if variance_df is None:
            variance_df = self._results_to_df(variance_results)

        total_budget = variance_df.groupby('期间')['预算金额'].sum().mean()

        anomalies = []

        for result in variance_results:
            if abs(result.relative_variance) >= self.config.anomaly_threshold:
                impact_score = self._calculate_impact_score(result, total_budget)

                variance_type = self._get_variance_type(result)
                cause_placeholder = self._get_cause_placeholder(result, variance_type)

                anomalies.append(AnomalyItem(
                    account_code=result.account_code,
                    account_name=result.account_name,
                    period=result.period,
                    absolute_variance=result.absolute_variance,
                    relative_variance=result.relative_variance,
                    impact_score=impact_score,
                    cause_placeholder=cause_placeholder,
                    variance_type=variance_type
                ))

        anomalies.sort(key=lambda x: abs(x.impact_score), reverse=True)

        return anomalies[:self.config.top_n_anomalies]

    def _calculate_impact_score(self, result: VarianceResult, total_budget: float) -> float:
        """
        计算影响分数，综合考虑绝对差异和相对差异

        影响分数 = 绝对差异 / 期间总预算 * 100% * 权重1 + 相对差异 * 权重2
        """
        abs_impact = result.absolute_variance / total_budget * 100 if total_budget != 0 else 0
        rel_impact = result.relative_variance * 100

        return abs_impact * 0.7 + rel_impact * 0.3

    def _get_variance_type(self, result: VarianceResult) -> str:
        """判断差异类型"""
        account_code = result.account_code
        abs_var = result.absolute_variance

        if account_code.startswith('6'):
            if account_code.startswith('60') or account_code.startswith('63'):
                return 'revenue_positive' if abs_var > 0 else 'revenue_negative'
            else:
                return 'cost_positive' if abs_var > 0 else 'cost_negative'

        return 'cost_positive' if abs_var > 0 else 'cost_negative'

    def _get_cause_placeholder(self, result: VarianceResult, variance_type: str) -> str:
        """根据科目和差异类型获取成因占位符"""
        templates = self.CAUSE_TEMPLATES.get(variance_type, self.CAUSE_TEMPLATES['cost_positive'])
        template_index = abs(hash(result.account_code + result.period)) % len(templates)
        return templates[template_index]

    def _results_to_df(self, results: List[VarianceResult]) -> pd.DataFrame:
        """将结果转换为DataFrame"""
        data = []
        for r in results:
            data.append({
                '科目编码': r.account_code,
                '科目名称': r.account_name,
                '期间': r.period,
                '预算金额': r.budget,
                '实际金额': r.actual,
                '绝对差异': r.absolute_variance,
                '相对差异(%)': r.relative_variance * 100
            })
        return pd.DataFrame(data)

    def anomalies_to_dataframe(self, anomalies: List[AnomalyItem]) -> pd.DataFrame:
        """将异常项转换为DataFrame"""
        data = []
        for idx, a in enumerate(anomalies, 1):
            data.append({
                '排名': idx,
                '科目编码': a.account_code,
                '科目名称': a.account_name,
                '期间': a.period,
                '绝对差异': a.absolute_variance,
                '相对差异(%)': round(a.relative_variance * 100, 2),
                '影响分数': round(a.impact_score, 2),
                '差异类型': '有利差异' if 'positive' in a.variance_type else '不利差异',
                '成因分析（待核实）': a.cause_placeholder
            })

        return pd.DataFrame(data)
