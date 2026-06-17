import os
import math
import warnings
import pandas as pd
from typing import List, Dict, Optional, Tuple
import yaml
from .models import VarianceResult, AnomalyItem, ReportConfig


DEFAULT_CAUSE_TEMPLATES = {
    'revenue_positive': {
        'description': '收入类科目有利差异（实际>预算）',
        'templates': [
            "【待核实】市场需求超预期增长，销售表现优于预算",
            "【待核实】新产品/服务推广效果显著，带动收入增长",
            "【待核实】主要客户订单增加或新增大客户",
            "【待核实】产品定价策略调整带来溢价",
            "【待核实】季节性因素或行业周期影响",
            "【待核实】营销活动转化效果超预期",
            "【待核实】竞争对手市场份额下降"
        ]
    },
    'revenue_negative': {
        'description': '收入类科目不利差异（实际<预算）',
        'templates': [
            "【待核实】市场竞争加剧，销售未达预期",
            "【待核实】产品交付延迟或质量问题导致收入确认延后",
            "【待核实】主要客户需求下降或流失",
            "【待核实】促销活动效果不及预期",
            "【待核实】宏观经济环境或政策变化影响",
            "【待核实】产品定价竞争力不足",
            "【待核实】渠道拓展进度缓慢"
        ]
    },
    'cost_positive': {
        'description': '成本/费用类科目超支（实际>预算）',
        'templates': [
            "【待核实】原材料采购价格上涨超出预期",
            "【待核实】业务规模扩张导致相关成本增加",
            "【待核实】低效运营或浪费导致成本超支",
            "【待核实】意外支出或一次性费用发生",
            "【待核实】供应商议价能力变化或合同条款调整",
            "【待核实】人力成本超预算（加班/新增人员）",
            "【待核实】通胀因素导致物价普遍上涨"
        ]
    },
    'cost_negative': {
        'description': '成本/费用类科目节省（实际<预算）',
        'templates': [
            "【待核实】成本控制措施见效，采购价格下降",
            "【待核实】业务量低于预期导致变动成本减少",
            "【待核实】运营效率提升带来成本节约",
            "【待核实】预算编制偏保守，实际支出优化",
            "【待核实】费用延后确认或计入期间调整",
            "【待核实】外包/替代方案降低了成本",
            "【待核实】库存管理优化减少损耗"
        ]
    }
}


_VALID_YAML_KEYS = {
    'revenue_unfavorable', 'revenue_favorable',
    'cost_unfavorable', 'cost_favorable',
    'revenue_positive', 'revenue_negative',
    'cost_positive', 'cost_negative',
    'cause_templates',
    'actions', 'note',
    'excel_colors', 'color_config'
}


