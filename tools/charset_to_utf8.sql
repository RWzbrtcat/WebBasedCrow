-- ============================================================================
--  字符集迁移：把「cp1252 转义」的老数据还原成真正的 utf8mb4 中文
-- ============================================================================
--  ★ 执行前必须：
--      1. 先跑 tools/charset_precheck.sql 并确认【2】段的判断；
--      2. 做备份（错了只能靠它回滚）：
--           mysqldump -u root -p --default-character-set=binary blogdb > blogdb.bak.sql
--
--  用法：
--      mysql -u root -p --default-character-set=utf8mb4 blogdb < tools/charset_to_utf8.sql
--
--  原理：老表存的是「UTF-8 字节的 cp1252 转义」。
--          CONVERT(col USING latin1)  把它们转回 latin1 字节（= 原始 UTF-8 字节）
--          CAST(... AS BINARY)        保留字节，不让 MySQL 再做任何字符转换
--          CONVERT(... USING utf8mb4) 按真正的 UTF-8 解释 → 中文还原
--        例：åŠŸèƒ½ → 功能
--
--  两条安全保障（缺一不可）：
--    ① 逐列 WHERE 守卫：只处理「latin1 可表示」的值。
--       含真中文的行若被 CONVERT ... USING latin1 会被写成 ?，所以必须跳过。
--       守卫 `CONVERT(col USING latin1) = 反向转回` 恰好只对 latin1 可表示的值成立。
--       注意守卫**必须逐列判断**，不能用某一列（如 title）的守卫去改另一列（如 content）。
--    ② 幂等：转换成功后守卫变为不成立，重复执行不会二次转换。
--
--  迁移后：老表数据与 questions 一样都是真 utf8mb4，连接即可统一切到 utf8mb4
--         （部署新二进制后 applyConnectionCharset() 会自动探测为 utf8mb4）。
-- ============================================================================

SET NAMES utf8mb4;

SELECT '迁移前抽样（utf8mb4 客户端下应看到 åŠŸèƒ½ 这类形态）' AS `步骤`;
SELECT id, LEFT(title, 40) AS `迁移前` FROM posts ORDER BY id LIMIT 3;
SELECT id, LEFT(name, 30)  AS `迁移前` FROM topics ORDER BY id LIMIT 3;

-- ---------------------------------------------------------------------------
-- posts
-- ---------------------------------------------------------------------------
UPDATE posts SET title = CONVERT(CAST(CONVERT(title USING latin1) AS BINARY) USING utf8mb4)
 WHERE title IS NOT NULL AND CONVERT(title USING latin1) = CONVERT(CONVERT(title USING latin1) USING utf8mb4);

UPDATE posts SET content = CONVERT(CAST(CONVERT(content USING latin1) AS BINARY) USING utf8mb4)
 WHERE content IS NOT NULL AND CONVERT(content USING latin1) = CONVERT(CONVERT(content USING latin1) USING utf8mb4);

UPDATE posts SET summary = CONVERT(CAST(CONVERT(summary USING latin1) AS BINARY) USING utf8mb4)
 WHERE summary IS NOT NULL AND CONVERT(summary USING latin1) = CONVERT(CONVERT(summary USING latin1) USING utf8mb4);

UPDATE posts SET author = CONVERT(CAST(CONVERT(author USING latin1) AS BINARY) USING utf8mb4)
 WHERE author IS NOT NULL AND CONVERT(author USING latin1) = CONVERT(CONVERT(author USING latin1) USING utf8mb4);

UPDATE posts SET topic = CONVERT(CAST(CONVERT(topic USING latin1) AS BINARY) USING utf8mb4)
 WHERE topic IS NOT NULL AND CONVERT(topic USING latin1) = CONVERT(CONVERT(topic USING latin1) USING utf8mb4);

UPDATE posts SET theme = CONVERT(CAST(CONVERT(theme USING latin1) AS BINARY) USING utf8mb4)
 WHERE theme IS NOT NULL AND CONVERT(theme USING latin1) = CONVERT(CONVERT(theme USING latin1) USING utf8mb4);

-- ---------------------------------------------------------------------------
-- topics
-- ---------------------------------------------------------------------------
UPDATE topics SET name = CONVERT(CAST(CONVERT(name USING latin1) AS BINARY) USING utf8mb4)
 WHERE name IS NOT NULL AND CONVERT(name USING latin1) = CONVERT(CONVERT(name USING latin1) USING utf8mb4);

