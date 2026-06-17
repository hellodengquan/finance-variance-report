import os
import math
import pandas as pd
from datetime import datetime
from typing import List, Optional
from .models import ReportConfig, AnomalyItem, VarianceResult


class MarkdownReporter:
    """Markdown 格式报告生成器"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()

    @staticmethod
    def _format_pct(value: Optional[float]) -> str:
        """格式化百分比，处理 None 和 inf 情况"""
        if value is None:
            return "N/A"
        if math.isinf(value):
            return "∞%" if value > 0 else "-∞%"
        if math.isnan(value):
            return "N/A"
        return f"{value:+.2f}%"

    @staticmethod
    def _is_revenue_account(account_code: str) -> bool:
        """判断是否为收入类科目"""
        return account_code.startswith('60') or account_code.startswith('63')

    def generate(self,
                 variance_results: List[VarianceResult],
                 variance_df: pd.DataFrame,
                 account_summary: pd.DataFrame,
                 period_summary: pd.DataFrame,
                 anomalies: List[AnomalyItem],
                 anomalies_df: pd.DataFrame,
                 output_path: str) -> str:
        """生成 Markdown 报告"""
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

        sort_mode = "超支/节省分组排序" if self.config.separate_anomaly_groups else "综合影响分数排序"

        yaml_info = ""
        if self.config.cause_templates_path:
            yaml_info = f"\n**成因模板配置**：`{self.config.cause_templates_path}`"

        color_cfg = self.config.excel_color_config

        return f"""# {self.config.title}

**公司名称**：{self.config.company_name}
**生成时间**：{now}
{period_info}
**异常阈值**：{self.config.anomaly_threshold * 100:.0f}%
**展示Top异常数**：{self.config.top_n_anomalies}
**异常排序模式**：{sort_mode}
**颜色分级阈值**：±{color_cfg.level1_threshold*100:.0f}% / ±{color_cfg.level2_threshold*100:.0f}% / ±{color_cfg.level3_threshold*100:.0f}%
{yaml_info}

---
"""

    def _generate_overview(self, account_summary: pd.DataFrame, period_summary: pd.DataFrame) -> str:
        """生成总体概览"""
        total_budget = account_summary['预算金额'].sum()
        total_actual = account_summary['实际金额'].sum()
        total_variance = account_summary['绝对差异'].sum()

        total_relative_pct = None
        if total_budget != 0:
            total_relative_pct = total_variance / total_budget * 100

        favorable_count = len(account_summary[account_summary['绝对差异'] > 0])
        unfavorable_count = len(account_summary[account_summary['绝对差异'] < 0])
        on_track_count = len(account_summary[account_summary['绝对差异'] == 0])

        variance_status = "✅ 完成预算" if total_variance >= 0 else "❌ 未达预算"
        variance_class = "有利差异" if total_variance >= 0 else "不利差异"

        rel_str = self._format_pct(total_relative_pct)

        return f"""## 一、总体概览

### 核心指标

| 指标 | 金额（{self.config.currency_symbol}） | 备注 |
|------|---------------------|------|
| 预算总额 | {self._format_number(total_budget)} | |
| 实际总额 | {self._format_number(total_actual)} | |
| **总差异** | **{self._format_number(total_variance)}** | **{variance_class} {variance_status}** |
| **总差异率** | **{rel_str}** | |

### 科目差异分布

- ✅ 有利差异科目：{favorable_count} 个
- ⚠️ 不利差异科目：{unfavorable_count} 个
- ➖ 预算持平科目：{on_track_count} 个

### 整体评价

