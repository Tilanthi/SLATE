#!/usr/bin/env python3
"""
Quick CLI tool to run profitability reports
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slate_core.analytics.profitability_reporter import get_profitability_reporter

def main():
    print("🔍 SLATE Profitability Analysis")
    print("=" * 50)

    # Run comprehensive report
    reporter = get_profitability_reporter()
    report = reporter.generate_comprehensive_report(output_dir="reports")

    # Print summary
    metrics = report['overall_metrics']
    print(f"\n📊 Analysis of {metrics.total_strategies:,} strategies:")
    print(f"   ✅ Profitable: {metrics.profitable_strategies:,} ({metrics.success_rate:.1f}%)")
    print(f"   ❌ Unprofitable: {metrics.unprofitable_strategies:,} ({100-metrics.success_rate:.1f}%)")
    print(f"   ⏱️  Generated in {report['generation_time_seconds']:.1f}s")

    print("\n🎯 Top Recommendations:")
    for i, rec in enumerate(report['recommendations'], 1):
        print(f"   {i}. {rec}")

    print("\n📁 Full report saved to reports/")

if __name__ == "__main__":
    main()