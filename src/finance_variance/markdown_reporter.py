import os
import math
import pandas as pd
from datetime import datetime
from typing import List, Optional
from .models import ReportConfig, AnomalyItem, VarianceResult
from .variance_calculator import VarianceCalculator


class MarkdownReporter:
    """Markdown 格式报告生成器"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()

    @staticmethod
    def _format_pct_from_values(value: Optional[float], budget: float, actual: float) -> str:
        """
        格式化百分比，通过 budget/actual 值精确判定语义

        统一 NaN 语义下：
        - budget != 0      -> 显示 +X.XX% / -X.XX%
        - budget == 0 且 actual > 0  -> 显示 ∞%
        - budget == 0 且 actual < 0  -> 显示 -∞%
        - budget == 0 且 actual == 0 -> 显示 N/A
        """
        case = VarianceCalculator.classify_divide_case(actual - budget, budget)
        if case == 'positive_inf':
            return "∞%"
        if case == 'negative_inf':
            return "-∞%"
        if case == 'both_zero':
            return "N/A"

        if value is None:
            return "N/A"
        try:
            if math.isnan(value):
                return "N/A"
            if math.isinf(value):
                return "∞%" if value > 0 else "-∞%"
        except (TypeError, ValueError):
            return "N/A"
        return f"{value:+.2f}%"

    @staticmethod
    def _is_revenue_account(account_code: str) -> bool:
        """判断是否为收入类科目"""
        return str(account_code).startswith('60') or str(account_code).startswith('63')

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
            yaml_info = f"\n**成因&颜色模板配置**：`{self.config.cause_templates_path}`"

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

        total_relative_ratio = VarianceCalculator.safe_divide(total_variance, total_budget)
        rel_str = self._format_pct_from_values(total_relative_ratio, total_budget, total_actual)

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
| **总差异率** | **{rel_str}** | |

### 科目差异分布

- ✅ 有利差异科目：{favorable_count} 个
- ⚠️ 不利差异科目：{unfavorable_count} 个
- ➖ 预算持平科目：{on_track_count} 个

### 整体评价

{self._generate_overall_comment(total_variance, total_relative_ratio, total_budget, total_actual,
                                 favorable_count, unfavorable_count)}
"""

    def _generate_overall_comment(self, total_variance: float, total_relative_ratio: float,
                                  total_budget: float, total_actual: float,
                                  favorable_count: int, unfavorable_count: int) -> str:
        """生成整体评价"""
        case = VarianceCalculator.classify_divide_case(total_variance, total_budget)
        if case in ('positive_inf', 'negative_inf', 'both_zero'):
            severity = "差异率计算异常（预算为0），建议人工核查。"
        else:
            pct = abs(total_relative_ratio) * 100
            if pct < 5:
                severity = "整体表现平稳，差异在可控范围内。"
            elif pct < 10:
                severity = "存在一定程度的差异，需要关注主要异常科目。"
            else:
                severity = "差异较大，建议深入分析原因并采取相应措施。"

        var_str = self._format_number(abs(total_variance))
        rel_str = self._format_pct_from_values(
            abs(total_relative_ratio) if total_relative_ratio is not None else None,
            total_budget, total_actual
        )

        if total_variance >= 0:
            return f"本期整体实现{self._format_number(total_variance)}的有利差异，差异率{self._format_pct_from_values(total_relative_ratio, total_budget, total_actual)}。{severity}"
        else:
            return f"本期整体出现{var_str}的不利差异，差异率{rel_str}。{severity}"

    def _generate_account_summary(self, account_summary: pd.DataFrame) -> str:
        """生成按科目汇总表"""
        rows = []
        for _, row in account_summary.iterrows():
            variance_symbol = "+" if row['绝对差异'] >= 0 else ""
            status = "✅" if row['绝对差异'] >= 0 else "⚠️"

            budget = float(row['预算金额'])
            actual = float(row['实际金额'])
            rel_raw = row.get('相对差异(%)')

            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw):
                rel_ratio = rel_raw / 100
                rel_str = self._format_pct_from_values(rel_ratio, budget, actual)
            else:
                rel_str = self._format_pct_from_values(None, budget, actual)

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

            budget = float(row['预算金额'])
            actual = float(row['实际金额'])
            rel_raw = row.get('相对差异(%)')
            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw):
                rel_ratio = rel_raw / 100
                rel_str = self._format_pct_from_values(rel_ratio, budget, actual)
            else:
                rel_str = self._format_pct_from_values(None, budget, actual)

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

            group_section = "（已按 超支组/节省组 分别按金额排序，合并 Top-N 列表）"
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

        n = len(headers)
        empty_placeholder = "| " + " *（无）* |" * n

        if has_group and self.config.separate_anomaly_groups:
            return f"""## 四、重大异常分析（Top {len(anomalies_df)}）{group_section}

> **说明**：相对差异超过 {self.config.anomaly_threshold * 100:.0f}% 的项标记为异常。
> 超支组（不利影响）在前，节省组（有利影响）在后，组内按绝对差异金额从大到小排序。
> 客户端可通过 `detect_anomalies()` 一次获取合并后的完整 Top-N 列表，再用
> `get_anomaly_groups()` 按分组切片。

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
5. 成因模板与 Excel 企业色可在 `config/cause_templates.yaml` 中自定义，无需修改代码
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
5. 成因模板与 Excel 企业色可在 `config/cause_templates.yaml` 中自定义，无需修改代码
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

            budget = float(row.get('预算金额', 0)) if '预算金额' in df.columns else 0
            actual = float(row.get('实际金额', 0)) if '实际金额' in df.columns else 0
            abs_var = float(row['绝对差异'])
            if budget == 0 and actual == 0:
                budget = 0
                actual = abs_var

            rel_raw = row.get('相对差异(%)')
            if isinstance(rel_raw, (int, float)) and not math.isnan(rel_raw):
                rel_ratio = rel_raw / 100
                rel_str = self._format_pct_from_values(rel_ratio, budget, actual)
            else:
                rel_str = self._format_pct_from_values(None, budget, actual)

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

            cum_budget = float(row['累计预算'])
            cum_actual = float(row['累计实际'])
            cum_rel_raw = row.get('累计相对偏离(%)')
            if isinstance(cum_rel_raw, (int, float)) and not math.isnan(cum_rel_raw):
                cum_rel_ratio = cum_rel_raw / 100
                cum_rel_str = self._format_pct_from_values(cum_rel_ratio, cum_budget, cum_actual)
            else:
                cum_rel_str = self._format_pct_from_values(None, cum_budget, cum_actual)

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
2. **相对差异** = 绝对差异 / 预算金额 × 100%（内部统一用 NaN 表示除零）
   - 预算为0 且 实际>0  → 显示 `∞%`
   - 预算为0 且 实际<0  → 显示 `-∞%`
   - 预算为0 且 实际=0  → 显示 `N/A`
3. **累计偏离** = 自分析起始期间至当前期间的累计实际 - 累计预算
4. **影响分数** = 绝对差异/期间总预算 × 70% + 相对差异 × 30%
5. **异常合并 Top-N 接口**：
   - `detect_anomalies()` 一次返回超支+节省合并的完整 Top-N 列表
   - `get_anomaly_groups(list)` 可再按「超支组/节省组」切片
   - `anomalies_to_dataframe()` 含「分组」列，展示层直接渲染
6. **异常分组排序**：
   - 超支组（不利）：收入未达预期 + 成本费用超支
   - 节省组（有利）：收入超预期 + 成本费用节省
   - 组内按绝对差异金额从大到小分别排序
7. **Excel颜色分级**（三档可调，运营在 YAML `excel_colors` 节自定义企业色）：
   - 0 ~ ±{cc.level1_threshold*100:.0f}%：正常色（无色）
   - ±{cc.level1_threshold*100:.0f}% ~ ±{cc.level2_threshold*100:.0f}%：浅色
   - ±{cc.level2_threshold*100:.0f}% ~ ±{cc.level3_threshold*100:.0f}%：中色
   - > ±{cc.level3_threshold*100:.0f}%：深色（加粗）
8. **成因模板 YAML 校验**：
   - 合法键：`revenue_unfavorable` / `revenue_favorable` / `cost_unfavorable` / `cost_favorable`
   - 键名拼写错误会产生运行时警告（不会静默降级）
9. 期间格式支持：`1月`...`12月` / `YYYY年第Q季度` / `YYYY年上半年` `YYYY年下半年` `H1` `H2`
10. 本报告由财务差异报告生成器自动生成，如有疑问请联系财务部门

---
*生成工具：财务差异报告生成器 v1.2.0*
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
