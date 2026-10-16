#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import audioop
import ctypes
import ctypes.util
import wave
from pathlib import Path

import objc
from Cocoa import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSAlert,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSBox,
    NSBoxSeparator,
    NSButton,
    NSClosableWindowMask,
    NSColor,
    NSEvent,
    NSFont,
    NSImage,
    NSImageOnly,
    NSLeftMouseDownMask,
    NSMakeRect,
    NSMakeSize,
    NSMiniaturizableWindowMask,
    NSObject,
    NSOffState,
    NSOnState,
    NSOtherMouseDownMask,
    NSPopUpButton,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSRightMouseDownMask,
    NSRoundedBezelStyle,
    NSSegmentedControl,
    NSSegmentStyleRounded,
    NSStatusBar,
    NSTextField,
    NSTitledWindowMask,
    NSVariableStatusItemLength,
    NSView,
    NSViewController,
    NSWindow,
    NSWorkspace,
    NSSwitchButton,
)
from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
from CoreFoundation import kCFBooleanTrue
from Foundation import NSURL
from Foundation import NSBundle
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)
from PyObjCTools import AppHelper

try:
    import pyperclip
except Exception as error:  # pragma: no cover - surfaced in UI at runtime.
    pyperclip = None
    PYPERCLIP_IMPORT_ERROR = error
else:
    PYPERCLIP_IMPORT_ERROR = None


APP_NAME = "OpenFunASR"
PASTE_SELF_TEST_PREFIX = "--paste-self-test="
PASTE_SELF_TEST_MARKER = "OPENFUNASR_PASTE_OK"
CONFIG_DIR = Path(
    os.environ.get(
        "OPENFUNASR_CONFIG_DIR",
        str(Path.home() / "Library" / "Application Support" / "OpenFunASR"),
    )
).expanduser().resolve()
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "app.log"
PASTE_SELF_TEST_TRIGGER = CONFIG_DIR / ".paste-self-test"
LOCAL_RUNTIME_ROOT = Path(
    os.environ.get("OPENFUNASR_LOCAL_RUNTIME_ROOT", str(CONFIG_DIR / "runtime"))
).expanduser().resolve()


def default_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if executable.parent.name == "MacOS" and executable.parent.parent.name == "Contents":
            return executable.parent.parent / "Resources"
    return Path(__file__).resolve().parent


RESOURCE_ROOT = Path(os.environ.get("OPENFUNASR_RESOURCE_ROOT", str(default_resource_root()))).resolve()
MODELS_DIR = RESOURCE_ROOT / "models"
DEFAULT_VAD_MODEL_NAME = "ggml-silero-v6.2.0.bin"
FUNASR_ENCODER_MODEL_NAME = "funasr-encoder-f16.gguf"
FUNASR_DECODER_MODEL_NAME = "qwen3-0.6b-q5km.gguf"
FUNASR_VAD_MODEL_NAME = "fsmn-vad.gguf"
ENGINE_DISPLAY_NAME = "Fun-ASR Nano Q5_K_M"
DEFAULT_AUDIO_FILE = Path(f"/tmp/openfunasr-{os.getpid()}.wav")
MIN_AUDIO_DURATION_SECONDS = 0.25
MIN_AUDIO_RMS_RATIO = 0.001
VAD_TIMEOUT_SECONDS = 15
TRANSCRIPTION_TIMEOUT_SECONDS = 180
K_AUDIO_FORMAT_LINEAR_PCM = 1819304813
CHINESE_DIGIT_VALUES = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "壹": 1,
    "贰": 2,
    "叁": 3,
    "肆": 4,
    "伍": 5,
    "陆": 6,
    "柒": 7,
    "捌": 8,
    "玖": 9,
}
CHINESE_SMALL_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
CHINESE_LARGE_UNITS = {"万": 10_000, "萬": 10_000, "亿": 100_000_000, "億": 100_000_000}
CHINESE_NUMERAL_CHARACTERS = "零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟萬億"
CHINESE_NUMERAL_PATTERN = re.compile(f"[{CHINESE_NUMERAL_CHARACTERS}]+")
CHINESE_DECIMAL_PATTERN = re.compile(
    f"(?P<sign>负)?(?P<whole>[{CHINESE_NUMERAL_CHARACTERS}]+)点"
    f"(?P<fraction>[零〇一二两三四五六七八九壹贰叁肆伍陆柒捌玖]+)"
)
CHINESE_PERCENT_PATTERN = re.compile(f"百分之(?P<number>[{CHINESE_NUMERAL_CHARACTERS}]+)")
STRONG_NUMERIC_FOLLOWER_PATTERN = re.compile(
    r"(?:个|位|名|人|次|遍|回|件|条|份|张|本|台|辆|只|支|杯|瓶|箱|套|组|种|类|项|"
    r"页|行|列|章|节|集|季|期|级|层|楼|号|天|周|星期|年|月|日|小时|分钟|秒|岁|"
    r"毫米|厘米|公里|千米|米|毫克|克|公斤|千克|斤|吨|元|块|美元|欧元|倍|成|折|"
    r"度|兆|GB|MB|TB|%|％)"
)
MEASUREMENT_NUMERIC_FOLLOWER_PATTERN = re.compile(
    r"(?:小时|分钟|秒|毫米|厘米|公里|千米|米|毫克|克|公斤|千克|斤|吨|元|块|"
    r"美元|欧元|倍|成|折|度|兆|GB|MB|TB|%|％)"
)
GENERIC_COUNT_FOLLOWER_PATTERN = re.compile(
    r"(?:个|位|名|人|次|遍|回|件|条|份|张|本|台|辆|只|支|杯|瓶|箱|套|组|种|类|项)"
)
ARABIC_ORDINAL_FOLLOWER_PATTERN = re.compile(
    r"(?:页|行|列|章|节|集|季|期|级|层|楼|号)"
)
CHINESE_DATE_PATTERN = re.compile(
    f"(?P<year>[{CHINESE_NUMERAL_CHARACTERS}]{{2,}})年"
    f"(?P<month>[{CHINESE_NUMERAL_CHARACTERS}]+)月"
    f"(?P<day>[{CHINESE_NUMERAL_CHARACTERS}]+)日?"
)
CHINESE_YEAR_PATTERN = re.compile(
    r"(?P<year>[零〇一二两三四五六七八九壹贰叁肆伍陆柒捌玖]{4})年"
)
CHINESE_MONTH_DAY_PATTERN = re.compile(
    f"(?P<month>[{CHINESE_NUMERAL_CHARACTERS}]+)月"
    f"(?P<day>[{CHINESE_NUMERAL_CHARACTERS}]+)日"
)
CHINESE_TIME_PATTERN = re.compile(
    f"(?P<hour>[{CHINESE_NUMERAL_CHARACTERS}]+)点"
    f"(?P<minute>[{CHINESE_NUMERAL_CHARACTERS}]+)分?"
)
PREFIXED_CHINESE_HOUR_PATTERN = re.compile(
    f"(?P<prefix>凌晨|早上|上午|中午|下午|晚上)"
    f"(?P<hour>[{CHINESE_NUMERAL_CHARACTERS}]+)点"
)
CONTEXTUAL_DIGIT_SEQUENCE_PATTERN = re.compile(
    r"(?P<label>验证码|密码|编号|号码|代码|尾号|工号|订单号|房间号)"
    r"(?P<number>[零〇一二两三四五六七八九壹贰叁肆伍陆柒捌玖]{2,})"
)
LEXICAL_NUMERAL_TOKENS = {"万一", "千万"}
PAUSE_COMMA_FUNCTION_WORD_PATTERN = re.compile(
    r"(?P<prefix>[\u3400-\u9fffA-Za-z0-9])"
    r"(?P<function>关于|对于|根据|按照|通过|为了|除了|对|把|被|给|向|从|与|跟|"
    r"将|替|让|使|令|比)[，,]\s*(?=[\u3400-\u9fffA-Za-z0-9])"
)
PAUSE_COMMA_PRONOUN_PREDICATE_PATTERN = re.compile(
    r"(?P<subject>我|你|他|她|它|我们|你们|他们|她们|大家|自己)[，,]\s*"
    r"(?=(?:很|非常|特别|尤其|最|更|也|都|就|还|只|又|并|却|才|真|实在|确实|"
    r"完全|绝对|不|没|没有|要|会|能|可以|应该|必须|需要|想|希望|认为|觉得|"
    r"喜欢|讨厌|厌恶|关注|要求|接受|拒绝|同意|反对|知道|明白|发现|看到|听到|"
    r"担心|害怕))"
)
PAUSE_COMMA_MODIFIER_PATTERN = re.compile(
    r"(?P<modifier>非常|特别|尤其|十分|实在|确实|完全|绝对|应该|必须|需要|"
    r"可以|不会|不能|不要|没有)[，,]\s*"
    r"(?=(?:喜欢|讨厌|厌恶|关注|要求|接受|拒绝|同意|反对|知道|明白|发现|"
    r"看到|听到|担心|害怕|希望|重要|清楚|明显|严重|好|差|大|小|高|低|快|慢))"
)
RELATIVE_CLAUSE_QUESTION_BREAK_PATTERN = re.compile(
    r"(?P<head>(?:^|[。！？!?])[^。！？!?]*"
    r"(?:有哪些|有什么|哪些|什么样|哪种|哪类|哪一个)"
    r"[^。！？!?]{0,80}的)[？?]\s*"
    r"(?P<tail>[\u3400-\u9fffA-Za-z0-9·—-]{1,20})[。.]?$"
)
QUESTION_BREAK_TAIL_PREDICATES = (
    "是", "有", "会", "能", "要", "想", "可以", "应该", "很多", "不少", "很好", "怎么", "为什么"
)
VALID_NAMED_HOTKEYS = {
    "space",
    "tab",
    "enter",
    "return",
    "esc",
    "escape",
    "backspace",
    "delete",
    "home",
    "end",
    "page_up",
    "page_down",
    "up",
    "down",
    "left",
    "right",
} | {f"f{index}" for index in range(1, 21)}
AV_MEDIA_TYPE_AUDIO = "soun"
AV_AUTH_NOT_DETERMINED = 0
AV_AUTH_RESTRICTED = 1
AV_AUTH_DENIED = 2
AV_AUTH_AUTHORIZED = 3
MICROPHONE_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
ACCESSIBILITY_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
PRIVACY_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy"
KEYCODE_V = 9
K_EVENT_CLASS_KEYBOARD = int.from_bytes(b"keyb", "big")
K_EVENT_HOT_KEY_PRESSED = 5
K_EVENT_HOT_KEY_RELEASED = 6
K_EVENT_HOT_KEY_ID_SIGNATURE = int.from_bytes(b"OFAS", "big")
MAC_KEY_CODES = {
    "a": 0,
    "s": 1,
    "d": 2,
    "f": 3,
    "h": 4,
    "g": 5,
    "z": 6,
    "x": 7,
    "c": 8,
    "v": 9,
    "b": 11,
    "q": 12,
    "w": 13,
    "e": 14,
    "r": 15,
    "y": 16,
    "t": 17,
    "1": 18,
    "2": 19,
    "3": 20,
    "4": 21,
    "6": 22,
    "5": 23,
    "=": 24,
    "9": 25,
    "7": 26,
    "-": 27,
    "8": 28,
    "0": 29,
    "]": 30,
    "o": 31,
    "u": 32,
    "[": 33,
    "i": 34,
    "p": 35,
    "l": 37,
    "j": 38,
    "'": 39,
    "k": 40,
    ";": 41,
    "\\": 42,
    ",": 43,
    "/": 44,
    "n": 45,
    "m": 46,
    ".": 47,
    "`": 50,
    "enter": 36,
    "return": 36,
    "tab": 48,
    "space": 49,
    "backspace": 51,
    "delete": 51,
    "esc": 53,
    "escape": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "f1": 122,
    "f2": 120,
    "f3": 99,
    "f4": 118,
    "f5": 96,
    "f6": 97,
    "f7": 98,
    "f8": 100,
    "f9": 101,
    "f10": 109,
    "f11": 103,
    "f12": 111,
    "f13": 105,
    "f14": 107,
    "f15": 113,
    "f16": 106,
    "f17": 64,
    "f18": 79,
    "f19": 80,
    "f20": 90,
}


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


