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
    assert postprocess_transcript("第一段。第二段。", 3) == ("第一段，第二段。", 0, 1)
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