class AnomalyDetector:
    """异常检测和排序模块"""

    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self.cause_templates, self.yaml_warnings = self._load_cause_templates()

    @staticmethod
    def _map_yaml_key(yaml_key: str) -> Optional[str]:
        """将 YAML 简洁键映射到内部键

        revenue_unfavorable -> revenue_negative
        revenue_favorable   -> revenue_positive
        cost_unfavorable    -> cost_positive (成本超支)
        cost_favorable      -> cost_negative (成本节省)
        """
        mapping = {
            'revenue_unfavorable': 'revenue_negative',
            'revenue_favorable': 'revenue_positive',
            'cost_unfavorable': 'cost_positive',
            'cost_favorable': 'cost_negative',
        }
        return mapping.get(yaml_key)

    def _load_cause_templates(self) -> Tuple[Dict, List[str]]:
        """从YAML文件或默认值加载成因模板，同时返回未知键的警告列表

        - 严格校验字段名，未知键写入 warnings 并通过 warnings.warn() 提示
        - 运营拼写错误（如 revenue_unfavorabl）不会静默降级
        """
        templates = {k: dict(v) for k, v in DEFAULT_CAUSE_TEMPLATES.items()}
        warning_msgs: List[str] = []

        yaml_path = self.config.cause_templates_path
        if not (yaml_path and os.path.exists(yaml_path)):
            return templates, warning_msgs

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f)

            if not yaml_data:
                return templates, warning_msgs

            def _emit_warning(key, reason):
                msg = f"[成因模板] YAML 字段 '{key}' {reason} (文件: {yaml_path})"
                warning_msgs.append(msg)
                warnings.warn(msg, UserWarning, stacklevel=2)

            known_valid_keys = set(_VALID_YAML_KEYS)

            if isinstance(yaml_data, dict):
                for key, value in yaml_data.items():
                    if key in ('excel_colors', 'color_config', 'actions', 'note'):
                        continue
                    if key not in known_valid_keys:
                        _emit_warning(key, "不被识别，已忽略。请检查拼写是否正确")
                        continue

                    internal_key = self._map_yaml_key(key) or key
                    if isinstance(value, list):
                        templates[internal_key] = {
                            'description': f'YAML配置: {key}',
                            'templates': [str(x) for x in value]
                        }
                    elif isinstance(value, dict):
                        if 'templates' in value:
                            templates[internal_key] = {
                                'description': value.get('description', f'YAML配置: {key}'),
                                'templates': list(value['templates'])
                            }
                        else:
                            _emit_warning(key, "缺少 templates 列表，已忽略")
                    else:
                        _emit_warning(key, "值必须是列表或含 templates 的字典，已忽略")

                if 'cause_templates' in yaml_data and isinstance(yaml_data['cause_templates'], dict):
                    for key, value in yaml_data['cause_templates'].items():
                        if key not in known_valid_keys:
                            _emit_warning(f"cause_templates.{key}", "不被识别，已忽略")
                            continue
                        internal_key = self._map_yaml_key(key) or key
                        if isinstance(value, list):
                            templates[internal_key] = {
                                'description': f'YAML配置: {key}',
                                'templates': [str(x) for x in value]
                            }
                        elif isinstance(value, dict) and 'templates' in value:
                            templates[internal_key] = {
                                'description': value.get('description', ''),
                                'templates': list(value['templates'])
                            }

        except Exception as e:
            msg = f"[成因模板] 加载YAML失败: {e}，使用默认模板 (文件: {yaml_path})"
            warning_msgs.append(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)

        return templates, warning_msgs

    def detect_anomalies(self, variance_results: List[VarianceResult],
                         variance_df: Optional[pd.DataFrame] = None) -> List[AnomalyItem]:
        """
        检测异常项并按影响排序（超支/节省已合并成单一 Top-N 列表）

        - 若 config.separate_anomaly_groups=True：异常先按「超支组」「节省组」拆分，
          组内分别按绝对差异金额降序，再按 超支组+节省组 合并，返回合并后的 Top N；
          DataFrame 列含「分组」供展示层使用。
        - 若 config.separate_anomaly_groups=False：按影响分数综合排序。

        客户端只需调用一次即可拿到完整异常列表。
        """
        if variance_df is None:
            variance_df = self._results_to_df(variance_results)

        total_budget = variance_df.groupby('期间')['预算金额'].sum().mean()

        overspend_anomalies = []
        saving_anomalies = []

        for result in variance_results:
            rel_var = result.relative_variance

            if pd.isna(rel_var):
                if result.budget == 0 and result.actual != 0:
                    pass
                else:
                    continue

            abs_rel = abs(rel_var) if not pd.isna(rel_var) else float('inf')
            if abs_rel < self.config.anomaly_threshold and not pd.isna(rel_var):
                continue
            if not pd.isna(rel_var) and abs_rel < self.config.anomaly_threshold:
                continue

            impact_score = self._calculate_impact_score(result, total_budget)
            variance_type = self._get_variance_type(result)
            cause_placeholder = self._get_cause_placeholder(result, variance_type)

            item = AnomalyItem(
                account_code=result.account_code,
                account_name=result.account_name,
                period=result.period,
                absolute_variance=result.absolute_variance,
                relative_variance=result.relative_variance,
                impact_score=impact_score,
                cause_placeholder=cause_placeholder,
                variance_type=variance_type
            )

            if self._is_overspend(result, variance_type):
                overspend_anomalies.append(item)
            else:
                saving_anomalies.append(item)

        if self.config.separate_anomaly_groups:
            overspend_anomalies.sort(key=lambda x: abs(x.absolute_variance), reverse=True)
            saving_anomalies.sort(key=lambda x: abs(x.absolute_variance), reverse=True)
            combined = overspend_anomalies + saving_anomalies
            return combined[:self.config.top_n_anomalies]
        else:
            all_anomalies = overspend_anomalies + saving_anomalies
            all_anomalies.sort(key=lambda x: abs(x.impact_score), reverse=True)
            return all_anomalies[:self.config.top_n_anomalies]

    def get_anomaly_groups(self, anomalies: List[AnomalyItem]) -> Dict[str, List[AnomalyItem]]:
        """
        合并 Top-N 接口的补充：将完整异常列表按分组返回，
        便于客户端分别展示超支/节省组。
        """
        groups = {'超支组': [], '节省组': []}
        for a in anomalies:
            is_rev = (a.account_code.startswith('60') or a.account_code.startswith('63'))
            if is_rev:
                key = '超支组' if a.variance_type == 'revenue_negative' else '节省组'
            else:
                key = '超支组' if a.variance_type == 'cost_positive' else '节省组'
            groups[key].append(a)
        return groups

    @staticmethod
    def _is_overspend(result: VarianceResult, variance_type: str) -> bool:
        """
        判断是否为超支（对利润的不利影响）：
        - 收入类：实际 < 预算（revenue_negative）
        - 成本类：实际 > 预算（cost_positive）
        """
        account_code = result.account_code
        is_revenue = (account_code.startswith('60') or account_code.startswith('63'))
        if is_revenue:
            return variance_type == 'revenue_negative'
        else:
            return variance_type == 'cost_positive'

    def _calculate_impact_score(self, result: VarianceResult, total_budget: float) -> float:
        """
        计算影响分数，综合考虑绝对差异和相对差异

        影响分数 = 绝对差异 / 期间总预算 * 100% * 权重1 + 相对差异 * 权重2
        NaN（budget=0 情况）按最大相对差异处理（+100 或 -100）
        """
        abs_impact = result.absolute_variance / total_budget * 100 if total_budget != 0 else 0

        rel_var = result.relative_variance
        if pd.isna(rel_var):
            if result.budget == 0:
                if result.actual > 0:
                    rel_impact = 100.0
                elif result.actual < 0:
                    rel_impact = -100.0
                else:
                    rel_impact = 0.0
            else:
                rel_impact = 0.0
        else:
            rel_impact = rel_var * 100

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
        templates_data = self.cause_templates.get(
            variance_type,
            self.cause_templates.get('cost_positive', DEFAULT_CAUSE_TEMPLATES['cost_positive'])
        )
        templates = templates_data.get('templates', [])

        if not templates:
            templates = DEFAULT_CAUSE_TEMPLATES['cost_positive']['templates']

        template_index = abs(hash(result.account_code + result.period)) % len(templates)
        return templates[template_index]

    def _results_to_df(self, results: List[VarianceResult]) -> pd.DataFrame:
        """将结果转换为DataFrame（列类型统一 float64）"""
        data = []
        for r in results:
            data.append({
                '科目编码': r.account_code,
                '科目名称': r.account_name,
                '期间': r.period,
                '预算金额': float(r.budget),
                '实际金额': float(r.actual),
                '绝对差异': float(r.absolute_variance),
                '相对差异(%)': float('nan') if pd.isna(r.relative_variance) else round(r.relative_variance * 100, 2)
            })
        return pd.DataFrame(data)

    @staticmethod
    def _get_display_types(account_code: str, variance_type: str) -> Tuple[str, str]:
        """获取显示用的差异类型和分组标签

        分组规则：
        - 超支组（对利润不利）：收入未达(revenue_negative) + 成本超支(cost_positive)
        - 节省组（对利润有利）：收入超预期(revenue_positive) + 成本节省(cost_negative)
        """
        is_revenue = (account_code.startswith('60') or account_code.startswith('63'))

        if is_revenue:
            if variance_type == 'revenue_positive':
                return '有利差异', '节省组'
            else:
                return '不利差异', '超支组'
        else:
            if variance_type == 'cost_negative':
                return '有利差异', '节省组'
            else:
                return '不利差异', '超支组'

    def anomalies_to_dataframe(self, anomalies: List[AnomalyItem]) -> pd.DataFrame:
        """将异常项转换为DataFrame（超支/节省已合并成单一 Top-N 列表，含分组列）"""
        data = []
        for idx, a in enumerate(anomalies, 1):
            if pd.isna(a.relative_variance):
                rel_var_pct = float('nan')
            else:
                rel_var_pct = round(a.relative_variance * 100, 2)

            display_type, group_label = self._get_display_types(a.account_code, a.variance_type)

            data.append({
                '排名': idx,
                '科目编码': a.account_code,
                '科目名称': a.account_name,
                '期间': a.period,
                '绝对差异': float(a.absolute_variance),
                '相对差异(%)': float(rel_var_pct),
                '影响分数': round(a.impact_score, 2),
                '差异类型': display_type,
                '分组': group_label,
                '成因分析（待核实）': a.cause_placeholder
            })

        return pd.DataFrame(data)
