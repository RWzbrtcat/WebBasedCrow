-- ============================================================================
--  字符集诊断（只读，不修改任何数据）
-- ============================================================================
--  用法：
--      mysql -u root -p --default-character-set=utf8mb4 blogdb < tools/charset_precheck.sql
--
--  背景：站点出现「每日一题中文全是 ?，但文章标题中文正常」。
--        已确认所有表与列都是 utf8mb4，差异不在表定义，而在**数据的存储形态**：
--
--          · posts / topics / comments / settings / admins 的数据是经 latin1 连接
--            写入的 —— MySQL 把应用发来的 UTF-8 字节当成 latin1 字符，转存进 utf8mb4 列，
--            实际字符是「UTF-8 字节的 cp1252 转义」。字节一个没丢。
--          · questions 的数据由 mysql 客户端以 utf8mb4 导入 —— 存的是真中文。
--
--        应用连接恰好是 latin1（`MYSQL_SET_CHARSET_NAME` 在该环境未生效），于是：
--            老表 cp1252 转义 → 转回 latin1 = 原字节 → 显示完全正常（整站靠这个巧合工作）
--            questions 真中文 → 无法用 latin1 表示 → 逐字符替换成 ?
--
--  本脚本把上面的判断坐实，并给出迁移前对照，供后续修复决策。
-- ============================================================================

SET NAMES utf8mb4;

SELECT '【1】表与列字符集（期望全部为 utf8mb4）' AS `步骤`;

SELECT TABLE_NAME, TABLE_COLLATION
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = DATABASE()
 ORDER BY TABLE_NAME;

SELECT TABLE_NAME, COLUMN_NAME, CHARACTER_SET_NAME
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND CHARACTER_SET_NAME IS NOT NULL
 ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT '【2】老表：当前形态 vs 迁移后（同一行并列，一眼可辨）' AS `步骤`;
-- 若「当前形态」显示成 åŠŸèƒ½ 这类，而「迁移后」是真中文，
-- 即坐实老表数据为「cp1252 转义」，可执行 tools/charset_to_utf8.sql 迁移。
SELECT 'posts' AS tbl, id,
       LEFT(title, 40)                                                    AS `当前形态`,
       CONVERT(CAST(CONVERT(title USING latin1) AS BINARY) USING utf8mb4) AS `迁移后`
  FROM posts ORDER BY id LIMIT 5;

SELECT '【3】questions：期望「当前形态」本身就是真中文（它不需要迁移）' AS `步骤`;
SELECT id,
       LEFT(question, 40)                                                    AS `当前形态`,
       CONVERT(CAST(CONVERT(question USING latin1) AS BINARY) USING utf8mb4) AS `若强行迁移会变成`
  FROM questions ORDER BY id LIMIT 3;

SELECT '【4】风险盘点：含「非 latin1 字符」的行（迁移脚本会自动跳过这些行）' AS `步骤`;
-- 期望大多为 0。若某列不为 0，说明该列存在真中文（例如被服务端 DDL 默认值
-- '匿名' 填过的行），迁移脚本的守卫会跳过它们，不会被写成 ?。
-- 理论来源：DDL 里的 DEFAULT '匿名' 由服务端填充，落地即为真中文。
SELECT 'posts.title'      AS col, COUNT(*) AS rows_with_nonlatin1 FROM posts
 WHERE title    IS NOT NULL AND CONVERT(title    USING latin1) <> CONVERT(CONVERT(title    USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.content', COUNT(*) FROM posts
 WHERE content  IS NOT NULL AND CONVERT(content  USING latin1) <> CONVERT(CONVERT(content  USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.summary', COUNT(*) FROM posts
 WHERE summary  IS NOT NULL AND CONVERT(summary  USING latin1) <> CONVERT(CONVERT(summary  USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.author', COUNT(*) FROM posts
 WHERE author   IS NOT NULL AND CONVERT(author   USING latin1) <> CONVERT(CONVERT(author   USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.topic', COUNT(*) FROM posts
 WHERE topic    IS NOT NULL AND CONVERT(topic    USING latin1) <> CONVERT(CONVERT(topic    USING latin1) USING utf8mb4)
UNION ALL SELECT 'posts.theme', COUNT(*) FROM posts
 WHERE theme    IS NOT NULL AND CONVERT(theme    USING latin1) <> CONVERT(CONVERT(theme    USING latin1) USING utf8mb4)
UNION ALL SELECT 'topics.name', COUNT(*) FROM topics
 WHERE name     IS NOT NULL AND CONVERT(name     USING latin1) <> CONVERT(CONVERT(name     USING latin1) USING utf8mb4)
UNION ALL SELECT 'comments.nickname', COUNT(*) FROM comments
 WHERE nickname IS NOT NULL AND CONVERT(nickname USING latin1) <> CONVERT(CONVERT(nickname USING latin1) USING utf8mb4)
UNION ALL SELECT 'comments.content', COUNT(*) FROM comments
 WHERE content  IS NOT NULL AND CONVERT(content  USING latin1) <> CONVERT(CONVERT(content  USING latin1) USING utf8mb4)
UNION ALL SELECT 'settings.v', COUNT(*) FROM settings
 WHERE v        IS NOT NULL AND CONVERT(v        USING latin1) <> CONVERT(CONVERT(v        USING latin1) USING utf8mb4)
UNION ALL SELECT 'admins.nickname', COUNT(*) FROM admins
 WHERE nickname IS NOT NULL AND CONVERT(nickname USING latin1) <> CONVERT(CONVERT(nickname USING latin1) USING utf8mb4);

SELECT '【5】连接层对照（在另一个终端跑，复现应用的行为）' AS `步骤`;
-- 应用当前等价于 latin1 连接，可这样复现：
--   mysql --default-character-set=latin1 -u root -p blogdb \
--     -e "SELECT id,title FROM posts LIMIT 2; SELECT id,question FROM questions LIMIT 2;"
--   期望：posts 显示真中文，questions 显示 ???（与应用接口一字不差）
