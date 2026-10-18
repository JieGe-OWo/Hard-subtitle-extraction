# 杰哥硬字幕提取

**视频硬字幕提取**工具（CPU 部署）。两种用法：

- **桌面版（推荐给普通用户）**：打包成免安装的便携软件，解压双击即用、**无需账号**、内置数据库，不需要装 Python/MySQL。
- **网页版（服务器部署）**：Vue3 + FastAPI 前后端分离，带账号体系（邮箱注册 + 激活码）与管理员后台。

界面为淡黄简约风格。功能照搬 [video-subtitle-extractor](https://github.com/YaoFANGUK/video-subtitle-extractor)：本地 OCR 提取视频硬字幕，生成 SRT/TXT 字幕文件，并可边播放边校对改错字。

## 桌面版（便携软件）

### 给使用者

1. 解压压缩包到任意目录（路径含中文也可以）
2. 双击 **「启动 杰哥硬字幕提取.bat」**，稍等几秒弹出软件窗口
3. 上传视频 → 在预览图上框选字幕区域 → 点「开始提取」→ 完成后下载 SRT 或进「校对」改错字

所有数据都在软件目录内的 `backend\data\`，整个文件夹拷走即可迁移；删掉该目录即恢复出厂状态。详细说明见包内 `使用说明.txt`。

- 无需注册、无需登录、免费使用
- 系统要求：Windows 10/11 64 位，建议 4 核 CPU / 8GB 内存
- 窗口用 WebView2（Win10/11 自带）；启动异常时双击「调试启动.bat」看报错

### 给开发者（自己打包）

```bash
cd frontend && npm run build          # 先构建前端
python build_portable.py              # 在项目根目录执行，产出 dist_portable/杰哥硬字幕提取/
```

打包脚本会复制一份 Python 3.12 运行时 + 全部依赖 + OCR 模型 + VideoSubFinder，产出约 **1.5GB** 的免安装目录；压缩成 zip 发给别人即可。

> 📦 **模型怎么下载和配置**：仓库不含 OCR 模型（约 253 MB）和 VideoSubFinder（182 MB），详细步骤见 [模型配置说明.md](模型配置说明.md)。

> **中文路径兼容**：Paddle Inference、VideoSubFinder 这类 C++ 组件在 Windows 下用 ANSI 文件接口，
> 软件一旦装在含中文的路径下（如 `D:\软件\杰哥硬字幕提取`）就会读不到模型。项目在
> [`backend/app/runtime_paths.py`](backend/app/runtime_paths.py) 里做了自动处理：检测到非 ASCII 路径时，
> 在纯英文目录（如 `G:\JiegeZiMuRuntime\<指纹>`）为 `models` / `subfinder` / `data` 建立**目录联接**，
> 文件仍实际存放在软件目录内，但交给 C++ 组件的路径是纯英文。不支持联接的文件系统（exFAT U 盘）会自动退化为复制。

压缩后实测 **665MB**（原目录 1495MB），用 Windows 自带 `tar` 即可：

```bash
tar -a -c -f "杰哥硬字幕提取-Windows便携版.zip" -C dist_portable "杰哥硬字幕提取"
```

## 功能特性

- **字幕提取**：关键帧提取 → 字幕区域检测 → OCR 识别 → 水印/场景文本过滤 → 去重生成 SRT（可选 TXT）
- **字幕校对**：进入 `/review/{taskId}`，左边播视频右边同步高亮字幕，**双击任意一行直接改错字**，改完保存并导出修正后的 SRT/TXT
- **免账号桌面模式**：`DESKTOP_MODE=1` 时去掉登录/注册/激活，自动以本地用户进入，前端隐藏账号相关入口
- **CPU 部署**：纯 CPU 运行，不依赖 GPU / CUDA
- **邮箱注册 / 激活码激活**（网页版）：注册需邮箱验证码，账号需激活码才能使用提取功能，一个激活码只能激活一个账号
- **管理员后台**（网页版）：固定管理员账号，可生成/添加/停用/删除激活码，管理用户
- **数据库**：默认 MySQL（也兼容 SQLite），并预留支付订单表，后续可扩展「充值一个月使用权限」
- **淡黄简约主题**：全局主题变量在 [`frontend/src/styles/theme.css`](frontend/src/styles/theme.css)，改一处即可换肤

## 默认账号

首次启动后端时会按环境变量自动创建**管理员账号**；**测试账号**是本地数据库里已存在的普通用户，用于验证登录与提取流程，代码不会自动创建。

> ⚠️ 正式上线前请立即修改下面的密码，并删除两个测试账号。

### 管理员

| 项目  | 值                                       |
| --- | --------------------------------------- |
| 邮箱  | `zimuadminj8wfe@gmail.com`              |
| 密码  | `Admin@123456`                          |
| 权限  | 管理激活码与用户，登录后进入 `/admin/dashboard`，无需激活码 |

### 测试账号

| 邮箱                    | 密码            | 状态  | 说明             |
| --------------------- | ------------- | --- | -------------- |
| `tester1@example.com` | `Test@123456` | 已激活 | 可直接登录，用于验证提取流程 |
| `tester2@example.com` | `Test@123456` | 已激活 | 可直接登录，用于验证提取流程 |

说明：

- 管理员账号可通过 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 环境变量覆盖；已存在管理员时 `init_admin()` 会直接跳过，改名需同步修改数据库。
- 测试账号只存在于 `backend/data/zimu.db`，删库重启只会重建管理员，不会重建它们；需要时请用注册接口重新注册并激活。

## 目录结构

```
ZiMu/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── routers/    # auth / admin / extract
│   │   ├── services/
│   │   │   ├── extraction/  # 提取引擎（照搬原项目，CPU 版）
│   │   │   └── task_manager.py
│   │   ├── config.py   database.py   models.py   security.py   schemas.py
│   ├── models/V5/      # PP-OCRv5 模型（必须）
│   ├── subfinder/      # VideoSubFinder 二进制（Linux/Windows/macOS）
│   ├── configs/typoMap.json
│   └── run.py
├── frontend/           # Vue3 + Vite 前端
├── zimu.sql            # MySQL 建库建表脚本（含预留支付表）
├── zimu-all.sql        # 建库 + 建表 + 当前数据，一个文件搞定（推荐）
├── zimu-data.sql       # 仅数据（旧 SQLite 导出，可选）
├── 测试.md             # 测试报告（bug 修复验证 + 全功能测试）
└── README.md
```

## 部署步骤

### 1. 后端

> **Python 版本要求：3.10+（推荐 3.12）**。项目依赖（paddlepaddle 3.3.1 / pydantic-core 等）是 3.12 的二进制包，用 3.9 会直接导入失败。

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# CPU 版 PaddlePaddle
pip install paddlepaddle==3.3.1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install -r requirements.txt

# 启动
python run.py
```

> 首次启动会自动创建固定管理员账号（`zimuadminj8wfe@gmail.com` / `Admin@123456`），请立即修改。完整账号见 [默认账号](#默认账号)。

### 2. 数据库（MySQL）

后端默认连 MySQL（`DB_TYPE=mysql`），启动前先建库建表。**一个文件搞定（建库 + 建表 + 可选数据导入）**：

```bash
# 推荐：建库、建表、导入现有数据一次完成（可重复执行）
mysql -u root -p < zimu-all.sql

# 或者只要空库（不含数据）：
mysql -u root -p < zimu.sql
# 之后再单独导数据：
mysql -u root -p < zimu-data.sql
```

- 连接参数写在 `backend/.env`（复制 `backend/.env.example` 改即可，后端启动时自动读取），也可用系统环境变量覆盖：

  ```ini
  DB_TYPE=mysql
  DB_HOST=127.0.0.1
  DB_PORT=3306
  DB_USER=root
  DB_PASSWORD=你的密码
  DB_NAME=zimu
  ```

- 本地没有 MySQL、只想先跑起来：设 `DB_TYPE=sqlite`，用内置 SQLite（`backend/data/zimu.db`）。
- **预留的支付表**：`pay_orders`（订单号/套餐/金额/状态/支付渠道/到期快照）与 `users.subscription_expire_at`（订阅到期时间，0=不受限）已建好，后续做「充值一个月使用权限」时直接在支付回调里延长该字段即可，当前版本不读写它们。
- 数据导出脚本：`backend/scripts/sqlite_to_mysql.py`（`--all` 参数会额外生成 `zimu-all.sql`），数据用 `INSERT IGNORE`，重复执行不会报错。

### 3. 前端

```bash
cd frontend
npm install
npm run dev      # 开发模式
npm run build    # 构建到 dist（可由 FastAPI 直接托管）
```

### 4. 环境变量（可选）

> 后端启动时会自动读取 `backend/.env`（复制 `backend/.env.example` 改名即可），系统环境变量优先级更高。见 [`backend/.env`](backend/.env)。

| 变量                                | 说明          | 默认值                         |
| --------------------------------- | ----------- | --------------------------- |
| `SECRET_KEY`                      | JWT 密钥      | 内置默认值（生产请修改）                |
| `ADMIN_EMAIL`                     | 管理员邮箱       | `zimuadminj8wfe@gmail.com`  |
| `ADMIN_PASSWORD`                  | 管理员密码       | `Admin@123456`              |
| `DB_TYPE`                         | 数据库类型       | `mysql`（也可 `sqlite`）          |
| `DB_HOST` / `DB_PORT`             | MySQL 地址     | `127.0.0.1` / `3306`        |
| `DB_USER` / `DB_PASSWORD`         | MySQL 账号     | `root` / 空                  |
| `DB_NAME`                         | MySQL 库名     | `zimu`                      |
| `SMTP_HOST` / `SMTP_PORT`         | SMTP 服务器    | 空（开发模式）                     |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP 账号     | 空                           |
| `SMTP_FROM` / `SMTP_SSL`          | 发件人 / SSL开关 | 空 / `1`                     |
| `CORS_ORIGINS`                    | 允许的跨域来源     | `http://localhost:5173,...` |
| `MAX_UPLOAD_SIZE`                 | 上传大小限制(字节)  | `2147483648`                |

### 5. Linux 注意事项

VideoSubFinder 需要执行权限：

```bash
chmod +x backend/subfinder/linux/VideoSubFinderCli.run
```

视频与项目路径请勿包含中文和空格。

## API 概览

| 方法   | 路径                                  | 说明           |
| ---- | ----------------------------------- | ------------ |
| POST | `/api/auth/send-register-code`      | 发送注册邮箱验证码    |
| POST | `/api/auth/register`                | 注册           |
| POST | `/api/auth/login`                   | 登录           |
| GET  | `/api/auth/me`                      | 当前用户         |
| POST | `/api/auth/activate`                | 激活码激活        |
| POST | `/api/extract/upload`               | 上传视频         |
| POST | `/api/extract/{id}/start`           | 开始提取（可选字幕区域） |
| GET  | `/api/extract/{id}/status`          | 任务进度/日志      |
| GET  | `/api/extract/{id}/download/{file}` | 下载结果         |
| GET  | `/api/extract/{id}/video`           | 视频流（Range，URL 带 `?token=`，校对页播放用） |
| GET  | `/api/extract/{id}/subtitles`       | 读取字幕（校对页）    |
| POST | `/api/extract/{id}/subtitles`       | 保存修改后的字幕（同步写回 SRT/TXT） |
| POST | `/api/admin/codes`                  | 生成激活码（管理员）   |
| GET  | `/api/admin/dashboard`              | 统计（管理员）      |

> 字幕校对入口：任务完成后，首页「结果下载」区点 **校对** 进入 `/review/{taskId}`——左侧播视频、右侧同步高亮当前字幕，点行跳转、双击修改，改完「保存修改」再导出 SRT/TXT。

## 测试

完整测试过程与结果见 [测试.md](测试.md)：46 项接口测试、9 项坐标换算单元测试、真实视频框选提取、MySQL 迁移与字幕校对 21 项功能测试全部通过（2026-10-12/13 验证）。

## 常见问题

**1. 启动报 `SyntaxError: invalid syntax` 指向 `click/utils.py`，或 `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`**

venv 里的解释器版本不对（依赖是 Python 3.12 的包，解释器却是 3.9）。先确认：

```bash
backend\venv\Scripts\python.exe -c "import sys; print(sys.version)"
```

应该输出 `3.12.x`。若不对，用 3.12 重建并重装：

```bash
cd backend
rmdir /s /q venv            # Windows（Linux: rm -rf venv）
"C:\Users\<你>\AppData\Local\Programs\Python\Python312\python.exe" -m venv venv
venv\Scripts\activate
pip install paddlepaddle==3.3.1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install -r requirements.txt
```

**2. 直接访问 `http://127.0.0.1:8000` 是 404，但接口正常**

后端只托管 `frontend/dist`（存在才注册页面路由）。先构建前端：

```bash
cd frontend && npm run build     # 之后重启后端
```

开发时也可以只跑前端 `npm run dev`（5173 端口，已配置 `/api` 代理到 8000）。

**3. MySQL 连不上**

确认 `backend/.env` 里的 `DB_USER` / `DB_PASSWORD` / `DB_NAME` 正确，且已执行过 `zimu-all.sql`；只想先跑起来可临时设 `DB_TYPE=sqlite`。