{self._generate_overall_comment(total_variance, total_relative_pct, favorable_count, unfavorable_count)}
"""

    def _generate_overall_comment(self, total_variance: float, total_relative_pct: Optional[float],
                                  favorable_count: int, unfavorable_count: int) -> str:
        """生成整体评价"""
        if total_relative_pct is None or math.isnan(total_relative_pct):
            severity = "差异率计算异常（预算为0），建议人工核查。"
        elif abs(total_relative_pct) < 5:
            severity = "整体表现平稳，差异在可控范围内。"
        elif abs(total_relative_pct) < 10:
            severity = "存在一定程度的差异，需要关注主要异常科目。"
        else:
            severity = "差异较大，建议深入分析原因并采取相应措施。"

        var_str = self._format_number(abs(total_variance))
        rel_str = self._format_pct(abs(total_relative_pct) if total_relative_pct is not None else None)

        if total_variance >= 0:
            return f"本期整体实现{self._format_number(total_variance)}的有利差异，差异率{self._format_pct(total_relative_pct)}。{severity}"
        else:
            return f"本期整体出现{var_str}的不利差异，差异率{rel_str}。{severity}"

    def _generate_account_summary(self, account_summary: pd.DataFrame) -> str:
        """生成按科目汇总表"""
        rows = []
        for _, row in account_summary.iterrows():
            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            status = "✅" if row['绝对差异'] >= 0 else "⚠️"

            rel_raw = row.get('相对差异(%)')
            rel_str = self._format_pct(rel_raw)
            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw) and not math.isinf(rel_raw):
                rel_symbol = "+" if rel_raw >= 0 else ""
                rel_str = f"{rel_symbol}{rel_raw:.2f}%"

            rows.append(
                f"| {row['科目编码']} | {row['科目名称']} | {self._format_number(row['预算金额'])} | "
                f"{self._format_number(row['实际金额'])} | {status} {variance_symbol}{self._format_number(row['绝对差异'])} | "
                f"{rel_str} |"
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
            status = "✅" if row['绝对差异'] >= 0 else "⚠️"

            rel_raw = row.get('相对差异(%)')
            rel_str = self._format_pct(rel_raw)
            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw) and not math.isinf(rel_raw):
                rel_symbol = "+" if rel_raw >= 0 else ""
                rel_str = f"{rel_symbol}{rel_raw:.2f}%"

            rows.append(
                f"| {row['期间']} | {self._format_number(row['预算金额'])} | "
                f"{self._format_number(row['实际金额'])} | {status} {variance_symbol}{self._format_number(row['绝对差异'])} | "
                f"{rel_str} | {self._format_number(row['累计偏离'])} |"
            )

        return f"""## 三、期间趋势分析

| 期间 | 预算金额 | 实际金额 | 期间差异 | 差异率 | 累计偏离 |
|------|----------|----------|----------|--------|----------|
{chr(10).join(rows)}
"""

    def _generate_anomalies(self, anomalies_df: pd.DataFrame) -> str:
        """生成异常分析部分，支持分组显示"""
        if anomalies_df.empty:
            return """## 四、重大异常分析

> ✅ 未发现超过阈值的异常项，整体表现平稳。
"""

        has_group = '分组' in anomalies_df.columns

        if has_group and self.config.separate_anomaly_groups:
            bad_mask = anomalies_df['差异类型'] == '不利差异'
            good_mask = anomalies_df['差异类型'] == '有利差异'

            bad_df = anomalies_df[bad_mask].copy()
            good_df = anomalies_df[good_mask].copy()

            bad_rows = self._build_anomaly_rows(bad_df, start_rank=1)
            good_rows = self._build_anomaly_rows(good_df, start_rank=1)

            group_section = "（已按 超支组/节省组 分别按金额排序）"
        else:
            bad_rows = ""
            good_rows = ""
            all_rows = self._build_anomaly_rows(anomalies_df, start_rank=1, has_group=has_group)
            group_section = ""

        headers = ["排名"]
        if has_group:
            headers.append("分组")
        headers.extend(["科目名称", "期间", "绝对差异", "相对差异", "影响分数", "差异类型", "成因分析（待核实）"])
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "|" + "|".join(["----------"] * len(headers)) + "|"

        if has_group and self.config.separate_anomaly_groups:
            n = len(headers)
            empty_placeholder = "| " + " *（无）* |" * n

            return f"""## 四、重大异常分析（Top {len(anomalies_df)}）{group_section}

> **说明**：相对差异超过 {self.config.anomaly_threshold * 100:.0f}% 的项标记为异常。
> 超支组（不利影响）在前，节省组（有利影响）在后，组内按绝对差异金额从大到小排序。

### 4.1 超支组（不利差异）

{header_line}
{sep_line}
{bad_rows if bad_rows else empty_placeholder}

### 4.2 节省组（有利差异）

{header_line}
{sep_line}
{good_rows if good_rows else empty_placeholder}

### 行动建议

1. 针对上述异常项，财务部门应协同业务部门核实具体原因
2. 对于重大不利差异，需制定相应的改进措施和时间节点
3. 对于重大有利差异，需总结经验并考虑是否调整后续预算
4. 所有成因核实后，请更新本报告中的"成因分析"字段
5. 成因模板可在 `config/cause_templates.yaml` 中自定义，无需修改代码
"""
        else:
            return f"""## 四、重大异常分析（Top {len(anomalies_df)}）

> **说明**：根据相对差异超过 {self.config.anomaly_threshold * 100:.0f}% 且综合影响分数排序，以下科目需重点关注。

{header_line}
{sep_line}
{all_rows}

### 行动建议

