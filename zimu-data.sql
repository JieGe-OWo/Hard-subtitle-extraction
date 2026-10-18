-- =====================================================================
-- ZiMu 数据导出（由 backend/scripts/sqlite_to_mysql.py 生成）
-- 生成时间：2026-10-14 00:25:16
-- 目标数据库：`zimu`（脚本会自动创建，无需先手动建库）
-- 可重复执行：使用 INSERT IGNORE，已存在的行会被跳过。
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `zimu` DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci;

USE `zimu`;

-- 强制本次连接的字符集，避免图形化工具默认 latin1 导致中文报错
SET NAMES utf8mb4;

-- ---------- users（4 行） ----------
INSERT IGNORE INTO `users` (`id`, `email`, `password_hash`, `role`, `status`, `created_at`, `activated_at`, `last_login_at`, `subscription_expire_at`) VALUES
(1, 'zimuadminj8wfe@gmail.com', 'pbkdf2_sha256$600000$4e375e9d00a2c504b169250191cf87c5c36fd36453e63cc95069edc3defabefb$c87d9fa55617c59ef620b542fb5dfae5a1a294647290405454044685f0d8549f', 'admin', 'active', 1791720889.7557254, 1791720889.7557254, 1791906277.7787907, 0.0),
(2, 'tester1@example.com', 'pbkdf2_sha256$600000$77e7ce339307882332d8ab79e0216f226cfbd4c5b8419ba03181d5a2a9316fba$6365b01f6e5be88d8916b5f49ec52b24a1a2bc60d0617be89dccd0b10ff13f67', 'user', 'active', 1791720891.3957098, 1791720891.765128, 1791906278.4915645, 0.0),
(3, 'tester2@example.com', 'pbkdf2_sha256$600000$bbbffd2566bd147ad8f97e8e2bf483c8d2cc77011b1be651e2346fecb3a16705$839adf5806d5147d0af1d7a33440e0de3139a43b96c64426eeca3b3f0433dccb', 'user', 'active', 1791720892.4976594, 1791720892.8592632, NULL, 0.0),
(4, '2940648276@qq.com', 'pbkdf2_sha256$600000$59f559767f714f193c19f0a18de853540e617bfe91e47cf41de7e8ebd099854c$d73228e3f0b41ed535e271129e946472026a9b915c015afbf4a7f678b80230b4', 'user', 'active', 1791736477.0260048, 1791737815.8459666, 1791737969.4360015, 0.0);

-- ---------- email_codes（3 行） ----------
INSERT IGNORE INTO `email_codes` (`id`, `email`, `code`, `purpose`, `created_at`, `expires_at`, `attempts`, `used_at`) VALUES
(1, 'tester1@example.com', '097211', 'register', 1791720890.9125881, 1791721490.9125881, 0, 1791720891.0763962),
(2, 'tester2@example.com', '031635', 'register', 1791720892.0105293, 1791721492.0105293, 0, 1791720892.1853466),
(3, '2940648276@qq.com', '282540', 'register', 1791736449.592787, 1791737049.592787, 0, 1791736476.4841814);

-- ---------- activation_codes（3 行） ----------
INSERT IGNORE INTO `activation_codes` (`id`, `code`, `enabled`, `note`, `created_by`, `created_at`, `expires_at`, `used_by`, `used_at`) VALUES
(1, '6ZREYZT5V2F6JNJX', 1, '测试', 1, 1791720890.3631306, 1794312890.3631306, 2, 1791720891.6005456),
(2, 'PAW8VSTPNFZX4F7D', 1, '测试', 1, 1791720890.549546, 1794312890.3631306, 3, 1791720892.6682682),
(3, '2CHN57QBQNHZCF5E', 0, '测试', 1, 1791720890.7508252, 1794329808.294027, NULL, NULL);

-- ---------- tasks（9 行） ----------
INSERT IGNORE INTO `tasks` (`id`, `user_id`, `video_name`, `status`, `progress_frame`, `progress_ocr`, `progress_post`, `error`, `output_srt`, `output_txt`, `options`, `created_at`, `finished_at`) VALUES
('eee99d92bee04c96a77bbdbfa725156f', 1, '9月19日', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791737839.3906457, NULL),
('ef94f751b15644b08c6596ca3de9c7fa', 1, '9月19日', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791737855.387124, NULL),
('e8cbabea6e514c1f90dd0127c7d6954b', 1, '9月19日(1)', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791737856.7625692, NULL),
('1914ff78797d44e58d9e61c874d85e21', 1, '9月19日', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791737933.253733, NULL),
('4a2414edcb1940b3aba8c9608d1d94ad', 4, '9月19日', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791737977.1248865, NULL),
('3b45d8ce85c34296a9b89ab3d3a8be50', 4, '9月19日(1)', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791817193.886968, NULL),
('0d75ac486017499cb8b1f55aca1cc623', 4, '9月19日', 'pending', 0.0, 0.0, 0.0, NULL, NULL, NULL, '{}', 1791817228.0723655, NULL),
('0dbc40cbdef548e1a22bfeb2b4a3fe51', 4, '9月19日', 'cancelled', 0.0, 100.0, 0.0, '任务已取消', NULL, NULL, '{''language'': ''ch'', ''mode'': ''fast'', ''subtitleArea'': 2, ''extractFrequency'': 1, ''thresholdTextSimilarity'': 80, ''dropScore'': 75, ''filterWatermark'': False, ''filterSceneText'': True, ''generateTxt'': True, ''wordSegmentation'': True}', 1791819533.0373368, 1791821248.3762608),
('73b38c291b5444c0bf0f7960024dd145', 4, '9月19日', 'completed', 100.0, 100.0, 100.0, NULL, '9月19日.srt', NULL, '{''language'': ''ch'', ''mode'': ''fast'', ''subtitleArea'': 2, ''extractFrequency'': 3, ''thresholdTextSimilarity'': 80, ''dropScore'': 75, ''filterWatermark'': False, ''filterSceneText'': True, ''generateTxt'': True, ''wordSegmentation'': True}', 1791904056.4614863, 1791904323.2012317);
