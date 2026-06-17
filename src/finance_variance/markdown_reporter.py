import os
import pandas as pd
from datetime import datetime
from typing import List, Optional
from .models import ReportConfig, AnomalyItem, VarianceResult


class MarkdownReporter:
    """Markdown 格式报告生成器"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()

    def generate(self,
                 variance_results: List[VarianceResult],
                 variance_df: pd.DataFrame,
                 account_summary: pd.DataFrame,
                 period_summary: pd.DataFrame,
                 anomalies: List[AnomalyItem],
                 anomalies_df: pd.DataFrame,
                 output_path: str) -> str:
        """
        生成 Markdown 报告

        Args:
            variance_results: 详细差异计算结果
            variance_df: 差异数据DataFrame
            account_summary: 按科目汇总
            period_summary: 按期间汇总
            anomalies: 异常项列表
            anomalies_df: 异常项DataFrame
            output_path: 输出文件路径

        Returns:
            生成的报告内容
        """
        content = []

        content.append(self._generate_header())
        content.append(self._generate_overview(account_summary, period_summary))
        content.append(self._generate_account_summary(account_summary))
        content.append(self._generate_period_summary(period_summary))
        content.append(self._generate_anomalies(anomalies_df))

        if self.config.include_cumulative:
            content.append(self._generate_cumulative_analysis(variance_df))

        content.append(self._generate_footer())

        report_content = '\n\n'.join(content)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        return report_content

    def _generate_header(self) -> str:
        """生成报告头部"""
        now = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

        period_info = ""
        if self.config.start_period and self.config.end_period:
            period_info = f"**分析期间**：{self.config.start_period} 至 {self.config.end_period}"
        elif self.config.start_period:
            period_info = f"**分析期间**：{self.config.start_period} 起"
        elif self.config.end_period:
            period_info = f"**分析期间**：截至 {self.config.end_period}"

        return f"""# {self.config.title}

**公司名称**：{self.config.company_name}
**生成时间**：{now}
{period_info}
**异常阈值**：{self.config.anomaly_threshold * 100:.0f}%
**展示Top异常数**：{self.config.top_n_anomalies}

---
"""

    def _generate_overview(self, account_summary: pd.DataFrame, period_summary: pd.DataFrame) -> str:
        """生成总体概览"""
        total_budget = account_summary['预算金额'].sum()
        total_actual = account_summary['实际金额'].sum()
        total_variance = account_summary['绝对差异'].sum()
        total_relative = (total_variance / total_budget * 100) if total_budget != 0 else 0

        favorable_count = len(account_summary[account_summary['绝对差异'] > 0])
        unfavorable_count = len(account_summary[account_summary['绝对差异'] < 0])
        on_track_count = len(account_summary[account_summary['绝对差异'] == 0])

        variance_status = "✅ 完成预算" if total_variance >= 0 else "❌ 未达预算"
        variance_class = "有利差异" if total_variance >= 0 else "不利差异"

        return f"""## 一、总体概览

### 核心指标

| 指标 | 金额（{self.config.currency_symbol}） | 备注 |
|------|---------------------|------|
| 预算总额 | {self._format_number(total_budget)} | |
| 实际总额 | {self._format_number(total_actual)} | |
| **总差异** | **{self._format_number(total_variance)}** | **{variance_class} {variance_status}** |
| **总差异率** | **{total_relative:.2f}%** | |

### 科目差异分布

- ✅ 有利差异科目：{favorable_count} 个
- ⚠️ 不利差异科目：{unfavorable_count} 个
- ➖ 预算持平科目：{on_track_count} 个

### 整体评价

{self._generate_overall_comment(total_variance, total_relative, favorable_count, unfavorable_count)}
"""

    def _generate_overall_comment(self, total_variance: float, total_relative: float,
                                  favorable_count: int, unfavorable_count: int) -> str:
        """生成整体评价"""
        if abs(total_relative) < 5:
            severity = "整体表现平稳，差异在可控范围内。"
        elif abs(total_relative) < 10:
            severity = "存在一定程度的差异，需要关注主要异常科目。"
        else:
            severity = "差异较大，建议深入分析原因并采取相应措施。"

        if total_variance >= 0:
            return f"本期整体实现{self._format_number(total_variance)}的有利差异，差异率{total_relative:.2f}%。{severity}"
        else:
            return f"本期整体出现{self._format_number(abs(total_variance))}的不利差异，差异率{abs(total_relative):.2f}%。{severity}"

    def _generate_account_summary(self, account_summary: pd.DataFrame) -> str:
        """生成按科目汇总表"""
        rows = []
        for _, row in account_summary.iterrows():
            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            rel_variance_symbol = "+" if row['相对差异(%)'] >= 0 else ""
            status = "✅" if row['绝对差异'] >= 0 else "⚠️"

            rows.append(
                f"| {row['科目编码']} | {row['科目名称']} | {self._format_number(row['预算金额'])} | "
                f"{self._format_number(row['实际金额'])} | {status} {variance_symbol}{self._format_number(row['绝对差异'])} | "
                f"{rel_variance_symbol}{row['相对差异(%)']:.2f}% |"
            )

        return f"""## 二、科目差异汇总（按影响金额排序）