-- ---------------------------------------------------------------------------
-- comments
-- ---------------------------------------------------------------------------
UPDATE comments SET nickname = CONVERT(CAST(CONVERT(nickname USING latin1) AS BINARY) USING utf8mb4)
 WHERE nickname IS NOT NULL AND CONVERT(nickname USING latin1) = CONVERT(CONVERT(nickname USING latin1) USING utf8mb4);

UPDATE comments SET content = CONVERT(CAST(CONVERT(content USING latin1) AS BINARY) USING utf8mb4)
 WHERE content IS NOT NULL AND CONVERT(content USING latin1) = CONVERT(CONVERT(content USING latin1) USING utf8mb4);

-- ---------------------------------------------------------------------------
-- settings（k 为 ASCII 配置键，只处理值列 v）
-- ---------------------------------------------------------------------------
UPDATE settings SET v = CONVERT(CAST(CONVERT(v USING latin1) AS BINARY) USING utf8mb4)
 WHERE v IS NOT NULL AND CONVERT(v USING latin1) = CONVERT(CONVERT(v USING latin1) USING utf8mb4);

-- ---------------------------------------------------------------------------
-- admins（email / avatar 为 ASCII，只处理昵称）
-- ---------------------------------------------------------------------------
UPDATE admins SET nickname = CONVERT(CAST(CONVERT(nickname USING latin1) AS BINARY) USING utf8mb4)
 WHERE nickname IS NOT NULL AND CONVERT(nickname USING latin1) = CONVERT(CONVERT(nickname USING latin1) USING utf8mb4);

-- ---------------------------------------------------------------------------
-- questions / daily_questions / daily_seen **不动** ——
-- 它们的数据本来就是真 utf8mb4（由 mysql 客户端导入），再转一次会变成乱码。
-- ---------------------------------------------------------------------------

SELECT '迁移后抽样（应为真中文）' AS `步骤`;
SELECT id, LEFT(title, 40) AS `迁移后` FROM posts ORDER BY id LIMIT 3;
SELECT id, LEFT(name, 30)  AS `迁移后` FROM topics ORDER BY id LIMIT 3;
SELECT id, LEFT(question, 40) AS `questions 不变` FROM questions ORDER BY id LIMIT 3;

SELECT '收尾自检：仍处于 cp1252 转义形态的行数，期望全为 0' AS `步骤`;
-- 判据：非纯 ASCII（CHAR_LENGTH <> LENGTH）且「latin1 可表示」—— 后者正是转义形态的特征，
-- 真中文会因无法用 latin1 表示而使该条件不成立。两个条件同时成立即说明还没迁移干净。
SELECT 'posts.title' AS col, COUNT(*) AS still_escaped FROM posts
 WHERE CHAR_LENGTH(title) <> LENGTH(title)
   AND CONVERT(title USING latin1) = CONVERT(CONVERT(title USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.content', COUNT(*) FROM posts
 WHERE CHAR_LENGTH(content) <> LENGTH(content)
   AND CONVERT(content USING latin1) = CONVERT(CONVERT(content USING latin1) USING utf8mb4)
UNION ALL SELECT 'topics.name', COUNT(*) FROM topics
 WHERE CHAR_LENGTH(name) <> LENGTH(name)
   AND CONVERT(name USING latin1) = CONVERT(CONVERT(name USING latin1) USING utf8mb4)
UNION ALL SELECT 'comments.nickname', COUNT(*) FROM comments
 WHERE CHAR_LENGTH(nickname) <> LENGTH(nickname)
   AND CONVERT(nickname USING latin1) = CONVERT(CONVERT(nickname USING latin1) USING utf8mb4)
UNION ALL SELECT 'comments.content', COUNT(*) FROM comments
 WHERE CHAR_LENGTH(content) <> LENGTH(content)
   AND CONVERT(content USING latin1) = CONVERT(CONVERT(content USING latin1) USING utf8mb4)
UNION ALL SELECT 'settings.v', COUNT(*) FROM settings
 WHERE CHAR_LENGTH(v) <> LENGTH(v)
   AND CONVERT(v USING latin1) = CONVERT(CONVERT(v USING latin1) USING utf8mb4)
UNION ALL SELECT 'admins.nickname', COUNT(*) FROM admins
 WHERE CHAR_LENGTH(nickname) <> LENGTH(nickname)
   AND CONVERT(nickname USING latin1) = CONVERT(CONVERT(nickname USING latin1) USING utf8mb4);
