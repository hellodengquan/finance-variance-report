#!/usr/bin/env python3
"""测试 v1.2.0 全部补丁功能"""
import os
import sys
import math
import warnings
import pandas as pd

warnings.filterwarnings('ignore', category=DeprecationWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.finance_variance import (
    ReportConfig, ExcelColorConfig, PeriodParser
)
from src.finance_variance.variance_calculator import VarianceCalculator
from src.finance_variance.report_generator import FinanceVarianceReportGenerator

TEST_OUTPUT = os.path.join(os.path.dirname(__file__), 'test_output')
os.makedirs(TEST_OUTPUT, exist_ok=True)

passed = 0
failed = 0


def check(cond, msg=""):
    global passed, failed
    if cond:
        print("✅ 通过" + (f" ({msg})" if msg else ""))
        passed += 1
        return True
    else:
        print(f"❌ 失败: {msg}")
        failed += 1
        return False


def main():
    global passed, failed
    print("=" * 70)
    print("财务差异报告生成器 v1.2.0 补丁测试")
    print("=" * 70)
    print()

    # 补丁1: 统一 NaN 语义
    print("【补丁1】inf / None 统一语义为 NaN (pandas 列类型一致)")
    print("-" * 70)

    check(VarianceCalculator.safe_divide(50000, 0) != 0 and math.isnan(VarianceCalculator.safe_divide(50000, 0)),
          "budget=0, actual>0 → NaN")
    check(math.isnan(VarianceCalculator.safe_divide(-50000, 0)), "budget=0, actual<0 → NaN")
    check(math.isnan(VarianceCalculator.safe_divide(0, 0)), "budget=0, actual=0 → NaN")
    check(abs(VarianceCalculator.safe_divide(5000, 100000) - 0.05) < 0.001, "正常: 5000/100000 = 0.05")

    check(VarianceCalculator.classify_divide_case(50000, 0) == 'positive_inf',
          "classify_divide_case: +inf")
    check(VarianceCalculator.classify_divide_case(-50000, 0) == 'negative_inf',
          "classify_divide_case: -inf")
    check(VarianceCalculator.classify_divide_case(0, 0) == 'both_zero',
          "classify_divide_case: both_zero")
    check(VarianceCalculator.classify_divide_case(5000, 100000) == 'normal',
          "classify_divide_case: normal")

    # 验证 DataFrame 列类型
    cfg1 = ReportConfig(anomaly_threshold=0.10, separate_anomaly_groups=False)
    gen1 = FinanceVarianceReportGenerator(cfg1)
    gen1.load_data('data/budget_zero_test.csv', 'data/actual_zero_test.csv', 'csv')
    gen1.calculate()
    df1 = gen1.variance_df
    check(pd.api.types.is_float_dtype(df1['相对差异(%)']),
          "DataFrame['相对差异(%)'] 是 float64 列 (统一 NaN)")
    check(df1['相对差异(%)'].isna().sum() >= 3,
          "DataFrame 中存在至少 3 个 NaN (除零情况正确落 NaN)")
    print()

    # 补丁2: 超支/节省合并 Top-N 接口
    print("【补丁2】超支/节省合并 Top-N 接口 (客户端一次拿全)")
    print("-" * 70)

    cfg2 = ReportConfig(anomaly_threshold=0.08, separate_anomaly_groups=True, top_n_anomalies=20)
    gen2 = FinanceVarianceReportGenerator(cfg2)
    gen2.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen2.calculate()
    anomalies2, df2 = gen2.detect_anomalies()
    groups2 = gen2.get_anomaly_groups()

    check(isinstance(anomalies2, list) and len(anomalies2) > 0,
          "detect_anomalies() 返回合并 Top-N 列表")
    check(isinstance(groups2, dict) and '超支组' in groups2 and '节省组' in groups2,
          "get_anomaly_groups() 返回含 超支组/节省组 的 dict")
    check(len(anomalies2) == len(groups2['超支组']) + len(groups2['节省组']),
          "合并 Top-N 与切片总数一致")
    check('分组' in df2.columns, "anomalies_to_dataframe 含 分组 列")
    print(f"   合并总数: {len(anomalies2)} (超支: {len(groups2['超支组'])}, 节省: {len(groups2['节省组'])})")
    print()

    # 补丁3: YAML 严格校验
    print("【补丁3】YAML 字段名校验 (未知 key 警告)")
    print("-" * 70)

    bad_yaml = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config', 'bad_templates_test.yaml'
    )
    check(os.path.exists(bad_yaml), f"故意拼错字段的测试 YAML 存在: {os.path.basename(bad_yaml)}")

    cfg3_bad = ReportConfig(anomaly_threshold=0.08, cause_templates_path=bad_yaml)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        gen3_bad = FinanceVarianceReportGenerator(cfg3_bad)
        warn_msgs = [str(x.message) for x in w]
    yaml_warns = [m for m in warn_msgs if '成因模板' in m or 'YAML' in m]
    check(len(yaml_warns) >= 2, f"未知键产生警告数: {len(yaml_warns)} (期望 ≥2)")
    for m in yaml_warns:
        print(f"   ⚠️  {m[:90]}...")

    cfg3_good = ReportConfig(
        anomaly_threshold=0.08,
        cause_templates_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config', 'cause_templates.yaml'
        )
    )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        gen3_good = FinanceVarianceReportGenerator(cfg3_good)
        yaml_warns_good = [str(x.message) for x in w if '成因模板' in str(x.message)]
    check(len(yaml_warns_good) == 0,
          f"合法 YAML 无警告 (实际: {len(yaml_warns_good)})")
    print()

    # 补丁4: Excel 颜色 HEX 从 YAML 加载
    print("【补丁4】Excel 颜色 HEX 从 YAML 加载 (运营改企业色)")
    print("-" * 70)

    cfg4 = ReportConfig(
        anomaly_threshold=0.08,
        cause_templates_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config', 'cause_templates.yaml'
        )
    )
    gen4 = FinanceVarianceReportGenerator(cfg4)
    cc = gen4.config.excel_color_config

    check(cc.favorable_level1_bg.upper() == '#E8F5E9',
          f"YAML 自定义有利浅色生效: {cc.favorable_level1_bg} (期望 #E8F5E9)")
    check(cc.unfavorable_level1_bg.upper() == '#FFEBEE',
          f"YAML 自定义不利浅色生效: {cc.unfavorable_level1_bg}")
    check(cc.neutral_font.upper() == '#212121',
          f"YAML 自定义中性字体色: {cc.neutral_font}")
    check(abs(cc.level1_threshold - 0.05) < 0.001,
          f"YAML 一级阈值: {cc.level1_threshold}")

    gen4.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen4.calculate()
    a4, df4 = gen4.detect_anomalies()
    md4, xlsx4 = gen4.generate_all(TEST_OUTPUT, 'patch4_yaml_colors')
    check(os.path.exists(xlsx4), f"Excel 报告生成: {os.path.basename(xlsx4)}")

    with open(md4, 'r', encoding='utf-8') as f:
        md4_content = f.read()
    check('成因&颜色模板配置' in md4_content, "Markdown 头部显示模板 YAML 路径")
    print(f"   从 YAML 加载的企业色: 有利浅={cc.favorable_level1_bg} / 不利浅={cc.unfavorable_level1_bg}")
    print()

    # 补丁5: 多期日期解析支持「上半年/下半年/半年」
    print("【补丁5】多期日期解析支持 上半年 / 下半年 / H1 / H2")
    print("-" * 70)

    half_cases = [
        ('2024年上半年', 2024 * 100 + 75, '2024年上半年'),
        ('2024年下半年', 2024 * 100 + 100, '2024年下半年'),
        ('2024上半年', 2024 * 100 + 75, '2024年上半年'),
        ('2023下半年', 2023 * 100 + 100, '2023年下半年'),
        ('2024 H1', 2024 * 100 + 75, '2024年上半年'),
        ('2024H2', 2024 * 100 + 100, '2024年下半年'),
        ('H1 2025', 2025 * 100 + 75, '2025年上半年'),
        ('上半年', 50.0, '上半年'),
        ('下半年', 75.0, '下半年'),
    ]
    all_ok = True
    for raw, exp_key, exp_std in half_cases:
        key, std = PeriodParser.parse(raw)
        ok = (abs(key - exp_key) < 0.001) and (std == exp_std)
        if not ok:
            all_ok = False
            print(f"   ❌ {raw} → ({key}, {std}), 期望 ({exp_key}, {exp_std})")
    check(all_ok, "所有上半年/下半年/H1/H2 格式解析正确")

    cfg5 = ReportConfig(anomaly_threshold=0.05, separate_anomaly_groups=True, top_n_anomalies=10)
    gen5 = FinanceVarianceReportGenerator(cfg5)
    gen5.load_data('data/budget_halfyear.csv', 'data/actual_halfyear.csv', 'csv')
    gen5.calculate()
    a5, df5 = gen5.detect_anomalies()
    period_summary_5 = gen5.period_summary
    periods = period_summary_5['期间'].tolist()
    check(len(periods) == 4, f"半年数据共 4 个期间: {periods}")
    check(periods[0] == '2023年下半年', f"首期间排序: {periods[0]}")
    check(periods[-1] == '2025年上半年', f"末期间排序: {periods[-1]}")

    md5, xlsx5 = gen5.generate_all(TEST_OUTPUT, 'patch5_halfyear')
    check(os.path.exists(md5), "半年 Markdown 报告生成成功")
    with open(md5, 'r', encoding='utf-8') as f:
        md5_content = f.read()
    check('2024年上半年' in md5_content and '2025年上半年' in md5_content,
          "半年 Markdown 中存在中文半年表头")
    print(f"   期间顺序: {periods}")
    print()

    # 整合测试
    print("【整合测试】月度 + YAML 配色 + 严格校验 + 合并接口")
    print("-" * 70)
    cfg_full = ReportConfig(
        title='财务差异分析报告（v1.2 整合）',
        company_name='示例科技有限公司',
        anomaly_threshold=0.08,
        top_n_anomalies=15,
        separate_anomaly_groups=True,
        cause_templates_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'config', 'cause_templates.yaml'
        )
    )
    gen_full = FinanceVarianceReportGenerator(cfg_full)
    gen_full.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen_full.calculate()
    a_full, df_full = gen_full.detect_anomalies()
    g_full = gen_full.get_anomaly_groups()
    md_full, xlsx_full = gen_full.generate_all(TEST_OUTPUT, 'full_v1.2')

    with open(md_full, 'r', encoding='utf-8') as f:
        fc = f.read()

    features = [
        ('超支组（不利差异）' in fc, '分组异常：超支组标题'),
        ('内部统一用 NaN 表示除零' in fc, 'NaN 统一语义说明'),
        ('合并 Top-N' in fc, '合并 Top-N 接口说明'),
        ('上半年' in fc and '下半年' in fc, '半年格式在说明中'),
        ('YAML 校验' in fc or 'YAML' in fc and '校验' in fc, 'YAML 校验说明'),
        ('excel_colors' in fc, 'YAML 企业色配置说明'),
        (len(df_full) == len(g_full['超支组']) + len(g_full['节省组']),
         '合并 Top-N 与分组切片一致'),
        (pd.api.types.is_float_dtype(gen_full.variance_df['相对差异(%)']),
         'variance_df 相对差异列为 float64'),
    ]
    for cond, desc in features:
        check(cond, desc)

    print(f"   📄 Markdown: {os.path.relpath(md_full)}")
    print(f"   📊 Excel: {os.path.relpath(xlsx_full)}")
    print()

    # 总结
    print("=" * 70)
    total = passed + failed
    print(f"测试完成: 通过 {passed}/{total}", end='')
    if failed == 0:
        print(" ✅ 全部通过!")
    else:
        print(f" ❌ {failed} 项失败!")
    print("=" * 70)
    print(f"\n所有测试输出文件位于: {os.path.abspath(TEST_OUTPUT)}")
    return failed == 0


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
