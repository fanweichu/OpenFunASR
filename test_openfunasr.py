#!/usr/bin/env python3
"""Focused regression checks for Fun-ASR commands, text cleanup, and silence gating."""

from __future__ import annotations

import math
import struct
import tempfile
import wave
from pathlib import Path

from openfunasr_app import (
    build_funasr_command,
    chinese_integer_to_arabic,
    clean_transcript,
    merge_config,
    postprocess_transcript,
    remove_spurious_pause_commas,
    repair_spurious_question_breaks,
    wav_has_enough_signal,
)


def write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def main() -> None:
    assert merge_config({"hotkeys": "F8"})["hotkeys"] == "F8"
    assert "backend" not in merge_config({"backend": "legacy"})
    assert "prompt" not in merge_config({"prompt": "legacy"})

    assert build_funasr_command(
        Path("fun"), Path("encoder"), Path("decoder"), Path("vad"), Path("audio.wav")
    ) == ["fun", "--enc", "encoder", "-m", "decoder", "--vad", "vad", "-a", "audio.wav"]
    assert clean_transcript("一二三四") == "一二三四"
    assert clean_transcript("壹贰叁肆") == "1234"
    assert clean_transcript("二零二六年九月十九日") == "2026年9月19日"
    assert clean_transcript("二零二六年，九月十九日") == "2026年，9月19日"
    assert clean_transcript("2026年九月十九日") == "2026年9月19日"
    assert clean_transcript("一千二百三十四个") == "1234个"
    assert clean_transcript("十分钟后还有十五个人") == "10分钟后还有15个人"
    assert clean_transcript("下午三点十五分输入验证码一二三四") == "下午3点15分输入验证码1234"
    assert clean_transcript("我有三个要求，第一点最重要") == "我有三个要求，第一点最重要"
    assert clean_transcript("请看第三章和第五页") == "请看第3章和第5页"
    assert clean_transcript("这件事十分重要，千万不要忘记") == "这件事十分重要，千万不要忘记"
    assert clean_transcript("百分之五十，圆周率三点一四") == "50%，圆周率3.14"
    assert clean_transcript("一方面要注意，万一失败也千万不要慌") == "一方面要注意，万一失败也千万不要慌"
    assert clean_transcript("第三个人从三到五楼") == "第三个人从3到5楼"
    assert postprocess_transcript("第一段。第二段。", 3) == ("第一段。第二段。", 0, 0)
    assert postprocess_transcript("第一段。第二段。", 1) == ("第一段。第二段。", 0, 0)
    assert clean_transcript("版本3.14不变") == "版本3.14不变"

    sample = "review所有的文档，分析写作风格，以及我对，格式的要求。特别关注我，非常关注的情况。"
    assert clean_transcript(sample) == (
        "review所有的文档，分析写作风格，以及我对格式的要求。特别关注我非常关注的情况。"
    )
    assert remove_spurious_pause_commas("对，我同意。") == ("对，我同意。", 0)
    assert remove_spurious_pause_commas("他对，我却不同意。") == ("他对，我却不同意。", 0)
    assert remove_spurious_pause_commas("特别，我还想补充一点。") == ("特别，我还想补充一点。", 0)
    assert remove_spurious_pause_commas("好的，的确如此。") == ("好的，的确如此。", 0)
    assert remove_spurious_pause_commas("这是我对，结果的要求。") == ("这是我对结果的要求。", 1)
    assert remove_spurious_pause_commas("我，非常厌恶这种情况。") == ("我非常厌恶这种情况。", 1)

    broken_question = "以城市中心为核心，有哪些单次车程在3小时以内的？旅游目的地"
    assert clean_transcript(broken_question) == (
        "以城市中心为核心，有哪些单次车程在3小时以内的旅游目的地？"
    )
    assert repair_spurious_question_breaks("有哪些值得去的？旅游景点。") == (
        "有哪些值得去的旅游景点？",
        1,
    )
    assert repair_spurious_question_breaks("你说的是什么？旅游目的地很多。") == (
        "你说的是什么？旅游目的地很多。",
        0,
    )
    assert repair_spurious_question_breaks("有哪些好吃的？餐厅很多。") == (
        "有哪些好吃的？餐厅很多。",
        0,
    )

    # Check semantics, not just that a substitution ran. Include neighboring
    # cases so the repair cannot turn quantities, identifiers or valid prose
    # into different content.
    quality_cases = [
        ("增长百分之三点五。", "增长3.5%。"),
        ("下降百分之零点五。", "下降0.5%。"),
        ("变化百分之负三点零五。", "变化-3.05%。"),
        ("百分之零点零零五和百分之十二点五。", "0.005%和12.5%。"),
        ("要等三四分钟，需要两三个人。", "要等三四分钟，需要两三个人。"),
        ("约三五天，还有七八十人。", "约三五天，还有七八十人。"),
        ("有两三万元，等三四十分钟。", "有两三万元，等三四十分钟。"),
        ("编号三四，验证码是零零一二三四。", "编号34，验证码是001234。"),
        ("编号为零零五六，尾号：零零七八。", "编号为0056，尾号：0078。"),
        ("编号 是 零零五六。", "编号 是 0056。"),
        ("一万亿元和一亿二千万欧元。", "1000000000000元和120000000欧元。"),
        ("预算一千二元。", "预算一千二元。"),
        ("一百二元、一万二元、一亿二元。", "一百二元、一万二元、一亿二元。"),
        ("一千零二元和一千二百元。", "1002元和1200元。"),
        ("测试结，果已经出来了。", "测试结果已经出来了。"),
        ("分析结, 果表明可以继续。", "分析结果表明可以继续。"),
        ("检查结果，随后再决定。", "检查结果，随后再决定。"),
        ("先把袋口打结，果子就不会掉下来。", "先把袋口打结，果子就不会掉下来。"),
        ("有哪些开源的？Python。", "有哪些开源的？Python。"),
        ("有哪些可用的？Node22。", "有哪些可用的？Node22。"),
        ("请调用 foo(bar)，再读取 items[0]。", "请调用 foo(bar)，再读取 items[0]。"),
        ("方案 A (recommended) 可以保留。", "方案 A (recommended) 可以保留。"),
        ("保留[备注]以及(foo(bar))。", "保留[备注]以及(foo(bar))。"),
    ]
    for raw, expected in quality_cases:
        actual = clean_transcript(raw)
        assert actual == expected, (raw, expected, actual)
        assert clean_transcript(actual) == actual, ("not idempotent", raw, actual)

    integer_cases = {
        "一万亿": "1000000000000",
        "一万亿零三万零五": "1000000030005",
        "一亿零三万零五": "100030005",
        "一千亿二千三百万": "100023000000",
        "一百零二": "102",
        "十万零一": "100001",
        "一千零二十": "1020",
        "一万二千": "12000",
        "壹萬億": "1000000000000",
        "一千二": None,
        "两三万": None,
        "一百百": None,
    }
    for raw, expected in integer_cases.items():
        assert chinese_integer_to_arabic(raw) == expected, (raw, expected)

    for segments in (1, 2, 5):
        for text in (
            "今天先到这里。明天继续。",
            "今天结束.明天继续.",
            "Please review the PR. Then run pytest.",
            "版本3.14不变，阈值0.05。",
        ):
            assert postprocess_transcript(text, segments) == (text, 0, 0)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        silence = root / "silence.wav"
        speech_like = root / "speech-like.wav"
        write_wav(silence, [0] * 16000)
        write_wav(
            speech_like,
            [int(5000 * math.sin(2 * math.pi * 220 * index / 16000)) for index in range(16000)],
        )
        assert not wav_has_enough_signal(silence)
        assert wav_has_enough_signal(speech_like)

    print("Fun-ASR command, post-processing, and silence-gate tests passed")


if __name__ == "__main__":
    main()
