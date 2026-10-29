#!/usr/bin/env python3
"""Replay synthetic text against the real postprocessor; no audio or UI actions.

These cases diagnose transformation errors, not recognition accuracy. Expected
variants express the test's intended meaning; undecided oral shorthand is kept
separate from failures. Reports are local evidence, not release acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openfunasr_app import postprocess_transcript  # noqa: E402


# id, focus, input, VAD segment count, acceptable output variants, mismatch class
CASES = [
    ("T01", "整数百分比", "增长百分之五十。", 1, ["增长50%。"], "错误"),
    ("T02", "小数百分比", "增长百分之三点五。", 1, ["增长3.5%。"], "错误"),
    ("T03", "小数百分比含零", "下降百分之零点五。", 1, ["下降0.5%。"], "错误"),
    ("T04", "完整日期", "二零二六年十月二十九日开会。", 1, ["2026年10月29日开会。"], "错误"),
    ("T05", "时间", "下午三点十五分开会。", 1, ["下午3点15分开会。", "下午3:15开会。"], "错误"),
    ("T06", "明确整数", "预算一千二百元。", 1, ["预算1200元。"], "错误"),
    ("T07", "相邻约数", "要等三四分钟。", 1, ["要等三四分钟。", "要等3到4分钟。", "要等3至4分钟。", "要等3—4分钟。"], "错误"),
    ("T08", "相邻人数约数", "需要两三个人。", 1, ["需要两三个人。", "需要2到3个人。", "需要2至3个人。", "需要2—3个人。"], "错误"),
    ("T09", "编号前导零", "验证码零零一二三四。", 1, ["验证码001234。"], "错误"),
    ("T10", "编号标签中有是", "验证码是零零一二三四。", 1, ["验证码是001234。"], "格式差异"),
    ("T11", "嵌套大单位", "总额一万亿元。", 1, ["总额1000000000000元。", "总额一万亿元。", "总额1万亿元。"], "错误"),
    ("T12", "数字词语保护", "千万不要忘记，万一失败就重试。", 1, ["千万不要忘记，万一失败就重试。"], "错误"),
    ("T13", "口述版本号", "使用 Python 三点一二版本，调用 API。", 1, ["使用 Python 3.12版本，调用 API。"], "错误"),
    ("T14", "英语参数及中文小数", "请把 timeout 设成三点五秒，再跑 pytest。", 1, ["请把 timeout 设成3.5秒，再跑 pytest。"], "错误"),
    ("T15", "完整双句单片段", "今天先到这里。明天继续。", 1, ["今天先到这里。明天继续。"], "错误"),
    ("T16", "完整双句多片段", "今天先到这里。明天继续。", 2, ["今天先到这里。明天继续。"], "错误"),
    ("T17", "已覆盖的介词停顿", "这是我对，结果的要求。", 1, ["这是我对结果的要求。"], "错误"),
    ("T18", "词内部被插入逗号", "测试结，果已经出来了。", 1, ["测试结果已经出来了。"], "错误"),
    ("T19", "错误问号位置", "有哪些值得去的？旅游景点。", 1, ["有哪些值得去的旅游景点？"], "错误"),
    ("T20", "独立问答需要保留", "有哪些开源的？Python。", 1, ["有哪些开源的？Python。"], "错误"),
    ("T21", "技术文本括号内容", "请调用 foo(bar)，再读取 items[0]。", 1, ["请调用 foo(bar)，再读取 items[0]。"], "错误"),
    ("T22", "英文多句保护", "Please review the PR. Then run pytest.", 2, ["Please review the PR. Then run pytest."], "错误"),
    ("T23", "已有版本及小数保护", "版本3.14不变，阈值0.05。", 2, ["版本3.14不变，阈值0.05。"], "错误"),
    ("T24", "口语省略待定", "预算一千二元。", 1, None, "待定"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Local report directory; keep outside tracked source")
    args = parser.parse_args()
    rows = []
    for case_id, focus, raw, segments, acceptable, mismatch in CASES:
        final, numeral_conversions, softened_periods = postprocess_transcript(raw, segments)
        status = "待定" if acceptable is None else ("通过" if final in acceptable else mismatch)
        rows.append(dict(id=case_id, focus=focus, input=raw, speech_segment_count=segments,
                         acceptable_outputs=acceptable, actual=final, status=status,
                         numeral_conversions=numeral_conversions, softened_periods=softened_periods))
    summary = dict(Counter(row["status"] for row in rows))
    report = dict(tested_at=datetime.now(timezone.utc).isoformat(),
                  scope="Synthetic text replay against source postprocess_transcript; no ASR/audio/live app test",
                  source="openfunasr_app.py", source_sha256=hashlib.sha256((ROOT / "openfunasr_app.py").read_bytes()).hexdigest(),
                  python=sys.version.split()[0], summary=summary, cases=rows)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "text-probes.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# OpenFunASR 文本后处理探针", "", f"执行时间：{report['tested_at']}",
             f"源码 SHA-256：`{report['source_sha256']}`", f"Python：{report['python']}", "",
             "调用现有源码的真实后处理函数。输入为人工构造的引擎文本，片段数为测试参数；未运行语音识别或已安装应用。",
             "T20 明确按独立问答评分；T21 假定引擎已经正确输出技术括号。它们不证明引擎会生成这些文本。",
             "T10 只记格式不一致，数字含义未丢失；T24 的口语含义待确认，不计失败。",
             "T18 检查已有错误是否仍残留，不能归因于后处理制造了逗号。",
             "", "统计：" + "；".join(f"{key} {value}" for key, value in summary.items()), "",
             "| ID | 检查点 | 输入 | 片段数 | 实际输出 | 结果 |", "|---|---|---|---:|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {row['focus']} | {row['input']} | {row['speech_segment_count']} | {row['actual']} | {row['status']} |")
    lines += ["", "完整期望值与统计字段见同目录 text-probes.json。此处通过数量不代表产品识别准确率。", ""]
    (args.output / "text-probes.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(output=str(args.output), summary=summary), ensure_ascii=False))


if __name__ == "__main__":
    main()
