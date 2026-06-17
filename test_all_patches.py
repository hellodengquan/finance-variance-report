#!/usr/bin/env python3
"""测试所有 v1.1.0 补丁功能"""
import os
import sys
import math
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.finance_variance import (
    ReportConfig, ExcelColorConfig, PeriodParser
)
from src.finance_variance.report_generator import FinanceVarianceReportGenerator

TEST_OUTPUT = os.path.join(os.path.dirname(__file__), 'test_output')
os.makedirs(TEST_OUTPUT, exist_ok=True)

passed = 0
failed = 0


def test(name):
    """装饰器：运行测试并记录结果"""
    global passed, failed
    try:
        result = None
        def wrapper():
            global passed, failed
            try:
                print(f"[?] 测试: {name} ... ", end='', flush=True)
                return True
            except Exception as e:
                print(f"❌ 失败: {e}")
                failed += 1
                return False
        result = wrapper()
        return result
    except Exception as e:
        print(f"❌ 失败: {e}")
        failed += 1
        return False


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
    print("财务差异报告生成器 v1.1.0 补丁测试")
    print("=" * 70)
    print()

    # ============ 补丁1: 相对差异公式 safe_divide ============
    print("【补丁1】相对差异公式 budget=0 避免 ZeroDivisionError")
    print("-" * 70)

    cfg1 = ReportConfig(anomaly_threshold=0.10, separate_anomaly_groups=False)
    gen1 = FinanceVarianceReportGenerator(cfg1)
    gen1.load_data('data/budget_zero_test.csv', 'data/actual_zero_test.csv', 'csv')
    gen1.calculate()
    vr = gen1.variance_results

    # 检查 2月-主营业务收入: budget=0, actual=50000 → 应为 inf
    item_6001_2 = [r for r in vr if r.account_code == '6001' and r.period == '2月'][0]
    has_inf = math.isinf(item_6001_2.relative_variance)
    check(has_inf, "2月收入 budget=0, actual>0 → relative_variance=inf")

    # 检查 3月-主营业务收入: budget=0, actual=0 → 应为 None
    item_6001_3 = [r for r in vr if r.account_code == '6001' and r.period == '3月'][0]
    check(item_6001_3.relative_variance is None, "3月收入 budget=0, actual=0 → relative_variance=None")

    # 检查 2月-主营业务成本: budget=0, actual=0 → 应为 None
    item_6401_2 = [r for r in vr if r.account_code == '6401' and r.period == '2月'][0]
    check(item_6401_2.relative_variance is None, "2月成本 budget=0, actual=0 → relative_variance=None")

    # 检查正常项: 1月收入 budget=100000, actual=105000 → relative_variance = 0.05 (比率)
    item_6001_1 = [r for r in vr if r.account_code == '6001' and r.period == '1月'][0]
    check(abs(item_6001_1.relative_variance - 0.05) < 0.001,
          f"1月收入正常计算 = +5% (实际: {item_6001_1.relative_variance})")

    print()

    # ============ 补丁2: 异常分组排序 ============
    print("【补丁2】异常排序：超支/节省两组分别按金额排序")
    print("-" * 70)

    cfg2 = ReportConfig(anomaly_threshold=0.08, separate_anomaly_groups=True, top_n_anomalies=20)
    gen2 = FinanceVarianceReportGenerator(cfg2)
    gen2.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen2.calculate()
    anomalies2, df2 = gen2.detect_anomalies()

    check('分组' in df2.columns, "异常DataFrame含'分组'列")
    check('差异类型' in df2.columns, "异常DataFrame含'差异类型'列")

    # 检查分组排序：超支组在前，节省组在后
    if '分组' in df2.columns and len(df2) > 0:
        first_group = df2.iloc[0]['分组']
        # 找到第一个 节省组 的位置
        save_idx = None
        for i, row in df2.iterrows():
            if row['分组'] == '节省组':
                save_idx = i
                break
        check(save_idx is None or all(df2.iloc[:save_idx]['分组'] == '超支组'),
              "超支组全部排在节省组之前")

        # 检查超支组内部排序：绝对差异从大到小
        bad_df = df2[df2['分组'] == '超支组']
        if len(bad_df) >= 2:
            bad_abs = bad_df['绝对差异'].abs().tolist()
            check(bad_abs == sorted(bad_abs, reverse=True), "超支组内部按绝对差异降序")

        # 检查节省组内部排序
        good_df = df2[df2['分组'] == '节省组']
        if len(good_df) >= 2:
            good_abs = good_df['绝对差异'].abs().tolist()
            check(good_abs == sorted(good_abs, reverse=True), "节省组内部按绝对差异降序")

    print(f"   共检测到 {len(df2)} 个异常")
    if '分组' in df2.columns:
        print(f"   超支组: {len(df2[df2['分组'] == '超支组'])} 个, 节省组: {len(df2[df2['分组'] == '节省组'])} 个")
    print()

    # ============ 补丁3: YAML成因占位符 ============
    print("【补丁3】成因占位符从 YAML 加载（运营自定义）")
    print("-" * 70)

    yaml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'config', 'cause_templates.yaml'
    )
    check(os.path.exists(yaml_path), f"YAML 模板文件存在: {yaml_path}")

    cfg3 = ReportConfig(anomaly_threshold=0.08, separate_anomaly_groups=True,
                        cause_templates_path=yaml_path, top_n_anomalies=20)
    gen3 = FinanceVarianceReportGenerator(cfg3)
    gen3.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen3.calculate()
    anomalies3, df3 = gen3.detect_anomalies()

    check('成因分析（待核实）' in df3.columns, "含成因分析列")
    if len(df3) > 0:
        causes = df3['成因分析（待核实）'].tolist()
        check(all('【待核实】' in c for c in causes), "所有成因含【待核实】标记")
        check(len(set(causes)) >= 2, "成因模板非单一内容（多样化）")

    print("   成因示例:")
    for i in range(min(3, len(df3))):
        print(f"     - {df3.iloc[i]['科目名称']}({df3.iloc[i]['期间']}): {df3.iloc[i]['成因分析（待核实）'][:40]}...")
    print()

    # ============ 补丁4: Excel颜色阈值配置 ============
    print("【补丁4】Excel 单元格颜色阈值：三档可调配置")
    print("-" * 70)

    color_cfg = ExcelColorConfig(
        level1_threshold=0.03,
        level2_threshold=0.07,
        level3_threshold=0.15,
        favorable_level1_bg='#C8E6C9',
        favorable_level1_font='#2E7D32',
        favorable_level2_bg='#81C784',
        favorable_level2_font='#1B5E20',
        favorable_level3_bg='#4CAF50',
        favorable_level3_font='#FFFFFF',
        unfavorable_level1_bg='#FFCDD2',
        unfavorable_level1_font='#C62828',
        unfavorable_level2_bg='#E57373',
        unfavorable_level2_font='#7F0000',
        unfavorable_level3_bg='#F44336',
        unfavorable_level3_font='#FFFFFF'
    )
    check(color_cfg.level1_threshold == 0.03, "一级阈值 = 3%")
    check(color_cfg.level2_threshold == 0.07, "二级阈值 = 7%")
    check(color_cfg.level3_threshold == 0.15, "三级阈值 = 15%")

    cfg4 = ReportConfig(anomaly_threshold=0.08, excel_color_config=color_cfg)
    gen4 = FinanceVarianceReportGenerator(cfg4)
    gen4.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen4.calculate()
    anomalies4, df4 = gen4.detect_anomalies()
    md4, xlsx4 = gen4.generate_all(TEST_OUTPUT, 'patch4_color_test')

    check(os.path.exists(xlsx4), f"Excel 文件生成: {os.path.basename(xlsx4)}")
    check(os.path.exists(md4), f"Markdown 文件生成: {os.path.basename(md4)}")

    with open(md4, 'r', encoding='utf-8') as f:
        md_content = f.read()
    check('±3% / ±7% / ±15%' in md_content, "Markdown 报告头部包含自定义颜色阈值信息")
    print()

    # ============ 补丁5: 多期日期解析支持季度格式 ============
    print("【补丁5】多期日期解析：支持 YYYY年第Q季度 文本格式")
    print("-" * 70)

    # 测试 PeriodParser 排序键
    test_periods = ['2025年第2季度', '2024年第3季度', '2024年第1季度', '2025年第1季度', '2024年第2季度', '2024年第4季度']
    expected = ['2024年第1季度', '2024年第2季度', '2024年第3季度', '2024年第4季度', '2025年第1季度', '2025年第2季度']
    sorted_periods = sorted(test_periods, key=lambda p: PeriodParser.parse(p)[0])
    check(sorted_periods == expected, f"季度格式正确排序: {sorted_periods}")

    # 混合格式测试：月份 + 季度
    mixed = ['2024年第2季度', '3月', '2024年第1季度', '1月', '2月', '12月']
    sorted_mixed = sorted(mixed, key=lambda p: PeriodParser.parse(p)[0])
    print(f"   混合排序: {sorted_mixed}")
    check(len(sorted_mixed) == 6, "混合格式排序不丢失元素")

    cfg5 = ReportConfig(anomaly_threshold=0.05, separate_anomaly_groups=True,
                        top_n_anomalies=15)
    gen5 = FinanceVarianceReportGenerator(cfg5)
    gen5.load_data('data/budget_quarterly.csv', 'data/actual_quarterly.csv', 'csv')
    gen5.calculate()
    anomalies5, df5 = gen5.detect_anomalies()

    # 从 period_summary 获取期间列表（已按 PeriodParser 排序）
    period_summary_5 = gen5.period_summary
    periods = period_summary_5['期间'].tolist()
    check(len(periods) == 6, f"季度数据共 6 个期间: {periods}")
    check('2024年第1季度' in periods, "期间包含 2024年第1季度")
    check(periods[0] == '2024年第1季度', f"期间排序正确: 第一个={periods[0]}")
    check(periods[-1] == '2025年第2季度', f"期间排序正确: 最后一个={periods[-1]}")

    md5, xlsx5 = gen5.generate_all(TEST_OUTPUT, 'patch5_quarterly_test')
    check(os.path.exists(xlsx5), "季度数据 Excel 报告生成成功")

    with open(md5, 'r', encoding='utf-8') as f:
        md5_content = f.read()
    check('2024年第1季度' in md5_content, "Markdown 含季度期间")
    check('2025年第2季度' in md5_content, "Markdown 含最新季度")

    print(f"   期间顺序: {periods}")
    print()

    # ============ 整合测试：月度数据完整版 ============
    print("【整合测试】月度数据 - 输出完整报告（含所有补丁特性）")
    print("-" * 70)

    cfg_full = ReportConfig(
        title='财务差异分析报告（月度·完整版）',
        company_name='示例科技有限公司',
        anomaly_threshold=0.08,
        top_n_anomalies=15,
        separate_anomaly_groups=True,
        cause_templates_path=yaml_path,
        excel_color_config=ExcelColorConfig(
            level1_threshold=0.05, level2_threshold=0.10, level3_threshold=0.20
        )
    )
    gen_full = FinanceVarianceReportGenerator(cfg_full)
    gen_full.load_data('data/budget.csv', 'data/actual.csv', 'csv')
    gen_full.calculate()
    a_full, df_full = gen_full.detect_anomalies()
    md_full, xlsx_full = gen_full.generate_all(TEST_OUTPUT, 'full_monthly_v1.1')

    with open(md_full, 'r', encoding='utf-8') as f:
        full_content = f.read()

    features = [
        ('超支组（不利差异）' in full_content, '分组异常：超支组标题'),
        ('节省组（有利差异）' in full_content, '分组异常：节省组标题'),
        ('成因模板配置' in full_content, 'YAML 配置信息在头部'),
        ('颜色分级阈值' in full_content, '颜色分级信息在头部'),
        ('∞%' in full_content or 'N/A' in full_content, '相对差异特殊值展示 (inf/N/A)'),
        ('config/cause_templates.yaml' in full_content, '运营自定义说明'),
    ]
    for cond, desc in features:
        check(cond, desc)

    print(f"   📄 Markdown: {os.path.relpath(md_full)}")
    print(f"   📊 Excel: {os.path.relpath(xlsx_full)}")
    print()

    # ============ 总结 ============
    print("=" * 70)
    total = passed + failed
    print(f"测试完成: 通过 {passed}/{total}", end='')
    if failed == 0:
        print(" ✅ 全部通过!")
    else:
        print(f" ❌ {failed} 项失败!")
    print("=" * 70)

    print()
    print(f"所有测试输出文件位于: {os.path.abspath(TEST_OUTPUT)}")

    return failed == 0


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