1. 针对上述异常项，财务部门应协同业务部门核实具体原因
2. 对于重大不利差异，需制定相应的改进措施和时间节点
3. 对于重大有利差异，需总结经验并考虑是否调整后续预算
4. 所有成因核实后，请更新本报告中的"成因分析"字段
5. 成因模板可在 `config/cause_templates.yaml` 中自定义，无需修改代码
"""

    def _build_anomaly_rows(self, df: pd.DataFrame, start_rank: int = 1, has_group: bool = None) -> str:
        """构建异常行字符串"""
        if df.empty:
            return ""

        if has_group is None:
            has_group = '分组' in df.columns

        rows = []
        for local_idx, (_, row) in enumerate(df.iterrows(), 0):
            rank = start_rank + local_idx

            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            type_icon = "✅" if row['差异类型'] == '有利差异' else "⚠️"

            rel_raw = row.get('相对差异(%)')
            rel_str = self._format_pct(rel_raw)
            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw) and not math.isinf(rel_raw):
                rel_symbol = "+" if rel_raw >= 0 else ""
                rel_str = f"{rel_symbol}{rel_raw:.2f}%"

            cells = [
                str(rank),
            ]
            if has_group:
                cells.append(str(row.get('分组', '')))
            cells.extend([
                str(row['科目名称']),
                str(row['期间']),
                f"{variance_symbol}{self._format_number(row['绝对差异'])}",
                rel_str,
                str(row['影响分数']),
                f"{type_icon} {row['差异类型']}",
                str(row['成因分析（待核实）'])
            ])
            rows.append("| " + " | ".join(cells) + " |")

        return chr(10).join(rows)

    def _generate_cumulative_analysis(self, variance_df: pd.DataFrame) -> str:
        """生成累计偏离分析"""
        latest_period = variance_df['期间'].iloc[-1]
        latest_data = variance_df[variance_df['期间'] == latest_period].copy()
        latest_data = latest_data.sort_values('累计偏离', key=lambda x: x.abs(), ascending=False)

        rows = []
        for _, row in latest_data.iterrows():
            variance_symbol = "+" if row['累计偏离'] >= 0 else ""
            status = "✅" if row['累计偏离'] >= 0 else "⚠️"

            cum_rel_raw = row.get('累计相对偏离(%)')
            cum_rel_str = self._format_pct(cum_rel_raw)
            if isinstance(cum_rel_raw, (int, float)) and not math.isnan(cum_rel_raw) and not math.isinf(cum_rel_raw):
                cum_rel_str = f"{cum_rel_raw:.2f}%"

            rows.append(
                f"| {row['科目编码']} | {row['科目名称']} | {self._format_number(row['累计预算'])} | "
                f"{self._format_number(row['累计实际'])} | {status} {variance_symbol}{self._format_number(row['累计偏离'])} | "
                f"{cum_rel_str} |"
            )

        return f"""## 五、累计偏离分析（截至 {latest_period}）

| 科目编码 | 科目名称 | 累计预算 | 累计实际 | 累计偏离 | 累计偏离率 |
|----------|----------|----------|----------|----------|------------|
{chr(10).join(rows)}
"""

    def _generate_footer(self) -> str:
        """生成页脚"""
        cc = self.config.excel_color_config
        return f"""---

## 六、说明

1. **绝对差异** = 实际金额 - 预算金额
2. **相对差异** = 绝对差异 / 预算金额 × 100%
   - 预算为0时：实际>0 显示 `∞%`，实际<0 显示 `-∞%`，实际=0 显示 `N/A`
3. **累计偏离** = 自分析起始期间至当前期间的累计实际 - 累计预算
4. **影响分数** = 绝对差异/期间总预算 × 70% + 相对差异 × 30%
5. **异常分组排序**：
   - 超支组（不利）：收入未达预期 + 成本费用超支
   - 节省组（有利）：收入超预期 + 成本费用节省
   - 组内按绝对差异金额从大到小分别排序
6. **Excel颜色分级**（三档可调，在 ReportConfig.excel_color_config 配置）：
   - 0 ~ ±{cc.level1_threshold*100:.0f}%：正常色（无色）
   - ±{cc.level1_threshold*100:.0f}% ~ ±{cc.level2_threshold*100:.0f}%：浅色
   - ±{cc.level2_threshold*100:.0f}% ~ ±{cc.level3_threshold*100:.0f}%：中色
   - > ±{cc.level3_threshold*100:.0f}%：深色（加粗）
7. 报告中"【待核实】"标记的成因分析为系统自动生成的占位符
   - 运营团队可在 `config/cause_templates.yaml` 中自定义模板
   - 无需修改代码即可扩展或替换成因模板
8. 本报告由财务差异报告生成器自动生成，如有疑问请联系财务部门

---
*生成工具：财务差异报告生成器 v1.1*
"""

    def _format_number(self, value: float) -> str:
        """格式化数字显示"""
        if value is None:
            return "N/A"
        try:
            if math.isnan(value) or math.isinf(value):
                return str(value)
        except (TypeError, ValueError):
            return str(value)

        if abs(value) >= 100000000:
            return f"{self.config.currency_symbol}{value / 100000000:.2f}亿"
        elif abs(value) >= 10000:
            return f"{self.config.currency_symbol}{value / 10000:.2f}万"
        else:
            return f"{self.config.currency_symbol}{value:,.2f}"
