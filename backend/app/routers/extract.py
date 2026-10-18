import os
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app import models
from app.config import MAX_UPLOAD_SIZE, UPLOAD_DIR
from app.deps import get_active_user
from app.services.extraction.settings import ExtractionConfig
from app.services.preview import VideoPreview
from app.services.subtitle_edit import load_srt, save_srt, save_txt
from app.services.task_manager import task_manager

router = APIRouter(prefix='/api/extract', tags=['extract'], dependencies=[Depends(get_active_user)])

ALLOWED_EXT = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts', '.mpeg', '.mpg', '.wmv', '.webm', '.rmvb', '.rm', '.3gp', '.f4v'}

# 预览图放在输出目录的子目录里，避免被 /files 当成字幕结果列出来
PREVIEW_SUBDIR = 'preview'
PREVIEW_FILENAME = 'frame.jpg'

# 支持的字幕语言（与 PaddleModelConfig 中的语言代码对应）
LANGUAGES = [
    {'code': 'ch', 'label': '简体中文（含中英双语）'},
    {'code': 'chinese_cht', 'label': '繁體中文'},
    {'code': 'en', 'label': 'English'},
    {'code': 'japan', 'label': '日本語'},
    {'code': 'korean', 'label': '한국어'},
    {'code': 'ru', 'label': 'Русский'},
    {'code': 'german', 'label': 'Deutsch'},
    {'code': 'french', 'label': 'Français'},
    {'code': 'es', 'label': 'Español'},
    {'code': 'pt', 'label': 'Português'},
    {'code': 'it', 'label': 'Italiano'},
    {'code': 'vi', 'label': 'Tiếng Việt'},
    {'code': 'ar', 'label': 'العربية'},
    {'code': 'th', 'label': 'ไทย'},
    {'code': 'tamil', 'label': 'தமிழ்'},
]


@router.get('/meta')
def meta():
    return {
        'languages': LANGUAGES,
        'modes': [
            {'code': 'fast', 'label': '快速（推荐）', 'desc': '轻量模型，快速提取，可能丢少量字幕'},
            {'code': 'auto', 'label': '自动（推荐）', 'desc': 'CPU 下等价于快速模式'},
            {'code': 'accurate', 'label': '精准（慢）', 'desc': '精准检测，逐帧判断，速度很慢'},
        ],
        'subtitle_areas': [
            {'code': 2, 'label': '未知（全屏）'},
            {'code': 1, 'label': '上半部分'},
            {'code': 0, 'label': '下半部分'},
        ],
    }