EventHandlerProc = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


def register_avfoundation_metadata() -> None:
    try:
        objc.registerMetaDataForSelector(
            b"AVCaptureDevice",
            b"requestAccessForMediaType:completionHandler:",
            {
                "arguments": {
                    3: {
                        "callable": {
                            "retval": {"type": objc._C_VOID},
                            "arguments": {0: {"type": objc._C_NSBOOL}},
                        }
                    }
                }
            },
        )
    except Exception as error:
        append_log(f"AVFoundation metadata registration failed: {error}")
DEFAULT_CONFIG = {
    "hotkeys": "F5, F9",
    "auto_paste": True,
    "recent_result_expanded": False,
    "onboarding_done": False,
}


def merge_config(data: dict | None) -> dict:
    config = DEFAULT_CONFIG.copy()
    if isinstance(data, dict):
        for key in DEFAULT_CONFIG:
            if key in data:
                config[key] = data[key]
    return config


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as handle:
                return merge_config(json.load(handle))
        except Exception:
            return merge_config(None)
    return merge_config(None)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)


def append_log(message: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def first_existing_path(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def resolve_binary(name: str, fallback: str) -> Path | None:
    candidates = [LOCAL_RUNTIME_ROOT / "bin" / name, RESOURCE_ROOT / "bin" / name]
    discovered = shutil.which(name)
    if discovered:
        candidates.append(Path(discovered))
    candidates.append(Path(fallback))
    return first_existing_path(candidates)


def resolve_vad_model() -> Path | None:
    candidates = [LOCAL_RUNTIME_ROOT / "models" / DEFAULT_VAD_MODEL_NAME, MODELS_DIR / DEFAULT_VAD_MODEL_NAME]
    return first_existing_path(candidates)


def resolve_vad_binary() -> Path | None:
    discovered = shutil.which("whisper-vad-speech-segments")
    return resolve_binary("speech-vad", discovered or "/usr/local/bin/whisper-vad-speech-segments")


def resolve_funasr_binary() -> Path | None:
    return resolve_binary("llama-funasr-cli", "/usr/local/bin/llama-funasr-cli")


def resolve_funasr_model(name: str) -> Path | None:
    candidates = [LOCAL_RUNTIME_ROOT / "models" / name, MODELS_DIR / name]
    return first_existing_path(candidates)


def chinese_integer_to_arabic(token: str) -> str | None:
    """Convert an unambiguous Chinese integer token without guessing lexical uses."""
    if not token:
        return None
    has_unit = any(character in CHINESE_SMALL_UNITS or character in CHINESE_LARGE_UNITS for character in token)
    if not has_unit:
        try:
            return "".join(str(CHINESE_DIGIT_VALUES[character]) for character in token)
        except KeyError:
            return None

    if not any(character in CHINESE_DIGIT_VALUES for character in token):
        return "10" if token in {"十", "拾"} else None

    total = 0
    section = 0
    number = 0
    for character in token:
        if character in CHINESE_DIGIT_VALUES:
            number = CHINESE_DIGIT_VALUES[character]
        elif character in CHINESE_SMALL_UNITS:
            section += (number or 1) * CHINESE_SMALL_UNITS[character]
            number = 0
        elif character in CHINESE_LARGE_UNITS:
            section += number
            total += (section or 1) * CHINESE_LARGE_UNITS[character]
            section = 0
            number = 0
        else:
            return None
    return str(total + section + number)


def normalize_chinese_numerals(text: str) -> tuple[str, int]:
    """Normalize Chinese numerals only when the surrounding text calls for digits."""
    conversions = 0

    def replace_percent(match: re.Match[str]) -> str:
        nonlocal conversions
        value = chinese_integer_to_arabic(match.group("number"))
        if value is None:
            return match.group(0)
        conversions += 1
        return f"{value}%"

    def replace_decimal(match: re.Match[str]) -> str:
        nonlocal conversions
        whole = chinese_integer_to_arabic(match.group("whole"))
        fraction = chinese_integer_to_arabic(match.group("fraction"))
        if whole is None or fraction is None:
            return match.group(0)
        conversions += 1
        sign = "-" if match.group("sign") else ""
        return f"{sign}{whole}.{fraction}"

    text = CHINESE_PERCENT_PATTERN.sub(replace_percent, text)
    text = CHINESE_DECIMAL_PATTERN.sub(replace_decimal, text)

    def replace_date(match: re.Match[str]) -> str:
        nonlocal conversions
        year = chinese_integer_to_arabic(match.group("year"))
        month = chinese_integer_to_arabic(match.group("month"))
        day = chinese_integer_to_arabic(match.group("day"))
        if year is None or month is None or day is None:
            return match.group(0)
        conversions += 3
        suffix = "日" if match.group(0).endswith("日") else ""
        return f"{year}年{month}月{day}{suffix}"

    def replace_year(match: re.Match[str]) -> str:
        nonlocal conversions
        year = chinese_integer_to_arabic(match.group("year"))
        if year is None:
            return match.group(0)
        conversions += 1
        return f"{year}年"

    text = CHINESE_DATE_PATTERN.sub(replace_date, text)
    text = CHINESE_YEAR_PATTERN.sub(replace_year, text)

    def replace_month_day(match: re.Match[str]) -> str:
        nonlocal conversions
        month = chinese_integer_to_arabic(match.group("month"))
        day = chinese_integer_to_arabic(match.group("day"))
        if month is None or day is None:
            return match.group(0)
        conversions += 2
        return f"{month}月{day}日"

    def replace_time(match: re.Match[str]) -> str:
        nonlocal conversions
        hour = chinese_integer_to_arabic(match.group("hour"))
        minute = chinese_integer_to_arabic(match.group("minute"))
        if hour is None or minute is None:
            return match.group(0)
        conversions += 2
        suffix = "分" if match.group(0).endswith("分") else ""
        return f"{hour}点{minute}{suffix}"

    def replace_prefixed_hour(match: re.Match[str]) -> str:
        nonlocal conversions
        hour = chinese_integer_to_arabic(match.group("hour"))
        if hour is None:
            return match.group(0)
        conversions += 1
        return f'{match.group("prefix")}{hour}点'

    def replace_contextual_digit_sequence(match: re.Match[str]) -> str:
        nonlocal conversions
        number = chinese_integer_to_arabic(match.group("number"))
        if number is None:
            return match.group(0)
        conversions += 1
        return f'{match.group("label")}{number}'

    text = CHINESE_MONTH_DAY_PATTERN.sub(replace_month_day, text)
    text = CHINESE_TIME_PATTERN.sub(replace_time, text)
    text = PREFIXED_CHINESE_HOUR_PATTERN.sub(replace_prefixed_hour, text)
    text = CONTEXTUAL_DIGIT_SEQUENCE_PATTERN.sub(replace_contextual_digit_sequence, text)

    def replace_integer(match: re.Match[str]) -> str:
        nonlocal conversions
        token = match.group(0)
        start, end = match.span()
        previous = text[start - 1] if start else ""
        following = text[end:]
        is_financial = any(character in "壹贰叁肆伍陆柒捌玖拾佰仟萬億" for character in token)
        has_unit = any(character in CHINESE_SMALL_UNITS or character in CHINESE_LARGE_UNITS for character in token)
        strong_context = (
            (bool(previous) and previous in "到至")
            or (following[:1] in "到至" and len(following) > 1)
            or STRONG_NUMERIC_FOLLOWER_PATTERN.match(following) is not None
        )
        if token in LEXICAL_NUMERAL_TOKENS and not strong_context:
            return token
        if len(token) == 1 and not is_financial and not strong_context:
            return token
        if (
            has_unit
            and not any(character in CHINESE_DIGIT_VALUES for character in token)
            and not (token in {"十", "拾"} and strong_context)
        ):
            return token
        value = chinese_integer_to_arabic(token)
        if value is None:
            return token
        numeric_value = int(value)
        is_range = (bool(previous) and previous in "到至") or (
            bool(following) and following[:1] in "到至"
        )
        is_ordinal = previous == "第"
        if is_ordinal and ARABIC_ORDINAL_FOLLOWER_PATTERN.match(following) is None:
            return token
        if not has_unit and not is_financial and not is_range and not is_ordinal:
            if MEASUREMENT_NUMERIC_FOLLOWER_PATTERN.match(following) is None:
                if GENERIC_COUNT_FOLLOWER_PATTERN.match(following) is None or numeric_value < 10:
                    return token
        if GENERIC_COUNT_FOLLOWER_PATTERN.match(following) is not None and numeric_value < 10:
            return token
        conversions += 1
        return value

    return CHINESE_NUMERAL_PATTERN.sub(replace_integer, text), conversions


def remove_spurious_pause_commas(text: str) -> tuple[str, int]:
    """Remove commas that split a small set of high-confidence Chinese grammar chunks."""
    removed = 0

    def join_named_group(match: re.Match[str], group: str) -> str:
        nonlocal removed
        removed += 1
        return match.group(group)

    def join_function_word(match: re.Match[str]) -> str:
        nonlocal removed
        following = match.string[match.end():]
        if match.group("function") == "对" and re.match(
            r"(?:我(?:们)?|你(?:们)?|他(?:们)?|她(?:们)?|它(?:们)?|大家|但是|可是|却)",
            following,
        ):
            return match.group(0)
        removed += 1
        return f'{match.group("prefix")}{match.group("function")}'

    text = PAUSE_COMMA_FUNCTION_WORD_PATTERN.sub(join_function_word, text)
    text = PAUSE_COMMA_PRONOUN_PREDICATE_PATTERN.sub(
        lambda match: join_named_group(match, "subject"), text
    )
    text = PAUSE_COMMA_MODIFIER_PATTERN.sub(
        lambda match: join_named_group(match, "modifier"), text
    )
    return text, removed


def repair_spurious_question_breaks(text: str) -> tuple[str, int]:
    """Move a question mark that splits a relative clause from its short noun head."""
    repairs = 0

    def move_question_mark(match: re.Match[str]) -> str:
        nonlocal repairs
        tail = match.group("tail")
        if any(predicate in tail for predicate in QUESTION_BREAK_TAIL_PREDICATES):
            return match.group(0)
        repairs += 1
        return f'{match.group("head")}{tail}？'

    return RELATIVE_CLAUSE_QUESTION_BREAK_PATTERN.sub(move_question_mark, text), repairs


def postprocess_transcript(text: str, speech_segment_count: int = 1) -> tuple[str, int, int]:
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    text, _ = remove_spurious_pause_commas(text)
    text, _ = repair_spurious_question_breaks(text)
    text, numeral_conversions = normalize_chinese_numerals(text)
    softened_periods = 0
    if speech_segment_count > 1:
        text, softened_periods = re.subn(r"(?<=\S)。\s*(?=\S)", "，", text)
        text, ascii_softened = re.subn(r"(?<=[\u3400-\u9fff])\.\s*(?=[\u3400-\u9fff])", "，", text)
        softened_periods += ascii_softened
    return text, numeral_conversions, softened_periods


def clean_transcript(text: str, speech_segment_count: int = 1) -> str:
    return postprocess_transcript(text, speech_segment_count)[0]


def build_funasr_command(
    binary: Path,
    encoder: Path,
    model: Path,
    vad_model: Path,
    audio: Path,
) -> list[str]:
    return [
        str(binary), "--enc", str(encoder), "-m", str(model),
        "--vad", str(vad_model), "-a", str(audio),
    ]


def wav_has_enough_signal(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as audio:
            frame_count = audio.getnframes()
            frame_rate = audio.getframerate()
            sample_width = audio.getsampwidth()
            frames = audio.readframes(frame_count)
    except Exception as error:
        append_log(f"wav signal check failed: {error}")
        return True

    if frame_rate <= 0 or frame_count <= 0 or sample_width <= 0:
        return False
    duration = frame_count / frame_rate
    if duration < MIN_AUDIO_DURATION_SECONDS:
        append_log(f"audio ignored: duration={duration:.3f}s")
        return False
    if not frames:
        return False

    rms = audioop.rms(frames, sample_width)
    max_value = float(2 ** (8 * sample_width - 1))
    ratio = rms / max_value if max_value else 0.0
    if ratio < MIN_AUDIO_RMS_RATIO:
        append_log(f"audio ignored: rms={ratio:.6f}")
        return False
    return True


def parse_hotkey_tokens(raw: str) -> set[str]:
    tokens: set[str] = set()
    for part in raw.split(","):
        token = part.strip().lower()
        if not token:
            continue
        if token.startswith("key."):
            token = token[4:]
        if token not in VALID_NAMED_HOTKEYS and not (len(token) == 1 and token.isprintable()):
            raise ValueError(f"不支持的快捷键: {part.strip()}")
        tokens.add(token)
    return tokens or {"f5", "f9"}


def token_to_mac_keycode(token: str) -> int:
    if token not in MAC_KEY_CODES:
        raise ValueError(f"当前版本不支持这个快捷键: {token}")
    return MAC_KEY_CODES[token]


def load_carbon():
    path = "/System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/HIToolbox"
    carbon = ctypes.CDLL(path)
    carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
    carbon.GetEventKind.argtypes = [ctypes.c_void_p]
    carbon.GetEventKind.restype = ctypes.c_uint32
    carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p,
        EventHandlerProc,
        ctypes.c_uint32,
        ctypes.POINTER(EventTypeSpec),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.InstallEventHandler.restype = ctypes.c_int32
    carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
    carbon.RemoveEventHandler.restype = ctypes.c_int32
    carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        EventHotKeyID,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    carbon.RegisterEventHotKey.restype = ctypes.c_int32
    carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    carbon.UnregisterEventHotKey.restype = ctypes.c_int32
    return carbon


def accessibility_permission_state(prompt: bool = False) -> str:
    try:
        options = {kAXTrustedCheckOptionPrompt: kCFBooleanTrue} if prompt else None
        return "已授权" if AXIsProcessTrustedWithOptions(options) else "未授权"
    except Exception as error:
        append_log(f"accessibility permission check failed: {error}")
        return "无法检测"


def paste_with_quartz() -> None:
    # The caller owns prompting. A transcription must never make macOS open the
    # privacy pane repeatedly just because the current code signature is stale.
    if accessibility_permission_state(prompt=False) != "已授权":
        raise RuntimeError("自动粘贴未授权")

    for is_down in (True, False):
        event = CGEventCreateKeyboardEvent(None, KEYCODE_V, is_down)
        if event is None:
            raise RuntimeError("粘贴按键事件创建失败")
        CGEventSetFlags(event, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event)
        time.sleep(0.02)


def av_capture_device_class():
    try:
        bundle = NSBundle.bundleWithPath_("/System/Library/Frameworks/AVFoundation.framework")
        if bundle is not None:
            bundle.load()
        register_avfoundation_metadata()
        return objc.lookUpClass("AVCaptureDevice")
    except Exception as error:
        append_log(f"AVFoundation unavailable: {error}")
        return None


def av_audio_recorder_class():
    try:
        bundle = NSBundle.bundleWithPath_("/System/Library/Frameworks/AVFoundation.framework")
        if bundle is not None:
            bundle.load()
        return objc.lookUpClass("AVAudioRecorder")
    except Exception as error:
        append_log(f"AVAudioRecorder unavailable: {error}")
        return None


def microphone_permission_state() -> tuple[int | None, str]:
    device_class = av_capture_device_class()
    if device_class is None:
        return None, "无法检测"
    try:
        status = int(device_class.authorizationStatusForMediaType_(AV_MEDIA_TYPE_AUDIO))
    except Exception as error:
        append_log(f"microphone permission check failed: {error}")
        return None, "无法检测"
    if status == AV_AUTH_NOT_DETERMINED:
        return status, "待授权"
    if status == AV_AUTH_RESTRICTED:
        return status, "受限制"
    if status == AV_AUTH_DENIED:
        return status, "未授权"
    if status == AV_AUTH_AUTHORIZED:
        return status, "已授权"
    return status, "未知"


def make_audio_recorder(path: Path):
    recorder_class = av_audio_recorder_class()
    if recorder_class is None:
        raise RuntimeError("AVAudioRecorder 不可用")
    url = NSURL.fileURLWithPath_(str(path))
    settings = {
        "AVFormatIDKey": K_AUDIO_FORMAT_LINEAR_PCM,
        "AVSampleRateKey": 16000.0,
        "AVNumberOfChannelsKey": 1,
        "AVLinearPCMBitDepthKey": 16,
        "AVLinearPCMIsFloatKey": False,
        "AVLinearPCMIsBigEndianKey": False,
    }
    recorder = recorder_class.alloc().initWithURL_settings_error_(url, settings, None)
    if recorder is None:
        raise RuntimeError("录音器初始化失败")
    if not recorder.prepareToRecord():
        raise RuntimeError("录音器准备失败")
    return recorder


class CarbonHotKeyManager:
    def __init__(self, delegate):
        self.delegate = delegate
        self.carbon = None
        self.handler_ref = ctypes.c_void_p()
        self.callback = None
        self.hotkey_refs: list[ctypes.c_void_p] = []

    def start(self, tokens: set[str]) -> None:
        self.stop()
        self.carbon = load_carbon()
        self.callback = EventHandlerProc(self.handle_event)
        event_types = (EventTypeSpec * 2)(
            EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOT_KEY_PRESSED),
            EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOT_KEY_RELEASED),
        )
        target = self.carbon.GetApplicationEventTarget()
        status = self.carbon.InstallEventHandler(
            target,
            self.callback,
            2,
            event_types,
            None,
            ctypes.byref(self.handler_ref),
        )
        if status != 0:
            raise RuntimeError(f"热键处理器注册失败: {status}")

        registered = 0
        for index, token in enumerate(sorted(tokens), start=1):
            keycode = token_to_mac_keycode(token)
            hotkey_ref = ctypes.c_void_p()
            hotkey_id = EventHotKeyID(K_EVENT_HOT_KEY_ID_SIGNATURE, index)
            status = self.carbon.RegisterEventHotKey(keycode, 0, hotkey_id, target, 0, ctypes.byref(hotkey_ref))
            if status != 0:
                append_log(f"hotkey registration failed token={token} status={status}")
                continue
            self.hotkey_refs.append(hotkey_ref)
            registered += 1
        if registered == 0:
            self.stop()
            raise RuntimeError("没有可用快捷键")

    def stop(self) -> None:
        if self.carbon is not None:
            for hotkey_ref in self.hotkey_refs:
                if hotkey_ref:
                    try:
                        self.carbon.UnregisterEventHotKey(hotkey_ref)
                    except Exception:
                        pass
            if self.handler_ref:
                try:
                    self.carbon.RemoveEventHandler(self.handler_ref)
                except Exception:
                    pass
        self.hotkey_refs = []
        self.handler_ref = ctypes.c_void_p()
        self.callback = None
        self.carbon = None

    def handle_event(self, next_handler, event, user_data):
        try:
            kind = self.carbon.GetEventKind(event) if self.carbon is not None else 0
            if kind == K_EVENT_HOT_KEY_PRESSED:
                AppHelper.callAfter(self.delegate.startRecording)
            elif kind == K_EVENT_HOT_KEY_RELEASED:
                AppHelper.callAfter(self.delegate.stopRecordingAndTranscribe)
        except Exception as error:
            append_log(f"hotkey event failed: {error}")
        return 0


class PanelViewController(NSViewController):
    def initWithDelegate_(self, delegate):
        self = objc.super(PanelViewController, self).init()
        if self is None:
            return None
        self.delegate = delegate
        self.controls_ready = False
        return self

    def loadView(self):
        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 320, 286))
        self.setView_(view)

        self.title_label = self.addLabel(view, APP_NAME, 16, 248, 150, 24, size=17, bold=True)
        self.state_label = self.addLabel(view, "", 16, 226, 288, 18, size=12, secondary=True)

        self.addLabel(view, "引擎", 16, 194, 54, 18, size=12, secondary=True, bold=True)
        self.addLabel(view, ENGINE_DISPLAY_NAME, 78, 192, 226, 20, size=13)

        self.mode_segment = NSSegmentedControl.alloc().initWithFrame_(NSMakeRect(16, 150, 288, 26))
        self.mode_segment.setSegmentCount_(2)
        self.mode_segment.setLabel_forSegment_("自动粘贴", 0)
        self.mode_segment.setLabel_forSegment_("只复制", 1)
        self.mode_segment.setWidth_forSegment_(144, 0)
        self.mode_segment.setWidth_forSegment_(144, 1)
        self.mode_segment.setSegmentStyle_(NSSegmentStyleRounded)
        self.mode_segment.setTarget_(self)
        self.mode_segment.setAction_("changeMode:")
        view.addSubview_(self.mode_segment)

        self.addSeparator(view, 132)

        self.addLabel(view, "快捷键", 16, 110, 54, 18, size=12, secondary=True, bold=True)
        self.hotkey_label = self.addLabel(view, "", 78, 108, 140, 20, size=13)
        self.change_hotkey_button = self.addButton(view, "修改", "openSettings:", 244, 104, 60, 24)

        self.addLabel(view, "状态", 16, 78, 54, 18, size=12, secondary=True, bold=True)
        self.error_label = self.addLabel(view, "", 78, 76, 226, 20, size=12)

        self.recent_button = self.addButton(view, "最近结果", "toggleRecent:", 16, 44, 92, 24)
        self.recent_button.setBezelStyle_(NSBezelStyleRounded)
        self.recent_label = self.addLabel(view, "", 120, 44, 184, 22, size=12)

        self.restart_button = self.addButton(view, "重启服务", "restartService:", 16, 12, 88, 24)
        self.settings_button = self.addButton(view, "设置", "openSettings:", 116, 12, 72, 24)
        self.quit_button = self.addButton(view, "退出", "quitApp:", 244, 12, 60, 24)

        self.controls_ready = True
        self.updateView()

    @objc.python_method
    def addLabel(self, parent, text, x, y, width, height, size=13, secondary=False, bold=False):
        label = NSTextField.labelWithString_(text)
        label.setFrame_(NSMakeRect(x, y, width, height))
        label.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
        if secondary:
            label.setTextColor_(NSColor.secondaryLabelColor())
        parent.addSubview_(label)
        return label

    @objc.python_method
    def addButton(self, parent, title, action, x, y, width, height):
        button = NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(NSMakeRect(x, y, width, height))
        button.setBezelStyle_(NSRoundedBezelStyle)
        parent.addSubview_(button)
        return button

    @objc.python_method
    def addSeparator(self, parent, y):
        line = NSBox.alloc().initWithFrame_(NSMakeRect(16, y, 288, 1))
        line.setBoxType_(NSBoxSeparator)
        parent.addSubview_(line)

    @objc.python_method
    def updateView(self):
        if not self.controls_ready:
            return
        app = self.delegate
        self.state_label.setStringValue_(app.status_text())
        self.mode_segment.setSelectedSegment_(0 if app.config["auto_paste"] else 1)
        self.hotkey_label.setStringValue_(app.config["hotkeys"])
        self.error_label.setStringValue_(app.last_error or "正常")
        self.error_label.setTextColor_(NSColor.systemRedColor() if app.last_error else NSColor.secondaryLabelColor())

        if app.config["recent_result_expanded"]:
            self.recent_button.setTitle_("隐藏结果")
            self.recent_label.setHidden_(False)
            self.recent_label.setStringValue_(app.last_result or "暂无")
        else:
            self.recent_button.setTitle_("最近结果")
            self.recent_label.setHidden_(True)

    def changeMode_(self, sender):
        self.delegate.config["auto_paste"] = sender.selectedSegment() == 0
        self.delegate.persist_and_update()

    def toggleRecent_(self, sender):
        self.delegate.config["recent_result_expanded"] = not self.delegate.config["recent_result_expanded"]
        self.delegate.persist_and_update()

    def restartService_(self, sender):
        self.delegate.restartService_(sender)

    def openSettings_(self, sender):
        self.delegate.showSettings_(sender)

    def quitApp_(self, sender):
        NSApp.terminate_(None)


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.config = load_config()
        microphone_status, microphone_state = microphone_permission_state()
        append_log(
            "startup permissions "
            f"accessibility={accessibility_permission_state(prompt=False)} "
            f"microphone={microphone_state}({microphone_status})"
        )
        self.runtime_state = "启动中"
        self.last_error = ""
        self.last_result = ""
        self.permission_states = {
            "麦克风": "待授权",
            "快捷键": "待授权",
            "自动粘贴": "待授权",
        }
        self.vad_bin: Path | None = None
        self.vad_model_path: Path | None = None
        self.funasr_bin: Path | None = None
        self.funasr_encoder_path: Path | None = None
        self.funasr_model_path: Path | None = None
        self.funasr_vad_path: Path | None = None
        self.hotkey_manager = CarbonHotKeyManager(self)
        self.hotkey_tokens: set[str] = set()
        self.audio_recorder = None
        self.recognition_process: subprocess.Popen | None = None
        self.recording = False
        self.transcribing = False
        self.popover = None
        self.popover_event_monitor = None
        self.status_animation_index = 0
        self.status_animation_timer = None
        self.auto_paste_permission_prompted = False
        self.panel_controller = None
        self.onboarding_window = None
        self.settings_window = None
        self.settings_controls = {}
        self.permission_settings_opened = False
        self.paste_self_test_stop_event = threading.Event()
        signal.signal(signal.SIGUSR1, self.handlePasteSelfTestSignal)
        threading.Thread(target=self.watchPasteSelfTestTrigger, daemon=True).start()
        self.buildStatusItem()
        self.buildPopover()
        self.requestStartupPermissions()
        self.startService()
        if self.shouldShowStartupWindow():
            self.showOnboarding_(None)
            self.openNeededPermissionSettings(prompt_accessibility=True)
        elif "--show-settings" in sys.argv:
            AppHelper.callAfter(self.showSettings_, None)
        elif "--request-accessibility" in sys.argv:
            AppHelper.callAfter(self.requestAccessibilityPermission)

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return False

    @objc.python_method
    def handlePasteSelfTestSignal(self, signum, frame):
        AppHelper.callAfter(self.runPasteSelfTest)

    @objc.python_method
    def runPasteSelfTest(self):
        permission = accessibility_permission_state(prompt=False)
        frontmost = NSWorkspace.sharedWorkspace().frontmostApplication()
        frontmost_name = frontmost.localizedName() if frontmost is not None else "unknown"
        append_log(
            "paste self-test started "
            f"accessibility={permission} frontmost={frontmost_name} marker={PASTE_SELF_TEST_MARKER}"
        )
        if permission != "已授权":
            append_log("paste self-test failed: accessibility denied")
            return
        if pyperclip is None:
            append_log(f"paste self-test failed: clipboard unavailable {PYPERCLIP_IMPORT_ERROR}")
            return
        pyperclip.copy(PASTE_SELF_TEST_MARKER)
        try:
            paste_with_quartz()
        except Exception as error:
            append_log(f"paste self-test failed: {error!r}")
            return
        append_log("paste self-test event posted by resident app")

    @objc.python_method
    def watchPasteSelfTestTrigger(self):
        while not self.paste_self_test_stop_event.wait(0.2):
            if not PASTE_SELF_TEST_TRIGGER.exists():
                continue
            try:
                PASTE_SELF_TEST_TRIGGER.unlink()
            except OSError as error:
                append_log(f"paste self-test trigger failed: {error!r}")
                continue
            AppHelper.callAfter(self.runPasteSelfTest)

    def applicationWillTerminate_(self, notification):
        self.paste_self_test_stop_event.set()
        self.stopService()

    def applicationDidResignActive_(self, notification):
        self.closePopover()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, sender, hasVisibleWindows):
        self.updatePermissionStates(prompt_accessibility=False)
        if self.shouldShowStartupWindow():
            self.showOnboarding_(None)
            self.openNeededPermissionSettings(prompt_accessibility=True, force=True)
        else:
            self.showPopover()
        return True

    @objc.python_method
    def buildStatusItem(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(26.0)
        self.status_button = self.status_item.button()
        self.status_button.setTarget_(self)
        self.status_button.setAction_("togglePopover:")
        self.updateStatusItem()

    @objc.python_method
    def buildPopover(self):
        self.panel_controller = PanelViewController.alloc().initWithDelegate_(self)
        self.popover = NSPopover.alloc().init()
        self.popover.setBehavior_(NSPopoverBehaviorTransient)
        self.popover.setContentViewController_(self.panel_controller)
        self.popover.setDelegate_(self)

    def togglePopover_(self, sender):
        if self.popover.isShown():
            self.closePopover()
        else:
            self.showPopover()

    @objc.python_method
    def showPopover(self):
        self.panel_controller.updateView()
        self.popover.showRelativeToRect_ofView_preferredEdge_(self.status_button.bounds(), self.status_button, 1)
        self.installPopoverEventMonitor()

    @objc.python_method
    def closePopover(self):
        if self.popover is not None and self.popover.isShown():
            self.popover.performClose_(None)
        self.removePopoverEventMonitor()

    @objc.python_method
    def installPopoverEventMonitor(self):
        if self.popover_event_monitor is not None:
            return

        def handler(event):
            AppHelper.callAfter(self.closePopover)

        mask = NSLeftMouseDownMask | NSRightMouseDownMask | NSOtherMouseDownMask
        self.popover_event_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, handler)

    @objc.python_method
    def removePopoverEventMonitor(self):
        if self.popover_event_monitor is None:
            return
        NSEvent.removeMonitor_(self.popover_event_monitor)
        self.popover_event_monitor = None

    def popoverDidClose_(self, notification):
        self.removePopoverEventMonitor()

    @objc.python_method
    def status_text(self):
        if self.last_error:
            return self.last_error
        if self.runtime_state == "可用":
            return f"Fun-ASR 可用，按住 {self.config['hotkeys']} 说话"
        return self.runtime_state

    @objc.python_method
    def updateStatusItem(self):
        if self.runtime_state == "识别中":
            frames = ("ellipsis.circle", "ellipsis.circle.fill")
            self.setStatusSymbol(
                frames[self.status_animation_index % len(frames)],
                "正在识别语音",
                "…",
            )
        elif self.recording:
            self.setStatusSymbol("mic.fill", "正在录音", "●")
        elif self.last_error:
            self.setStatusSymbol("exclamationmark.triangle", "OpenFunASR 出现错误", "!")
        else:
            self.setStatusSymbol("waveform", "OpenFunASR 已就绪", "FA")

    @objc.python_method
    def setStatusSymbol(self, symbol_name: str, description: str, fallback: str):
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol_name, description)
        if image is None:
            self.status_button.setImage_(None)
            self.status_button.setTitle_(fallback)
            return
        image.setSize_(NSMakeSize(18, 18))
        image.setTemplate_(True)
        self.status_button.setTitle_("")
        self.status_button.setImagePosition_(NSImageOnly)
        self.status_button.setImage_(image)
        self.status_button.setAccessibilityLabel_(description)

    @objc.python_method
    def startStatusAnimation(self):
        if self.status_animation_timer is not None:
            return
        self.status_animation_index = 0
        self.scheduleStatusAnimationTick()

    @objc.python_method
    def scheduleStatusAnimationTick(self):
        if self.runtime_state != "识别中":
            self.status_animation_timer = None
            self.updateStatusItem()
            return
        self.status_animation_index += 1
        self.updateStatusItem()
        self.status_animation_timer = threading.Timer(0.2, lambda: AppHelper.callAfter(self.scheduleStatusAnimationTick))
        self.status_animation_timer.daemon = True
        self.status_animation_timer.start()

    @objc.python_method
    def stopStatusAnimation(self):
        timer = self.status_animation_timer
        self.status_animation_timer = None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
        self.updateStatusItem()

    @objc.python_method
    def updateViews(self):
        self.updateStatusItem()
        if self.panel_controller is not None:
            self.panel_controller.updateView()
        self.updateOnboarding()

    @objc.python_method
    def shouldShowStartupWindow(self) -> bool:
        if not self.config.get("onboarding_done", False):
            return True
        return self.hasBlockingStartupIssue()

    @objc.python_method
    def hasBlockingStartupIssue(self) -> bool:
        if self.last_error:
            return True
        return False

    @objc.python_method
    def persist_and_update(self):
        save_config(self.config)
        self.updateViews()

    @objc.python_method
    def set_error(self, message: str):
        self.last_error = message
        append_log(f"ERROR {message}")
        self.updateViews()

    @objc.python_method
    def clear_error(self):
        self.last_error = ""
        self.updateViews()

    @objc.python_method
    def checkRuntime(self) -> bool:
        if PYPERCLIP_IMPORT_ERROR is not None:
            self.set_error(f"剪贴板模块不可用: {PYPERCLIP_IMPORT_ERROR}")
            return False

        self.vad_bin = resolve_vad_binary()
        self.vad_model_path = resolve_vad_model()
        self.funasr_bin = resolve_funasr_binary()
        self.funasr_encoder_path = resolve_funasr_model(FUNASR_ENCODER_MODEL_NAME)
        self.funasr_model_path = resolve_funasr_model(FUNASR_DECODER_MODEL_NAME)
        self.funasr_vad_path = resolve_funasr_model(FUNASR_VAD_MODEL_NAME)

        if self.vad_bin is None:
            self.set_error("找不到语音检测程序")
            return False
        if self.vad_model_path is None:
            self.set_error("找不到语音检测模型")
            return False
        if self.funasr_bin is None:
            self.set_error("找不到 Fun-ASR 运行程序")
            return False
        if self.funasr_encoder_path is None or self.funasr_model_path is None or self.funasr_vad_path is None:
            self.set_error("找不到 Fun-ASR 模型")
            return False

        self.clear_error()
        append_log("engine=funasr_nano_q5_k_m")
        append_log(f"local_runtime_root={LOCAL_RUNTIME_ROOT}")
        append_log(f"vad_binary={self.vad_bin}")
        append_log(f"vad_model={self.vad_model_path}")
        append_log(f"funasr-cli={self.funasr_bin}")
        append_log(f"funasr_encoder={self.funasr_encoder_path}")
        append_log(f"funasr_model={self.funasr_model_path}")
        append_log(f"funasr_vad={self.funasr_vad_path}")
        return True

    @objc.python_method
    def requestStartupPermissions(self):
        self.updatePermissionStates(prompt_accessibility=False)
        status, _ = microphone_permission_state()
        if status != AV_AUTH_NOT_DETERMINED:
            return
        device_class = av_capture_device_class()
        if device_class is None:
            return

        def completion(*args):
            granted = bool(args[0]) if args else False
            AppHelper.callAfter(self.microphonePermissionFinished, granted)

        try:
            device_class.requestAccessForMediaType_completionHandler_(AV_MEDIA_TYPE_AUDIO, completion)
        except Exception as error:
            append_log(f"microphone permission request failed: {error}")

    @objc.python_method
    def microphonePermissionFinished(self, granted: bool):
        self.permission_states["麦克风"] = "已授权" if granted else "未授权"
        self.updateViews()

    @objc.python_method
    def updatePermissionStates(self, prompt_accessibility: bool = False):
        _, microphone_state = microphone_permission_state()
        self.permission_states = {
            "麦克风": microphone_state,
            "快捷键": "无需授权",
            "自动粘贴": accessibility_permission_state(prompt=False),
        }
        self.updateViews()

    @objc.python_method
    def startService(self):
        self.stopKeyboardListener()
        self.runtime_state = "启动中"
        self.updateViews()
        if not self.checkRuntime():
            return
        self.updatePermissionStates(prompt_accessibility=False)
        try:
            self.hotkey_tokens = parse_hotkey_tokens(self.config["hotkeys"])
            for token in self.hotkey_tokens:
                token_to_mac_keycode(token)
        except ValueError as error:
            self.set_error(str(error))
            return
        try:
            self.hotkey_manager.start(self.hotkey_tokens)
        except Exception as error:
            self.set_error(f"快捷键监听失败: {error}")
            return

        self.runtime_state = "可用"
        self.updatePermissionStates(prompt_accessibility=False)
        append_log(f"service started hotkeys={sorted(self.hotkey_tokens)}")
        self.updateViews()

    @objc.python_method
    def stopService(self):
        self.stopRecording()
        self.stopRecognitionProcess()
        self.stopKeyboardListener()

    @objc.python_method
    def stopKeyboardListener(self):
        self.hotkey_manager.stop()

    @objc.python_method
    def startRecording(self):
        if self.recording or self.transcribing or self.last_error:
            return
        status, state = microphone_permission_state()
        if status == AV_AUTH_DENIED:
            self.set_error("麦克风未授权")
            return
        if status == AV_AUTH_RESTRICTED:
            self.set_error("麦克风受限制")
            return

        try:
            if DEFAULT_AUDIO_FILE.exists():
                DEFAULT_AUDIO_FILE.unlink()
            self.audio_recorder = make_audio_recorder(DEFAULT_AUDIO_FILE)
            if not self.audio_recorder.record():
                self.audio_recorder = None
                self.set_error(f"录音启动失败: 麦克风{state}")
                return
        except Exception as error:
            self.audio_recorder = None
            self.set_error(f"录音启动失败: {error}")
            return

        self.recording = True
        self.runtime_state = "录音中"
        append_log("recording started")
        self.updateViews()

    @objc.python_method
    def stopRecording(self):
        recorder = self.audio_recorder
        self.audio_recorder = None
        if recorder is not None:
            try:
                recorder.stop()
            except Exception:
                pass
        self.recording = False

    @objc.python_method
    def stopRecognitionProcess(self):
        process = self.recognition_process
        self.recognition_process = None
        if process is None:
            return
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass
        try:
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    @objc.python_method
    def stopRecordingAndTranscribe(self):
        if not self.recording:
            return
        self.stopRecording()
        if self.transcribing:
            return
        self.transcribing = True
        self.runtime_state = "识别中"
        append_log("recording stopped; transcribing")
        self.updateViews()
        self.startStatusAnimation()
        threading.Thread(target=self.transcribeWorker, daemon=True).start()

    @objc.python_method
    def transcribeWorker(self):
        try:
            text = self.runTranscription()
        except Exception as error:
            AppHelper.callAfter(self.finishWithError, str(error))
            return
        AppHelper.callAfter(self.finishTranscription, text)

    @objc.python_method
    def runTranscription(self) -> str:
        if self.vad_bin is None:
            raise RuntimeError("找不到语音检测程序")
        if self.vad_model_path is None:
            raise RuntimeError("找不到语音检测模型")
        if self.funasr_bin is None:
            raise RuntimeError("找不到 Fun-ASR 运行程序")
        if self.funasr_encoder_path is None or self.funasr_model_path is None or self.funasr_vad_path is None:
            raise RuntimeError("找不到 Fun-ASR 模型")
        if not DEFAULT_AUDIO_FILE.exists() or DEFAULT_AUDIO_FILE.stat().st_size == 0:
            append_log("audio ignored: missing or empty recording")
            return ""
        if not wav_has_enough_signal(DEFAULT_AUDIO_FILE):
            try:
                DEFAULT_AUDIO_FILE.unlink()
            except OSError:
                pass
            return ""

        env = os.environ.copy()
        env["PATH"] = f"{RESOURCE_ROOT / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + env.get(
            "PATH", ""
        )
        speech_segment_count = self.audioSpeechSegmentCount(DEFAULT_AUDIO_FILE, env)
        if speech_segment_count == 0:
            try:
                DEFAULT_AUDIO_FILE.unlink()
            except OSError:
                pass
            return ""

        command = build_funasr_command(
            self.funasr_bin,
            self.funasr_encoder_path,
            self.funasr_model_path,
            self.funasr_vad_path,
            DEFAULT_AUDIO_FILE,
        )
        result = self.runEngineCommand(command, env)
        try:
            DEFAULT_AUDIO_FILE.unlink()
        except OSError:
            pass
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or f"本地语音引擎退出码 {result.returncode}")
        append_log(f"engine=funasr_nano_q5_k_m raw transcript length={len(result.stdout.strip())}")
        text, numeral_conversions, softened_periods = postprocess_transcript(
            result.stdout, speech_segment_count
        )
        append_log(
            "postprocess "
            f"numerals={numeral_conversions} "
            f"pause_periods={softened_periods} "
            f"vad_segments={speech_segment_count}"
        )
        return text

    @objc.python_method
    def audioSpeechSegmentCount(self, audio_path: Path, env: dict[str, str]) -> int:
        command = [
            str(self.vad_bin),
            "-f",
            str(audio_path),
            "-vm",
            str(self.vad_model_path),
            "-np",
        ]
        result = self.runEngineCommand(command, env, timeout=VAD_TIMEOUT_SECONDS)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(detail or f"语音检测程序退出码 {result.returncode}")
        combined_output = f"{result.stdout}\n{result.stderr}"
        match = re.search(r"Detected\s+(\d+)\s+speech segments?", combined_output)
        if match is None:
            raise RuntimeError("语音检测程序没有返回有效结果")
        segment_count = int(match.group(1))
        append_log(f"vad speech_segments={segment_count}")
        return segment_count

    @objc.python_method
    def runEngineCommand(
        self,
        command: list[str],
        env: dict[str, str],
        timeout: int = TRANSCRIPTION_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess[str]:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            preexec_fn=os.setsid,
        )
        self.recognition_process = process
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            self.stopRecognitionProcess()
            return subprocess.CompletedProcess(command, 124, "", "本地语音处理超时")
        finally:
            if self.recognition_process is process:
                self.recognition_process = None

    @objc.python_method
    def finishTranscription(self, text: str):
        self.transcribing = False
        self.stopStatusAnimation()
        self.last_error = ""
        if not text:
            self.runtime_state = "未检测到有效语音"
            self.updateViews()
            threading.Timer(1.2, lambda: AppHelper.callAfter(self.returnToReady)).start()
            return

        self.last_result = text
        try:
            pyperclip.copy(text)
        except Exception as error:
            self.finishWithError(f"复制失败: {error}")
            return

        if self.config["auto_paste"]:
            try:
                paste_with_quartz()
                self.runtime_state = "已自动粘贴"
            except Exception as error:
                self.last_error = ""
                self.runtime_state = "粘贴失败，已复制到剪贴板"
                append_log(f"paste failed: {error!r}")
                if accessibility_permission_state(prompt=False) != "已授权":
                    self.requestAutoPastePermission()
                self.updateViews()
                threading.Timer(1.2, lambda: AppHelper.callAfter(self.returnToReady)).start()
        else:
            self.runtime_state = "已复制到剪贴板"

        append_log(f"transcript length={len(text)}")
        self.updateViews()
        threading.Timer(1.2, lambda: AppHelper.callAfter(self.returnToReady)).start()

    @objc.python_method
    def finishWithError(self, message: str):
        self.transcribing = False
        self.recording = False
        self.stopStatusAnimation()
        self.runtime_state = "可用"
        self.set_error(message)

    @objc.python_method
    def returnToReady(self):
        if self.runtime_state in ("已自动粘贴", "已复制到剪贴板", "粘贴失败，已复制到剪贴板", "未检测到有效语音"):
            self.runtime_state = "可用"
            self.last_error = ""
            self.updateViews()

    def restartService_(self, sender):
        self.restartService()

    @objc.python_method
    def restartService(self):
        previous_config = self.config.copy()
        self.runtime_state = "正在重启服务"
        self.last_error = ""
        self.updateViews()
        self.stopService()
        self.config.update(previous_config)
        self.startService()

    def showOnboarding_(self, sender):
        if self.onboarding_window is None:
            self.buildOnboardingWindow()
        self.onboarding_window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    @objc.python_method
    def buildOnboardingWindow(self):
        style = NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 420, 274),
            style,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("首次设置")
        window.center()
        window.setDelegate_(self)
        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 274))
        window.setContentView_(content)

        self.onboarding_title = self.addLabel(content, APP_NAME, 24, 226, 220, 28, size=20, bold=True)
        self.onboarding_rows = {}
        y = 180
        for name in ("麦克风", "快捷键", "自动粘贴"):
            self.addLabel(content, name, 32, y, 100, 22, size=14, bold=True)
            value = self.addLabel(content, "", 136, y, 150, 22, size=13, secondary=True)
            self.onboarding_rows[name] = value
            y -= 38

        self.addButton(content, "打开系统设置", "openSystemSettings:", 32, 38, 120, 28)
        self.addButton(content, "重新检测", "checkRuntimeFromButton:", 166, 38, 96, 28)
        self.addButton(content, "开始使用", "finishOnboarding:", 284, 38, 104, 28)
        self.onboarding_window = window
        self.updateOnboarding()

    @objc.python_method
    def updateOnboarding(self):
        if not self.onboarding_window or not hasattr(self, "onboarding_rows"):
            return
        for name, label in self.onboarding_rows.items():
            label.setStringValue_(self.permission_states[name])

    def openSystemSettings_(self, sender):
        self.openNeededPermissionSettings(prompt_accessibility=True, force=True)

    @objc.python_method
    def openNeededPermissionSettings(self, prompt_accessibility: bool = False, force: bool = False):
        if self.permission_settings_opened and not force:
            return
        self.updatePermissionStates(prompt_accessibility=prompt_accessibility)
        target_url = None
        if self.permission_states.get("麦克风") in {"未授权", "受限制", "无法检测"}:
            target_url = MICROPHONE_SETTINGS_URL
        if target_url is None:
            return
        self.permission_settings_opened = True
        self.openSettingsURL(target_url)

    @objc.python_method
    def openSettingsURL(self, target_url: str):
        append_log(f"opening system settings: {target_url}")
        url = NSURL.URLWithString_(target_url)
        if url is None:
            url = NSURL.URLWithString_(PRIVACY_SETTINGS_URL)
        NSWorkspace.sharedWorkspace().openURL_(url)

    @objc.python_method
    def requestAutoPastePermission(self):
        if self.auto_paste_permission_prompted:
            return
        self.auto_paste_permission_prompted = True
        accessibility_permission_state(prompt=True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("需要辅助功能权限")
        alert.setInformativeText_("OpenFunASR 需要这个权限才能自动粘贴。")
        alert.addButtonWithTitle_("打开系统设置")
        alert.addButtonWithTitle_("只复制")
        result = alert.runModal()
        if result == 1000:
            self.openSettingsURL(ACCESSIBILITY_SETTINGS_URL)

    @objc.python_method
    def requestAccessibilityPermission(self):
        self.auto_paste_permission_prompted = True
        accessibility_permission_state(prompt=True)

    def checkRuntimeFromButton_(self, sender):
        self.updatePermissionStates(prompt_accessibility=True)
        if self.checkRuntime():
            self.restartService()
        if self.hasBlockingStartupIssue():
            self.openNeededPermissionSettings(prompt_accessibility=True, force=True)
        self.updateViews()

    def finishOnboarding_(self, sender):
        self.updatePermissionStates(prompt_accessibility=True)
        self.restartService()
        if self.hasBlockingStartupIssue():
            self.openNeededPermissionSettings(prompt_accessibility=True, force=True)
        self.config["onboarding_done"] = True
        self.persist_and_update()
        self.onboarding_window.orderOut_(None)

    def windowWillClose_(self, notification):
        if notification.object() is self.onboarding_window:
            self.config["onboarding_done"] = True
            self.persist_and_update()

    def showSettings_(self, sender):
        if self.settings_window is None:
            self.buildSettingsWindow()
        self.refreshSettingsControls()
        self.settings_window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    @objc.python_method
    def buildSettingsWindow(self):
        style = NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 440, 284),
            style,
            NSBackingStoreBuffered,
            False,
        )
        window.setTitle_("设置")
        window.center()
        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 284))
        window.setContentView_(content)

        self.addLabel(content, "快捷键", 28, 230, 90, 22, size=13, bold=True)
        hotkeys = NSTextField.alloc().initWithFrame_(NSMakeRect(130, 226, 190, 26))
        content.addSubview_(hotkeys)
        self.settings_controls["hotkeys"] = hotkeys

        auto_paste = NSButton.buttonWithTitle_target_action_("自动粘贴", self, "noop:")
        auto_paste.setFrame_(NSMakeRect(130, 188, 110, 26))
        auto_paste.setButtonType_(NSSwitchButton)
        content.addSubview_(auto_paste)
        self.settings_controls["auto_paste"] = auto_paste

        self.addLabel(content, "识别引擎", 28, 152, 90, 22, size=13, bold=True)
        self.addLabel(content, ENGINE_DISPLAY_NAME, 130, 152, 260, 22, size=13)

        self.addLabel(content, "日志", 28, 76, 90, 22, size=13, bold=True)
        self.addButton(content, "打开日志目录", "openLogDirectory:", 130, 72, 118, 26)

        self.addLabel(content, "首次设置", 268, 76, 70, 22, size=13, bold=True)
        self.addButton(content, "打开", "showOnboarding:", 340, 72, 50, 26)

        self.addButton(content, "保存", "saveSettings:", 250, 24, 70, 28)
        self.addButton(content, "关闭", "closeSettings:", 330, 24, 70, 28)
        self.settings_window = window

    @objc.python_method
    def refreshSettingsControls(self):
        if not self.settings_controls:
            return
        self.settings_controls["hotkeys"].setStringValue_(self.config["hotkeys"])
        self.settings_controls["auto_paste"].setState_(NSOnState if self.config["auto_paste"] else NSOffState)

    def saveSettings_(self, sender):
        old_hotkeys = self.config["hotkeys"]
        new_hotkeys = self.settings_controls["hotkeys"].stringValue().strip() or "F5, F9"
        try:
            parse_hotkey_tokens(new_hotkeys)
        except ValueError as error:
            self.set_error(str(error))
            return
        self.config["hotkeys"] = new_hotkeys
        self.config["auto_paste"] = self.settings_controls["auto_paste"].state() == NSOnState
        self.persist_and_update()
        if self.config["hotkeys"] != old_hotkeys:
            self.restartService()

    def closeSettings_(self, sender):
        self.settings_window.orderOut_(None)

    def openLogDirectory_(self, sender):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(str(CONFIG_DIR)))

    def noop_(self, sender):
        return

    @objc.python_method
    def addLabel(self, parent, text, x, y, width, height, size=13, secondary=False, bold=False):
        label = NSTextField.labelWithString_(text)
        label.setFrame_(NSMakeRect(x, y, width, height))
        label.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
        if secondary:
            label.setTextColor_(NSColor.secondaryLabelColor())
        parent.addSubview_(label)
        return label

    @objc.python_method
    def addButton(self, parent, title, action, x, y, width, height):
        button = NSButton.buttonWithTitle_target_action_(title, self, action)
        button.setFrame_(NSMakeRect(x, y, width, height))
        button.setBezelStyle_(NSRoundedBezelStyle)
        parent.addSubview_(button)
        return button


