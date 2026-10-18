import glob
import json
import os
import threading
import time
import uuid

from app import models
from app.services.extraction.settings import ExtractionConfig
from app.services.extraction.area import SubtitleArea


class TaskManager:
    """字幕提取任务管理（内存态任务 + 数据库记录）"""

    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()
        self._extractors = {}

    def create(self, user_id: int, video_path: str, video_name: str, task_id: str = None) -> str:
        # 允许调用方指定 task_id：上传时文件名与输出目录都基于同一个 id，
        # 由这里另生成一个会让路由返回的 id 在任务表里查不到（「任务不存在」）。
        task_id = task_id or uuid.uuid4().hex
        out_dir = self.task_output_dir(user_id, task_id)
        os.makedirs(out_dir, exist_ok=True)
        models.create_task_record(task_id, user_id, video_name, '{}')
        with self._lock:
            self._tasks[task_id] = {
                'id': task_id,
                'user_id': user_id,
                'status': 'pending',
                'video_name': video_name,
                'video_path': video_path,
                'output_dir': out_dir,
                'progress': {'frame_extract': 0, 'ocr': 0, 'post': 0, 'overall': 0},
                'logs': [],
                'error': None,
                'files': [],
                'created_at': time.time(),
                'finished_at': None,
                'cancel_event': threading.Event(),
            }
        return task_id

    def task_output_dir(self, user_id: int, task_id: str) -> str:
        from app.config import OUTPUT_DIR
        path = os.path.join(str(OUTPUT_DIR), str(user_id), task_id)
        os.makedirs(path, exist_ok=True)
        return path

    def find_video(self, task_id: str, task: dict = None) -> str:
        """找出任务对应的原始视频文件。

        上传时的命名约定是 <上传目录>/<用户id>/<任务id>_<原文件名>，
        但 video_path 只存在内存里（数据库没有这个字段），
        所以服务一重启、任务从数据库重建后就取不到路径——校对页视频会 404。
        这里按约定反查，内存里有就直接用。
        """
        task = task or {}
        stored = task.get('video_path') or ''
        if stored and os.path.isfile(stored):
            return stored

        from app.config import UPLOAD_DIR
        base = str(UPLOAD_DIR)
        user_id = task.get('user_id')
        patterns = []
        if user_id is not None:
            patterns.append(os.path.join(base, str(user_id), f'{task_id}_*'))
        patterns.append(os.path.join(base, '*', f'{task_id}_*'))
        patterns.append(os.path.join(base, '**', f'{task_id}_*'))
        for pattern in patterns:
            try:
                hits = sorted(glob.glob(pattern, recursive=True))
            except Exception:
                continue
            for hit in hits:
                if os.path.isfile(hit):
                    return hit
        return ''

    def get(self, task_id: str, user_id: int = None):
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None:
            # 服务重启后内存里的任务会丢，这里从数据库重建，
            # 否则历史任务的「查看/下载/校对/视频播放」全部会 404（任务不存在）
            task = self._restore_from_db(task_id)
        if task is None:
            return None
        if user_id is not None and task['user_id'] != user_id and not self._is_admin(user_id):
            return None
        return task

    def _restore_from_db(self, task_id: str):
        try:
            row = models.get_task_record(task_id)
        except Exception:
            return None
        if not row:
            return None
        from app.config import OUTPUT_DIR
        out_dir = os.path.join(str(OUTPUT_DIR), str(row['user_id']), task_id)
        options = {}
        try:
            options = json.loads(row['options'] or '{}')
        except Exception:
            options = {}
        task = {
            'id': task_id,
            'user_id': row['user_id'],
            'status': row['status'],
            'video_name': row['video_name'],
            'video_path': self.find_video(task_id, {'user_id': row['user_id']}),
            'output_dir': out_dir,
            'options': options,
            'progress': {
                'frame_extract': row['progress_frame'] or 0,
                'ocr': row['progress_ocr'] or 0,
                'post': row['progress_post'] or 0,
                'overall': round(((row['progress_frame'] or 0) + (row['progress_ocr'] or 0)
                                  + (row['progress_post'] or 0)) / 3, 1),
            },
            'logs': [],
            'error': row['error'],
            'files': self._collect_files(out_dir) if os.path.isdir(out_dir) else [],
            'created_at': row['created_at'],
            'finished_at': row['finished_at'],
            'cancel_event': threading.Event(),
            'restored': True,
        }
        with self._lock:
            self._tasks[task_id] = task
        return task

    def attach(self, task_id: str, **kwargs):
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.update(kwargs)
        return task

    def set_options(self, task_id: str, sub_area_dict: dict, options: dict):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task['sub_area'] = sub_area_dict
            task['options'] = options
            return task

    def start(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
        if not task or task['status'] == 'running':
            return
        # 任务可能是服务重启后从数据库重建的，内存里没有 video_path，先按约定找回
        if not task.get('video_path'):
            found = self.find_video(task_id, task)
            if not found:
                raise RuntimeError('找不到原始视频文件，请重新上传后再提取')
            task['video_path'] = found
        options = task.get('options') or {}
        sub_area_dict = task.get('sub_area')
        sub_area = None
        if sub_area_dict:
            sub_area = SubtitleArea(sub_area_dict['ymin'], sub_area_dict['ymax'],
                                     sub_area_dict['xmin'], sub_area_dict['xmax'])
        # 注意：as_dict() 返回 dict，hasattr(dict, 'language') 恒为 False，
        # 会把用户选的参数全部丢掉，这里必须判断 key 是否在 dict 里。
        allowed = ExtractionConfig().as_dict().keys()
        cfg = ExtractionConfig(**{k: v for k, v in options.items() if k in allowed})

        cancel_event = task['cancel_event']
        task['status'] = 'running'
        task['started_at'] = __import__('time').time()
        models.update_task_record(task_id, status='running', options=str(options))

        def on_progress(ocr, frame_extract, post, finished):
            task['progress'] = {
                'frame_extract': round(frame_extract, 1),
                'ocr': round(ocr, 1),
                'post': round(post, 1),
                'overall': round((frame_extract + ocr + post) / 3, 1),
            }
            models.update_task_record(task_id, progress_frame=frame_extract, progress_ocr=ocr, progress_post=post)

        def on_log(msg):
            task['logs'].append(msg)
            if len(task['logs']) > 500:
                del task['logs'][:100]

        def runner():
            try:
                from app.services.extraction.extractor import VideoSubtitleExtractor
                extractor = VideoSubtitleExtractor(
                    video_path=task['video_path'],
                    output_dir=task['output_dir'],
                    sub_area=sub_area,
                    config=cfg,
                    cancel_event=cancel_event,
                    on_progress=on_progress,
                    on_log=on_log,
                )
                self._extractors[task_id] = extractor
                task['video_info'] = {
                    'width': extractor.frame_width,
                    'height': extractor.frame_height,
                    'fps': extractor.fps,
                    'frame_count': extractor.frame_count,
                }
                extractor.run()
                if cancel_event.is_set():
                    raise RuntimeError('任务已取消')
                task['status'] = 'completed'
                task['finished_at'] = __import__('time').time()
                task['files'] = self._collect_files(task['output_dir'])
                models.update_task_record(task_id, status='completed', finished_at=task['finished_at'],
                                           output_srt='.'.join([task['video_name'], 'srt']))
            except Exception as e:
                import traceback
                traceback.print_exc()
                task['status'] = 'cancelled' if cancel_event.is_set() else 'failed'
                task['error'] = str(e)
                task['finished_at'] = __import__('time').time()
                models.update_task_record(task_id, status=task['status'], error=str(e),
                                          finished_at=task['finished_at'])
            finally:
                self._extractors.pop(task_id, None)
                preview = task.get('preview')
                if preview is not None:
                    try:
                        preview.close()
                    except Exception:
                        pass

        threading.Thread(target=runner, daemon=True).start()

    def cancel(self, task_id: str):
        task = self.get(task_id)
        if not task:
            return False
        task['cancel_event'].set()
        task['status'] = 'cancelled'
        preview = task.get('preview')
        if preview is not None:
            try:
                preview.close()
            except Exception:
                pass
        extractor = self._extractors.get(task_id)
        if extractor:
            try:
                if extractor.vsf_runner:
                    extractor.vsf_runner.kill()
            except Exception:
                pass
        return True

    def _collect_files(self, out_dir: str):
        files = []
        if not os.path.isdir(out_dir):
            return files
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if os.path.isfile(path):
                files.append({
                    'name': name,
                    'size': os.path.getsize(path),
                    'url': f'',  # 由路由拼接
                })
        return files

    def find_output(self, task_id: str, suffix: str):
        """在任务输出目录里按后缀找结果文件（如 '.srt' / '.txt'），返回绝对路径或 None"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        out_dir = task['output_dir']
        if not os.path.isdir(out_dir):
            return None
        suffix = suffix.lower()
        for name in sorted(os.listdir(out_dir)):
            if name.lower().endswith(suffix) and os.path.isfile(os.path.join(out_dir, name)):
                return os.path.join(out_dir, name)
        return None

    def refresh_files(self, task_id: str):
        """重新扫描输出目录并更新内存中的 files 列表"""
        task = self._tasks.get(task_id)
        if not task:
            return []
        task['files'] = self._collect_files(task['output_dir'])
        return task['files']

    def file_path(self, task_id: str, filename: str):
        task = self._tasks.get(task_id)
        if not task:
            return None
        safe_name = os.path.basename(filename)
        path = os.path.join(task['output_dir'], safe_name)
        if os.path.isfile(path):
            return path
        return None

    def preview_path(self, task_id: str):
        task = self._tasks.get(task_id)
        if not task:
            return None
        path = task.get('preview_path')
        return path if path and os.path.isfile(path) else None

    @staticmethod
    def _is_admin(user_id: int):
        user = models.get_user_by_id(user_id)
        return user is not None and user['role'] == 'admin'


task_manager = TaskManager()