def _probe_video(video_path: str):
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail='无法打开视频，请检查文件格式是否受支持')
    info = {
        'frame_count': cap.get(cv2.CAP_PROP_FRAME_COUNT),
        'fps': cap.get(cv2.CAP_PROP_FPS) or 25,
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return info


@router.post('/upload')
def upload_video(file: UploadFile = File(...), user=Depends(get_active_user)):
    """上传视频。

    刻意写成同步 def：Starlette 会把同步端点丢进线程池执行，
    而 async def 里的同步磁盘写入和 OpenCV 打开视频会阻塞事件循环，
    导致上传期间 /status 等请求全部卡住（表现为「上传后不能及时响应」）。
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail='未选择文件')
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f'不支持的视频格式：{ext}')
    task_id = uuid.uuid4().hex
    user_dir = os.path.join(str(UPLOAD_DIR), str(user['id']))
    os.makedirs(user_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename)
    dest = os.path.join(user_dir, f'{task_id}_{safe_name}')
    size = 0
    try:
        with open(dest, 'wb') as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail='视频文件过大')
                f.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=500, detail='视频保存失败')
    finally:
        file.file.close()

    try:
        info = _probe_video(dest)
    except HTTPException:
        os.remove(dest)
        raise

    stem = os.path.splitext(safe_name)[0]
    # 必须把 task_id 交给 task_manager，否则任务表里的 id 与这里返回的不是同一个
    task_id = task_manager.create(user['id'], dest, stem, task_id=task_id)
    out_dir = task_manager.task_output_dir(user['id'], task_id)
    preview_path = os.path.join(out_dir, PREVIEW_SUBDIR, PREVIEW_FILENAME)
    # 预览对象只用 OpenCV，不加载提取引擎；真正的抓帧推迟到 /preview 按需执行
    task_manager.attach(task_id, preview_path=preview_path,
                        preview=VideoPreview(dest), ext=ext)

    return {
        'task_id': task_id,
        'video_name': stem,
        'video_info': info,
        'duration_ms': (info['frame_count'] / info['fps']) * 1000 if info['fps'] else 0,
        'preview_url': f'/api/extract/{task_id}/preview?t=0',
    }


@router.get('/{task_id}/preview')
def get_preview(task_id: str, t: int = 0, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    preview = task.get('preview')
    path = task.get('preview_path')
    if preview is None or not path:
        # 服务重启后内存里的预览对象会丢，这里按约定重新找视频并重建
        video = task_manager.find_video(task_id, task)
        if not video:
            raise HTTPException(status_code=404, detail='视频文件不存在，无法生成预览帧')
        out_dir = task_manager.task_output_dir(user['id'], task_id)
        path = os.path.join(out_dir, PREVIEW_SUBDIR, PREVIEW_FILENAME)
        preview = VideoPreview(video)
        task_manager.attach(task_id, preview_path=path, preview=preview)
    try:
        preview.grab(t, path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'读取视频帧失败：{e}')
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail='预览图生成失败')
    return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


# ---------------- 视频流（供「边播放边校对」使用，支持 HTTP Range） ----------------

_RANGE_RE = re.compile(r'bytes=(\d*)-(\d*)$')


@router.get('/{task_id}/video')
def get_video(task_id: str, request: Request, user=Depends(get_active_user)):
    """按 Range 输出上传的原视频，供前端 <video> 拖动播放。
    鉴权：<video> 直链带不了请求头，请在 URL 上带 ?token=xxx。"""
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    path = task_manager.find_video(task_id, task)
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail='视频文件不存在（可能已被清理，请重新上传提取）')
    size = os.path.getsize(path)
    content_type = 'video/mp4'

    range_header = request.headers.get('range', '').strip()
    m = _RANGE_RE.match(range_header)
    if m and (m.group(1) or m.group(2)):
        start = int(m.group(1)) if m.group(1) else None
        end = int(m.group(2)) if m.group(2) else None
        if start is None:
            # 后缀范围 bytes=-N：取最后 N 字节
            start = max(size - end, 0)
            end = size - 1
        else:
            end = min(end, size - 1) if end is not None else size - 1
        if start >= size or start > end:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        length = end - start + 1
        with open(path, 'rb') as f:
            f.seek(start)
            data = f.read(length)
        return Response(
            content=data, status_code=206, media_type=content_type,
            headers={
                'Content-Range': f'bytes {start}-{end}/{size}',
                'Accept-Ranges': 'bytes',
                'Content-Length': str(length),
            })
    return FileResponse(path, media_type=content_type, headers={'Accept-Ranges': 'bytes'})


# ---------------- 字幕校对（读取 / 保存编辑后的字幕） ----------------

class SubtitleEntry(BaseModel):
    index: int
    start: str
    end: str
    text: str


class SubtitleSaveRequest(BaseModel):
    subtitles: List[SubtitleEntry]


@router.get('/{task_id}/subtitles')
def get_subtitles(task_id: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    srt_path = task_manager.find_output(task_id, '.srt')
    return {
        'task_id': task_id,
        'video_name': task.get('video_name', ''),
        'status': task.get('status'),
        'subtitles': load_srt(srt_path) if srt_path else [],
        'video_url': f'/api/extract/{task_id}/video',
    }


@router.post('/{task_id}/subtitles')
def save_subtitles(task_id: str, body: SubtitleSaveRequest, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    items = [{'index': s.index, 'start': s.start, 'end': s.end, 'text': s.text}
             for s in body.subtitles]
    if len(items) > 50000:
        raise HTTPException(status_code=400, detail='字幕条目过多')

    srt_path = task_manager.find_output(task_id, '.srt')
    if not srt_path:
        raise HTTPException(status_code=400, detail='未找到 SRT 文件')
    try:
        save_srt(srt_path, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f'保存失败：{e}')

    # TXT 同步更新：有就重写，没有就按原名新建
    txt_path = task_manager.find_output(task_id, '.txt')
    if not txt_path:
        video_path = task_manager.find_video(task_id, task)
        stem = os.path.splitext(os.path.basename(video_path))[0] or task.get('video_name', 'subtitle')
        txt_path = os.path.join(task['output_dir'], f'{stem}.txt')
    save_txt(txt_path, items)

    files = task_manager.refresh_files(task_id)
    return {'message': '字幕已保存', 'files': files}



class StartRequest(BaseModel):
    # 前端「不框选区域」时会显式传 null，必须允许 None，
    # 否则全屏检测会被 422 校验挡掉（点击提取直接失败）。
    sub_area: Optional[dict] = None
    options: Optional[dict] = None


@router.post('/{task_id}/start')
def start_task(task_id: str, body: StartRequest, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    if task['status'] == 'running':
        raise HTTPException(status_code=400, detail='任务正在进行中')
    if task['status'] == 'completed':
        raise HTTPException(status_code=400, detail='任务已完成，请下载结果')

    sub_area_dict = body.sub_area
    if sub_area_dict:
        from app.services.extraction.area import SubtitleArea
        missing = [k for k in ('ymin', 'ymax', 'xmin', 'xmax') if k not in sub_area_dict]
        if missing:
            raise HTTPException(status_code=400, detail=f'字幕区域缺少参数：{missing}')
        area = SubtitleArea(sub_area_dict['ymin'], sub_area_dict['ymax'],
                            sub_area_dict['xmin'], sub_area_dict['xmax'])
        area.normalized()
        if area.width < 10 or area.height < 10:
            raise HTTPException(status_code=400, detail='字幕区域太小，请重新框选')
        sub_area_dict = area.to_dict()

    allowed = set(ExtractionConfig().as_dict().keys())
    options = {k: v for k, v in (body.options or {}).items() if k in allowed}
    if 'subtitleArea' not in options:
        options['subtitleArea'] = 2
    options.setdefault('language', 'ch')
    options.setdefault('mode', 'fast')

    task_manager.set_options(task_id, sub_area_dict, options)
    task['progress'] = {'frame_extract': 0, 'ocr': 0, 'post': 0, 'overall': 0}
    task['logs'] = []
    task['error'] = None
    task['files'] = []
    task['status'] = 'pending'
    task_manager.start(task_id)
    return {'message': '任务已开始', 'task_id': task_id}


@router.get('/{task_id}/status')
def task_status(task_id: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    return {
        'task_id': task['id'],
        'video_name': task['video_name'],
        'status': task['status'],
        'progress': task['progress'],
        'video_info': task.get('video_info'),
        'files': task.get('files', []),
        'error': task['error'],
        'logs': task['logs'][-200:],
        'created_at': task['created_at'],
        'finished_at': task['finished_at'],
    }


@router.get('/{task_id}/files')
def list_files(task_id: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    files = []
    out_dir = task['output_dir']
    if os.path.isdir(out_dir):
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if os.path.isfile(path):
                files.append({
                    'name': name,
                    'size': os.path.getsize(path),
                    'url': f'/api/extract/{task_id}/download/{name}',
                })
    task['files'] = files
    return {'files': files}


@router.get('/{task_id}/download/{filename}')
def download_file(task_id: str, filename: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    path = task_manager.file_path(task_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail='文件不存在')
    return FileResponse(path, filename=os.path.basename(path))


@router.get('/{task_id}/content/{filename}')
def get_content(task_id: str, filename: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    path = task_manager.file_path(task_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail='文件不存在')
    if not filename.lower().endswith(('.srt', '.txt', '.md')):
        raise HTTPException(status_code=400, detail='仅支持预览 srt/txt 文件')
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return {'name': filename, 'content': content[:200000]}


@router.post('/{task_id}/cancel')
def cancel_task(task_id: str, user=Depends(get_active_user)):
    task = task_manager.get(task_id, user['id'])
    if not task:
        raise HTTPException(status_code=404, detail='任务不存在')
    task_manager.cancel(task_id)
    models.update_task_record(task_id, status='cancelled')
    return {'message': '已取消'}


@router.get('/history')
def history(page: int = 1, page_size: int = 20, user=Depends(get_active_user)):
    rows = models.list_task_records(user['id'], limit=page_size)
    return {'items': [dict(r) for r in rows]}
