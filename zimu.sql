-- =====================================================================
-- ZiMu 字幕提取平台 建库建表脚本（MySQL 5.7+ / 8.x，utf8mb4）
--
-- 用法（任选其一）：
--   mysql -u root -p < zimu.sql
--   或在 mysql 客户端里：source /路径/zimu.sql
--
-- 说明：
--   1. 只建表不造数据；管理员账号由后端首次启动时自动创建
--      （见 .env.example 的 ADMIN_EMAIL / ADMIN_PASSWORD）。
--   2. 想把现有 SQLite 里的数据搬过来：再执行 backend/scripts 生成的
--      zimu-data.sql（或运行 backend/scripts/sqlite_to_mysql.py 重新生成）。
--   3. 后端连接参数：DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
--      （默认 127.0.0.1:3306 root 空密码 zimu）。
-- =====================================================================

CREATE DATABASE IF NOT EXISTS zimu
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE zimu;

-- 强制本次连接的字符集，避免图形化工具默认 latin1 导致中文报错
SET NAMES utf8mb4;

-- ---------------------------------------------------------------------
-- 用户表
-- subscription_expire_at：订阅到期时间（unix 秒）。
--   0 = 未订阅/不受限（管理员、老账号默认这样处理）；
--   后续实现「充值一个月使用权限」时：支付成功 -> 到期时间 += 30 天，
--   使用时判断 now < subscription_expire_at 才放行。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL COMMENT '登录邮箱',
  password_hash VARCHAR(255) NOT NULL COMMENT 'PBKDF2-SHA256 密码哈希',
  role VARCHAR(16) NOT NULL DEFAULT 'user' COMMENT 'admin/user',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/active/disabled',
  subscription_expire_at DOUBLE NOT NULL DEFAULT 0 COMMENT '订阅到期时间(unix秒)，0=不受限/未订阅',
  created_at DOUBLE NOT NULL COMMENT '注册时间(unix秒)',
  activated_at DOUBLE NULL COMMENT '激活时间(unix秒)',
  last_login_at DOUBLE NULL COMMENT '最近登录时间(unix秒)',
  UNIQUE KEY uq_users_email (email(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 注册邮箱验证码
CREATE TABLE IF NOT EXISTS email_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  code VARCHAR(16) NOT NULL,
  purpose VARCHAR(32) NOT NULL COMMENT '用途，当前固定 register',
  created_at DOUBLE NOT NULL,
  expires_at DOUBLE NOT NULL,
  attempts INT NOT NULL DEFAULT 0 COMMENT '已尝试次数',
  used_at DOUBLE NULL,
  KEY idx_email_purpose (email(150), purpose(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='注册邮箱验证码';

-- 激活码（现有「一次性激活」体系，与订阅字段并存）
CREATE TABLE IF NOT EXISTS activation_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL,
  enabled TINYINT NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  note VARCHAR(255) NOT NULL DEFAULT '',
  created_by INT NULL COMMENT '生成者 users.id',
  created_at DOUBLE NOT NULL,
  expires_at DOUBLE NULL,
  used_by INT NULL COMMENT '使用者 users.id',
  used_at DOUBLE NULL,
  UNIQUE KEY uq_activation_code (code),
  KEY idx_activation_used (used_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='激活码';

-- 提取任务记录（运行态在内存，这里存历史记录）
CREATE TABLE IF NOT EXISTS tasks (
  id VARCHAR(40) NOT NULL PRIMARY KEY,
  user_id INT NOT NULL,
  video_name VARCHAR(255) NOT NULL DEFAULT '',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/running/completed/failed/cancelled',
  progress_frame DOUBLE NOT NULL DEFAULT 0,
  progress_ocr DOUBLE NOT NULL DEFAULT 0,
  progress_post DOUBLE NOT NULL DEFAULT 0,
  error TEXT NULL,
  output_srt VARCHAR(512) NOT NULL DEFAULT '',
  output_txt VARCHAR(512) NOT NULL DEFAULT '',
  options TEXT NULL COMMENT '提取参数(JSON字符串)',
  created_at DOUBLE NOT NULL,
  finished_at DOUBLE NULL,
  KEY idx_tasks_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='提取任务记录';

-- ---------------------------------------------------------------------
-- 支付订单表（预留）
-- 为后续「充值获得一个月使用权限」预留，当前版本不会读写本表。
-- 建议的后续流程：
--   1) 创建订单：INSERT status='pending'，order_no 自生成（如 PA+时间戳+随机数）；
--   2) 用户支付成功后：UPDATE status='paid', paid_at=now,
--      并把 users.subscription_expire_at 延长 days 天
--      （expire_at 列存本次快照，便于对账）；
--   3) 未支付超时订单：status 改 'cancelled'。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pay_orders (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_no VARCHAR(40) NOT NULL COMMENT '业务订单号',
  user_id INT NOT NULL COMMENT 'users.id',
  plan VARCHAR(16) NOT NULL DEFAULT 'month' COMMENT '套餐标识：month=一个月',
  days INT NOT NULL DEFAULT 30 COMMENT '充值时长(天)',
  amount_cents INT NOT NULL DEFAULT 0 COMMENT '金额(分)',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/paid/cancelled',
  channel VARCHAR(32) NOT NULL DEFAULT '' COMMENT '支付渠道 alipay/wechat/manual...',
  created_at DOUBLE NOT NULL COMMENT '下单时间(unix秒)',
  paid_at DOUBLE NULL COMMENT '支付完成时间(unix秒)',
  expire_at DOUBLE NULL COMMENT '支付成功后写入的订阅到期时间快照(unix秒)',
  note VARCHAR(255) NOT NULL DEFAULT '',
  UNIQUE KEY uq_pay_order_no (order_no),
  KEY idx_pay_user (user_id),
  KEY idx_pay_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付订单表（预留，供充值一个月使用权使用）';
