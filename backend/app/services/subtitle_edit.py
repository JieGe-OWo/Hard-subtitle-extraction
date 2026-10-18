"""字幕文件读取/改写（供「边播放边校对」功能使用）。

SRT 解析用 pysrt（兼容各种现存格式），保存时输出标准 SRT（LF、逗号毫秒）。
"""
import os
import re

import pysrt

TIME_RE = re.compile(r'^\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}$')


def _norm_time(t: str) -> str:
    """统一成 HH:MM:SS,mmm"""
    t = t.strip()
    if not TIME_RE.match(t):
        raise ValueError(f'时间格式不正确：{t}')
    return t.replace('.', ',', 1)


def load_srt(path: str):
    """读取 SRT 文件，返回 [{'index': 1, 'start': 'HH:MM:SS,mmm', 'end': ..., 'text': ...}]"""
    if not path or not os.path.isfile(path):
        return []
    subs = pysrt.open(path, encoding='utf-8')
    items = []
    for i, sub in enumerate(subs, 1):
        items.append({
            'index': i,
            'start': _norm_time(str(sub.start)),
            'end': _norm_time(str(sub.end)),
            'text': sub.text,
        })
    return items


def save_srt(path: str, items) -> str:
    """把编辑后的条目写回 SRT（校验时间格式），返回文件路径"""
    lines = []
    for i, it in enumerate(items, 1):
        start = _norm_time(it['start'])
        end = _norm_time(it['end'])
        text = str(it.get('text') or '')
        lines.append(f'{i}\n{start} --> {end}\n{text}\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path


def save_txt(path: str, items) -> str:
    """按 srt2txt 的约定重写 TXT（每行一条字幕文本）"""
    with open(path, 'w', encoding='utf-8') as f:
        for it in items:
            f.write(f"{it.get('text') or ''}\n")
    return path