def main():
    paste_test_arguments = [
        argument for argument in sys.argv if argument.startswith(PASTE_SELF_TEST_PREFIX)
    ]
    if paste_test_arguments:
        marker = paste_test_arguments[-1].split("=", 1)[1] or "OPENFUNASR_PASTE_TEST"
        permission = accessibility_permission_state(prompt=False)
        append_log(f"paste self-test started accessibility={permission} marker={marker}")
        if permission != "已授权":
            append_log("paste self-test failed: accessibility denied")
            raise SystemExit(2)
        if pyperclip is None:
            append_log(f"paste self-test failed: clipboard unavailable {PYPERCLIP_IMPORT_ERROR}")
            raise SystemExit(3)
        pyperclip.copy(marker)
        time.sleep(1.0)
        try:
            paste_with_quartz()
        except Exception as error:
            append_log(f"paste self-test failed: {error!r}")
            raise SystemExit(4)
        append_log("paste self-test event posted")
        time.sleep(0.5)
        return
    if "--self-check" in sys.argv:
        print(f"resource_root={RESOURCE_ROOT}")
        print(f"local_runtime_root={LOCAL_RUNTIME_ROOT}")
        print("engine=Fun-ASR Nano Q5_K_M")
        print(f"vad_binary={resolve_vad_binary()}")
        print(f"vad_model={resolve_vad_model()}")
        print(f"funasr_cli={resolve_funasr_binary()}")
        print(f"funasr_encoder={resolve_funasr_model(FUNASR_ENCODER_MODEL_NAME)}")
        print(f"funasr_model={resolve_funasr_model(FUNASR_DECODER_MODEL_NAME)}")
        print(f"funasr_vad={resolve_funasr_model(FUNASR_VAD_MODEL_NAME)}")
        print(f"microphone={microphone_permission_state()}")
        print("hotkeys=Carbon RegisterEventHotKey")
        print(f"auto_paste_accessibility={accessibility_permission_state(False)}")
        print("note=command-line permission attribution is not an end-to-end app test")
        return
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.installMachInterrupt()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