| 科目编码 | 科目名称 | 预算金额 | 实际金额 | 绝对差异 | 相对差异 |
|----------|----------|----------|----------|----------|----------|
{chr(10).join(rows)}
"""

    def _generate_period_summary(self, period_summary: pd.DataFrame) -> str:
        """生成按期间汇总表"""
        rows = []
        for _, row in period_summary.iterrows():
            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            rel_variance_symbol = "+" if row['相对差异(%)'] >= 0 else ""
            status = "✅" if row['绝对差异'] >= 0 else "⚠️"

            rows.append(
                f"| {row['期间']} | {self._format_number(row['预算金额'])} | "
                f"{self._format_number(row['实际金额'])} | {status} {variance_symbol}{self._format_number(row['绝对差异'])} | "
                f"{rel_variance_symbol}{row['相对差异(%)']:.2f}% | {self._format_number(row['累计偏离'])} |"
            )

        return f"""## 三、期间趋势分析

| 期间 | 预算金额 | 实际金额 | 期间差异 | 差异率 | 累计偏离 |
|------|----------|----------|----------|--------|----------|
{chr(10).join(rows)}
"""

    def _generate_anomalies(self, anomalies_df: pd.DataFrame) -> str:
        """生成异常分析部分"""
        if anomalies_df.empty:
            return """## 四、重大异常分析

> ✅ 未发现超过阈值的异常项，整体表现平稳。
"""

        rows = []
        for _, row in anomalies_df.iterrows():
            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            rel_variance_symbol = "+" if row['相对差异(%)'] >= 0 else ""
            type_icon = "✅" if row['差异类型'] == '有利差异' else "⚠️"

            rows.append(
                f"| {row['排名']} | {row['科目名称']} | {row['期间']} | "
                f"{variance_symbol}{self._format_number(row['绝对差异'])} | "
                f"{rel_variance_symbol}{row['相对差异(%)']:.2f}% | {row['影响分数']} | "
                f"{type_icon} {row['差异类型']} | {row['成因分析（待核实）']} |"
            )

        return f"""## 四、重大异常分析（Top {len(anomalies_df)}）

> **说明**：根据相对差异超过 {self.config.anomaly_threshold * 100:.0f}% 且综合影响分数排序，以下科目需重点关注。

| 排名 | 科目名称 | 期间 | 绝对差异 | 相对差异 | 影响分数 | 差异类型 | 成因分析（待核实） |
|------|----------|------|----------|----------|----------|----------|-------------------|
{chr(10).join(rows)}

### 行动建议

1. 针对上述异常项，财务部门应协同业务部门核实具体原因
2. 对于重大不利差异，需制定相应的改进措施和时间节点
3. 对于重大有利差异，需总结经验并考虑是否调整后续预算
4. 所有成因核实后，请更新本报告中的"成因分析"字段
"""

    def _generate_cumulative_analysis(self, variance_df: pd.DataFrame) -> str:
        """生成累计偏离分析"""
        latest_period = variance_df['期间'].iloc[-1]
        latest_data = variance_df[variance_df['期间'] == latest_period].copy()
        latest_data = latest_data.sort_values('累计偏离', key=lambda x: x.abs(), ascending=False)

        rows = []
        for _, row in latest_data.iterrows():
            variance_symbol = "+" if row['累计偏离'] >= 0 else ""
            status = "✅" if row['累计偏离'] >= 0 else "⚠️"

            rows.append(
                f"| {row['科目编码']} | {row['科目名称']} | {self._format_number(row['累计预算'])} | "
                f"{self._format_number(row['累计实际'])} | {status} {variance_symbol}{self._format_number(row['累计偏离'])} | "
                f"{row['累计相对偏离(%)']:.2f}% |"
            )

        return f"""## 五、累计偏离分析（截至 {latest_period}）

| 科目编码 | 科目名称 | 累计预算 | 累计实际 | 累计偏离 | 累计偏离率 |
|----------|----------|----------|----------|----------|------------|
{chr(10).join(rows)}
"""

    def _generate_footer(self) -> str:
        """生成页脚"""
        return f"""---

## 六、说明

1. **绝对差异** = 实际金额 - 预算金额
2. **相对差异** = 绝对差异 / 预算金额 × 100%
3. **累计偏离** = 自分析起始期间至当前期间的累计实际 - 累计预算
4. **影响分数** = 绝对差异/期间总预算 × 70% + 相对差异 × 30%
5. 报告中"【待核实】"标记的成因分析为系统根据科目特性自动生成的占位符，需人工核实确认
6. 本报告由财务差异报告生成器自动生成，如有疑问请联系财务部门

---
*生成工具：财务差异报告生成器 v1.0*
"""

    def _format_number(self, value: float) -> str:
        """格式化数字显示"""
        if abs(value) >= 100000000:
            return f"{self.config.currency_symbol}{value / 100000000:.2f}亿"
        elif abs(value) >= 10000:
            return f"{self.config.currency_symbol}{value / 10000:.2f}万"
        else:
            return f"{self.config.currency_symbol}{value:,.2f}"
