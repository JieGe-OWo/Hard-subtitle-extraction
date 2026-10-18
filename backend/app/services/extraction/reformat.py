# -*- coding: UTF-8 -*-
"""英文连写分词与文本整理"""
import json
import os
import re
import sys
import traceback

import pysrt
import wordsegment as ws

from app.config import BASE_DIR


def execute(path, lang='en'):
    try:
        print(f'Starting to process subtitle file: {path}, language: {lang}')
        if sys.getrecursionlimit() < 100000:
            sys.setrecursionlimit(100000)

        if not os.path.exists(path):
            print(f'Error: Subtitle file does not exist: {path}')
            return False

        wordsegment = ws.Segmenter()
        wordsegment.load()

        try:
            subs = pysrt.open(path)
        except Exception as e:
            print(f'Error: Failed to open subtitle file: {str(e)}')
            return False

        verb_forms = ["I'm", "you're", "he's", "she's", "we're", "it's", "isn't", "aren't", "they're", "there's", "wasn't",
                      "weren't", "I've", "you've", "we've", "they've", "hasn't", "haven't", "I'd", "you'd", "he'd", "she'd",
                      "it'd", "we'd", "they'd", "doesn't", "don't", "didn't", "I'll", "you'll", "he'll", "she'll", "we'll",
                      "they'll", "there'll", "there'd", "can't", "couldn't", "daren't", "hadn't", "mightn't", "mustn't",
                      "needn't", "oughtn't", "shan't", "shouldn't", "usedn't", "won't", "wouldn't", "that's", "what's", "it'll"]
        verb_form_map = {}

        typo_map_path = os.path.join(str(BASE_DIR), 'configs', 'typoMap.json')
        try:
            with open(typo_map_path, 'r', encoding='utf-8') as load_f:
                typo_map = json.load(load_f)
        except Exception:
            typo_map = {}

        for verb in verb_forms:
            verb_form_map[verb.replace("'", "").lower()] = verb

        def format_seg_list(seg_list):
            new_seg = []
            for seg in seg_list:
                if seg in verb_form_map:
                    new_seg.append([seg, verb_form_map[seg]])
                else:
                    new_seg.append([seg])
            return new_seg

        def typo_fix(text):
            for k, v in typo_map.items():
                try:
                    text = re.sub(re.compile(k, re.I), v, text)
                except Exception:
                    pass
            return text

        def remove_invalid_segment(seg, text):
            try:
                seg_len = len(seg)
                span = None
                new_seg = []
                for i in range(seg_len - 1, -1, -1):
                    s = seg[i]
                    if len(s) > 1:
                        regex = re.compile(f"({s[0]}|{s[1]})", re.I)
                    else:
                        regex = re.compile(f"({s[0]})", re.I)
                    try:
                        ss = [(i) for i in re.finditer(regex, text)][-1]
                    except IndexError:
                        ss = None
                    if ss is None:
                        continue
                    text = text[:ss.span()[0]]
                    if span is None:
                        span = ss.span()
                        new_seg.append(s)
                        continue
                    if span > ss.span():
                        new_seg.append(s)
                        span = ss.span()
                return list(reversed(new_seg))
            except Exception:
                traceback.print_exc()
                return []

        modified_count = 0
        for index, sub in enumerate(subs):
            try:
                if not hasattr(sub, 'text') or not sub.text:
                    continue
                original_text = sub.text
                sub.text = typo_fix(sub.text)
                if len(sub.text) > 1000:
                    print(f'Warning: Subtitle text too long, skipping word segmentation: {len(sub.text)} characters')
                    continue
                try:
                    seg = wordsegment.segment(sub.text)
                    if len(seg) == 1:
                        seg = wordsegment.segment(re.sub(re.compile(f"(\ni)([^\\s])", re.I), "\\1 \\2", sub.text))
                except Exception:
                    traceback.print_exc()
                    continue
                seg = format_seg_list(seg)
                sub.text = re.sub(' +([\\u4e00-\\u9fa5])', ' \\1', sub.text)
                if lang in ['ch', 'ch_tra']:
                    sub.text = sub.text.replace('  ', '\n')
                lines = []
                remain = sub.text
                seg = remove_invalid_segment(seg, sub.text)
                seg_len = len(seg)
                for i in range(0, seg_len):
                    s = seg[i]
                    if len(s) > 1:
                        regex = re.compile(f"(.*?)({s[0]}|{s[1]})", re.I)
                    else:
                        regex = re.compile(f"(.*?)({s[0]})", re.I)
                    ss = re.search(regex, remain)
                    if ss is None:
                        if i == seg_len - 1:
                            lines.append(remain.strip())
                        continue
                    lines.append(remain[:ss.span()[1]].strip())
                    remain = remain[ss.span()[1]:].strip()
                    if i == seg_len - 1:
                        lines.append(remain)
                if seg_len > 0:
                    ss = ' '.join(lines)
                else:
                    ss = remain
                ss = typo_fix(ss)
                ss = re.sub("([^\\sA-Z\\-])([A-Z])", "\\1 \\2", ss)
                ss = ss.replace('  ', ' ')
                ss = ss.replace('。', '.')
                ss = re.sub(" *([\\.\\?\\!\\,])", "\\1", ss)
                ss = re.sub(" *([\\']) *", "\\1", ss)
                ss = re.sub('\n\\s*', '\n', ss)
                ss = re.sub('^\\s*', '', ss)
                ss = re.sub("([A-Za-z0-9]) (\\-[A-Za-z0-9])", '\\1\\2', ss)
                ss = re.sub("([A-Za-z0-9]) %", '\\1%', ss)
                ss = re.sub('·$', '.', ss)
                ss = re.sub(r'\bDr\. *\b', 'Dr.', ss)
                ss = re.sub(r'["“”]', '"', ss)
                ss = re.sub(r'，', ',', ss)
                ss = re.sub('([\\.,\\!\\?])([A-Za-z0-9\\u4e00-\\u9fa5])', '\\1 \\2', ss)
                ss = ss.replace('\n\n', '\n')
                sub.text = ss.strip()
                if original_text != sub.text:
                    modified_count += 1
            except Exception:
                print(f'Error: Failed to process subtitle line {index + 1}')
                traceback.print_exc()
                continue

        try:
            subs.save(path, encoding='utf-8')
            print(f'Successfully processed subtitle file: {path}, modified {modified_count} lines')
            return True
        except Exception:
            traceback.print_exc()
            return False
    except Exception:
        traceback.print_exc()
        return False
