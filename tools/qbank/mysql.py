# -*- coding: utf-8 -*-
"""MySQL / 数据库题库（新增 60 道，与已有 10 道合计 70 道）。"""

QUESTIONS = [
    (
        "MySQL",
        "存储引擎,架构",
        2,
        r"""InnoDB 的整体架构是怎样的？内存结构和磁盘结构分别有哪些部分？""",
        r"""**InnoDB = 内存结构 + 磁盘结构 + 后台线程**。

## 一、内存结构

| 组件 | 作用 |
|---|---|
| **Buffer Pool**（缓冲池）| 缓存**数据页 / 索引页 / undo 页 / 自适应哈希 / 锁信息 / change buffer**，是 InnoDB 最核心的内存区，通常占 70%~80% 物理内存（`innodb_buffer_pool_size`）|
| **Log Buffer** | 缓存 redo log，按 `innodb_flush_log_at_trx_commit` 刷盘（8.0 默认 16M）|
| **Adaptive Hash Index** | 对热数据页的索引前缀建哈希，加速等值查询（`innodb_adaptive_hash_index`）|
| **Change Buffer** | 缓存**非唯一二级索引**的写操作，等页被读入时再合并 |
| **Dictionary Cache** | 表/列等数据字典信息（8.0 起独立表空间 `mysql.ibd`）|

**Buffer Pool 内部三链表**（改进型 LRU，解决预读污染）：

```
LRU List = [ Young 区 (5/8) | Old 区 (3/8) ]
             ↑ 热数据            ↑ 新读入的页先放这里
```

- **新页插到 Old 区头部**（midpoint insertion），而不是 LRU 头部。
- 只有在 Old 区**停留超过 `innodb_old_blocks_time`（默认 1000ms）后又被访问**，才晋升到 Young 区。
- 效果：全表扫描/预读进来的一次性页，**来不及晋升就被挤出去**，不会污染热数据。
- 链表太长时按比例从尾部和 midpoint 附近批量淘汰（`innodb_lru_scan_depth`）。

## 二、磁盘结构

| 表空间 | 内容 |
|---|---|
| **系统表空间** `ibdata1` | 回滚段、双写缓冲、早期数据字典 |
| **独立表空间** `tablename.ibd` | 该表的 B+ 树数据 + 索引（`innodb_file_per_table=ON`，**推荐**）|
| **通用表空间** | 多个表共享 |
| **undo 表空间** | undo log 段（8.0 起可独立）|
| **临时表空间** | 排序/临时表 |
| **redo log** `#innodb_redo/` | 循环写的物理日志（8.0.30 前是 `ib_logfile0/1`）|
| **Doublewrite Buffer** | 刷脏页前先顺序写一份，防**页撕裂（partial page write）** |

## 三、后台线程

- **Master Thread**：1 次/秒、10 次/秒的调度主循环，负责刷脏、合并插入缓冲。
- **IO Thread**：`read` / `write` / `insert buffer` / `log` 四类，可配并发数。
- **Purge Thread**：回收已提交事务的 undo 页。
- **Page Cleaner Thread**：从 Buffer Pool 刷脏页到磁盘。

## 四、一条 UPDATE 的完整流转 ⭐

```
1. 从 Buffer Pool 找页；没有 → 从 .ibd 读入（读不到还要去 redo 里找？不用，异常恢复才用）
2. 写 undo log（记录旧值，供回滚 + MVCC）
3. 修改 Buffer Pool 中的页  ← 注意：此时磁盘上的页还是旧的（脏页）
4. 写 redo log 到 Log Buffer
5. 提交时按策略将 redo 刷盘（WAL：先日志后数据）
6. 脏页由 Page Cleaner 异步刷盘
```

**WAL（Write-Ahead Logging）的意义**：把"随机写数据页"变成"顺序写日志"，提交即可返回，数据页延后刷 —— 这是 MySQL 高吞吐的根本原因，也是崩溃恢复的依据。

**双写缓冲的意义**：InnoDB 页 16KB，而磁盘/文件系统原子写通常是 4KB，断电时可能只写了半个页。双写先写一份连续副本，恢复时用副本修复撕裂页。""",
    ),
    (
        "MySQL",
        "redo log,WAL,两阶段提交",
        3,
        r"""redo log 和 binlog 有什么区别？为什么需要两阶段提交（2PC）？""",
        r"""## 一、两者本质不同

| 维度 | **redo log** | **binlog** |
|---|---|---|
| 归属层 | **InnoDB 引擎层**（MyISAM 没有）| **MySQL Server 层**（所有引擎都有）|
| 类型 | **物理逻辑日志**：记"在哪个页做了什么修改" | **逻辑日志**：记"执行了什么 SQL / 行变更" |
| 大小 | **固定循环写**（`innodb_log_file_size`），会覆盖 | **追加写**，不覆盖，可归档 |
| 用途 | **崩溃恢复**（crash-safe），保证已提交事务不丢 | **主从复制**、**数据恢复**（PITR）|
| 刷盘 | `innodb_flush_log_at_trx_commit` | `sync_binlog` |
| 幂等性 | 幂等（页 + LSN）| 不幂等，重放要保证位置一致 |

## 二、为什么必须两阶段提交

考虑一次 `UPDATE`，两个日志分别刷盘的两种错误顺序：

**① 先写 redo，再写 binlog，binlog 没写完就崩**
- redo 已落盘 → 重启后**恢复出这次修改**（数据变了）。
- binlog 缺失 → **从库收不到这条变更**（主从不一致）。
- ❌ 数据变了但日志没记。

**② 先写 binlog，再写 redo，redo 没写完就崩**
- redo 未落盘 → 重启后**回滚这次修改**（数据没变）。
- binlog 已落盘 → **从库重放这条变更**（多了数据）。
- ❌ 日志记了但数据没变。

**结论**：只用其中一种顺序，都可能出现"主库数据"与"binlog"不一致。所以引入 **2PC**。

## 三、2PC 三个步骤 ⭐

```
     ① prepare 阶段
        redo log 写入并刷盘，事务状态标记为 prepare
        （此时事务还没提交，但 redo 可恢复）
                    │
                    ▼
     ② 写 binlog 并刷盘
                    │
                    ▼
     ③ commit 阶段
        在 redo log 里写入 commit 标记
        （这一步之后事务才真正可见/生效）
```

**崩溃恢复规则**（重启后扫 redo）：

| redo 状态 | binlog 状态 | 处理 |
|---|---|---|
| 有 prepare，**无** commit | **完整** | **提交**（binlog 全，按 binlog 主从一致原则）|
| 有 prepare，**无** commit | **不完整**（被截断）| **回滚**（binlog 不完整，不能提交）|
| 有 prepare，**有** commit | — | 提交 |

**判断 binlog 是否完整**：binlog 有 `XID` event 或结尾校验（`binlog_checksum`），而且每个事务的 binlog 记录了 `BEGIN`...`COMMIT` 边界，靠这个识别截断。

## 四、"双一"配置 ⭐

崩溃安全的最强组合：

```ini
innodb_flush_log_at_trx_commit = 1   # redo 每次提交都 fsync
sync_binlog = 1                      # binlog 每次提交都 fsync
```

- 性能与安全的权衡：`=2`（redo 只写 OS cache，每秒刷）能提升吞吐，但**宕机会丢 1s 数据**。
- `=0` 更快但不安全。
- 生产**默认建议双 1**；金融场景必须双 1。

## 五、组提交（Group Commit）

每次提交都 fsync 太慢，MySQL 把同一时刻的多个事务合并成**一次 fsync**：

```
T1 ─┐
T2 ─┼─► 一次 fsync 刷 redo ─► 一次 fsync 刷 binlog ─► 一起 commit
T3 ─┘
```

- `binlog_group_commit_sync_delay` + `binlog_group_commit_sync_no_delay_count` 可**主动等一小会儿**攒批量，提高组提交效率。
- 效果：并发越高，单事务的平均刷盘成本越低。""",
    ),
    (
        "MySQL",
        "MVCC,undo log,隔离级别",
        3,
        r"""MVCC 是怎么实现的？RR 隔离级别下具体是怎样避免不可重复读的？""",
        r"""## 一、三个隐藏字段

InnoDB 每行记录都有隐藏列：

| 字段 | 含义 |
|---|---|
| `DB_TRX_ID` | 最后修改该行的**事务 ID**（6 字节）|
| `DB_ROLL_PTR` | **回滚指针**，指向 undo log 中的旧版本（7 字节）|
| `DB_ROW_ID` | 无主键时生成的行 ID（6 字节）|

**版本链**：多次修改同一行，靠 `DB_ROLL_PTR` 串成一条**单向链表**（undo log 里），从新到旧：

```
当前行(trx 100) --roll_ptr--> 旧版本(trx 90) --> 旧版本(trx 80) --> NULL
```

## 二、Read View（读视图）

每个事务在**快照读**时生成一个 Read View，核心四个字段：

| 字段 | 含义 |
|---|---|
| `m_ids` | 生成快照时**活跃（未提交）**的事务 ID 列表 |
| `min_trx_id` | 活跃事务中的最小值 |
| `max_trx_id` | 下一个将分配的事务 ID（即活跃 ID 的上界）|
| `creator_trx_id` | 创建该 Read View 的事务 ID |

**可见性判断**（沿版本链从新到旧找第一条可见的）：

| 行的 `DB_TRX_ID` | 判断 |
|---|---|
| `== creator_trx_id` | **可见**（自己改的）|
| `< min_trx_id` | **可见**（在我开始前就提交了）|
| `>= max_trx_id` | **不可见**（在我开始后才开启的事务）|
| `in m_ids` | **不可见**（当时还活跃，未提交）|
| 不在 `m_ids` 且 `< max_trx_id` | **可见**（当时已提交）|

若当前版本不可见 → 顺 `DB_ROLL_PTR` 找上一版本，重复判断，直到找到可见版本。

## 三、RC 与 RR 的唯一区别：Read View 的生成时机 ⭐

| 隔离级别 | Read View 何时生成 | 效果 |
|---|---|---|
| **RC**（读已提交）| **每次 SELECT 都重新生成** | 别人提交后，我下次查就能看到 → **不可重复读** |
| **RR**（可重复读）| **只在事务第一次快照读时生成一次**，之后复用 | 整个事务看到的是**同一个快照** → **可重复读** |

**这就是"避免不可重复读"的机制**：RR 下事务复用同一个 Read View，`m_ids` 不变，别人的新提交事务 ID 落在 `m_ids` 或不满足条件 → 一直看不到 → 每次读结果一致。

## 四、快照读 vs 当前读 ⭐

| 类型 | 语句 | 读什么 |
|---|---|---|
| **快照读** | 普通 `SELECT` | Read View + undo 版本链（**不加锁**）|
| **当前读** | `SELECT ... FOR UPDATE` / `LOCK IN SHARE MODE`、`UPDATE` / `DELETE` / `INSERT` | **最新版本**，并加锁 |

## 五、RR 下为什么还需要间隙锁？

MVCC 只解决**快照读**的幻读。但如果事务里用的是**当前读**：

```sql
BEGIN;
SELECT * FROM t WHERE id > 5 FOR UPDATE;  -- 当前读，锁住 (5, +∞) 间隙
-- 另一事务 INSERT id=7 会被阻塞 ← 靠 Next-Key Lock 阻止幻读
COMMIT;
```

所以 **RR 通过 "Read View（快照读）+ Next-Key Lock（当前读）" 双保险**解决幻读。严格来说，如果事务里全部是快照读，RR 才不会出现幻读；一旦夹杂当前读和写，就需要间隙锁。

## 六、undo log 什么时候清理

- 版本链不能无限长：靠 **purge 线程**回收。
- **判断标准**：没有任何活跃 Read View 需要看到更老的版本时，对应的 undo 才能删。
- **长事务的危害** ⭐：一个开了很久没提交的事务会让 `m_ids` 一直占着 → **undo 无法 purge → 版本链越来越长 → 系统表空间暴涨 + 查询越来越慢**。所以必须监控并 kill 长事务。

```sql
-- 找长事务
SELECT trx_id, trx_started, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS sec,
       trx_state, trx_mysql_thread_id, trx_query
FROM information_schema.innodb_trx ORDER BY trx_started;
```

## 七、一句话总结

**MVCC = 隐藏字段 + undo 版本链 + Read View**；RC/RR 的差别只在 Read View 是"每次读重建"还是"首次读建一次"。""",
    ),
    (
        "MySQL",
        "锁,间隙锁,死锁",
        3,
        r"""InnoDB 有哪些锁？什么是 Next-Key Lock？死锁是怎么产生的，如何排查和避免？""",
        r"""## 一、锁的分类

**按粒度**：

| 锁 | 说明 |
|---|---|
| **表级锁** | 开销小、并发低。含**表锁**、**元数据锁 MDL**、**意向锁 IS/IX** |
| **行级锁** | InnoDB 特有，锁在**索引项**上（**不是锁在行记录上**，没有索引会退化成锁全表）|
| **页级锁** | 极少用 |

**按模式**：

| 锁 | 说明 |
|---|---|
| **共享锁 S** | `LOCK IN SHARE MODE`，读锁，S 与 S 兼容 |
| **排他锁 X** | `FOR UPDATE`、`UPDATE`、`DELETE`，X 与任何锁互斥 |
| **意向共享 IS / 意向排他 IX** | **表级**标记"表里某些行将被加 S/X"，让表锁与行锁能快速判断冲突 ⭐ |

**意向锁的意义**：事务 B 想加表锁，不必逐行检查，只看表上有没有 IX/IS 即可——**把 O(n) 行扫描变成 O(1)**。

## 二、行锁的三种形态 ⭐

设索引值依次为 `5, 10, 15`：

| 类型 | 锁定范围 | 例子 |
|---|---|---|
| **Record Lock**（记录锁）| 锁**单个索引记录** | `WHERE id = 10` 命中唯一索引 → 锁 id=10 |
| **Gap Lock**（间隙锁）| 锁**两个记录之间的开区间**，不锁记录本身 | 锁 `(5, 10)` |
| **Next-Key Lock**（临键锁）| **记录锁 + 前面的间隙** = `(前一个, 当前]` | 锁 `(5, 10]` |

**Next-Key Lock 是 RR 的默认行锁算法**，锁住 `(5, 10]` 这样的**左开右闭**区间。它的作用就是**阻止其他事务往这个区间插入新记录 → 防幻读**。

**退化规则**：
- 查询**命中唯一索引的等值条件**且记录存在 → Next-Key 退化为 **Record Lock**（只锁这一行，不锁间隙）。
- 记录**不存在** → 退化为 **Gap Lock**（锁住那个区间）。
- 查询**没有索引** → 全表扫描，**每一条记录都加 Next-Key Lock** → 相当于锁全表 ⭐（这就是"没索引的 UPDATE 会锁住整表"的原因）。

## 三、加锁原则（背下来）⭐

1. 加锁的基本单位是 **Next-Key Lock**。
2. 查找过程中**访问到的对象**才会加锁。
3. 唯一索引等值命中 → Next-Key **降级为 Record Lock**。
4. 唯一索引等值未命中 → Next-Key **降级为 Gap Lock**。
5. 不等值/范围扫描 → 继续用 Next-Key（或继续向右找，直到不满足条件为止）。

## 四、死锁的产生

**必要条件**：多个事务**以不同顺序**获取**互斥资源**，形成**循环等待**。

```sql
-- 事务 A                        -- 事务 B
BEGIN;                           BEGIN;
UPDATE t SET v=1 WHERE id=1;     UPDATE t SET v=1 WHERE id=2;
--                              （A 持 id=1 的 X 锁，B 持 id=2 的 X 锁）
UPDATE t SET v=1 WHERE id=2;     UPDATE t SET v=1 WHERE id=1;
-- ← 等 B 释放 id=2               -- ← 等 A 释放 id=1   ⇒ 死锁环形等待
```

**其他常见场景**：
- **间隙锁互相等待**：两个事务都在 `(5,10)` 里 `INSERT`，各自持间隙锁。
- **索引顺序不一致**：两条 SQL 的 `WHERE` 条件导致加锁顺序相反。
- **SELECT ... FOR UPDATE 后 UPDATE**：混合使用造成不一致顺序。
- **唯一索引冲突下的 S 锁**：`INSERT` 撞唯一键时会先加 S 锁，两个事务都插同一个键也能死锁。

**InnoDB 的处理**：自动检测死锁（**wait-for graph**），发现环就**回滚代价小的一方**（undo 量少的），并抛 `ERROR 1213: Deadlock found when trying to get lock`。所以死锁**不会让数据库卡死**，只是有一个事务失败。

## 五、排查 ⭐

```sql
SHOW ENGINE INNODB STATUS\G
-- 看 LATEST DETECTED DEADLOCK 段落，包含：
--   两个事务各自持有什么锁、在等什么锁、执行的 SQL、被回滚的是谁

-- 当前锁等待
SELECT * FROM performance_schema.data_locks;         -- 8.0（5.7 是 innodb_locks）
SELECT * FROM performance_schema.data_lock_waits;    -- 8.0（5.7 是 innodb_lock_waits）

-- 简化版：谁在等谁
SELECT r.trx_id AS waiting, r.trx_mysql_thread_id AS w_thread,
       b.trx_id AS blocking, b.trx_mysql_thread_id AS b_thread
FROM information_schema.innodb_lock_waits w
JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id;

-- 锁等待超时
-- innodb_lock_wait_timeout（默认 50s），超时抛 1205
```

```bash
# 打开全量死锁日志
# innodb_print_all_deadlocks = ON  → 死锁信息写入 error log
```

## 六、如何避免 ⭐

| 措施 | 说明 |
|---|---|
| **统一访问顺序** | 所有事务按同一顺序访问资源（如都按主键升序更新）|
| **缩短事务** | 事务里不要有网络调用/慢查询，尽快提交，减少持锁时间 |
| **索引命中** | 保证 `WHERE` 走索引，避免锁全表 + 大量 Next-Key |
| **拆分大事务** | 批量更新分批提交（每 500~1000 条）|
| **降低隔离级别** | RC 下没有间隙锁，能大幅减少间隙锁死锁（现在很多大厂用 RC + binlog ROW）|
| **重试机制** | 应用层捕获 1213/1205 后**有限次重试** ⭐ |
| **避免 `SELECT FOR UPDATE` 后长耗时操作** | 拿锁就尽快改完提交 |
| **`INSERT ... ON DUPLICATE KEY UPDATE` / `INSERT IGNORE`** | 用原子写入替代"先查后插"，从根上避免竞态 |

**一句话**：死锁是**并发系统的固有现象**，无法彻底消除，只能通过"统一顺序 + 短事务 + 好索引 + 重试"把概率降到可接受，并保证**发生时可自愈**。""",
    ),
    (
        "MySQL",
        "索引,B+树,回表,覆盖索引",
        2,
        r"""为什么 MySQL 索引用 B+ 树而不是 B 树、红黑树或哈希表？聚簇索引和二级索引有什么区别？""",
        r"""## 一、为什么是 B+ 树 ⭐

| 候选结构 | 为什么不用 |
|---|---|
| **哈希表** | **不支持范围查询/排序**（`>`、`BETWEEN`、`ORDER BY` 无能无力），只能等值；且有哈希冲突、需要扩容 rehash |
| **二叉搜索树** | 可能退化成链表，O(n)；树高太大 |
| **红黑树 / AVL** | 平衡性好，但**是二叉树**：1000 万数据高度约 24 层 → 24 次磁盘 IO，**每个节点只放一个元素，太浪费一次 IO** |
| **B 树** | 每个节点都存**数据**，导致：① 单个节点能放的**键太少** → 树更高；② **范围查询要中序遍历、多次回溯**；③ 数据分散在所有节点，不利于局部性 |
| **B+ 树** ✅ | ① **非叶子节点只存键、不存数据** → 一个 16KB 页能放几百上千个键 → 树高仅 **2~4 层**，3 层就能存约 2000 万行；② **所有数据都在叶子节点且用链表相连** → 范围查询和排序**顺序扫描即可**；③ 查询性能稳定（都要走到叶子）|

**关键数字**：InnoDB 页 16KB，假设主键 bigint(8B) + 页指针(6B) = 14B，一个非叶页可放约 `16384/14 ≈ 1170` 个键；叶子页按每行 1KB 可放 16 行。三层 B+ 树可容纳 `1170 × 1170 × 16 ≈ 2190 万`行 —— **三次 IO 查到 2000 万行中的一行**，这就是 B+ 树的威力。

## 二、聚簇索引 vs 二级索引 ⭐

| | **聚簇索引（Clustered，主键索引）** | **二级索引（Secondary，辅助索引）** |
|---|---|---|
| 叶子节点存什么 | **整行数据** | **索引列 + 主键值** |
| 数量 | 一张表**只能有一个** | 可以有多个 |
| 选取 | 优先主键；无主键取第一个非空唯一索引；都没有则用隐藏 `DB_ROW_ID` | 建索引时创建 |
| 通过它查询 | **一次即可拿到整行** | **需要回表** |

**示意图**：

```
聚簇索引：                二级索引 idx_name：
[10|30|50]                [Amy|10] [Bob|30] [Cat|50]
   ↓ 叶子                                  ↓ 拿到主键 30
[10: 整行数据] ← 顺序存放（主键有序，所以叫"聚簇/聚集"）    ↓
[30: 整行数据]                         回表：拿 30 再去聚簇索引查整行
[50: 整行数据]
```

## 三、回表与覆盖索引

**回表（Back to Table）**：二级索引拿到主键后，**再走一次聚簇索引**查完整行。每条记录一次回表 = 一次随机 IO，代价高。

```sql
-- 需要回表：name 是二级索引，但要拿 age
SELECT age FROM users WHERE name = 'Bob';
-- 1) idx_name 找到主键 30  2) 用 30 回表查 age
```

**覆盖索引（Covering Index）**：查询涉及的所有列**都在这棵二级索引上**，无需回表 ⭐

```sql
-- 建索引 idx_name_age(name, age)
SELECT name, age FROM users WHERE name = 'Bob';   -- Extra: Using index ✅ 不回表

-- explain 的 Extra 显示 "Using index" → 覆盖索引生效
```

## 四、索引设计实践

| 原则 | 说明 |
|---|---|
| **主键尽量短且自增** | 短 → 非叶页放更多键 → 树矮；自增 → 顺序插入，**避免页分裂** |
| **优先建联合索引** | 一次建 `(a,b,c)` 往往能覆盖多个查询，比建三个单列索引更省 |
| **利用覆盖索引消灭回表** | 高频查询需要的列一起放进联合索引尾部 |
| **不为低区分度列单独建索引** | 如"性别""状态"，选择性太低，优化器可能直接放弃 |
| **控制索引数量** | 每个索引都要维护（写放大），一般单表不超过 5~6 个 |
| **避免用 UUID 作主键** | 随机 → 频繁页分裂 + 页碎片 + 体积大（36 字节字符串），写性能差数倍 |
| **区分度公式** | `选择性 = 不重复值数 / 总行数`，越接近 1 越好（`COUNT(DISTINCT col)/COUNT(*)`）|

## 五、另一种索引：自适应哈希索引（AHI）

InnoDB 会**自动**为频繁访问的索引页建哈希索引，把某些等值查询变成 O(1)。由 `innodb_adaptive_hash_index` 控制（8.0 默认 ON，但高并发下 AHI 的 latch 竞争可能拖慢性能，部分场景建议关闭）。

**一句话总结**：**B+ 树把"一次磁盘 IO 能拿到多少有效信息"这个约束优化到极致**；聚簇索引让主键查询一次到位，二级索引以"回表"换存储空间。""",
    ),
    (
        "MySQL",
        "索引失效,explain,优化",
        2,
        r"""哪些情况会导致索引失效？EXPLAIN 的关键字段怎么读？""",
        r"""## 一、索引失效的常见场景 ⭐

| # | 场景 | 例子 | 原因 |
|---|---|---|---|
| 1 | **在索引列上做运算/函数** | `WHERE YEAR(create_time)=2024`、`WHERE id+1=5` | 索引按**原始值**排序，运算后无法定位 |
| 2 | **隐式类型转换** ⭐ | `WHERE phone=13800000000`（phone 是 varchar）| 字符串列与数字比较 → MySQL 把列**转成数字**再比 → 等于对列做函数 |
| 3 | **隐式字符集不一致** ⭐ | utf8mb4 表 JOIN utf8 表 | 会做 COLLATE 转换 → 退化为全表扫描（**本项目实战踩过**）|
| 4 | **前导模糊查询** | `LIKE '%abc'` / `LIKE '%abc%'` | 无法用 B+ 树定位起点（`LIKE 'abc%'` 可以用）|
| 5 | **违反最左前缀** | 索引 `(a,b,c)`，但 `WHERE b=1` | B+ 树按 (a,b,c) 逐级排序，跳过 a 无法定位 |
| 6 | **范围查询后面的列失效** | 索引 `(a,b)`，`WHERE a>1 AND b=2` | a 已用范围，b 在范围内无序（**但 8.0 有 ICP 可部分优化**）|
| 7 | **`!=` / `NOT IN` / `NOT LIKE`** | `WHERE a != 1` | 难以利用有序性，常退化为扫描（视数据分布而定）|
| 8 | **`OR` 连接的列有未建索引的** | `WHERE a=1 OR b=2`（b 无索引）| 无法合并，只能全表 |
| 9 | **`IS NULL` / `IS NOT NULL`** | 视情况 | 通常可用，但优化器可能判断全表更划算 |
| 10 | **优化器认为全表更快** | 小表、或要取大部分行 | **不是失效，是成本选择**（`ORDER BY` 全排序也可能）|
| 11 | **`SELECT *` 导致回表太多** | 覆盖索引被破坏 | 优化器可能改走全表扫描 |
| 12 | **使用 `ORDER BY` 与索引顺序不一致** | `ORDER BY a ASC, b DESC` | 混合方向在 8.0 前无法用索引有序性 |

**验证方法**：`EXPLAIN` 看 `type` 和 `key`，`SHOW WARNINGS` 看优化器改写后的 SQL。

## 二、EXPLAIN 关键字段 ⭐

```sql
EXPLAIN SELECT * FROM users WHERE name='Bob' AND age>20;
EXPLAIN ANALYZE ...   -- 8.0.18+ 真实执行并给出实际耗时/行数
```

| 字段 | 含义 | 关注点 |
|---|---|---|
| **`id`** | 查询序号 | 相同 = 同一组；不同 = 子查询/UNION；值越大越先执行 |
| **`select_type`** | 查询类型 | `SIMPLE` / `PRIMARY` / `SUBQUERY` / `DERIVED` / `UNION` |
| **`table`** | 表名 | |
| **`partitions`** | 命中的分区 | |
| **`type`** ⭐ | **访问类型**（最重要）| 见下表排序 |
| **`possible_keys`** | 可能用的索引 | 只是候选 |
| **`key`** ⭐ | **实际用的索引** | `NULL` = 没用索引 |
| **`key_len`** | 使用索引的字节数 | 可反推**用了联合索引的前几列** |
| **`ref`** | 与索引比较的列/常量 | |
| **`rows`** ⭐ | **预估扫描行数** | 越小越好，与 `filtered` 结合判断 |
| **`filtered`** | 按条件过滤后剩余的百分比 | 10% 表示还要过滤掉 90% |
| **`Extra`** ⭐ | 附加信息 | `Using index` / `Using where` / `Using temporary` / `Using filesort` / `Using index condition` |

**`type` 性能排序（从好到坏）** ⭐：

```
system > const > eq_ref > ref > range > index > ALL
                                    ↑          ↑
                              范围扫描    全索引扫描   全表扫描
```

| type | 说明 |
|---|---|
| `system` | 表只有一行 |
| `const` | 主键/唯一索引等值，**优化器阶段就能确定** |
| `eq_ref` | JOIN 时被驱动表用主键/唯一索引等值匹配 |
| `ref` | 普通二级索引等值匹配 |
| `range` | 范围扫描（`>`, `<`, `BETWEEN`, `IN`, `LIKE 'x%'`）|
| `index` | 扫整棵索引树（比 ALL 好，因为索引通常比行小）|
| `ALL` | **全表扫描，需要优化** ❌ |

**`Extra` 重点** ⭐：

| 值 | 含义 | 好坏 |
|---|---|---|
| `Using index` | **覆盖索引**，不用回表 | ✅ 好 |
| `Using index condition` | **索引下推 ICP**（5.6+），在存储引擎层用索引过滤 | ✅ 好 |
| `Using where` | 拿到行后在 Server 层再过滤 | ⚠️ 中性 |
| `Using temporary` | 用了**临时表**（常见于 `GROUP BY`/`DISTINCT`）| ❌ 差 |
| `Using filesort` | 需要**额外排序**（没走索引顺序）| ❌ 差 |
| `Using join buffer` | 没走索引，用 join buffer（BNL）| ❌ 差 |

## 三、优化的实操步骤

```sql
-- 1. 开慢查询日志
SET GLOBAL slow_query_log = ON;
SET GLOBAL long_query_time = 1;
SET GLOBAL log_queries_not_using_indexes = ON;

-- 2. 用自带工具汇总
-- mysqldumpslow -s t -t 10 /var/log/mysql/slow.log
-- pt-query-digest /var/log/mysql/slow.log   ← Percona 工具，更强

-- 3. 精确定位某个 SQL
EXPLAIN ANALYZE <你的SQL>;
SHOW PROFILE FOR QUERY <n>;   -- 或 performance_schema
```

**优化优先级**：**加/改索引 > 改写 SQL > 优化表结构 > 加缓存 > 分库分表**。不要一上来就分库分表。

## 四、记忆口诀

> **左前缀、不运算、类型对、字符集一致、范围在后、少 OR、覆盖索引不回表。**""",
    ),
    (
        "MySQL",
        "联合索引,最左前缀,ICP,前缀索引",
        3,
        r"""联合索引的最左前缀原则是什么？什么是索引下推（ICP）？前缀索引如何选择长度？""",
        r"""## 一、最左前缀原则

索引 `idx (a, b, c)` 的 B+ 树按 **(a, b, c)** 字典序排列：

```
a=1  →  b=1 → c=1
        b=1 → c=2
        b=2 → c=1
a=2  →  b=1 → c=1
```

**能用的查询**（✅）：

| 查询条件 | 用到的索引列 |
|---|---|
| `WHERE a=1` | (a) |
| `WHERE a=1 AND b=2` | (a,b) |
| `WHERE a=1 AND b=2 AND c=3` | (a,b,c) |
| `WHERE a=1 AND c=3` | 只用 (a)，c 不能用于定位（但可 ICP 过滤）|
| `WHERE a=1 AND b>2` | (a) 定位 + (b) 范围 |
| `WHERE a=1 ORDER BY b` | 索引天然有序，**免排序** ✅ |

**不能用的**（❌）：

| 查询条件 | 结果 |
|---|---|
| `WHERE b=2` | 无 a，无法定位 → 全表 |
| `WHERE b=2 AND c=3` | 同上 |
| `WHERE a=1 AND b>2 AND c=3` | c 用不上（范围后的列无序）|
| `WHERE a=1 ORDER BY c` | 需 filesort |

**关键理解**：`WHERE a=1 AND c=3` 中，**c 并不是完全没用**——它仍然参与 **ICP 过滤**，只是不能用于**缩小扫描范围**。

## 二、索引下推 ICP（Index Condition Pushdown，5.6+）⭐

**没有 ICP 时**：

```
存储引擎：用 (a=1) 从索引取主键 → 回表拿整行 → 交给 Server 层
Server 层：用 c=3 过滤
```

问题：**即使 c=3 不满足，也已经白回表了**。

**有 ICP 时**：

```
存储引擎：用 (a=1) 取索引项 → 直接在索引上判断 c=3
           c 不满足 → 不回表，直接跳过 ✅
           c 满足 → 才回表
```

**收益**：**大幅减少回表次数**。`Extra` 里显示 `Using index condition`。

**适用条件**：`type` 为 `range` / `ref` / `eq_ref` / `ref_or_null`，且条件能用索引中的列判断。

**注意**：ICP 是 **5.6** 引入；**索引条件下推不等于覆盖索引**（覆盖索引是根本不用回表，ICP 是少回表）。

## 三、联合索引的列顺序怎么排 ⭐

**核心原则：把"能用于等值定位"的列放前面，"范围/排序"的列放后面。**

```
① 等值查询的列 → 放最前
② 区分度高（选择性好）的列 → 优先放前
③ 需要 ORDER BY 的列 → 紧随等值列之后（利用索引有序性免排序）
④ 范围查询的列 → 尽量放最后
⑤ 高频查询要覆盖的列 → 作为"覆盖列"挂在最后
```

**例子**：

```sql
-- 常见查询：
-- A: WHERE user_id=? AND status=? ORDER BY create_time DESC
-- B: WHERE user_id=? AND create_time > ?
-- 索引设计：
CREATE INDEX idx ON orders (user_id, status, create_time);
--                         等值      等值     排序     ← 完美匹配 A，也能用 B 的前两列
```

**反例**：`(create_time, user_id, status)` —— A 和 B 都无法有效利用。

## 四、前缀索引（Prefix Index）⭐

**场景**：长字符串列（varchar(255)、URL、邮箱）建整列索引太占空间，可只索引前缀：

```sql
ALTER TABLE users ADD INDEX idx_email (email(10));
-- 注意：前缀索引 无法用于 ORDER BY，也无法做覆盖索引
```

**如何选长度**：目标是**前缀的选择性接近整列的选择性**。

```sql
SELECT
  COUNT(DISTINCT LEFT(email, 4)) / COUNT(*) AS sel4,
  COUNT(DISTINCT LEFT(email, 6)) / COUNT(*) AS sel6,
  COUNT(DISTINCT LEFT(email, 8)) / COUNT(*) AS sel8,
  COUNT(DISTINCT email)          / COUNT(*) AS sel_full
FROM users;
```

选**第一个使 `selN` 接近 `sel_full`（比如达到 90% 以上）的 N**。比如 sel6=0.98、sel_full=0.99 → 用 `(email(6))` 性价比最高。

**其他技巧**：
- **倒序存储 + 前缀索引**：解决"后缀区分度高"的场景（如身份证后面的随机码、文件名扩展名）。
- **CRC32/hash 列 + 索引**：把长字符串哈希成 4 字节整数再建索引（`WHERE email_hash = CRC32('...') AND email = '...'` 防哈希冲突）⭐
- 8.0 的 **函数索引**：`CREATE INDEX idx ON t ((SUBSTRING(email,1,6)))` 更直观。

## 五、覆盖索引与联合索引的组合应用 ⭐

```sql
-- 高频查询
SELECT order_no, amount FROM orders WHERE user_id=? AND status=? ORDER BY create_time DESC LIMIT 20;

-- 一个索引同时解决：定位 + 排序 + 覆盖
CREATE INDEX idx_cover ON orders (user_id, status, create_time, order_no, amount);
--                            ↑定位   ↑定位    ↑排序        ↑覆盖列（仅取值，不参与定位）

-- EXPLAIN → Extra: Using index（不回表），且无 Using filesort ✅
```

**代价**：覆盖列越多，索引越大，写放大越重。**只为最高频的查询专门建覆盖索引**。

## 六、一句话总结

**最左前缀决定了"能用索引缩小多少范围"，ICP 决定了"能少回表多少次"，覆盖索引决定了"能不能完全不回表"。** 三者叠加是索引优化的完整链路。""",
    ),
    (
        "MySQL",
        "binlog,主从复制,主从延迟",
        2,
        r"""MySQL 主从复制的原理是什么？主从延迟怎么产生、怎么解决？""",
        r"""## 一、复制的基本原理（三个线程）⭐

```
        Master                              Slave
  ┌────────────────┐                 ┌─────────────────────────┐
  │  ① dump 线程    │ ──binlog──────► │  ② IO 线程               │
  │  读 binlog 推给从库 │               │  拉取并写入 relay log     │
  └────────────────┘                 │            ↓             │
                                     │  ③ SQL 线程              │
                                     │  重放 relay log          │
                                     └─────────────────────────┘
```

| 线程 | 位置 | 职责 |
|---|---|---|
| **dump 线程** | Master | 每个从库连接启一个，读 binlog 并推送 |
| **IO 线程** | Slave | 连 Master 拉 binlog，写入本地 **relay log**，更新 `master.info` |
| **SQL 线程** | Slave | 读 relay log，在从库**重放**，更新 `relay-log.info` |

**关键点**：**拉取（IO）与重放（SQL）是异步分离的** → 这就是延迟的来源。

## 二、binlog 三种格式 ⭐

| 格式 | 记录内容 | 优点 | 缺点 |
|---|---|---|---|
| **STATEMENT** | 原始 SQL 语句 | 日志小 | **非确定性函数**（`NOW()`、`UUID()`、`RAND()`）会导致主从不一致；锁和自增可能不同 |
| **ROW** ⭐ | 每行**前后镜像** | **精确一致**，最安全 | 日志大（一条 `UPDATE` 影响 10 万行 → 10 万条记录）；DDL 仍记语句 |
| **MIXED** | 自动切换 | 折中 | 仍有隐患 |

**生产推荐 ROW**（`binlog_format=ROW`），配合 `binlog_row_image=MINIMAL` 可减小日志量。

## 三、复制方式

| 方式 | 说明 | 一致性 | 性能 |
|---|---|---|---|
| **异步复制**（默认）| Master 提交后**立即返回**，不等 Slave | ⚠️ 故障可能丢数据 | 最高 |
| **半同步复制** | Master 等**至少 N 个 Slave 确认收到**（不要求重放完）再返回 | 好 | 中等 |
| **组复制 MGR** | 基于 Paxos，多数派确认 | 强 | 较低 |

```sql
-- 半同步
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';
SET GLOBAL rpl_semi_sync_master_enabled = 1;
-- 超时后退化为异步：rpl_semi_sync_master_timeout（默认 10000ms）
```

## 四、主从延迟的原因 ⭐

| 原因 | 说明 |
|---|---|
| **① 从库压力大** | 从库上还有一堆查询/统计任务，SQL 线程抢不到资源 |
| **② 大事务** | 一个 `UPDATE` 影响百万行 → 主库执行 10s，binlog 传过去从库要重放更久 |
| **③ 大表 DDL** | 从库串行执行 DDL，阻塞后续所有重放 ⭐ |
| **④ 并行复制不足** | 5.7 前 SQL 线程单线程重放（**最大瓶颈**）|
| **⑤ 网络延迟** | 跨机房/跨国 |
| **⑥ 主库写入高峰** | 瞬时写入远超从库重放能力 |
| **⑦ 无主键/唯一键** | ROW 格式下 `UPDATE` 需要扫全表定位行，重放极慢 ⭐ |

**查看延迟**：

```sql
SHOW SLAVE STATUS\G
--   Seconds_Behind_Master: 5        ← 官方指标，但为 0 不代表真同步（IO 线程断了它也是 NULL/0）
--   Slave_IO_Running / Slave_SQL_Running: Yes/Yes
--   Retrieved_Gtid_Set vs Executed_Gtid_Set   ← 更准确（GTID 模式）⭐
--   Master_Log_File / Read_Master_Log_Pos vs Relay_Log_File / Exec_Master_Log_Pos
```

**更可靠的判断**：`SELECT @@gtid_executed` 与主库比较；或用 **pt-heartbeat**（Percona 工具，注入心跳表，精度到毫秒）⭐

## 五、解决方案 ⭐

| 方向 | 措施 |
|---|---|
| **减少 binlog 量** | 大事务拆小（批量插入每批 500~1000）；避免无主键表更新 |
| **并行复制** | 5.7+ `slave_parallel_workers=8` + `slave_parallel_type=LOGICAL_CLOCK`（按组提交并行）⭐ |
| **8.0 更强并行** | `binlog_transaction_dependency_tracking=WRITESET`，按**行级冲突**判断可并行，效果显著 |
| **提升从库性能** | 从库配置不低于主库；关闭从库 `binlog`（若从库不需要再级联）、`sync_binlog=0`、`innodb_flush_log_at_trx_commit=2` 可提速（**代价：从库崩溃后重放慢**）|
| **读写分离的兜底** | **写后立即读走主库**（同一用户的会话粘性）⭐ 最简单有效 |
| **半同步/组复制** | 对一致性要求高的场景 |
| **MTS + 组提交** | 确保主库开启组提交（`binlog_group_commit_sync_delay`）才能让从库并行的粒度更大 |

**架构层面**：
- **MHA / Orchestrator**：主库故障自动切换。
- **ProxySQL / MySQL Router**：读写分离路由 + 延迟感知（延迟超阈值自动把读切回主库）⭐

## 六、主从一致性校验

```bash
# Percona Toolkit
pt-table-checksum --host=master --databases=blogdb     # 主库计算校验和（会在从库重放）
pt-table-sync --replicate=percona.checksums ...        # 修复差异
```

**注意**：`pt-table-checksum` 会在主库产生 binlog，所以要**在主库上跑**（不能直接在从库跑）。

## 七、一句话总结

**复制 = dump 推日志 + IO 拉日志 + SQL 重放，异步的本质决定了必然有延迟**；大事务、单线程重放、从库资源争抢是三大主因；**拆小事务 + 并行复制 + 写后读主**是最实用的三招。""",
    ),
    (
        "MySQL",
        "分页优化,count,大表DDL",
        3,
        r"""`LIMIT 1000000, 20` 为什么慢？怎样优化？大表加索引/改字段（DDL）为什么危险，有哪些方案？""",
        r"""## 一、深分页为什么慢 ⭐

```sql
SELECT * FROM orders ORDER BY id LIMIT 1000000, 20;
```

**执行过程**：MySQL 必须**先读出前 1000020 行**（而且每行都要回表拿 `*`），然后**丢弃前 1000000 行**，只留 20 行。

- 代价 ≈ **全表扫描 100 万行 + 100 万次回表**。
- 越往后越慢（O(offset)）。

### 优化方案

**① 游标 / 键集分页（Keyset Pagination）—— 首选** ⭐

```sql
-- 用上一页最后一条的 id 作为锚点，只扫 20 行
SELECT * FROM orders WHERE id > 1000000 ORDER BY id LIMIT 20;
```

要求：**排序字段唯一且有索引**（多列时用 `(a,b)` 复合游标）。深分页性能从 O(n) 变成 O(1)，是**最优解**。

**② 延迟关联（Deferred Join）—— 保留 OFFSET 语义时的解法** ⭐

```sql
-- 先用覆盖索引只拿主键（不回表），再回表
SELECT o.* FROM orders o
JOIN (SELECT id FROM orders ORDER BY id LIMIT 1000000, 20) AS t
  ON o.id = t.id;
```

原理：子查询里 `id` 是主键，**命中覆盖索引，不回表**（只有 20 次回表）。如果 `ORDER BY` 的列上有索引，优化器会直接顺序扫描索引，无需读主键页。

**③ 业务上限制翻页深度**

搜索引擎式的**无限滚动**天然适配键集分页；如果用户确实要"跳到第 5 万页"，那通常是产品需求本身有问题。

**④ 记录总数与页码映射**

```sql
-- 预计算，避免每页都 COUNT(*) 全表
-- 或用近似值：EXPLAIN SELECT * FROM t  里的 rows
```

## 二、`COUNT(*)` 为什么慢，怎么优化 ⭐

**InnoDB 没有像 MyISAM 那样保存行数**（因为 MVCC 下每行是否可见依赖 Read View，"总数"不是固定值）。

| 写法 | 说明 |
|---|---|
| `COUNT(*)` | **最优**：优化器专门优化过，选最小的索引树遍历 |
| `COUNT(1)` | 与 `COUNT(*)` 基本等价（8.0 完全等价）|
| `COUNT(col)` | **更慢**：要判断 `col IS NOT NULL`，不统计 NULL 行 |
| `COUNT(主键)` | 与 `COUNT(*)` 差不多 |

**优化方案**：

| 方案 | 说明 |
|---|---|
| **加二级索引** | `COUNT(*)` 会选**最小的二级索引**遍历（比聚簇索引小得多）→ 快数倍 ⭐ |
| **缓存近似值** | Redis 计数器（增删时同步维护），接受少量误差 |
| **`SHOW TABLE STATUS` 的 `Rows`** | 近似值，`InnoDB` 采样估算（误差可达 40%）|
| **汇总表** | 定时任务统计写入中间表 |
| **业务分页改无限滚动** | 从根上不需要总数 |
| **`EXPLAIN` 估算法** | `EXPLAIN SELECT COUNT(*) ...` 的 `rows` 做粗略参考 |

## 三、大表 DDL 为什么危险 ⭐

**MySQL 5.5 及之前**：几乎**所有 DDL 都需重建表**（copy 算法）：
1. 建临时表（新结构）
2. **逐行**从原表拷到临时表 → **持锁 + 占满 IO + 表空间翻倍**
3. 改名替换

1000 万行的表加个字段可能**锁表几十分钟**，期间业务停摆。

**MySQL 5.6+ 的 Online DDL**：

```sql
ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INPLACE, LOCK=NONE;
--                                          ↑ 不拷贝表    ↑ 不阻塞读写
```

| 操作 | ALGORITHM | LOCK | 说明 |
|---|---|---|---|
| 加/删**二级索引** | INPLACE | NONE | **不阻塞读写** ✅ |
| 加列（末尾）| INPLACE | NONE | 8.0 支持 instant |
| **改列类型 / 加主键** | COPY | SHARED | ⚠️ 需拷贝表 |
| 改字符集 | COPY | SHARED | ⚠️ 很慢（本项目迁移时踩过）|
| 加全文索引 / 空间索引 | INPLACE | SHARED | 阻塞写 |
| `OPTIMIZE TABLE` | INPLACE | NONE | 重建表（回收碎片）|

**8.0 的 INSTANT ADD COLUMN** ⭐：

```sql
ALTER TABLE t ADD COLUMN c INT, ALGORITHM=INSTANT;
-- 只改元数据，秒级完成，即使 1 亿行也瞬间完成
```

限制：新列必须在末尾（8.0.29 起支持任意位置）；不支持 `AUTO_INCREMENT`、不支持加索引。

**8.0.12+ 也支持 INSTANT 改列顺序、改默认值、重命名列。**

## 四、无 Online DDL 或需更稳时的方案 ⭐

| 工具 | 原理 | 特点 |
|---|---|---|
| **pt-online-schema-change**（Percona）| 建**影子表**（新结构）+ **触发器**同步增量 → 拷数据 → 原子 `RENAME` | 成熟稳定；要求表有主键；触发器有性能开销 |
| **gh-ost**（GitHub）⭐ | 建影子表，**从库 binlog 模拟写入**（解耦主库）| **无触发器**，可随时暂停/限速；要求 ROW binlog |
| **MySQL 8.0 Clone Plugin** | 物理克隆 | 适合整实例迁移 |

**pt-osc 原理详解**：

```
1. CREATE TABLE _t_new LIKE t;  ALTER _t_new ...（新结构）
2. 在 t 上建三个触发器：INSERT / UPDATE / DELETE → 同步到 _t_new
3. 分批（chunk）把 t 的老数据拷入 _t_new
4. RENAME TABLE t TO _t_old, _t_new TO t;   ← 原子替换（毫秒级）
5. 删触发器和 _t_old
```

**使用建议**：

```bash
pt-online-schema-change \
  --alter "ADD COLUMN c INT" \
  --critical-load Threads_running=100 \
  --max-load Threads_running=50 \
  --chunk-time 0.5 \
  D=blogdb,t=orders --execute
```

- `--max-load`：超过阈值**自动暂停**，保护线上 ⭐
- `--chunk-time`：控制每批耗时，避免长事务
- **务必先在从库演练**，并留足磁盘（影子表 + 原表并存）

## 五、其他大表操作注意事项

| 操作 | 风险 | 建议 |
|---|---|---|
| `DELETE` 大量数据 | 长事务、undo 膨胀、主从延迟 | **分批删除** `LIMIT 1000` 循环 ⭐ |
| `TRUNCATE` | 速度快但不能回滚 | 用 `DROP + CREATE` 或 `TRUNCATE`（DDL，隐式提交）|
| `OPTIMIZE TABLE` | 重建表，占双倍空间 | 低峰期做，或用 pt-osc |
| 改 `sql_mode` | 可能让老数据插入失败 | 先在从库验证 |

**分批删除模板**：

```sql
-- 循环执行直到 affected rows = 0
DELETE FROM big_table WHERE create_time < '2023-01-01' ORDER BY id LIMIT 1000;
-- 每批之间 sleep 100ms，让从库追上
```

**一句话总结**：**深分页的关键是"别扫前面的行"（键集分页 > 延迟关联）；`COUNT(*)` 的关键是"扫最小的索引树"；大表 DDL 的关键是"绝不原地拷贝，用 INSTANT 或影子表"。**""",
    ),
    (
        "MySQL",
        "字符集,utf8mb4,collation",
        3,
        r"""`utf8` 和 `utf8mb4` 有什么区别？字符集不一致会带来什么问题？（结合线上实战）""",
        r"""## 一、utf8 vs utf8mb4 ⭐

| | `utf8`（别名 `utf8mb3`）| `utf8mb4` |
|---|---|---|
| 最大字节数 | **3 字节** | **4 字节** |
| 能表示 | BMP（基本多文种平面）：拉丁、希腊、**中日韩基本区** | 全部 Unicode（U+0000~U+10FFFF）|
| **Emoji** | ❌ **存不进去**（报 `Incorrect string value`）| ✅ 可以 |
| 生僻汉字（扩展 B 区+）| ❌ | ✅ |
| 最大 char 长度 | 索引列前缀上限 **767 字节**（旧规则）| 上限 **3072 字节**（`innodb_large_prefix`）|

**结论：现在一律用 `utf8mb4`。** MySQL 8.0 中 `utf8` 已被标记为 deprecated（`utf8mb3`），未来可能移除。

**为什么 MySQL 当年搞出个 "utf8 不是真 UTF-8"**：历史原因——早期为省空间只支持 3 字节。所以**"MySQL 的 utf8 ≠ 标准 UTF-8"** 是踩坑最多的地方。

## 二、排序规则 collation ⭐

```sql
-- 查看
SHOW VARIABLES LIKE 'character_set%';
SHOW VARIABLES LIKE 'collation%';
SHOW CREATE TABLE t;

-- 字符集与排序规则一一对应
utf8mb4_general_ci       -- 通用，比较快，但排序不严格（不区分语言规范）
utf8mb4_unicode_ci       -- 按 Unicode 规范排序，更准确
utf8mb4_unicode_520_ci   -- 按 Unicode 5.2 规范
utf8mb4_0900_ai_ci       -- 8.0 默认，基于 Unicode 9.0，最快且准确 ⭐
utf8mb4_bin              -- 二进制比较，区分大小写与重音
utf8mb4_zh_0900_as_cs    -- 中文拼音排序，区分大小写
```

**后缀含义**：

| 后缀 | 含义 |
|---|---|
| `_ci` | case insensitive，**不区分大小写** |
| `_cs` | case sensitive，区分大小写 |
| `_ai` | accent insensitive，不区分重音（`é` = `e`）|
| `_as` | accent sensitive |
| `_bin` | 按字节比较 |

**影响**：`WHERE name = 'Tom'` 在 `_ci` 下**能匹配到 `tom`**；在 `_bin` 下不能。**`utf8mb4_0900_ai_ci` 下 `'a' = 'á'`，做用户名唯一性校验时会踩坑**（要用 `_bin` 或 `_as_cs`）。

## 三、字符集不一致带来的问题 ⭐

### 问题 1：隐式转换导致索引失效

如果**表字符集是 utf8mb4，但连接字符集是 utf8**：

```sql
WHERE utf8_col = '中文'   -- 会做 COLLATE 转换，索引可能失效
```

**JOIN 两表字符集不同** → 无法用索引，退化为全表/嵌套循环：

```sql
-- utf8mb4 表 JOIN utf8 表 → ON 条件上要做 COLLATE 转换
SELECT * FROM a JOIN b ON a.name = b.name;   -- 索引失效 ❌
```

### 问题 2：写入报错或截断

```
ERROR 1366 (HY000): Incorrect string value: '\xF0\x9F\x98\x80' for column 'content'
```

存 Emoji 到 `utf8` 列必然失败。

### 问题 3：多字节字符按 utf8 连接写入后"变成 ? 或乱码"⭐（**本项目实战踩过**）

**这是最关键的一类**，在真实项目里排查了一整轮：

**现象**：整站中文正常，**只有某个表（questions）的中文全变 `?`**。

**根因链**（三环叠加）：

```
① 老表的历史数据是「应用用 latin1 连接写入的」：
   MySQL 把应用发来的 UTF-8 字节序列 **当成 latin1 字符** 再转存入 utf8mb4 列
   ⇒ 表里实际存的是「UTF-8 字节的 cp1252 转义」（字节一个没丢，只是被"重新解释"了）

② 应用连接恰好是 latin1（MYSQL_SET_CHARSET_NAME 在该环境未生效）
   ⇒ 读老表：cp1252 转义 → 转回 latin1 → 原始字节 → **显示完全正常**
      （整站靠这个"巧合"在工作！）

③ questions 表的数据是 mysql 客户端以 utf8mb4 导入的 ⇒ 存的是**真中文**
   ⇒ 用 latin1 连接读真中文 → latin1 表示不了 → **逐字符变 `?`**
```

**决定性证据（都是非视觉证据）**：

```bash
# 同一列，在两种 client 字符集下读出来完全不同
$ mysql --default-character-set=utf8mb4 -e "SELECT question FROM questions WHERE id=1;"
  std::shared_ptr åŠŸèƒ½æµ‹è¯•            ← 真中文被当成 latin1 转义显示

$ mysql --default-character-set=latin1  -e "SELECT question FROM questions WHERE id=1;"
  std::shared_ptr 功能测试                  ← ✅ 真中文

$ mysql --default-character-set=latin1  -e "SELECT question FROM questions WHERE id=1;"
  std::shared_ptr ?????????????????       ← 与应用 API 输出**逐字节一致**
```

⇒ 三方对照直接锁死：**app 的连接字符集是 latin1**。

**判据（区分"MySQL 转换"还是"程序按字节处理"）** ⭐：**看字符数比例**
- **1 个汉字 → 1 个 `?`** ⇒ **MySQL 字符集转换**（按字符处理，一个字符替换成一个 `?`）
- **1 个汉字 → 3 个 `?`** ⇒ **程序按字节处理**（UTF-8 汉字 3 字节，逐字节替换）

### 问题 4：`ALTER TABLE ... CONVERT TO CHARACTER SET` 会二次编码 ⭐

**这是最容易踩的陷阱**。很多人以为 `CONVERT TO` 是"换个解释方式"，其实它是**重新编码**：

```sql
-- ❌ 危险！会把已经是 utf8mb4 列里的 cp1252 转义数据再编码一次
ALTER TABLE t CONVERT TO CHARACTER SET utf8mb4;
-- 结果：åŠŸèƒ½ 这类"长得几乎一样、极难分辨"的新乱码
```

**正确的迁移姿势**（把 cp1252 转义还原成真中文）：

```sql
-- ✅ 三步法：换解释方式，而不是重新编码
UPDATE t SET col = CONVERT(CAST(CONVERT(col USING latin1) AS BINARY) USING utf8mb4)
WHERE col <> CONVERT(CAST(CONVERT(col USING latin1) AS BINARY) USING utf8mb4);
--                ↑ 用 latin1 解释 → 拿到原始字节 → 按 utf8mb4 重新解释
```

用幂等的 `WHERE` 守卫判断"只处理 latin1 可表示的值"，避免重复执行时二次损坏。

## 四、正确的统一姿势 ⭐

```sql
-- 1. 服务端配置（my.cnf）
[mysqld]
character-set-server = utf8mb4
collation-server     = utf8mb4_0900_ai_ci      -- 8.0

[client]
default-character-set = utf8mb4

-- 2. 建库/建表显式指定
CREATE DATABASE blogdb CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE TABLE t (...) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 3. 连接层（三处必须一致）⭐
--    a. 应用连接字符串：?charset=utf8mb4（或用 mysql_set_character_set / MYSQL_SET_CHARSET_NAME）
--    b. 客户端：--default-character-set=utf8mb4
--    c. 服务端：character_set_server=utf8mb4
```

**验证连接字符集**（唯一可靠方式）：

```sql
SHOW VARIABLES LIKE 'character_set_client';
SHOW VARIABLES LIKE 'character_set_connection';
SHOW VARIABLES LIKE 'character_set_results';
-- 这三个才是"连接层"字符集（对应 app 连接的三个变量）
```

```bash
# C API 侧确认（本项目相关）
mysql_options(conn, MYSQL_SET_CHARSET_NAME, "utf8mb4");
# 注意：某些环境下该选项未生效，需用 mysql_query(conn, "SET NAMES utf8mb4") 兜底
```

## 五、迁移的正确顺序（血泪教训）⭐

```
❌ 错误顺序：先部署新二进制 → 整站中文立刻变乱码（因为老数据是 cp1252 转义）
✅ 正确顺序：
   ① 备份（mysqldump 或物理备份）
   ② 用 HEX() 记录迁移前关键列的字节值
   ③ 迁移数据（CONVERT 三步法，幂等）
   ④ 用 HEX() 验证：迁移前后**字节值必须完全一致** ⭐
   ⑤ 再部署新二进制（连接切到 utf8mb4）
   ⑥ 回归验证
```

**关键洞察**：`HEX()` 是唯一不会骗你的验证手段。乱码在视觉上可能"看起来差不多"，但**字节值不会说谎**。

## 六、一句话总结

**utf8mb4 是唯一正确选择；字符集问题分三层（客户端/连接/服务端），必须三者一致；迁移时"换解释方式"≠"重新编码"，用 `CONVERT(... USING latin1)` + `CAST AS BINARY` 而不是 `ALTER ... CONVERT TO`；验证只信 `HEX()`。**""",
    ),
    (
        "MySQL",
        "事务,隔离级别,锁",
        2,
        r"""事务的 ACID 是怎么实现的？四种隔离级别分别解决什么问题？""",
        r"""## 一、ACID 与实现机制 ⭐

| 特性 | 含义 | **靠什么实现** |
|---|---|---|
| **A**tomicity 原子性 | 事务内操作要么全成功要么全失败 | **undo log**（回滚日志）⭐ |
| **C**onsistency 一致性 | 数据从一个合法状态到另一个合法状态 | 由 **A + I + D** 共同保证（+ 业务约束）|
| **I**solation 隔离性 | 并发事务互不干扰 | **锁 + MVCC** ⭐ |
| **D**urability 持久性 | 提交后永久生效 | **redo log**（+ 双写缓冲）⭐ |

**记忆**：**A 靠 undo，I 靠锁+MVCC，D 靠 redo，C 是目标不是手段。**

## 二、四种隔离级别 ⭐

| 级别 | 脏读 | 不可重复读 | 幻读 | 说明 |
|---|---|---|---|---|
| **READ UNCOMMITTED** | ✅ 会 | ✅ 会 | ✅ 会 | 能读到别人**未提交**的数据 |
| **READ COMMITTED** | ❌ 不会 | ✅ 会 | ✅ 会 | 只读已提交（Oracle/PG 默认）|
| **REPEATABLE READ** ⭐ | ❌ | ❌ | ❌（InnoDB 基本解决）| **MySQL 默认** |
| **SERIALIZABLE** | ❌ | ❌ | ❌ | 全部加锁，串行执行 |

### 三个读问题的定义

| 问题 | 现象 | 例子 |
|---|---|---|
| **脏读** | 读到**未提交**的数据，对方回滚后数据"凭空消失" | A 改钱未提交，B 读到新值，A 回滚 → B 读的是"幽灵值" |
| **不可重复读** | 同一事务内**两次读同一行结果不同**（别人 UPDATE 并提交）| A 第一次读余额 100，B 改成 200 提交，A 再读是 200 |
| **幻读** | 同一事务内**两次范围查询行数不同**（别人 INSERT 并提交）| A 查"年龄>20 共 5 人"，B 插入 1 人提交，A 再查变 6 人 |

**关键区别**：不可重复读针对**同一行被修改**；幻读针对**结果集行数变化（新增/删除）**。

### InnoDB 的 RR 如何做到"基本解决幻读" ⭐

**双保险**：

| 读类型 | 机制 | 作用 |
|---|---|---|
| **快照读**（普通 SELECT）| **MVCC**：事务首次读时建 Read View，全程复用 | 看不到别人新插入的行 → 无幻读 |
| **当前读**（`FOR UPDATE` / `UPDATE` / `DELETE`）| **Next-Key Lock**（临键锁）| 锁住间隙，**阻止别人插入** → 无幻读 |

**注意"基本"**：如果事务里**先快照读、再当前读**，可能出现"快照读没看到某行，当前读却看到了"的错觉。这是标准的**幻读边界**，但不会破坏数据一致性。

## 三、查看与设置隔离级别 ⭐

```sql
-- 查看
SELECT @@transaction_isolation;          -- 8.0
SELECT @@tx_isolation;                   -- 5.7

-- 设置
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;   -- 当前会话
SET GLOBAL  TRANSACTION ISOLATION LEVEL READ COMMITTED;   -- 全局（新连接生效）

-- my.cnf
[mysqld]
transaction-isolation = READ-COMMITTED
```

**生产实务**：不少互联网公司在 **RC + binlog ROW**，理由：
1. RC **没有间隙锁** → 死锁概率大幅降低 ⭐
2. RC 下 Read View 每次重建 → undo 版本链更短 → **长事务危害更小**
3. ROW 格式保证主从一致

前提：**应用层自己处理"不可重复读"**（不要把"同一事务内两次读一致"作为假设）。

## 四、隔离级别与锁的关系

| 级别 | 快照读 | 当前读 |
|---|---|---|
| RU | 直接读最新（无 MVCC 保护）| 加锁 |
| RC | 每次重建 Read View | Record Lock（**无间隙锁**）⭐ |
| RR | 首次读建一次 Read View | **Next-Key Lock**（防幻读）|
| SERIALIZABLE | 快照读也加 S 锁 | 加锁，读也阻塞写 |

**重要**：`innodb_locks_unsafe_for_binlog`（已废弃）曾是 RC 下"不加间隙锁"的开关；现在是隔离级别本身决定。

## 五、事务的写法建议 ⭐

```sql
-- ✅ 好的事务
BEGIN;
-- 1. 尽快拿到需要的锁，改完立即提交
UPDATE account SET balance = balance - 100 WHERE id = 1;
UPDATE account SET balance = balance + 100 WHERE id = 2;
COMMIT;    -- 事务里没有：网络调用、文件 IO、慢查询、等待用户输入

-- ❌ 坏的事务
BEGIN;
SELECT * FROM t WHERE id=1 FOR UPDATE;  -- 拿锁
-- ... 调用第三方支付接口（可能超时 30s）...  ← 锁被持有 30s
UPDATE t SET ...;
COMMIT;
```

**核心原则**：
1. **事务要短** —— 不要在事务里做 IO/网络。
2. **访问顺序一致** —— 防死锁。
3. **能不用事务就不用** —— 单条 SQL 本身就是事务。
4. **`autocommit` 建议开**（默认 1），显式 `BEGIN` 才开事务。
5. **异常必回滚** —— 用 `try/catch/finally` 或 RAII（C++ 里做个 `TransactionGuard`）⭐

**C++ 侧的 RAII 事务守卫**（本项目 Crow 场景适用）：

```cpp
class TransactionGuard {
    MYSQL* c_;
    bool committed_ = false;
public:
    explicit TransactionGuard(MYSQL* c) : c_(c) { mysql_query(c_, "START TRANSACTION"); }
    ~TransactionGuard() {
        if (!committed_) mysql_query(c_, "ROLLBACK");   // 异常/提前 return 也回滚
    }
    void commit() { mysql_query(c_, "COMMIT"); committed_ = true; }
};
```

## 六、一句话总结

**ACID 的实现 = undo（A）+ 锁&MVCC（I）+ redo（D）；隔离级别的本质是"允许你用多大代价换取多强的隔离"；InnoDB 的 RR 靠 MVCC + Next-Key Lock 双保险解决幻读。**""",
    ),
    (
        "MySQL",
        "自增主键,分库分表,读写分离",
        3,
        r"""为什么不推荐用 UUID 做主键？分库分表有哪些方案？分片键怎么选？""",
        r"""## 一、为什么不用 UUID 做主键 ⭐

| 问题 | 说明 |
|---|---|
| **① 写性能差（页分裂）** ⭐ | UUID 随机 → 新行**插入到 B+ 树中间** → 目标页已满就要**页分裂**（复制一半数据到新页、更新父节点）→ 大量随机 IO + 写放大 |
| **② 空间大** | `CHAR(36)` = 36 字节；即便存成 `BINARY(16)` 也 16 字节，而 `BIGINT` 只 **8 字节** → **非叶子节点能放的键少一半** → 树更高 |
| **③ 二级索引更胖** ⭐ | 二级索引叶子存"索引列 + **主键**"，主键越大，**每个二级索引都跟着膨胀** |
| **④ Buffer Pool 命中率低** | 随机访问导致热数据不集中 |
| **⑤ 无顺序性** | 无法用主键做范围分页、时间排序 |

**自增主键的优势**：顺序插入 → **只在最后一页追加**（几乎无页分裂）；8 字节小；二级索引紧凑；有天然顺序。

**如果非要全局唯一 ID，用雪花算法（Snowflake）** ⭐：

```
| 1 bit 符号 | 41 bit 时间戳 | 10 bit 机器 ID | 12 bit 序列号 |
= 64 bit 的 Long，趋势递增（时间在最高位）→ 兼顾唯一性与顺序性
```

- 趋势递增 → 页分裂大幅减少 ✅
- 本地生成，无中心依赖 ✅
- 需处理**时钟回拨**（回拨时等待或拒绝）
- 其他方案：**号段模式**（美团 Leaf）、**Redis INCR**、**MySQL 自增表**

## 二、什么时候真的需要分库分表 ⭐

**判断顺序（不要跳步）**：

```
① SQL 和索引优化好了吗？       ← 90% 的性能问题在这
② 加缓存（Redis）了吗？         ← 挡住绝大多数读
③ 读写分离了吗？               ← 读扩展
④ 硬件升级（SSD/内存）了吗？    ← 性价比常高于分片
⑤ 单表 > 500万~2000万行 / 单库 > 2TB / QPS 到瓶颈
        ↓
     才考虑分库分表
```

**分片带来的复杂度**：跨库 JOIN、分布式事务、全局唯一 ID、跨库分页排序、扩容迁移、运维成本。**能不分就不分。**

## 三、分片维度 ⭐

| 维度 | 说明 | 优点 | 缺点 |
|---|---|---|---|
| **垂直分库** | 按**业务**拆（用户库/订单库/商品库）| 业务解耦，职责清晰；不同库可独立扩展 | 跨库 JOIN 没了，需服务层组装 |
| **垂直分表** | 按**列**拆（常用列/大字段分开）| 单行变小 → 一页放更多行，IO 效率高 | 需要额外查询 |
| **水平分表** | 同一张表按行拆到多个表 | 单表变小 | 跨表查询/聚合 |
| **水平分库** | 拆到不同数据库实例 | 突破单机瓶颈 | 分布式事务 |

**实务组合**：**先垂直分库（业务解耦），必要时再水平分片（同类业务的数据量）**。

## 四、分片算法 ⭐

| 算法 | 说明 | 优点 | 缺点 |
|---|---|---|---|
| **范围分片** | `id % 0~1000 → 库0`，`1001~2000 → 库1` | 扩容简单、范围查询友好 | **热点集中**（新数据都写最后一库）|
| **哈希取模** | `hash(key) % N` | 数据分布均匀 | **扩容要重分布全部数据** ❌ |
| **一致性哈希** | 环 + 虚拟节点 | 扩容只影响相邻节点 | 需维护环、实现复杂 |
| **预分片（倍数扩容）** ⭐ | 一开始就分 2^k 片（如 1024），按 `hash % 1024`；扩容时**只挪整片** | **扩容平滑**，不用重分布 | 需提前规划 |
| **范围 + 哈希** | 先按时间范围，范围内再哈希 | 兼顾时序与均衡 | 需两段路由 |

**推荐：预分片 + 一致性哈希思想**。一次性分成 1024 个逻辑片，物理上先放几个库，扩容时**整片搬迁**（如 4 库 → 8 库，每库挪一半片），只涉及数据复制，不涉及重新哈希。

## 五、分片键（Sharding Key）怎么选 ⭐

**原则**：

| 原则 | 说明 |
|---|---|
| **① 高基数** | 取值足够多，避免数据倾斜（不能用"性别""状态"）|
| **② 分布均匀** | 哈希后各片数据量接近 |
| **③ 查询高频命中** ⭐ | **最重要的原则**：分片键必须是**最高频查询的过滤条件**，否则每次查询都要扫全部分片 |
| **④ 避免跨片** | 分片键相同的关联数据尽量放同一片（如订单和订单明细都按 `user_id` 分）|
| **⑤ 稳定不变** | 分片键一旦确定不能改（改了要迁数据）|

**典型选择**：

| 业务 | 分片键 | 理由 |
|---|---|---|
| 用户中心 | `user_id` | 高频按用户查 |
| 订单 | `user_id`（不用 `order_id`）| 用户查自己的订单，避免跨片 ⭐ |
| 订单（后台运营）| 需**异构索引表**（order_id → user_id 的映射表）解决"按订单号查" ⭐ |
| IM 消息 | `conversation_id` | 会话维度查询 |
| 日志 | `create_time`（范围）| 时序天然范围 |

**跨片问题的解法**：

| 问题 | 方案 |
|---|---|
| 按非分片键查询 | **异构索引表**（额外维护 非分片键 → 分片键 的映射）⭐ |
| 跨片 JOIN | ① 宽表冗余（空间换时间）② 服务层内存 JOIN ③ 数据仓库做离线 |
| 跨片分页/排序 | 各片取 Top N → 归并 → 取全局 Top N（**深度分页仍难**）|
| 全局唯一 ID | 雪花算法 |
| 分布式事务 | 尽量**避免**；必须时用 TCC / Saga / 本地消息表 |

## 六、中间件选型

| 类型 | 代表 | 特点 |
|---|---|---|
| **客户端代理（JDBC Sharding）** | **ShardingSphere-JDBC** | 无网络开销，性能好；语言绑定（Java）|
| **服务端代理（Proxy）** | **ShardingSphere-Proxy**、MyCat、ProxySQL | 语言无关；多一跳网络 |
| **云原生** | TiDB、OceanBase、PolarDB-X | **原生分布式，应用无感** ⭐ 未来趋势 |

**趋势**：越来越多的场景直接用 **NewSQL（TiDB/OceanBase）** 替代"MySQL + 分库分表中间件"，因为**应用代码零改造**、支持分布式事务和跨节点 JOIN。

## 七、扩容（最重要也最难的一步）

| 方案 | 说明 |
|---|---|
| **停机迁移** | 最简单，但业务停摆；小站点可用 |
| **双写 + 迁移** ⭐ | 老库新库双写 → 后台迁移历史数据 → 校验一致 → 切读新库 → 停双写 |
| **binlog 同步（DTS/Canal）** | 老库作为主，新库订阅 binlog 追平 → 校验 → 切换 |
| **预分片整片搬迁** | 只挪整片，最平滑 ⭐ |

**关键**：迁移后必须**校验数据一致性**（`pt-table-checksum` 或自研比对），并保留**回滚方案**。

## 八、一句话总结

**UUID 的问题不是"不唯一"，而是"随机导致页分裂 + 太胖导致索引膨胀"；分片的核心是"选一个高频查询用的分片键"，架构上优先垂直分库，扩张上优先预分片；能用 NewSQL 就别自己写分片中间件。**""",
    ),
    (
        "MySQL",
        "日志,刷盘,双一,性能调优",
        3,
        r"""`innodb_flush_log_at_trx_commit` 和 `sync_binlog` 各自怎么选？还有哪些关键 InnoDB 参数需要调优？""",
        r"""## 一、`innodb_flush_log_at_trx_commit` ⭐

控制**redo log 何时刷盘**（三个值）：

| 值 | 行为 | 丢数据风险 | 性能 |
|---|---|---|---|
| **0** | 每秒把 Log Buffer 刷到 OS cache 并 fsync 一次（**提交时什么都不做**）| 崩溃丢 1s | 最高 |
| **1** ✅ | **每次提交都 fsync 到磁盘** | **不丢**（满足 D）| 最低 |
| **2** | 每次提交写到 **OS cache**（write），每秒 fsync 一次 | **MySQL 进程崩溃不丢**，**OS/机器宕机丢 1s** | 中等 |

**选型**：

```
金融/支付/订单  → 1（必须）
普通业务主库    → 1（默认，安全第一）
从库            → 2 或 0（从库可重放，允许丢，换性能）
日志/埋点/统计  → 2 或 0
```

**注意 `=2` 的语义**：`write()` 只是把数据交给内核页缓存，**机器断电就没了**；只有 `fsync()` 才真正落盘。所以 `=2` 的"安全"只在"MySQL 进程挂掉但 OS 没挂"时成立。

## 二、`sync_binlog` ⭐

| 值 | 行为 | 风险 |
|---|---|---|
| **0** | 由 OS 决定何时刷（不受 MySQL 控制）| 最不安全 |
| **1** ✅ | **每次提交都 fsync binlog** | 最安全，主从不丢 |
| **N（>1）** | 每 N 个事务 fsync 一次 | 崩溃丢最多 N 个事务 |

**"双一" = `innodb_flush_log_at_trx_commit=1` + `sync_binlog=1`** ⭐ —— 这是满足"不丢已提交事务 + 主从一致"的最小配置。

**注意**：`sync_binlog=1` 在 5.6 之前只需 fsync 一次；5.6+ **每次事务要 fsync 两次**（一次写 `binlog cache`，一次写 `binlog file` 的 `XID`），所以性能影响更明显，**组提交**因此更重要。

## 三、其他关键 InnoDB 参数 ⭐

### 内存

| 参数 | 建议 | 说明 |
|---|---|---|
| `innodb_buffer_pool_size` ⭐ | **物理内存的 50%~80%**（专用库）| 最重要的参数，直接决定磁盘 IO 量 |
| `innodb_buffer_pool_instances` | 每实例 1G 左右，建议 8~16 | **减少 latch 竞争** ⭐ 高并发必备 |
| `innodb_log_buffer_size` | 16M~64M | 大事务多则调大 |
| `innodb_sort_buffer_size` | 1M~4M | 排序用 |
| `key_buffer_size` | MyISAM 用，InnoDB 基本不用 | |

### 日志与 IO

| 参数 | 建议 | 说明 |
|---|---|---|
| `innodb_log_file_size` | **1G~2G**（8.0.30+ 用 `innodb_redo_log_capacity`）| 太小 → 频繁 checkpoint（性能抖动）；太大 → 恢复慢 |
| `innodb_log_files_in_group` | 4（默认）| |
| `innodb_io_capacity` | SSD 2000~5000 | 告诉 InnoDB 磁盘能力，影响刷脏速度 ⭐ |
| `innodb_io_capacity_max` | 2× 上一项 | |
| `innodb_flush_method` | Linux 用 **`O_DIRECT`** | **绕开 OS page cache**，避免双重缓存 ⭐ |
| `innodb_flush_neighbors` | SSD 设 **0** | SSD 顺序访问无优势，关掉可减少写放大 ⭐ |
| `innodb_doublewrite` | 保持 ON（除非有掉电保护）| 防页撕裂 |
| `innodb_max_dirty_pages_pct` | 75% 左右 | 脏页上限，超了就加速刷 |
| `innodb_lru_scan_depth` | 1024（SSD 可调大）| 每次刷 LRU 扫描深度 |

### 并发

| 参数 | 建议 | 说明 |
|---|---|---|
| `innodb_thread_concurrency` | 0（不限）或核数×2 | 高并发争抢严重时可限制 |
| `innodb_read_io_threads` / `write_io_threads` | 4~8 | IO 线程数 |
| `innodb_purge_threads` | 4~8 | 清理 undo |
| `innodb_page_cleaners` | = `buffer_pool_instances` | 刷脏线程 |
| `innodb_adaptive_hash_index` | 高并发偶发性能抖动时**尝试关闭** | AHI 的 btr latch 竞争 ⭐ |

### 连接与表

| 参数 | 建议 | 说明 |
|---|---|---|
| `max_connections` | 按内存算（每连接约 200KB~1MB）| 太大反而拖垮，**应该用连接池** |
| `innodb_file_per_table` | **ON** ⭐ | 每表独立 ibd，便于回收空间和单表管理 |
| `innodb_autoinc_lock_mode` | **2**（ROW 格式下）| 交错模式，并发插入不互相阻塞 ⭐ |
| `innodb_lock_wait_timeout` | 10~50 | 锁等待超时 |
| `innodb_print_all_deadlocks` | ON（排查期）| 死锁写 error log |

### 服务器层

| 参数 | 建议 | 说明 |
|---|---|---|
| `table_open_cache` | 2000~4000 | 打开表缓存 |
| `tmp_table_size` / `max_heap_table_size` | 64M~256M | 内存临时表大小，超出落磁盘 ⭐ |
| `sort_buffer_size` / `join_buffer_size` | 2M~8M（**每连接**）| 太大 × 高并发 = 内存爆炸 ⚠️ |
| `thread_cache_size` | 100 左右 | 线程复用 |
| `back_log` | 512~1024 | TCP 连接队列 |
| `慢查询` | `slow_query_log=ON`, `long_query_time=1` | 必开 |

## 四、调优的通用方法论 ⭐

```
① 定位瓶颈：是 CPU、内存、磁盘 IO 还是锁？
   - top / pidstat  → CPU
   - vmstat / iostat -xz → 磁盘 %util、await
   - SHOW ENGINE INNODB STATUS → 语义级问题（锁、等待）
   - performance_schema / sys schema → 精确定位到 SQL

② 优化顺序（性价比从高到低）：
   索引 → SQL → 表结构 → 参数 → 缓存 → 架构（读写分离/分片）

③ 永远先测再说：
   改参数前用 sysbench/mysqlslap 压测，改后再测，对比 QPS/TP99
```

**几句口诀**：
> Buffer Pool 要大，日志文件要够，
> IO 能力要说清（`io_capacity`），`O_DIRECT` 要找对，
> 双一安全优先，从库可以放松，
> 排序 JOIN buffer 是**每连接**的，别贪心。

## 五、性能问题诊断速查

| 现象 | 首查参数/命令 |
|---|---|
| 提交很慢 | `sync_binlog`、`innodb_flush_log_at_trx_commit`、磁盘 IOPS |
| 间歇性卡顿 | `innodb_log_file_size` 太小导致 checkpoint 抖动；AHI 竞争 |
| 磁盘 IO 打满 | `innodb_buffer_pool_size` 太小 → 回表多；`innodb_io_capacity` 设小了 |
| 大量锁等待 | 长事务、缺索引、隔离级别（RR 的间隙锁）|
| 内存涨不停 | `sort_buffer_size`/`join_buffer_size` 太大 × 连接数 |
| 连接数爆了 | `max_connections` + 连接池配置 + 慢查询拖住连接 |

**一句话总结**：**先把 Buffer Pool 开够（收益最大），再保证 `io_capacity` 与 `flush_method` 匹配硬件，安全参数按业务容忍度选（主库双一），最后用 group commit 和并行复制把性能拉回来。**""",
    ),
    (
        "MySQL",
        "存储引擎,MyISAM,InnoDB",
        1,
        r"""MyISAM 和 InnoDB 有什么区别？现在应该怎么选？""",
        r"""## 核心对比 ⭐

| 维度 | **InnoDB** | **MyISAM** | **Memory** |
|---|---|---|---|
| **事务** | ✅ 支持 ACID | ❌ 不支持 | ❌ 不支持 |
| **锁粒度** | **行锁**（+ 间隙锁）| **表锁** | **表锁** |
| **外键** | ✅ 支持 | ❌ | ❌ |
| **崩溃恢复** | ✅ redo log，crash-safe ⭐ | ❌ 需 `myisamchk` 修复 | ❌ 数据全丢 |
| **索引结构** | **聚簇索引（B+ 树）** | **非聚簇索引（B+ 树 + 数据文件）** | 哈希索引 |
| **MVCC** | ✅ | ❌ | ❌ |
| **存储位置** | `.ibd`（数据+索引一起）| `.MYD`（数据）+ `.MYI`（索引）分开 | 内存 |
| **`COUNT(*)`** | ❌ 需扫索引（MVCC）| ✅ **直接读计数变量**，O(1) | ✅ |
| **全文索引** | 5.6+ 支持 | 老版本支持 | ❌ |
| **压缩表** | 支持（COMPRESSED）| 支持 myisampack | ❌ |
| **适用** | **通用，默认选择** | 只读/日志表、老系统 | 临时表/缓存 |

## 关键差异详解

### ① 索引用法不同（最重要）⭐

```
MyISAM（非聚簇）：
  .MYI 索引树：  [索引值 → 行地址(offset)]
  .MYD 数据文件：[行1][行2][行3]...

InnoDB（聚簇）：
  .ibd 索引树：  [主键 → 整行数据]
```

**后果**：
- MyISAM 的**主键索引和二级索引地位相同**，都要通过"行地址"再取一次数据。
- InnoDB **按主键组织数据**，主键查询一次到位；二级索引要"回表"。
- **InnoDB 必须有主键**（没有会用隐藏 `DB_ROW_ID`）。

### ② 崩溃安全 ⭐

- **InnoDB**：有 redo log + 双写缓冲，断电重启自动前滚/回滚，**数据不丢**。
- **MyISAM**：写索引文件时断电可能**索引损坏**，需要 `REPAIR TABLE` / `myisamchk`，且**可能丢数据**。

### ③ `COUNT(*)` 的速度差异（面试常问）

MyISAM 在表头维护了 `state->records` 计数，`SELECT COUNT(*)` **直接返回 O(1)**。
InnoDB 因为 MVCC（每行是否可见取决于 Read View），**无法维护一个准确的计数**，只能扫最小的二级索引树。

### ④ 全表扫描：MyISAM 更快？⭐

**某些场景确实更快**（顺序读 `.MYD`，无 MVCC 成本、无回表概念）。但**代价是没有事务和行锁**，现代 SSD 上这个优势已被 InnoDB 的 buffer pool 抵消。

## 现在怎么选 ⭐

```
默认：InnoDB（8.0 中它是唯一的默认引擎，且 MyISAM 已基本停止演进）
只有这些场景才考虑 MyISAM：
  ① 只读/几乎不写的小字典表（省内存）
  ② 需要 O(1) COUNT(*) 且不在乎事务的统计表
  ③ 历史遗留系统迁移成本太高
```

**8.0 的变化**：InnoDB 是**默认且唯一推荐的**引擎；`MyISAM` 仍然存在但不推荐新用；还有 **Archive**（高压缩只读日志）、**CSV**（数据交换）、**FEDERATED**（跨实例表）、**BLACKHOLE**（复制中继）。

**查看与修改**：

```sql
SHOW ENGINES;
SHOW TABLE STATUS LIKE 't'\G     -- 看 Engine 字段
ALTER TABLE t ENGINE = InnoDB;   -- 改引擎（会重建表，大表危险）⭐
SET default_storage_engine = InnoDB;
```

**一句话总结**：**有 InnoDB 就用 InnoDB**——事务、行锁、MVCC、崩溃恢复这四项是现代应用的硬需求，MyISAM 的全表扫描/`COUNT(*)` 优势不值得用数据安全换。""",
    ),
    (
        "MySQL",
        "行格式,溢出页,表空间",
        3,
        r"""InnoDB 的行格式（ROW_FORMAT）有哪几种？大字段（TEXT/BLOB）是怎么存储的？""",
        r"""## 一、四种行格式 ⭐

| 格式 | 说明 | 状态 |
|---|---|---|
| **COMPACT** | 紧凑格式，5.0 引入 | 5.6 及之前默认 |
| **REDUNDANT** | 冗余格式，兼容老版本 | 遗留 |
| **DYNAMIC** ⭐ | 5.7 默认；**长字段完全放到溢出页** | **推荐** |
| **COMPRESSED** | 基于 DYNAMIC + 页压缩（zlib）| 特殊场景（读多写少、IO 敏感）|

```sql
CREATE TABLE t (...) ROW_FORMAT=DYNAMIC;
ALTER TABLE t ROW_FORMAT=DYNAMIC;
SHOW TABLE STATUS LIKE 't'\G           -- Row_format 字段
SHOW VARIABLES LIKE 'innodb_default_row_format';
```

## 二、COMPACT vs DYNAMIC 的关键差异 ⭐

**COMPACT 的"溢出"策略**：当一行中某个变长字段（VARCHAR/TEXT/BLOB）太长，超出半页（约 8000 字节）时：
- 把该列的**前 768 字节**留在行内（"前缀"），其余放到**溢出页（off-page）**，行内存一个 20 字节指针。
- `COMPACT` 在行内**至少保留 768 字节前缀**。

**DYNAMIC 的"溢出"策略**：
- 长字段**完全放到溢出页**，行内**只存 20 字节指针**，不保留前缀 ✅
- 好处：**主行更小** → 一个 16KB 页能放更多行 → **更少的页读取、更好的 buffer pool 命中率** ⭐
- 代价：读取大字段要多一次 IO

```
COMPACT:  [行头][行内 768B 前缀 ...][20B 指针] ──► 溢出页 [剩余数据]
DYNAMIC:  [行头][20B 指针]                    ──► 溢出页 [全部数据]
```

## 三、行内结构（COMPACT）

```
┌─────────────────────────────────────────────────────────┐
│ 变长字段长度列表  │  NULL 值列表  │  记录头信息（5字节）  │
├─────────────────────────────────────────────────────────┤
│ 列1值 │ 列2值 │ 列3值 │ ...                             │
└─────────────────────────────────────────────────────────┘
```

**① 变长字段长度列表**：从右到左记录每个变长列的实际长度（1~2 字节每列）。
**② NULL 值列表**：用**位图**标记哪些列是 NULL（所以 NULL **不占数据空间**，但占位图 1 bit）。
**③ 记录头 5 字节**：含 `deleted_flag`、`min_rec_flag`、`n_owned`（页目录）、`heap_no`、`record_type`、`next_record`（**单向链表指针**，指向下一条记录）。

**关键洞察**：InnoDB 页内的行是**按主键顺序排列的单向链表**，页内用 **Page Directory（槽位稀疏索引）** 做二分查找。

## 四、页结构（16KB）

```
┌──────────────┐
│ File Header  │ 38B：页号、前后页指针、页类型、LSN
├──────────────┤
│ Page Header  │ 56B：记录数、空闲空间位置、槽数、页层级
├──────────────┤
│ Infimum/Supremum │ 虚拟最小/最大记录（页内链表的头尾）
├──────────────┤
│ User Records │ ← 真正的数据行
├──────────────┤
│ Free Space   │ 空闲区（新记录从这里分配，向中间生长）
├──────────────┤
│ Page Directory │ 槽位（每 4~8 条记录一个槽），支撑二分查找
├──────────────┤
│ File Trailer │ 8B：校验和 + LSN（配合双写检测页撕裂）
└──────────────┘
```

## 五、大字段存储的最佳实践 ⭐

| 建议 | 理由 |
|---|---|
| **大字段拆到独立表** | 主表保持精简 → 主表页可放更多行 → 查询更快。用 `1:1` 关联表存 TEXT/BLOB |
| **用 VARCHAR 代替 TEXT（如果长度可控）** | VARCHAR 可参与索引前缀、排序；TEXT 有额外开销 |
| **避免 `SELECT *`** | 会把大字段一起读出来（可能触发溢出页 IO）⭐ |
| **TEXT 的索引只能用前缀** | `KEY (content(100))` |
| **不要对大字段频繁 UPDATE** | 会触发溢出页重写 + undo 记录旧值（undo 暴涨）|
| **压缩存储**（如 gzip 存 BLOB）| 减小 IO，代价是应用侧解压 |
| **`innodb_page_size` 不要随便改** | 默认 16K；4K 适合某些 OLTP，但要建库时定死 |

## 六、页大小与 IO 单位

| `innodb_page_size` | 适用 |
|---|---|
| 4K | 写密集、小行、SSD |
| **16K** ⭐ | 默认，通用 |
| 32K/64K | 大行、分析型 |

**注意**：页大小**只能在 `mysqld --initialize` 时设定**，之后不能改；且会与文件系统块大小相互影响（`innodb_flush_method=O_DIRECT` 时更明显）。

## 七、级联溢出（Off-page）

- 若溢出页也放不下，会**再分配溢出页**，形成链表。
- 每个溢出页有 20 字节的行内指针描述符（space_id + page_no + 长度）。
- `innodb_page_size` 越小，越容易溢出。

## 八、一句话总结

**行格式决定"长字段怎么放"：COMPACT 留 768 字节前缀，DYNAMIC 全放溢出页（行更小、命中率更高，推荐）；大字段要么拆表、要么少读（别 `SELECT *`），否则溢出页会拖慢一切。**""",
    ),
    (
        "MySQL",
        "change buffer,唯一索引,写优化",
        3,
        r"""什么是 Change Buffer？为什么唯索引和普通索引在写性能上有差异？""",
        r"""## 一、Change Buffer 是什么 ⭐

**用途**：缓存**对非唯一二级索引的写操作（INSERT / UPDATE / DELETE）**，在**数据页不在 Buffer Pool 时**不立即读入页面，而是把"这次修改"记在 Change Buffer 里，等该页**因为其他原因被读入**时再**合并（merge）**进去。

**核心收益**：**把"随机读 + 随机写"变成"顺序写"** ⭐

```
没有 Change Buffer：
  INSERT → 需要更新的二级索引页不在内存 → 从磁盘随机读该页（随机 IO）→ 改 → 变脏页

有 Change Buffer：
  INSERT → 页不在内存 → 把修改记入 Change Buffer（顺序写，内存操作）✅
        → 等某次查询真的需要这页时 → 读入页 + merge Change Buffer
```

**为什么只对非唯一二级索引有效** ⭐（面试高频）：

| 索引类型 | 写入时 | 能否用 Change Buffer |
|---|---|---|
| **唯一索引 / 主键索引** | **必须先读页确认唯一性**（有没有冲突）| ❌ **无法避免随机读** |
| **普通二级索引** | 不需要检查唯一性 | ✅ 可以推迟合并 |

**结论**：**唯一索引的写性能比普通索引差**，因为它省不掉那一次随机读。这就是"**能确定业务上唯一性由应用保证时，优先用普通索引**"的技术根据（代价：牺牲数据库层的唯一约束）。

## 二、Change Buffer 的形态与持久化 ⭐

| 版本 | 存储位置 |
|---|---|
| **5.5 之前** | 叫 Insert Buffer，**只能在系统表空间**（`ibdata1`）|
| **5.5+** | 改名 **Change Buffer**，支持 INSERT/UPDATE/DELETE，可选择存**独立表空间** |
| **8.0** | `innodb_change_buffering` 默认 `all` |

**持久化**：Change Buffer 本身也走 redo log（WAL），崩溃后可恢复。但**如果实例异常重启，Change Buffer 的合并会变慢**（需要重放）。

**关键参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `innodb_change_buffering` | `all` | 缓冲哪些操作（`all`/`none`/`inserts`/`deletes`/`changes`/`purges`）|
| `innodb_change_buffer_max_size` | **25** | 占 Buffer Pool 的最大百分比（**最多 50**）|
| `innodb_ibuf_size` | — | 8.0.30+ 可独立配置 |

**监控**：

```sql
SHOW ENGINE INNODB STATUS\G
-- INSERT BUFFER AND ADAPTIVE HASH INDEX 段落
-- Ibuf: size 1, free list len 0, seg size 2, 0 merges
```

## 三、什么时候 Change Buffer 反而有害 ⭐

| 场景 | 影响 |
|---|---|
| **数据页马上就被读**（读多写少）| 刚写进 Change Buffer 立刻要 merge → 白折腾，还多一次开销 |
| **实例重启后** | 大量 merge 积压 → **启动慢、启动后 IO 飙高** |
| **`innodb_change_buffer_max_size` 太大** | 挤占 Buffer Pool 的页缓存空间 |
| **频繁读取 Change Buffer 覆盖的索引** | merge 压力大 |

**实践**：**读多写少的库**可以调小或 `innodb_change_buffering=none`；**写入密集型（日志、埋点）** 保持默认甚至调大。

## 四、与"唯一索引 vs 普通索引"的选型结论 ⭐

| 场景 | 选择 |
|---|---|
| 业务要求数据库层保证唯一（如 `username`、`email`）| **必须唯一索引**，性能代价可接受 |
| 业务逻辑保证不会重复，只是想加速查询 | **普通索引**更好（写更快、空间更小）|
| 需要 `INSERT IGNORE` / `ON DUPLICATE KEY` 的幂等写入 | 需要唯一索引（靠冲突检测）|
| 关联表 `(a_id, b_id)` 天然唯一 | 可以只用普通索引 + 应用保证 |

**注意**：这个优势在**页已在内存时就不存在了**——所以对**热数据表**，唯一索引与普通索引的差异很小。**Change Buffer 主要惠及"写入分散、页冷"的场景**（如大批量导入）。

## 五、写入路径上的"三大缓冲"总结 ⭐

| 缓冲 | 层 | 加速什么 |
|---|---|---|
| **Buffer Pool** | 内存 | 读（页缓存）+ 写（延迟刷脏）|
| **Change Buffer** | 内存 | **非唯一二级索引的写**（省随机读）|
| **Log Buffer** | 内存 | redo 的批量刷盘 |

再加上**组提交**，构成了 InnoDB 写性能的全部秘密。

**一句话总结**：**Change Buffer 的本质是"把随机写攒成顺序写"；唯一索引因为必须先读页校验唯一性，天然用不了这个优化 —— 这是"非唯一二级索引写更快"的底层原因。**""",
    ),
    (
        "MySQL",
        "8.0,新特性",
        2,
        r"""MySQL 8.0 相比 5.7 有哪些重要变化？升级要注意什么？""",
        r"""## 一、8.0 的重要新特性 ⭐

### 1. 默认字符集与排序规则

| | 5.7 | **8.0** |
|---|---|---|
| 默认字符集 | `latin1` | **`utf8mb4`** ⭐ |
| 默认排序规则 | `latin1_swedish_ci` | **`utf8mb4_0900_ai_ci`** |

**影响**：升级后**默认排序规则变化**会导致 `ORDER BY` 结果不同（`0900_ai_ci` 对某些字符的排序与旧规则不一致）⭐

### 2. 数据字典

- 5.7：`.frm` 文件 + 部分系统表，**DDL 不是原子的**。
- **8.0：统一到 InnoDB 的事务型数据字典**（`mysql.ibd`）→ **DDL 原子性** ✅、无 `.frm` 文件、崩溃后可恢复。

### 3. 窗口函数（Window Functions）⭐

```sql
SELECT name, dept, salary,
       ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) AS rn,
       RANK()       OVER (PARTITION BY dept ORDER BY salary DESC) AS rk,
       DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC) AS drk,
       SUM(salary)  OVER (PARTITION BY dept)                      AS dept_total,
       AVG(salary)  OVER (ORDER BY id ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS ma3
FROM emp;
```

**价值**：以前要写关联子查询或用户变量的需求（分组 TopN、环比同比、移动平均），现在一行搞定，且性能更好。

### 4. CTE 与递归查询 ⭐

```sql
-- 普通 CTE（可读性）
WITH t AS (SELECT ... GROUP BY ...) SELECT * FROM t WHERE ...;

-- 递归 CTE（查组织树/多级分类）
WITH RECURSIVE org AS (
    SELECT id, name, parent_id, 1 AS lvl FROM dept WHERE parent_id IS NULL
    UNION ALL
    SELECT d.id, d.name, d.parent_id, o.lvl + 1
    FROM dept d JOIN org o ON d.parent_id = o.id
)
SELECT * FROM org ORDER BY lvl;
```

### 5. 其他重要特性

| 特性 | 说明 |
|---|---|
| **降序索引** | `CREATE INDEX idx (a ASC, b DESC)` 真正生效（以前语法接受但被忽略）|
| **函数索引** | `CREATE INDEX idx ON t ((SUBSTRING(name,1,10)))` ⭐ |
| **不可见索引** | `ALTER TABLE t ALTER INDEX idx INVISIBLE` → 可以"先藏起来"验证是否真的没用 |
| **`EXPLAIN ANALYZE`** | 实际执行并给出真实耗时/行数 ⭐ |
| **JSON 增强** | `->>` 运算符、`JSON_TABLE()`、`JSON_PRETTY()`、部分更新 |
| **`NOWAIT` / `SKIP LOCKED`** | `SELECT ... FOR UPDATE NOWAIT` 立刻返回而不等待 ⭐ 实现队列的利器 |
| **Hash Join** | 8.0.18+ 支持无索引等值 JOIN 的哈希连接 ⭐ |
| **资源组** | `CREATE RESOURCE GROUP` 控制线程的 CPU 亲和与优先级 |
| **角色（Roles）** | `CREATE ROLE`、`GRANT role TO user` |
| **密码策略** | 插件化、`validate_password` 组件 |
| **`ALTER TABLE ... ALGORITHM=INSTANT`** | 加列**秒级完成**（见下文）⭐ |
| **原子 DDL** | DDL 要么全成功要么全失败 |
| **redo log 重构** | 8.0.30+ 用 `innodb_redo_log_capacity` 统一管理 |

### 6. 已移除/废弃 ⭐

| 移除项 | 替代 |
|---|---|
| **查询缓存（Query Cache）** | 8.0 **彻底移除**（用 Redis/ProxySQL 缓存）|
| **`\N`（NULL 的别名）** | 用 `NULL` |
| **`utf8` 作为默认** | 用 `utf8mb4` |
| **`PASSWORD()` 函数** | `CREATE USER` 语法 |
| **`GRANT ... IDENTIFIED BY`** | 分离 `CREATE USER` 与 `GRANT` |
| **`innodb_locks` 等表** | 迁到 `performance_schema.data_locks` |

## 二、升级注意事项 ⭐

| 检查项 | 说明 |
|---|---|
| **`sql_mode` 变化** ⭐ | 8.0 默认含 `ONLY_FULL_GROUP_BY`、`STRICT_TRANS_TABLES`、`NO_ZERO_DATE` 等 → **老 SQL 可能直接报错**。升级前先在 5.7 上把 `sql_mode` 调成 8.0 的默认值跑一遍回归 |
| **默认字符集/排序规则** | 建表不再显式写字符集的话，新表会用 `utf8mb4_0900_ai_ci`，与老表 `utf8mb4_general_ci` **JOIN 时可能触发 collation 转换 → 索引失效** ⭐ 建议显式指定 collation |
| **`GROUP BY` 隐式排序消失** | 5.7 的 `GROUP BY` 会隐式排序，8.0 不会（有 `ORDER BY` 的 SQL 才可靠）|
| **保留字变化** | `RANK`、`GROUPS`、`LEAD`、`LAG`、`ROW_NUMBER` 等成为保留字 → 作为列名需加反引号 |
| **`utf8mb3` 弃用警告** | 会有 deprecation warning |
| **认证插件默认变化** | 8.0 默认 `caching_sha2_password`，**老客户端驱动可能不支持** ⭐ 要么升级驱动，要么 `ALTER USER ... IDENTIFIED WITH mysql_native_password` |
| **`information_schema` 性能** | 8.0 改查数据字典，某些查询行为/权限不同 |
| **复制** | 8.0 从库可复制 5.7 主库；**5.7 从库不能复制 8.0 主库**（单向兼容）⭐ |

## 三、升级路径与工具

```
5.7 → 8.0 支持「原地升级（in-place）」和「逻辑/物理迁移」

推荐流程：
  ① 全量备份（xtrabackup 物理备份）⭐
  ② 在从库/测试环境先升级并跑全量回归（含 sql_mode 检查）
  ③ 用 mysqlsh（MySQL Shell）的 upgrade checker 工具扫描不兼容项 ⭐
     mysqlsh -- util check-for-server-upgrade root@host:3306
  ④ 主从逐步升级（先升从库，切换后再升主库）
  ⑤ 升级后 ANALYZE TABLE 更新统计信息
```

**`mysqlsh` 检查器能直接告警**：保留字冲突、`utf8mb3` 使用、`sql_mode` 差异、认证插件、移除的函数等。

## 四、8.0 的实用技巧 ⭐

```sql
-- 1. 不可见索引：安全删索引（先隐藏观察，无问题再真删）
ALTER TABLE t ALTER INDEX idx INVISIBLE;
SELECT * FROM information_schema.statistics WHERE is_visible='NO';

-- 2. NOWAIT / SKIP LOCKED：实现"任务队列"
START TRANSACTION;
SELECT * FROM jobs WHERE status='pending' ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED;      -- 不阻塞，直接跳到下一个可用行 ⭐
UPDATE jobs SET status='running' WHERE id = ?;
COMMIT;

-- 3. EXPLAIN ANALYZE 看真实执行
EXPLAIN ANALYZE SELECT ...;
-- 输出含 (actual time=... rows=... loops=...) 与估算对比

-- 4. 递归 CTE 查树上所有子孙
WITH RECURSIVE sub AS (
  SELECT id FROM dept WHERE id = 1
  UNION ALL SELECT d.id FROM dept d JOIN sub s ON d.parent_id = s.id
) SELECT COUNT(*) FROM sub;

-- 5. 窗口函数做分组 TopN
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) rn FROM emp
) x WHERE rn <= 3;
```

## 五、一句话总结

**8.0 的三大质变：默认 utf8mb4 + 事务型数据字典 + 窗口函数/CTE**；升级最大的坑是 **`sql_mode` 变严**、**默认排序规则变化（导致 JOIN 时 collation 不匹配）** 和 **`caching_sha2_password` 认证插件**。用 `mysqlsh` 的 upgrade checker 先扫一遍能避开绝大多数问题。""",
    ),
    (
        "MySQL",
        "JOIN,驱动表,优化",
        2,
        r"""MySQL 的 JOIN 算法有哪些？为什么说"小表驱动大表"？`IN` 和 `EXISTS` 怎么选？""",
        r"""## 一、三种 JOIN 算法 ⭐

| 算法 | 全称 | 原理 | 前提 |
|---|---|---|---|
| **NLJ** | Nested-Loop Join | 双重循环：外层每行，内层用索引查找 | **被驱动表有索引** ⭐ |
| **BNL** | Block Nested-Loop Join | 把驱动表数据读入 **join buffer**，批量与被驱动表比对 | 被驱动表**无索引**，`Extra: Using join buffer` |
| **BKA** | Batched Key Access（5.6+）| NLJ 的批量版：用 join buffer 里的键**批量**去查被驱动表索引，配合 MRR | 被驱动表有索引 + 开启 BKA |
| **Hash Join** | 8.0.18+ | 建哈希表探测 | **无索引的等值 JOIN** |

### NLJ 示意（有索引时）

```sql
SELECT * FROM a JOIN b ON a.id = b.a_id;
-- 驱动表 a（假设 1000 行），被驱动表 b 有 idx(a_id)

for each row in a:            -- 外层 1000 次
    lookup b WHERE a_id = a.id  -- 内层走索引，O(log n)
-- 总代价 ≈ 1000 × log(rows_b)
```

### BNL 示意（无索引时，性能灾难）

```sql
-- 被驱动表 b 没有 a_id 索引
join_buffer  ← 装满 a 的一批行（比如 1000 行）
for each row in b:                       -- 扫全表 b（比如 100 万行）
    for each row in join_buffer:         -- 内存中比对
        匹配则输出
-- 总代价 ≈ (rows_a / buffer_batch) × rows_b  ← 极其昂贵 ❌
```

**优化**：**给被驱动表的连接列建索引**，让 BNL 退化为 NLJ ⭐

```sql
ALTER TABLE b ADD INDEX idx_a_id (a_id);
-- EXPLAIN 的 Extra 从 "Using join buffer (Block Nested Loop)" 变成 "Using index"
```

## 二、为什么"小表驱动大表"？⭐

**驱动表（外层表）** 决定了内层查找的**次数**；每做一次内层查找就是一次索引搜索。

```
驱动表 a 有 m 行，被驱动表 b 有 n 行
NLJ 代价 ≈ m × log(n)

若 a 是 1000 行、b 是 1,000,000 行：
  以 a 驱动 ≈ 1000 × 20 = 20,000 次操作
  以 b 驱动 ≈ 1,000,000 × 10 = 10,000,000 次操作   ← 慢 500 倍 ⭐
```

**所以：用小表（结果集小的表）做驱动表**。

**`EXPLAIN` 中谁在上面（`id` 相同、`table` 靠前）谁就是驱动表**；`STRAIGHT_JOIN` 可以强制指定顺序。

**"小表"的定义** ⭐：经过 `WHERE` 过滤后的**实际参与 JOIN 的行数少**，而不一定是"总行数小"。优化器会**基于统计信息估算行数**来选驱动表，估算不准时会选错 → 用 `ANALYZE TABLE` 更新统计，或 `STRAIGHT_JOIN` 手动干预。

## 三、`IN` vs `EXISTS` ⭐

**经验法则**：

| 场景 | 推荐 | 理由 |
|---|---|---|
| **子查询结果集大，主表小** | `IN` | `IN` 先执行子查询 → 小表驱动大表 ✅ |
| **子查询结果集小，主表大** | `EXISTS` | `EXISTS` 外层逐行，子查询能命中索引就快速返回 ✅ |

**记忆**：**"小表在外"** —— `IN` 的子查询表在外层，`EXISTS` 的主表在外层。

```sql
-- IN：适用于 dept 小、emp 大
SELECT * FROM emp WHERE dept_id IN (SELECT id FROM dept WHERE ...);
-- 执行：先查出 dept 的 id 列表（小），然后扫描 emp 判断是否在列表中

-- EXISTS：适用于 emp 小（过滤后）、dept 大
SELECT * FROM dept d WHERE EXISTS (
  SELECT 1 FROM emp e WHERE e.dept_id = d.id
);
-- 执行：逐行读 dept，对每行用 e.dept_id 索引查一次（命中即返回）
```

**现代 MySQL 的优化（5.6+）** ⭐：`IN` 子查询会被优化器改写为 **semijoin（半连接）**：

```sql
-- 优化器可能改写为
SELECT DISTINCT emp.* FROM emp JOIN dept ON emp.dept_id = dept.id WHERE ...;
-- 或者物化为临时表 + 去重
```

所以**在 MySQL 5.6+ 里 `IN` 和 `EXISTS` 的性能差异常常不大**，**真正决定性能的是索引**。可以先用 `EXPLAIN` 看优化器的选择，不要凭直觉改写。

**`NOT IN` 的陷阱** ⭐：

```sql
-- ⚠️ 如果子查询返回 NULL，整个 NOT IN 结果恒为空！
SELECT * FROM emp WHERE dept_id NOT IN (SELECT id FROM dept);
-- dept.id 有 NULL → expr NOT IN (NULL) 结果是 UNKNOWN → 不返回任何行

-- 解法：加 IS NOT NULL，或用 NOT EXISTS
SELECT * FROM emp e WHERE NOT EXISTS (SELECT 1 FROM dept d WHERE d.id = e.dept_id);
```

## 四、JOIN 优化实践清单 ⭐

| 措施 | 说明 |
|---|---|
| **连接列建索引** | 被驱动表的连接列必须有索引（否则 BNL）⭐ |
| **类型和字符集一致** | 类型/字符集不一致会导致优化器放弃索引 ⭐ |
| **只 SELECT 需要的列** | 减少 join buffer 和回表开销 |
| **小表驱动大表** | 必要时用 `STRAIGHT_JOIN` |
| **提高 `join_buffer_size`** | 只在无法避免 BNL 时有效（**每连接一份，慎调大**）|
| **开启 BKA + MRR** | 有索引的批量访问可提速（`optimizer_switch='mrr=on,mrr_cost_based=off,batched_key_access=on'`）|
| **大表 JOIN 拆开** | 应用层分两次查 + 内存拼装，往往比 SQL JOIN 更可控 |
| **避免多表 JOIN** | 3 表以上 JOIN 优化器容易选错计划（搜索空间爆炸）|
| **`ANALYZE TABLE`** | 统计信息不准会选错驱动表 |

## 五、`EXPLAIN` 里识别 JOIN 问题

| 字段值 | 含义 |
|---|---|
| `Using join buffer (Block Nested Loop)` | ❌ 被驱动表没索引，走 BNL |
| `Using join buffer (hash join)` | 8.0 的 Hash Join（比 BNL 好，但仍不如索引）|
| `Using index condition` | ✅ ICP 生效 |
| `Using MRR` | ✅ 多范围读，减少了随机 IO |
| `type=ALL` 出现在被驱动表 | ❌ 被驱动表全表扫描，最差 |

**一句话总结**：**JOIN 的性能只有一个关键 —— 被驱动表的连接列有没有索引；其余都是围绕"驱动表越小越好、被驱动表别全表扫"做文章。** `IN`/`EXISTS` 在 5.6+ 差异不大，先看 `EXPLAIN`。""",
    ),
    (
        "MySQL",
        "窗口函数,CTE,分析函数",
        2,
        r"""窗口函数是什么？和 `GROUP BY` 有什么区别？常用来解决什么问题？""",
        r"""## 一、核心区别 ⭐

| | **`GROUP BY`** | **窗口函数** |
|---|---|---|
| 输出行数 | **聚合后行数变少**（每组一行）| **行数不变**（每行都保留）⭐ |
| 能否看到明细 | ❌ 只看聚合结果 | ✅ **既能看明细，又能看聚合** |
| 排序 | 需 `ORDER BY` | `OVER (ORDER BY ...)` 决定窗口顺序 |
| 典型 | `SELECT dept, COUNT(*) FROM emp GROUP BY dept` | `SELECT name, dept, COUNT(*) OVER (PARTITION BY dept) FROM emp` |

```
GROUP BY：
  dept   cnt
  研发    3
  销售    2

窗口函数：
  name  dept   cnt_over
  张三   研发    3
  李四   研发    3
  王五   研发    3      ← 明细行全保留，每行都带上了所属组的统计
  赵六   销售    2
  钱七   销售    2
```

## 二、语法结构

```sql
函数名() OVER (
    PARTITION BY 分组列1, 分组列2     -- 可选：划分窗口（类似 GROUP BY）
    ORDER BY 排序列                    -- 可选：窗口内排序（决定"累积"行为）
    ROWS BETWEEN 边界 AND 边界          -- 可选：滑动窗口范围
)
```

**三种函数**：

| 类别 | 函数 | 说明 |
|---|---|---|
| **序号函数** | `ROW_NUMBER()`、`RANK()`、`DENSE_RANK()`、`NTILE(n)`、`PERCENT_RANK()` | 排名 |
| **聚合函数** | `SUM/AVG/COUNT/MAX/MIN/STDDEV/VAR_POP` | 加 `OVER` 后即窗口聚合 |
| **偏移/取值函数** | `LAG()`、`LEAD()`、`FIRST_VALUE()`、`LAST_VALUE()`、`NTH_VALUE()` | 取前后行 |

## 三、实战场景 ⭐

### 1. 分组 TopN（最经典）

```sql
-- 每个部门薪资前 3 名
SELECT * FROM (
    SELECT e.*, ROW_NUMBER() OVER (PARTITION BY dept_id ORDER BY salary DESC) AS rn
    FROM emp e
) t WHERE rn <= 3;
```

**以前要写**：关联子查询 `WHERE (SELECT COUNT(*) FROM emp e2 WHERE e2.dept_id=e.dept_id AND e2.salary>e.salary) < 3`（O(n²)）；现在 O(n log n) 且清晰。

### 2. 组内占比

```sql
SELECT dept_id, emp_name, salary,
       ROUND(salary / SUM(salary) OVER (PARTITION BY dept_id) * 100, 2) AS pct
FROM emp;
```

### 3. 环比 / 同比（`LAG` / `LEAD`）

```sql
SELECT month, amount,
       LAG(amount, 1) OVER (ORDER BY month) AS prev_month,
       ROUND(amount / LAG(amount, 1) OVER (ORDER BY month) - 1, 4) AS mom_rate,
       LAG(amount, 12) OVER (ORDER BY month) AS last_year,   -- 同比
       LEAD(amount, 1) OVER (ORDER BY month) AS next_month
FROM sales;
```

### 4. 累积求和（`ROWS BETWEEN`）

```sql
SELECT dt, amount,
       SUM(amount) OVER (ORDER BY dt ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_sum,
       AVG(amount) OVER (ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)          AS ma7,
       SUM(amount) OVER (ORDER BY dt ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING)          AS centered
FROM daily_sales;
```

**边界写法对照**：

| 写法 | 含义 |
|---|---|
| `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` | 从第一行到当前行（**累积**）|
| `ROWS BETWEEN 2 PRECEDING AND CURRENT ROW` | 前 2 行 + 当前行 |
| `ROWS BETWEEN N PRECEDING AND N FOLLOWING` | 居中 n 行窗口（去噪）|
| `ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING` | 当前行到最后 |
| **默认**（有 `ORDER BY` 无 `ROWS`）| `RANGE UNBOUNDED PRECEDING AND CURRENT ROW` ⭐ 也是累积 |
| **默认**（无 `ORDER BY`）| 整个分区 |

**`ROWS` vs `RANGE` 的区别** ⭐：`ROWS` 按**物理行数**，`RANGE` 按**值**（相同值会一起被包含）。`RANGE` 在排序值有重复时容易出意外。

### 5. 去重取最新一条 ⭐

```sql
-- 取每个用户的最后一条登录记录
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY login_time DESC) AS rn
    FROM login_log
) t WHERE rn = 1;
```

**比 `GROUP BY user_id` + `SUBSTRING_INDEX(GROUP_CONCAT(...))` 之类的黑魔法清晰得多。**

### 6. 连续登录天数 / 会话划分（`RANK` 差值技巧）⭐

```sql
-- 求每个用户连续登录的最大天数
WITH t1 AS (
    SELECT DISTINCT user_id, DATE(login_time) AS d,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY DATE(login_time)) AS rn,
           DATE_SUB(DATE(login_time),
                    INTERVAL ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY DATE(login_time)) DAY) AS grp
    FROM login_log
), t2 AS (
    SELECT user_id, grp, COUNT(*) AS streak FROM t1 GROUP BY user_id, grp
)
SELECT user_id, MAX(streak) AS max_streak FROM t2 GROUP BY user_id;
```

**原理**：日期 `d` 减去行号 `rn`，若连续则差值恒定 → 相同差值归为一组（**"打洞法"**）。这和本项目"每日一题"里的"跳过天数不会错位"用同一类思路。

### 7. 移动平均 / 去噪

```sql
SELECT dt, price,
       AVG(price) OVER (ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7
FROM stock_price;
```

## 四、性能注意 ⭐

| 注意点 | 说明 |
|---|---|
| **窗口函数扫描后排序** | 每个 `PARTITION BY` 都需要排序，磁盘临时表可能被用上（看 `EXPLAIN` 的 `Using temporary; Using filesort`）|
| **给 `PARTITION BY` + `ORDER BY` 建联合索引** | 可避免额外排序 ⭐ |
| **不要在窗口上套复杂表达式** | 先在子查询里算好再套窗口 |
| **8.0 之前不可用** | 5.7 只能用用户变量模拟（不可靠，官方明确不保证顺序）⭐ |
| **窗口函数不能出现在 `WHERE` 里** | 因为执行顺序在 `WHERE` 之后 → 必须外层子查询过滤（如上面的 `rn <= 3`）|

**SQL 执行顺序**（含窗口函数的位置）⭐：

```
FROM → ON → JOIN → WHERE → GROUP BY → HAVING
     → 窗口函数（WINDOW）→ SELECT → DISTINCT → ORDER BY → LIMIT
```

所以窗口函数的结果**不能在同一个 `SELECT` 的 `WHERE`/`GROUP BY`/`HAVING` 中引用**。

## 五、一句话总结

**窗口函数 = "带分组和排序语义的聚合 + 明细行全保留"**；最实用的四招是 **分组 TopN、占比、环比、去重取最新**。它把以前需要自连接或用户变量才能实现的活儿变成一行可读 SQL，代价是一次排序。""",
    ),
    (
        "MySQL",
        "JSON,半结构化",
        2,
        r"""MySQL 的 JSON 类型有什么用？是怎么存储的？什么时候不该用 JSON？""",
        r"""## 一、JSON 类型的基本特性 ⭐

| 特性 | 说明 |
|---|---|
| **存储** | **二进制格式**（不是纯文本），解析后按内部结构存 → 读取时**不用重新解析** ⭐ |
| **校验** | 插入时**自动校验**是否合法 JSON，非法直接报错 |
| **大小** | 二进制格式通常比等价的文本**更小**（去掉了冗余空格、键只存一次）|
| **NULL** | JSON 列的 `NULL` 与 `JSON 值 'null'` 是**两回事** ⭐ |
| **索引** | **不能直接给 JSON 列建索引** → 必须用**生成列 + 索引** 或 **多值索引**（8.0.17+）|

## 二、核心函数 ⭐

```sql
-- 读取
JSON_EXTRACT(doc, '$.name')          -- 提取
doc -> '$.name'                      -- 等价简写，返回 JSON（带引号的字符串）
doc ->> '$.name'                     -- ⭐ -> 后再 UNQUOTE，返回普通字符串（最常用）
JSON_UNQUOTE(JSON_EXTRACT(doc,'$.name'))

-- 路径支持
'$.a.b.c'        -- 嵌套
'$.arr[0]'       -- 数组下标
'$.arr[*]'       -- 所有元素（多值）
'$.arr[1 to 3]'  -- 切片（8.0）

-- 修改（返回新值，需 UPDATE 写回）
JSON_SET(doc, '$.age', 30)                    -- 有则改，无则加
JSON_INSERT(doc, '$.x', 1)                    -- 只加不改
JSON_REPLACE(doc, '$.x', 1)                   -- 只改不加
JSON_REMOVE(doc, '$.x')                        -- 删除
JSON_ARRAY_APPEND(doc, '$.tags', 'new')
-- 8.0 的 -> / 复合写法
doc = JSON_SET(doc, '$.a', 1)

-- 其他
JSON_VALID(x)         -- 是否合法
JSON_TYPE(x)          -- 类型
JSON_KEYS(x)          -- 所有键
JSON_LENGTH(x)        -- 长度
JSON_CONTAINS(doc, '"x"', '$.tags')   -- 包含
JSON_TABLE(...)       -- ⭐ 把 JSON 展开成行（8.0）
JSON_PRETTY(x)        -- 美化输出（8.0）
```

## 三、如何给 JSON 建索引 ⭐

### 方法 1：生成列（虚拟列）+ 索引（5.7+，最通用）

```sql
ALTER TABLE orders
  ADD COLUMN cust_id BIGINT
      GENERATED ALWAYS AS (JSON_EXTRACT(payload, '$.customer_id')) VIRTUAL,
  ADD INDEX idx_cust (cust_id);

-- 之后就能用索引了
SELECT * FROM orders WHERE cust_id = 1001;
-- 或者直接对表达式查询（优化器会自动匹配生成列）
SELECT * FROM orders WHERE payload ->> '$.customer_id' = '1001';
```

**VIRTUAL vs STORED**：

| | VIRTUAL（默认）| STORED |
|---|---|---|
| 存储 | **不占空间**，查询时计算 | 占空间，写入时计算 |
| 索引 | ✅ 可索引 | ✅ 可索引 |
| 二级索引 | 索引里存计算结果 | 同 |
| 适合 | 大部分场景 ⭐ | 计算昂贵、频繁读 |

### 方法 2：多值索引（Multi-Valued Index，8.0.17+）⭐

用于 **JSON 数组**的索引：

```sql
ALTER TABLE t ADD INDEX idx_tags ((CAST(payload->'$.tags' AS CHAR(20) ARRAY)));
--                                                ↑ ARRAY 关键字，基于 CAST ... AS ... ARRAY

SELECT * FROM t WHERE JSON_CONTAINS(payload->'$.tags', '"mysql"');
SELECT * FROM t WHERE 'mysql' MEMBER OF (payload->'$.tags');   -- ⭐ 更直观
```

适合"一个文档有多个标签"的检索。

### 方法 3：关系化建模（根本解法）

```sql
-- 不要：orders(payload JSON)  里塞 tags: ["a","b","c"]
-- 而是：
CREATE TABLE order_tags (order_id BIGINT, tag VARCHAR(32), KEY(tag));
```

能关系化就不要 JSON —— JSON 只适合**结构多变、不常查询的"附属性"字段**。

## 四、`JSON_TABLE`：把 JSON 变成行 ⭐

```sql
SELECT o.id, jt.*
FROM orders o,
JSON_TABLE(o.payload, '$.items[*]' COLUMNS (
    sku    VARCHAR(32) PATH '$.sku',
    qty    INT         PATH '$.qty',
    price  DECIMAL(10,2) PATH '$.price'
)) AS jt
WHERE o.id = 1;
```

**这是 JSON 与关系模型之间的桥梁**：把"嵌套的订单明细"展开成多行，再正常 JOIN / 聚合。适合**报表、导出、迁移**。

## 五、什么时候不该用 JSON ⭐

| 不该用的场景 | 原因 |
|---|---|
| **需要频繁按某个字段查询/排序/分组** | 索引要额外做生成列，不如直接建列 |
| **字段结构稳定、字段数固定** | 直接建列更清晰、类型更强、更省空间 |
| **需要外键约束 / 唯一约束** | JSON 无法建外键和真正的唯一约束 |
| **需要事务级别的部分更新** | 5.7 里每次 `JSON_SET` 都要重写整个文档 ❌（8.0 有部分更新优化）|
| **单文档很大（几 MB）** | 每次读取都要加载整个文档 |
| **需要 JOIN 到其他表** | 必须先 `JSON_TABLE` 展开 |
| **数据分析/统计** | 列存（ClickHouse）或关系化更适合 |
| **数据完整性要求高** | 没有 schema 校验（8.0 才有 `CHECK` 配合 `JSON_SCHEMA_VALID`）|

**8.0 的改进：部分更新（Partial Update）** ⭐ —— 当 `JSON_SET/REPLACE/REMOVE` 修改的字段足够小（新值不超过原长度且路径不改变结构）时，只更新文档的**局部二进制片段**，而不是重写整个文档。可用 `JSON_STORAGE_SIZE()` vs `JSON_STORAGE_FREE()` 观察。

## 六、适用场景 ✅

```
✔ 动态属性/扩展字段（不同商品有不同的规格参数）
✔ 第三方 API 的原始响应存证（结构不固定，仅归档）
✔ 配置项（读多写少，整体读写）
✔ 事件/日志的负载
✔ 需要保留"原始结构"的场景（再解析/审计）
```

## 七、一句话总结

**JSON 类型的价值是"灵活的半结构化存储 + 二进制高效访问"，代价是"不能直接索引、没有强约束"。** 用它的判断标准很简单：**这个字段会不会被用于查询条件/排序？会 → 关系化建模；不会 → JSON 可以接受。** 需要索引时用**生成列**（通用）或**多值索引**（数组）。""",
    ),
    (
        "MySQL",
        "分区表,管理,维护",
        2,
        r"""MySQL 分区表是什么？有哪些分区类型？有什么坑？""",
        r"""## 一、分区表的本质 ⭐

**分区（Partitioning）**：把**一张逻辑表**在存储层拆成**多个物理文件**（`t#p#p0.ibd` 等），MySQL 根据分区规则 **`pruning`（分区裁剪）** 自动只访问相关分区。

**目的**：
1. **管理性**：快速删除历史数据（`DROP PARTITION` 秒级，而 `DELETE` 要很久）⭐
2. **查询裁剪**：`WHERE dt = '2024-01-01'` 只扫一个分区
3. **并行扫描**（8.0 部分支持）

**注意**：**分区 ≠ 分表，也 ≠ 分库**。所有分区仍在**同一个 MySQL 实例、同一张逻辑表**下；**不能分散到多台机器**，也没有解决单机写入瓶颈。

## 二、四种分区类型 ⭐

| 类型 | 规则 | 例子 |
|---|---|---|
| **RANGE** ⭐ | 按范围 | `PARTITION BY RANGE (YEAR(dt))` |
| **LIST** | 按枚举值列表 | `PARTITION BY LIST (region_id)` |
| **HASH** | 按哈希取模 | `PARTITION BY HASH(id) PARTITIONS 4` |
| **KEY** | 按 MySQL 内置哈希（支持非整型/多列）| `PARTITION BY KEY(a, b) PARTITIONS 8` |

**RANGE 变种**：`RANGE COLUMNS`（多列范围）、`RANGE` on 表达式（仅支持 `TO_DAYS()`、`YEAR()`、`MONTH()` 等少数函数）。

```sql
-- 按月分区的日志表（最常用）⭐
CREATE TABLE access_log (
    id BIGINT NOT NULL AUTO_INCREMENT,
    dt DATE NOT NULL,
    url VARCHAR(255),
    PRIMARY KEY (id, dt)          -- ⚠️ 分区键必须在所有唯一键中！
) ENGINE=InnoDB
PARTITION BY RANGE COLUMNS(dt) (
    PARTITION p202401 VALUES LESS THAN ('2024-02-01'),
    PARTITION p202402 VALUES LESS THAN ('2024-03-01'),
    PARTITION p202403 VALUES LESS THAN ('2024-04-01'),
    PARTITION pmax    VALUES LESS THAN (MAXVALUE)   -- 兜底分区
);
```

## 三、分区管理操作

```sql
-- 加分区
ALTER TABLE t ADD PARTITION (PARTITION p202404 VALUES LESS THAN ('2024-05-01'));

-- ⭐ 秒级删除历史分区（比 DELETE 快几个数量级，且不产生大量 undo/binlog）
ALTER TABLE t DROP PARTITION p202401;

-- 清空分区（保留分区定义）
ALTER TABLE t TRUNCATE PARTITION p202401;

-- 拆分/合并分区（REORGANIZE）
ALTER TABLE t REORGANIZE PARTITION pmax INTO (
    PARTITION p202404 VALUES LESS THAN ('2024-05-01'),
    PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

-- 交换（把分区变成独立表 / 反向）
ALTER TABLE t EXCHANGE PARTITION p202401 WITH TABLE t_archive;

-- 查看
SELECT * FROM information_schema.partitions WHERE table_name = 'access_log';
EXPLAIN SELECT ... ;   -- 看 partitions 字段是否只命中一个分区 ⭐
```

**`EXPLAIN` 的 `partitions` 列**是验证分区裁剪是否生效的关键：

```
partitions: p202403      ← ✅ 只扫一个分区（pruning 生效）
partitions: p202401,p202402,p202403,pmax   ← ❌ 扫了全部分区（没裁剪）
```

## 四、分区裁剪生效的条件 ⭐

```sql
-- ✅ 生效：分区键直接参与比较
WHERE dt = '2024-03-15'
WHERE dt BETWEEN '2024-03-01' AND '2024-03-31'
WHERE dt >= '2024-03-01' AND dt < '2024-04-01'

-- ❌ 不生效：
WHERE YEAR(dt) = 2024                 -- 对分区键用了函数（RANGE COLUMNS 场景）
WHERE DATE_FORMAT(dt,'%Y-%m') = '2024-03'
WHERE id = 100                        -- 分区键是 dt，不是 id
WHERE dt + INTERVAL 1 DAY = '2024-03-16'
```

**原则**：**分区键必须以"裸列"的形式出现在 `WHERE` 的常量比较中**。

## 五、分区的坑（务必知道）⭐

| 坑 | 说明 |
|---|---|
| **① 分区键必须包含在每个唯一索引中** ⭐ | 主键/唯一键必须**包含分区键的所有列**。否则报错：`A PRIMARY KEY must include all columns in the table's partitioning function` |
| **② 最多 8192 个分区** | 分区太多 → 打开文件数暴涨、元数据开销巨大（每分区至少 2 个文件）|
| **③ 不支持外键** | 分区表**不能有外键**，也不能被外键引用 ⭐ |
| **④ 分区键不能修改** | 想换分区键只能重建表 |
| **⑤ NULL 值走第一个分区**（RANGE）| `NULL` 会被归入 `< 最小值` 的分区（通常是最小分区），意外打爆它 |
| **⑥ 没有 `MAXVALUE` 兜底时会插入失败** | 新数据没有对应分区 → `ERROR 1526: Table has no partition for value` ⭐ |
| **⑦ 全局唯一索引无法保证** | 唯一性只在分区内检查（因为唯一索引必须含分区键）⭐ |
| **⑧ 跨分区查询没有收益** | 如果查询总是不带分区键，分区只增加开销 |
| **⑨ `EXPLAIN` 有额外开销** | 分区裁剪本身要计算，分区数极多时元数据操作变慢 |
| **⑩ 8.0 移除了分区表的很多限制** | 但原生分区（InnoDB 的**可传输表空间 / 原生分区**）与老的分区实现行为不同 |
| **⑪ `DROP PARTITION` 会重建统计信息** | 大分区表上可能短暂抖动 |
| **⑫ 分区表的统计信息是"每个分区"级别** | 优化器对分区表的估算更容易失准 |

## 六、分区 vs 分表 vs 分库 ⭐

| | 分区表 | 分表（应用层）| 分库分表 |
|---|---|---|---|
| 物理位置 | **同一实例同一表** | 同实例多表 | 多实例 |
| 应用改造 | **无** ✅ | 需改造 | 需中间件 |
| 突破单机写入 | ❌ | ❌ | ✅ |
| 跨片 JOIN | ✅ 原生支持 | ❌ | ❌ |
| 分布式事务 | 不需要 | 不需要 | ❌ 需要处理 |
| 快速删历史 | ✅ `DROP PARTITION` ⭐ | 需 `DROP TABLE` | 同 |
| 适用 | **单机内的数据生命周期管理** | 数据量中等 | 真正的水平扩展 |

**结论**：**分区表最适合"按时间滚动、只查近期、定期清理历史"的日志/流水表**。它**不是**水平扩展方案。

## 七、最佳实践 ⭐

```sql
-- 1. 用 RANGE COLUMNS(dt) + 按月分区 + MAXVALUE 兜底
-- 2. 主键设计为 (id, dt) 或干脆用 dt 做主键（日志表常见）
-- 3. 用定时任务提前创建未来 3 个月的分区，删除 3 个月前的分区
-- 4. 查询必须带分区键（在应用层强制）
-- 5. 分区数量控制在几百以内（按月分区 = 保留几年）
```

**自动维护脚本思路**：

```sql
-- 每天跑一次
ALTER TABLE access_log ADD PARTITION (PARTITION p202405 VALUES LESS THAN ('2024-06-01'));
ALTER TABLE access_log DROP PARTITION p202311;
```

**一句话总结**：**分区表的核心价值是"用 `DROP PARTITION` 代替 `DELETE` 来管理数据生命周期"，而不是性能扩展**；最大的坑是"唯一索引必须含分区键"，最常见的设计是"按月 RANGE COLUMNS + MAXVALUE 兜底"。""",
    ),
    (
        "MySQL",
        "视图,触发器,存储过程",
        1,
        r"""视图、触发器、存储过程分别是什么？各自适合什么场景，有什么缺点？""",
        r"""## 一、视图（View）

**本质**：一个**保存下来的 SELECT 语句**，本身不存数据（普通视图），查询时展开执行。

```sql
CREATE VIEW v_user_order AS
SELECT u.id, u.name, o.order_no, o.amount
FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = 'paid';

SELECT * FROM v_user_order WHERE amount > 100;   -- 像用表一样用视图
```

| 优点 | 缺点 |
|---|---|
| **简化复杂查询**（多表 JOIN 封装成一个"表"）| **性能不提升**：每次查询都展开成原 SQL |
| **权限隔离**：只暴露部分列/行 ⭐ | 嵌套视图会让优化器难以优化 |
| **逻辑解耦**：表结构变了只改视图 | 无法建索引（普通视图）|
| **向后兼容**：重命名表后建同名视图 | `SELECT *` 在视图定义里会被固化（表加列后视图看不到新列）⭐ |

**`WITH CHECK OPTION`**：限制通过视图写入的行必须满足视图的 `WHERE` 条件。

**物化视图**：**MySQL 原生不支持**（PostgreSQL/Oracle 有）。替代方案：
- **汇总表 + 定时任务**（最常见）
- **触发器维护**
- **`CREATE TABLE ... AS SELECT`**（快照，不自动刷新）

## 二、触发器（Trigger）

**本质**：在 `INSERT` / `UPDATE` / `DELETE` 前后**自动执行**的一段逻辑。

```sql
CREATE TRIGGER trg_order_after_insert
AFTER INSERT ON orders FOR EACH ROW
BEGIN
    UPDATE stats SET order_count = order_count + 1 WHERE dt = CURDATE();
END;
```

| 优点 | 缺点 ⭐ |
|---|---|
| 自动化（审计日志、同步冗余字段、级联计算）| **对应用不可见**：最难排查的问题往往藏在这里 ⭐ |
| 强一致（与主操作同一事务）| **性能隐忧**：`FOR EACH ROW` 在大批量 DML 上放大数倍 |
| 绕不过去（任何写入都触发）| **调试困难**：没有堆栈，只能查 `SHOW TRIGGERS` / `information_schema.triggers` |
| | **复制风险**：STATEMENT 格式下触发器可能在从库被触发两次 ⭐ |
| | **级联触发器**：A 的触发器改 B，B 的又改 C → 难以追踪 |
| | **DDL 风险**：`pt-online-schema-change` 会因触发器冲突而失败/需要特殊处理 |
| | MySQL **不支持 `INSTEAD OF` 触发器**（不能拦截视图写入）|

**典型反例**：用触发器同步"订单表 → 统计表"。一旦统计逻辑变了，历史数据无法回补；而且 binlog 量翻倍。

**替代方案**：**应用层显式处理**（Service 层事务）、**binlog 订阅（Canal/Debezium）异步同步**、**定时任务**。

**结论**：**触发器只适合"审计日志"这类简单、幂等、不会频繁变更的场景**；业务逻辑尽量放应用层。

## 三、存储过程 / 函数（Stored Procedure / Function）

**本质**：一组预编译的 SQL 语句，可带参数和控制流（`IF`、`LOOP`、`CURSOR`）。

```sql
DELIMITER $$
CREATE PROCEDURE sp_batch_delete(IN p_days INT)
BEGIN
    DECLARE affected INT DEFAULT 1;
    WHILE affected > 0 DO
        DELETE FROM logs WHERE dt < DATE_SUB(CURDATE(), INTERVAL p_days DAY) LIMIT 1000;
        SET affected = ROW_COUNT();
        DO SLEEP(0.1);
    END WHILE;
END$$
DELIMITER ;

CALL sp_batch_delete(30);
```

| 优点 | 缺点 ⭐ |
|---|---|
| **减少网络往返**：批量逻辑一次调用 ⭐ | **业务逻辑分散**：部分在 DB、部分在应用 → 难维护、难测试、难版本控制 ⭐ |
| **预编译**：解析一次，多次执行（但 8.0 每条连接首次仍需解析）| **调试/单测极难**（没有 IDE 级别的支持）|
| **权限集中**：应用只需 `EXECUTE` 权限 | **数据库 CPU 压力**：所有逻辑挤在 DB，**无法水平扩展** ❌ |
| **批量维护任务**（数据清理、统计汇总）✅ | **可移植性差**：跨数据库（PG/Oracle）要重写 |
| | **迁移/升级风险**：DDL 变更后过程可能失效 |
| | 高并发下容易**锁住连接** |

**该用的场景** ✅：**一次性/周期性数据维护脚本**（分批删除、数据回填、统计重算）——这类"运维任务"用存储过程比写脚本方便。

**不该用的场景** ❌：**业务逻辑**（订单状态机、库存扣减）——放应用层，配合自动化测试和代码评审。

## 四、函数（Function）vs 过程（Procedure）

| | Function | Procedure |
|---|---|---|
| 返回值 | **必须有且只有一个返回值** | 可多个（`OUT` 参数）|
| 调用 | 可在 SQL 里使用（`SELECT my_func(x)`）| `CALL p(...)` |
| 事务 | **不能**包含事务控制语句 | 可以 `COMMIT`/`ROLLBACK` |
| 限制 | 不能有 `CALL`、不能用动态 SQL 的结果集 | 灵活 |
| 性能 | **在 SQL 中对每一行调用 = 灾难** ⭐ | — |

**⚠️ 最大的坑**：`SELECT * FROM t WHERE my_func(col) = 1` —— 函数会在**每一行**上执行，且**让索引失效**。如果函数里还查表，就是 O(n × m)。

## 五、其他相关对象

| 对象 | 说明 |
|---|---|
| **事件调度器（Event Scheduler）** | MySQL 内置定时任务：`CREATE EVENT ... ON SCHEDULE EVERY 1 DAY DO ...`（需 `event_scheduler=ON`）⭐ 替代 cron 做库内维护 |
| **序列** | MySQL 无原生序列，用 `AUTO_INCREMENT` 或自增表模拟 |
| **用户定义函数 UDF** | 用 C/C++ 编译成 `.so` 加载，**能突破 SQL 限制但有安全风险** ⚠️ |

**事件调度器示例**：

```sql
SET GLOBAL event_scheduler = ON;
CREATE EVENT ev_clean_log
ON SCHEDULE EVERY 1 DAY STARTS '2024-05-01 03:00:00'
DO
  DELETE FROM logs WHERE dt < DATE_SUB(CURDATE(), INTERVAL 30 DAY);
```

## 六、选型总表 ⭐

| 需求 | 推荐方案 |
|---|---|
| 封装复杂查询、权限隔离 | **视图** |
| 审计日志 | 触发器（简单）或**应用层日志** |
| 冗余字段同步 | **应用层** 或 **binlog 订阅** ⭐ |
| 定时清理/统计 | **存储过程 + Event Scheduler** 或外部 cron ⭐ |
| 业务逻辑 | **应用层**（有测试、有版本控制）⭐ |
| 复杂计算（多行）| **应用层**（语言生态更丰富）|
| 一次性数据修复 | **存储过程** 或 Python/Shell 脚本 |

**一句话总结**：**视图是"查询的封装"，触发器是"隐式的副作用"，存储过程是"库内程序"**。三者都是"把逻辑放进数据库"，而现代架构的共识是 —— **数据库只负责存与取，业务逻辑归应用层**；只在"运维型批处理"这个窄场景里用存储过程才划算。""",
    ),
    (
        "MySQL",
        "备份,恢复,xtrabackup",
        3,
        r"""MySQL 备份有哪几种方式？`mysqldump` 和 XtraBackup 有什么区别？怎么验证备份可用？""",
        r"""## 一、备份分类 ⭐

```
按形式：  逻辑备份（SQL 文本）  vs  物理备份（数据文件拷贝）
按范围：  全量  vs  增量  vs  差异
按状态：  热备（不锁）  vs  温备（只读）  vs  冷备（停机）
```

| 工具 | 类型 | 锁 | 适用规模 |
|---|---|---|---|
| **`mysqldump`** | 逻辑 | InnoDB 下**基本不锁**（`--single-transaction`）| **< 50GB**，小库 ⭐ |
| **`mysqlpump`** | 逻辑（并行）| 同上 | 中等（8.0 已弃用）|
| **`mysqlsh` util dump** | 逻辑（并行，8.0）| 同上 | 中等偏大 ✅ |
| **XtraBackup（Percona）** | **物理** | **几乎不锁**（`--backup-lock=OFF` 8.0）| **大库，TB 级** ⭐ |
| **Clone Plugin（8.0.17+）** | 物理（本地/远程克隆）| 极短 | 建从库**最快** ⭐ |
| **文件系统快照（LVM/ZFS）** | 物理 | 秒级锁表 | 云环境常见 |
| **`SELECT ... INTO OUTFILE`** | 逻辑（单表）| — | 数据交换 |

## 二、`mysqldump` ⭐

**一致性全量备份（InnoDB）**：

```bash
mysqldump -u root -p \
  --single-transaction \          # ⭐ 用 REPEATABLE READ 快照，保证一致性且不锁表（仅 InnoDB）
  --master-data=2 \               # ⭐ 记录 binlog 位点（注释形式），用于搭建从库/PITR
  --flush-logs \                  # 备份后切新 binlog
  --routines --triggers --events \# 导出存储过程/触发器/事件
  --set-gtid-purged=OFF \         # 视情况；搭从库时需要 ON
  --default-character-set=utf8mb4 \   # ⭐ 避免乱码（本项目实战教训）
  --hex-blob \                    # BLOB 用十六进制，防二进制乱码
  --databases blogdb > blogdb_$(date +%F).sql
```

**关键选项详解**：

| 选项 | 说明 |
|---|---|
| `--single-transaction` ⭐ | 在一个事务里导出所有表 → **一致性快照**，不锁表。**仅对 InnoDB 有效**；有 MyISAM 表时会失效 |
| `--master-data=2` ⭐ | 把 `CHANGE MASTER TO MASTER_LOG_FILE=..., MASTER_LOG_POS=...` 以**注释**写入文件头（`=1` 则不注释，恢复时会自动执行）|
| `--flush-logs` | 备份前切 binlog，便于 PITR 定位 |
| `--default-character-set=utf8mb4` ⭐ | **不写这个很容易导出乱码**（尤其在有 latin1 遗留数据的项目里）|
| `--hex-blob` | 二进制列以 `0x...` 形式导出，避免不可见字符破坏 SQL |
| `--where='id<1000'` | 条件导出（分片拉取）|
| `--skip-lock-tables` | 避免 MyISAM 锁表 |
| `--no-data` | 只导结构（`-d`）|
| `--routines --triggers --events` | 默认**不含**这些对象 ⚠️ |

**备份单表 / 结构**：

```bash
mysqldump -u root -p blogdb posts > posts.sql
mysqldump -u root -p -d blogdb > schema_only.sql    # 只要结构
mysqldump -u root -p blogdb --ignore-table=blogdb.logs > nodata.sql
```

**恢复**：

```bash
mysql -u root -p blogdb < blogdb_2024-05-01.sql
# 大文件加速（关掉 binlog、关掉唯一性检查）
mysql -u root -p \
  -e "SET GLOBAL sql_log_bin=0; SET UNIQUE_CHECKS=0; SET FOREIGN_KEY_CHECKS=0;" \
  blogdb < dump.sql
```

## 三、XtraBackup ⭐

**原理**：

```
① 短暂加锁，记录起始 LSN（Log Sequence Number）
② 以物理方式边读边拷贝 InnoDB 数据文件（不阻塞 DML）
③ 同时持续拷贝 redo log，保证"拷贝过程中发生的变化"也在里面
④ 解锁，结束
⑤ 备份完成后需 --prepare：用 redo log 把数据文件"前滚"到一致状态 ⭐
```

**核心优势**：

| | mysqldump | XtraBackup |
|---|---|---|
| 备份速度 | 慢（要读全部数据 + 生成 SQL）| **快**（顺序拷贝文件）|
| 恢复速度 | **慢**（要逐条重放 SQL、重建索引）⭐ | **快**（直接拷回文件）|
| 备份体积 | 大（含 SQL 文本）| **小**（压缩后可很小）|
| 增量备份 | ❌ | ✅ **支持增量** ⭐ |
| 跨版本/跨平台 | ✅ 好 | ⚠️ 受限 |
| 适用规模 | < 50GB | **100GB ~ TB 级** ⭐ |

**常用命令**：

```bash
# 全量备份
xtrabackup --backup --target-dir=/backup/full --user=root --password=xxx

# 增量备份（基于上次全量）
xtrabackup --backup --target-dir=/backup/inc1 \
  --incremental-basedir=/backup/full --user=root --password=xxx

# prepare（关键步骤）
xtrabackup --prepare --apply-log-only --target-dir=/backup/full        # 全量
xtrabackup --prepare --apply-log-only --target-dir=/backup/full \
  --incremental-dir=/backup/inc1                                        # 应用增量
xtrabackup --prepare --target-dir=/backup/full                          # 最后一次不加 --apply-log-only

# 恢复
systemctl stop mysqld
rm -rf /var/lib/mysql/*
xtrabackup --copy-back --target-dir=/backup/full
chown -R mysql:mysql /var/lib/mysql
systemctl start mysqld
```

**⚠️ `--apply-log-only` 的规则**：应用**中间**的增量备份时必须加；应用**最后一个**增量/做最终 prepare 时**不能**加，否则回滚未提交事务被跳过 → 数据不一致 ⭐

## 四、如何验证备份可用 ⭐（最重要的一步）

**"没验证过的备份等于没有备份"**。

| 验证层次 | 做法 |
|---|---|
| **① 文件完整性** | 检查文件大小、`gzip -t` 校验、备份日志无 error |
| **② 可恢复性（必做）** ⭐ | **定期在测试机真实恢复一次**，并跑数据校验 |
| **③ 数据一致性** | 恢复后 `CHECK TABLE`、`pt-table-checksum` 与源库对比 |
| **④ 时间可接受性** | 记录恢复耗时（RTO），确认在业务容忍范围内 |
| **⑤ 自动化** | 备份脚本 + 恢复演练脚本 + 告警（备份失败必须能通知到人）⭐ |

**校验恢复的具体方法**：

```bash
# 1. 恢复到独立的测试实例（不同端口/容器）
# 2. 对比行数与校验和
mysql -e "SELECT COUNT(*) FROM blogdb.posts"       # 源
mysql -e "SELECT COUNT(*) FROM blogdb.posts"       # 恢复目标
# 3. 用 pt-table-checksum 做逐行校验
pt-table-checksum --host=source --databases=blogdb
# 4. 抽查关键业务数据（最新一条订单、最新评论）
# 5. 启动应用连接测试库，跑一遍冒烟测试 ⭐
```

**备份策略（3-2-1 原则）** ⭐：

```
3 份副本  ·  2 种介质  ·  1 份异地
+ 保留策略：日备保留 7 天，周备保留 4 周，月备保留 12 个月
+ 备份文件也要加密（含敏感数据）
+ 备份文件必须与数据库实例分离存放（防同一台机器一起坏）
```

## 五、PITR（时间点恢复）⭐

**全量备份 + binlog 重放** 可恢复到任意时间点：

```bash
# 1. 恢复全量备份
# 2. 从 --master-data=2 记录的位点开始重放 binlog
mysqlbinlog --start-position=1234 \
  --stop-datetime='2024-05-01 10:29:00' \
  /var/lib/mysql/mysql-bin.000012 | mysql -u root -p

# 或用 GTID
mysqlbinlog --skip-gtids --include-gtids='uuid:1-100' mysql-bin.000012 | mysql -u root -p
```

**典型用途**：误 `DELETE` / 误 `DROP TABLE` 后恢复到误操作前一刻 ⭐

**注意**：
- **ROW 格式的 binlog 才可靠**（STATEMENT 下非确定性语句无法保证重放结果）⭐
- 恢复前先 `mysqlbinlog ... > x.sql` 用编辑器**去掉误操作那一段**更稳妥
- **GTID 模式下要加 `--skip-gtids`**，否则重放会被 GTID 去重而跳过

## 六、一句话总结

**备份三件事：选对工具（小库 dump / 大库 XtraBackup）、保证一致性（`--single-transaction` / redo log 前滚）、验证可恢复（定期真实演练）**；再配合 **binlog 做 PITR**，才算一套完整的"数据不丢"方案。""",
    ),
    (
        "MySQL",
        "权限,安全,SQL注入",
        2,
        r"""MySQL 的权限体系是怎样的？如何防范 SQL 注入？怎样做到最小权限？""",
        r"""## 一、权限体系（四层）⭐

```
全局级（*.*）  →  数据库级（db.*）  →  表级（db.t）  →  列级（db.t.col）
```

授权时按**最具体**的匹配生效；但**全局权限只能由全局 `REVOKE` 收回**（局部不能覆盖全局）。

```sql
-- 全局
GRANT SELECT, INSERT, UPDATE, DELETE ON *.* TO 'app'@'%';
-- 库级
GRANT ALL ON blogdb.* TO 'app'@'10.0.0.%';
-- 表级
GRANT SELECT ON blogdb.posts TO 'readonly'@'%';
-- 列级
GRANT SELECT (id, title) ON blogdb.posts TO 'reader'@'%';

-- 查看
SHOW GRANTS FOR 'app'@'%';
SELECT * FROM mysql.user WHERE user='app'\G
```

**关键权限说明** ⭐：

| 权限 | 说明 |
|---|---|
| `SELECT/INSERT/UPDATE/DELETE` | 基本 DML |
| `CREATE/DROP/ALTER/INDEX` | DDL |
| **`FILE`** | ⚠️ **能读写服务器任意文件**（`LOAD DATA INFILE`、`INTO OUTFILE`）→ **绝不能给应用账号** |
| **`PROCESS`** | 看所有连接（含其他用户）→ 慎给 |
| **`SUPER`** | 8.0 已拆分；能 kill 别人的连接、改全局变量 ⚠️ |
| **`GRANT OPTION`** | 能把自己权限再授权给别人 ⚠️ 慎给 |
| `EXECUTE` | 调用存储过程 |
| `RELOAD` | `FLUSH` 操作 |
| `REPLICATION CLIENT/SLAVE` | 复制相关 |

**账号格式 `'user'@'host'`** ⭐：`app'@'localhost'` 与 `'app'@'%'` 是**两个不同账号**（MySQL 支持同名不同 host）。认证时按 host 最具体的匹配。

**8.0 的变化**：`CREATE USER` 与 `GRANT` 分离（不再支持 `GRANT ... IDENTIFIED BY`）；引入 **角色（Role）**：

```sql
CREATE ROLE 'app_rw';
GRANT SELECT, INSERT, UPDATE, DELETE ON blogdb.* TO 'app_rw';
GRANT 'app_rw' TO 'app'@'%';
SET DEFAULT ROLE 'app_rw' TO 'app'@'%';
```

## 二、最小权限原则 ⭐

```
① 应用账号只给需要的库 + 需要的 DML 权限（通常 SELECT/INSERT/UPDATE/DELETE，不给 DDL）
② 限制来源：'app'@'10.0.0.%' 而不是 '%' ⭐（防外网爆破，也防内网横向）
③ 独立账号：不同服务用不同账号，便于审计与隔离（本项目：博客应用账号 ≠ 运维 root）
④ 不用 root 跑应用 ⚠️ 这是最基础也最常被违反的一条
⑤ 禁止 FILE / SUPER / GRANT OPTION / PROCESS 给应用账号
⑥ 只读副本用只读账号（SELECT + REPLICATION CLIENT）
⑦ 定期审计：SELECT user,host FROM mysql.user; 检查空密码账号、通配 host
```

**本项目踩过的坑** ⭐：README 里写了专用账号 `blog`，但服务器上**只有 root** → 导入种子 SQL 时命令失败。**正确做法**是按最小权限原则**真的创建**专用账号：

```sql
CREATE USER 'blog'@'localhost' IDENTIFIED BY '<强密码>';
GRANT SELECT, INSERT, UPDATE, DELETE ON blogdb.* TO 'blog'@'localhost';
FLUSH PRIVILEGES;
```

然后应用连接串改用 `blog`，而不是"图省事继续用 root"。

**检查权限是否合理**：

```sql
-- 列出所有账号与 host
SELECT user, host, plugin, account_locked FROM mysql.user ORDER BY user;
-- 找出空密码账号（危险）
SELECT user, host FROM mysql.user WHERE authentication_string = '';
-- 找出 host 为 % 的账号
SELECT user, host FROM mysql.user WHERE host = '%';
```

## 三、SQL 注入 ⭐

### 原理

```sql
-- 应用代码（❌ 字符串拼接）
std::string sql = "SELECT * FROM users WHERE name = '" + input + "'";
-- 用户输入：' OR '1'='1
-- 实际执行：SELECT * FROM users WHERE name = '' OR '1'='1'   ← 返回全表
```

**更危险的版本**：

```
输入：'; DROP TABLE posts; --
输入：' UNION SELECT user, authentication_string FROM mysql.user --
```

### 防御（按优先级）⭐

| # | 措施 | 说明 |
|---|---|---|
| **① 参数化查询 / 预处理语句** ⭐⭐ | **唯一根本解法**。SQL 结构与数据**分离编译**，数据永远只是"数据"，不会变成语法 |
| **② 白名单校验** | 表名、列名、排序方向（`ASC/DESC`）**无法参数化** → 必须用**白名单映射** ⭐ |
| **③ 转义** | 兜底手段。`mysql_real_escape_string()`（C API）/ `mysqli_real_escape_string`。**必须配合字符集正确设置**（连接字符集不对转义会失效）⭐ |
| **④ 最小权限** | 即使被注入，账号也没有 `FILE`/`DROP`/跨库权限 |
| **⑤ 错误信息不返回给用户** | 防信息泄露（表名、SQL 片段）|
| **⑥ WAF / 输入校验** | 辅助层，不能替代 ① |
| **⑦ 关闭多语句** | C API `mysql_real_connect` 时不要开 `CLIENT_MULTI_STATEMENTS` ⭐（本项目 Crow 场景要特别注意）|

### C API 的正确姿势 ⭐

**❌ 错误（字符串拼接）**：

```cpp
std::string q = "SELECT * FROM posts WHERE title LIKE '%" + kw + "%'";
mysql_query(conn, q.c_str());
```

**✅ 方式一：`mysql_real_escape_string` + 转义**

```cpp
char esc[1024];
unsigned long n = mysql_real_escape_string(conn, esc, kw.c_str(), kw.size());
// esc 里所有危险字符（' " \ NUL 等）都被加了反斜杠，长度至多 2n+1
std::string q = std::string("SELECT * FROM posts WHERE title LIKE '%") + esc + "%'";
```

**✅ 方式二：预处理语句（推荐）** ⭐

```cpp
MYSQL_STMT* stmt = mysql_stmt_init(conn);
mysql_stmt_prepare(stmt, "SELECT id, title FROM posts WHERE title LIKE ? AND status = ?", -1);

MYSQL_BIND bind[2] = {};
std::string like = "%" + kw + "%";
unsigned long len = like.size();
bind[0].buffer_type = MYSQL_TYPE_STRING;
bind[0].buffer = like.data();
bind[0].buffer_length = like.size();   // ⭐ 不写 buffer_length 会截断/出错
bind[0].length = &len;
int st = 1;
bind[1].buffer_type = MYSQL_TYPE_LONG;
bind[1].buffer = &st;

mysql_stmt_bind_param(stmt, bind);
mysql_stmt_execute(stmt);
// ... mysql_stmt_bind_result + mysql_stmt_fetch 读结果
mysql_stmt_close(stmt);
```

**预处理语句为什么安全**：占位符 `?` 在 `prepare` 阶段就确定了 SQL 的**语法结构**，`execute` 阶段传进来的值**只被当作数据**，永远不会被解析为语法。**这是原理层面的安全，而不是"过滤了多少危险字符"**。

### 无法参数化的部分怎么处理 ⭐

```cpp
// ❌ 错误：把表名拼进 SQL
std::string q = "SELECT * FROM " + table + " WHERE id = " + std::to_string(id);

// ✅ 正确：白名单映射
static const std::map<std::string, std::string> TABLES = {
    {"posts", "posts"}, {"comments", "comments"}, {"users", "users"}
};
auto it = TABLES.find(table);
if (it == TABLES.end()) return error("invalid table");
std::string q = "SELECT * FROM " + it->second + " WHERE id = ?";   // 值走参数化
```

**排序方向同理**：

```cpp
std::string dir = (order == "asc") ? "ASC" : "DESC";   // 只映射到两个常量
```

### `LIKE` 的通配符要额外转义 ⭐

```cpp
// 用户输入里的 % 和 _ 是 LIKE 的通配符，要转义成 \% 和 \_
// 否则用户输入 "%" 会匹配所有数据
std::string escapeLike(std::string s) {
    std::string r;
    for (char c : s) {
        if (c == '%' || c == '_' || c == '\\') r += '\\';
        r += c;
    }
    return r;
}
```

## 四、传输与存储安全 ⭐

| 项 | 措施 |
|---|---|
| **传输加密** | 开启 TLS：`require_secure_transport=ON`，`CREATE USER ... REQUIRE SSL` |
| **存储加密** | 表空间加密（`innodb_encrypt_tables=ON`）、文件系统加密、云盘加密 |
| **敏感字段** | 密码**加盐哈希**（bcrypt/argon2），不要明文/单轮 MD5 ⭐；手机号/身份证做脱敏或加密 |
| **审计** | `audit_log` 插件（企业版/Percona 开源版）、`general_log` 临时排查用（性能开销大）|
| **网络隔离** | MySQL 只监听内网/`bind-address=127.0.0.1`，**绝不暴露公网** ⭐ |
| **备份加密** | 备份文件本身含明文数据 |
| **CVE 与补丁** | 定期升级小版本（8.0.x 安全补丁）|

**脱敏查询时注意 `->>` 之类的函数不影响脱敏**：如果用视图做脱敏（`SELECT id, LEFT(phone,3)...`），别让应用有直接查基表的权限。

## 五、一句话总结

**权限 = 四层结构 + 最具体匹配 + 最小权限；SQL 注入的唯一根本解法是"参数化查询/预处理语句"（数据与语法分离），转义只是兜底，白名单负责解决"表名/列名/排序方向无法参数化"的部分。** 应用**绝不要用 root**，也**绝不要给 `FILE` 权限**。""",
    ),
    (
        "MySQL",
        "连接池,连接数,架构",
        2,
        r"""为什么要用数据库连接池？`max_connections` 该怎么设？连接数过高会有什么问题？""",
        r"""## 一、为什么需要连接池 ⭐

**一次 MySQL 连接的开销**：

| 阶段 | 开销 |
|---|---|
| **TCP 三次握手** | 1 个 RTT |
| **（如启用 TLS）握手** | 额外多个 RTT + 非对称加密运算 ⭐ 很贵 |
| **认证** | 密码哈希计算（`caching_sha2_password` 首次更贵）|
| **分配线程 + 会话内存** ⭐ | 每连接约 **200KB ~ 1MB**（`thread_stack`、`net_buffer`、`sort_buffer` 等按需分配）|
| **权限表查询** | 每次连接都要查权限 |

**结论**：如果每个请求都新建连接，**连接建立的开销可能远超 SQL 本身**。

**连接池的价值**：

```
① 复用连接 → 消除握手/认证/建线程的开销 ⭐
② 限流保护 → 上限固定，避免雪崩式打满数据库 ⭐
③ 统一管理 → 事务、超时、重试、监控集中在池层
④ 削峰 → 请求排队而不是压垮数据库
```

## 二、连接池的关键参数 ⭐

| 参数 | 作用 | 建议 |
|---|---|---|
| **`min_idle` / `minimumIdle`** | 最小空闲连接（预热）| 5~10，避免冷启动抖动 |
| **`max_pool_size` / `maximumPoolSize`** ⭐ | **池上限** | 见下方计算 |
| **`connectionTimeout`** | 从池取连接的超时（**不是 SQL 超时**）| 1~3s，快速失败 ⭐ |
| **`idleTimeout`** | 空闲连接回收时间 | 10~30min，**必须小于 MySQL 的 `wait_timeout`** ⭐ |
| **`maxLifetime`** | 连接最大存活时间 | **比 `wait_timeout` 短 30s~1min** ⭐ 防止用被服务端杀掉的连接 |
| **`validationQuery`** | 借出前校验（`SELECT 1`）| 或依赖 `keepalive` |
| **`leakDetectionThreshold`** | 连接泄漏检测（超时未归还告警）| 生产必开 ⭐ |

**`maxLifetime` vs `wait_timeout` 的关系（高频事故）** ⭐：

```
MySQL wait_timeout = 28800（8h，默认）
池 maxLifetime     = 30min     ← ✅ 短于服务端，池主动回收，不会用到死连接
若 maxLifetime > wait_timeout  → 池里的连接被服务端悄悄断开 → 应用拿到"死连接"报错
   通信异常 / Communications link failure / MySQL server has gone away
```

## 三、`max_connections` 怎么设 ⭐

**核心：不是越大越好。**

**内存角度**：

```
每连接内存 ≈ thread_stack + net_buffer_length + 按需的 sort/join/read/write buffer
典型估算：200KB ~ 1MB（取决于查询复杂度）

max_connections × 每连接内存 必须 < 可用内存，且要给 Buffer Pool 留足
例：16GB 内存
   innodb_buffer_pool_size = 10GB
   剩余 ~5GB 给连接和系统
   若每连接 1MB → max_connections 可设 2000~4000
   若查询常用大 sort_buffer（4MB）→ 每连接可能 10MB+ → 只能设几百 ⚠️
```

**并发角度**：

```
经验值：
  小型应用（单机）      → 100 ~ 300
  中型应用（连接池）    → 500 ~ 1000
  大型/多应用共享       → 1000 ~ 2000，但必须配合连接池

更重要的公式：max_connections ≈ Σ(各应用连接池 max_pool_size) × 1.5（留余量）
```

**反直觉的事实** ⭐：**连接数过多会降低总吞吐**。

```
① 每个活跃连接 = 一个线程 → 线程被 OS 调度 → 上下文切换开销 ⭐
   （MySQL 处理查询的活跃连接，超过核数×2 就开始互相抢 CPU）
② 线程争抢互斥量/锁 → latch 竞争（buf_pool mutex、trx sys mutex）
③ 内存膨胀 → 可能触发 swap → 性能断崖式下跌
④ 大量连接各自持有事务 → undo 版本链长、锁等待多 → 死锁概率上升
```

**所以现代实践是**：**少量长连接 + 连接池排队**。多进程/多线程应用共享一个池，而不是"每个线程一个连接"。

**监控**：

```sql
SHOW STATUS LIKE 'Threads_connected';    -- 当前连接数
SHOW STATUS LIKE 'Threads_running';      -- 正在执行的（这个更关键）⭐
SHOW STATUS LIKE 'Threads_created';      -- 累计创建的线程数
SHOW STATUS LIKE 'Max_used_connections'; -- 历史峰值 ⭐
SHOW VARIABLES LIKE 'max_connections';
SHOW VARIABLES LIKE '%timeout%';         -- wait_timeout / interactive_timeout
SHOW PROCESSLIST;                        -- 当前所有连接
```

**判断连接数是否合理**：

```
Max_used_connections / max_connections   < 85%  → 合理
Max_used_connections / max_connections   > 85%  → 需要扩容或加池 ⭐
Threads_running 长期 > 核数 × 2           → CPU 争抢，需要优化 SQL 而不是加连接
Threads_created 持续快速增长              → 连接没有复用（池失效或 maxLifetime 太短）
```

## 四、常见连接问题与排查 ⭐

| 现象 | 原因 | 解决 |
|---|---|---|
| `Too many connections` | 连接打满 | 加池 / 缩短事务 / 检查泄漏；临时用 `SUPER` 账号登录（8.0 保留 1 个给 `CONNECTION_ADMIN`）|
| `MySQL server has gone away` | 用了被 `wait_timeout` 断开的连接；或包太大（`max_allowed_packet`）| 池 `maxLifetime` < `wait_timeout`；调大 `max_allowed_packet` ⭐ |
| **连接泄漏** | 代码里 `conn.close()` 没执行（异常路径）| 用 **RAII/`try-with-resources`** 保证归还 ⭐ |
| 连接建立慢 | DNS 反查、TLS 握手 | `skip-name-resolve`、会话复用 |
| `Lock wait timeout` | 长事务持锁 | 缩短事务 |
| 空闲连接被回收后报错 | 池没做校验 | 开 `testOnBorrow`（有开销）或 `keepalive` |

**C++ 侧的 RAII 连接守卫**（本项目 Crow 场景）⭐：

```cpp
class ConnGuard {
    MYSQL* c_;
    std::function<void(MYSQL*)> release_;
public:
    ConnGuard(MYSQL* c, std::function<void(MYSQL*)> rel) : c_(c), release_(std::move(rel)) {}
    ~ConnGuard() { if (c_) release_(c_); }              // 异常也归还
    MYSQL* get() const { return c_; }
    ConnGuard(const ConnGuard&) = delete;
    ConnGuard& operator=(const ConnGuard&) = delete;     // 防重复归还
};
```

## 五、连接池之外的相关配置

| 参数 | 说明 |
|---|---|
| `wait_timeout` / `interactive_timeout` | 空闲连接超时（默认 28800s）；调小可回收僵尸连接 |
| `max_allowed_packet` | 单包上限（默认 64MB / 4MB）；大 BLOB 场景要调大 ⭐ |
| `back_log` | TCP 连接队列长度（listen backlog），短时高并发需调大 |
| `thread_cache_size` | 线程缓存（复用，省创建开销）|
| `skip-name-resolve` | 跳过 DNS 反查，加速连接 ⭐ |
| `max_connect_errors` | 连接失败次数上限（超过会封 host）|

**`Aborted_connects` / `Aborted_clients`** 的监控：

```sql
SHOW STATUS LIKE 'Aborted_connects';   -- 握手阶段失败（认证失败、超时）
SHOW STATUS LIKE 'Aborted_clients';    -- 已建立但非正常断开（客户端没 quit、超时）
```

这两个值持续增长 → 网络问题或连接管理有问题。

## 六、一句话总结

**连接池的核心是"复用 + 限流"**；`max_connections` 必须按**内存 + 核数**估算而不是拍脑袋，**连接不是越多越好**（超过核数×2 就开始负收益）；最常见的两个坑是 **`maxLifetime` 没短于 `wait_timeout`** 和 **连接泄漏（要用 RAII 保证归还）**。""",
    ),
    (
        "MySQL",
        "表设计,范式,字段类型",
        1,
        r"""数据库表设计有哪些规范？金额、时间、状态、布尔值这些字段该用什么类型？""",
        r"""## 一、范式与反范式 ⭐

| 范式 | 要求 | 目的 |
|---|---|---|
| **1NF** | 每列**原子**（不可再分），无重复组 | 消除"一个格子里放列表" |
| **2NF** | 消除**部分依赖**（非主键列不依赖主键的一部分）| 联合主键场景 |
| **3NF** | 消除**传递依赖**（非主键列不依赖其他非主键列）| 消除冗余 |

**实践**：**OLTP 一般做到 3NF，再适度反范式**。

**为什么需要反范式** ⭐：
- 冗余字段（如订单表里存 `user_name`）**避免 JOIN**，提升读性能。
- **代价**：更新时要保证一致（事务内一起改，或异步同步），存在**数据不一致窗口**。

**判断标准**：这个冗余字段会被**高频读**、**极少改**吗？是 → 可以冗余；否 → 老老实实 JOIN。

## 二、字段类型选择 ⭐

### 整数

| 类型 | 字节 | 范围 |
|---|---|---|
| `TINYINT` | 1 | -128~127（unsigned 0~255）|
| `SMALLINT` | 2 | ±3.2万 |
| `MEDIUMINT` | 3 | ±838万 |
| **`INT`** | 4 | ±21亿 |
| **`BIGINT`** | 8 | ±922亿亿 |

**原则**：**选能覆盖业务最大值的"最小"类型**（省空间 → 页能放更多行 → IO 更少）。

**常见陷阱**：
- `INT` 只到 21 亿 → **自增主键用到 21 亿就爆**（大表要考虑 `BIGINT`）⭐
- `INT(11)` 的 `11` **不是长度限制**，只是**显示宽度**（`ZEROFILL` 才有意义）⭐ 8.0 已弃用该语法。

### 金额 ⭐（面试高频）

| 类型 | 评价 |
|---|---|
| **`DECIMAL(M,D)`** ⭐ | **推荐**。定点数，精确存储，无浮点误差。金额用 `DECIMAL(18,2)` |
| `FLOAT` / `DOUBLE` | ❌ **禁用**。二进制浮点有精度误差（`0.1+0.2 != 0.3`），累加会漂移 |
| `BIGINT`（存"分"）⭐ | 也推荐。用整数存最小货币单位（分/厘），避免精度问题且运算快 |
| `VARCHAR` 存数字 | ❌ 无法比较大小、无法算术 |

```sql
amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00   -- 以元为单位
-- 或
amount_fen BIGINT NOT NULL DEFAULT 0          -- 以分为单位，应用侧换算
```

**取舍**：`DECIMAL` 直观但运算略慢；`BIGINT` 快但要在应用层处理单位。**两者都对，绝不能选浮点**。

### 时间 ⭐

| 类型 | 范围 | 时区 | 建议 |
|---|---|---|---|
| **`DATETIME`** ⭐ | 1000~9999 年 | **不受时区影响**（存字面值）| **推荐** |
| **`TIMESTAMP`** | 1970~2038 年（**2038 问题**）| 存 UTC，按 `time_zone` 转换显示 | 需要自动时区转换时用 |
| `DATE` | 日期 | — | 只关心日期 |
| `TIME` | 时间 | — | |
| `BIGINT`（时间戳）| 2038 之后也行 | 无时区语义 | 跨时区系统或需要精确排序 |

**关键选择** ⭐：

```sql
-- 推荐：DATETIME(3) 存毫秒精度，不受时区影响，语义明确
created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)

-- ✅ 好的实践：
--   ① 库里统一存 UTC 或统一存业务时区的本地时间（二选一，全库一致）
--   ② 应用层负责时区转换
--   ③ 用 DATETIME(3) 而不是 DATETIME（毫秒精度在并发排序时很重要）

-- ❌ 避免：
--   ① 混用 DATETIME 和 TIMESTAMP
--   ② 用 VARCHAR 存时间（无法比较、无法索引有序）
--   ③ 用 TIMESTAMP 存"未来久远的时间"（2038 溢出）
```

**`TIMESTAMP` 的自动行为**（容易踩坑）：`TIMESTAMP` 列默认有 `DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP`，即**每次 UPDATE 都会自动改**（除非显式设为 NULL）⭐

### 状态 / 枚举

| 方案 | 优点 | 缺点 |
|---|---|---|
| **`TINYINT`** ⭐ | 省空间、快、**易扩展**（加状态不用 DDL）| 语义不直观（要靠文档/常量）|
| `ENUM` | 语义清晰、省空间 | **加值要 DDL**（`ALTER TABLE`）⭐、排序按定义顺序、跨库迁移难 |
| `VARCHAR` | 可读性最好 | 占空间大、比较慢 |

```sql
-- 推荐：TINYINT + 应用层常量/字典表
status TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0待支付 1已支付 2已发货 3已完成 4已取消'

-- 用字典表更规范（可做外键、可在后台维护）
CREATE TABLE dict_order_status (code TINYINT PRIMARY KEY, name VARCHAR(20) NOT NULL);
```

**`comment` 一定要写** ⭐ 这是最便宜的文档。

### 布尔值

```sql
is_deleted TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0否 1是'
-- MySQL 里 BOOL/BOOLEAN 就是 TINYINT(1) 的别名，没有真正的布尔类型
```

**软删除设计** ⭐：

```sql
-- 简单方案
is_deleted TINYINT NOT NULL DEFAULT 0,
KEY idx_deleted (is_deleted)

-- 更好：用"删除时间"，既能表示删除，又保留信息
deleted_at DATETIME(3) NULL DEFAULT NULL,
KEY idx_deleted (deleted_at)
-- 查询：WHERE deleted_at IS NULL
```

**注意**：软删除 + 唯一索引冲突 ⭐ —— `username` 唯一索引下，删掉用户后无法再注册同名。解法：唯一索引改为 `(username, deleted_at)`，删除时把 `deleted_at` 设为时间（而不是 NULL）。

### 字符串

| 类型 | 说明 |
|---|---|
| **`VARCHAR(n)`** ⭐ | 变长。`n` 是**字符数**（utf8mb4 下最多 16383，实际受行大小 65535 限制）|
| `CHAR(n)` | 定长，适合**长度固定**的短串（MD5 32 位、UUID、国家代码）；**没有变长头开销** |
| **`TEXT`** | 长文本，**不能有默认值**、只能用前缀索引 |
| **`BLOB`** | 二进制 |

**原则**：
- **长度按实际需求**，不要全用 `VARCHAR(255)`（`ORDER BY`/临时表会按最大长度分配内存 ⭐）
- 需要索引的列要受限（utf8mb4 索引前缀上限 3072 字节）
- 大文本/二进制**拆到独立表**（见"行格式"那题）

### 主键

```sql
id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY
```

**推荐规范**：
- **`BIGINT UNSIGNED`** 自增（`UNSIGNED` 用完另一半空间；`BIGINT` 防 21 亿溢出）
- **不用 `UUID`**（页分裂 + 索引膨胀）
- **业务主键**（如手机号、身份证）**单独建唯一索引**，不要当主键

## 三、表设计规范清单 ⭐

| 规范 | 说明 |
|---|---|
| **必须有主键** | InnoDB 按主键组织数据；无主键会用隐藏 row_id |
| **必须有 `created_at` / `updated_at`** | 排查问题时是救命信息 |
| **`NOT NULL` + `DEFAULT`** | NULL 会让索引统计复杂、`COUNT(col)` 慢、`NOT IN` 失效 ⭐ |
| **每列写 `COMMENT`** | 最便宜的文档 |
| **字段数控制在 20~30 以内** | 太多考虑垂直拆表 |
| **单表行数控制** | 500万~2000万，再大考虑归档/分片 |
| **统一命名** | 全小写 + 下划线；表名用单数还是复数要**全库统一** |
| **枚举值用 `TINYINT` + 字典表/注释** | 不用 `ENUM` |
| **金额用 `DECIMAL` 或分单位 `BIGINT`** | 绝不用浮点 |
| **不用外键**（互联网业务）| 用应用层保证，外键在高并发下有锁和性能问题 ⭐ |
| **索引命名统一** | `idx_表名_列名`、`uk_表名_列名`、`fk_...` |
| **预留扩展** | 少量 `ext` JSON 字段，或提前想好垂直拆表边界 |

## 四、几张常见表的参考设计

```sql
-- 用户表
CREATE TABLE users (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username     VARCHAR(32)  NOT NULL COMMENT '用户名，唯一',
    pass_hash    CHAR(60)     NOT NULL COMMENT 'bcrypt 哈希',
    phone        VARCHAR(20)  NULL     COMMENT '手机号，加密存储',
    status       TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1正常 2禁用',
    deleted_at   DATETIME(3)  NULL     DEFAULT NULL COMMENT '软删除时间',
    created_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username, deleted_at),
    KEY idx_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 文章表（本项目场景）
CREATE TABLE posts (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    title      VARCHAR(200) NOT NULL,
    summary    VARCHAR(500) NOT NULL DEFAULT '' COMMENT '列表页摘要，避免列表页读 content',
    content    MEDIUMTEXT   NULL COMMENT '正文 markdown',
    category   VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '分类',
    views      INT UNSIGNED NOT NULL DEFAULT 0,
    status     TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0草稿 1已发布',
    created_at DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_posts_status_created (status, created_at),
    KEY idx_posts_category (category),
    FULLTEXT KEY ft_posts (title, summary)    -- 若要全文检索
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

**注意 `summary` 的设计** ⭐：列表页只读 `summary` 不读 `content` → 避免把 `MEDIUMTEXT` 一起读出来（溢出页 IO），这是很实用的优化。

## 五、一句话总结

**表设计的核心是"选最小的类型 + 明确的约束（NOT NULL/COMMENT）+ 合适的主键"**；金额用 `DECIMAL` 或分单位整数，时间用 `DATETIME(3)`，状态用 `TINYINT` + 注释/字典表，布尔用 `TINYINT(1)`；**适度反范式换读性能**，但冗余字段必须有明确的一致性维护策略。""",
    ),
    (
        "MySQL",
        "读写分离,一致性,架构",
        2,
        r"""读写分离是怎么实现的？主从延迟导致"写完立刻读读不到"怎么办？""",
        r"""## 一、实现层次 ⭐

| 层次 | 方案 | 特点 |
|---|---|---|
| **代码层** | 手动指定数据源（写走主库、读走从库）| 灵活但侵入业务 |
| **中间件层** ⭐ | **ProxySQL**、MyCat、ShardingSphere-Proxy、MySQL Router | 应用无感，可动态调整 |
| **驱动层** | ShardingSphere-JDBC、动态数据源 | 有语言绑定 |
| **云服务层** | RDS 的读写分离地址（自带延迟感知）| 最省事 |

**路由规则**：

```
写操作（INSERT/UPDATE/DELETE/DDL）  → 主库
读操作（SELECT）                    → 从库（轮询/权重）
事务内                              → 全部走主库 ⭐（否则事务里的读可能读不到自己刚写的数据）
```

## 二、核心问题：主从延迟 ⭐

**现象**：

```
T0: 用户在主库注册，INSERT users  ← 主库立即返回成功
T1: 应用跳转到"个人中心"，SELECT ... → 走从库 → 从库还没重放 → 查不到 ⭐
   用户看到"用户不存在"
```

**根因**：异步复制的 IO/SQL 线程是滞后的（见"主从复制"题）。

## 三、解决方案（按推荐度）⭐

### ① 写后立即读走主库（最简单有效）⭐⭐

```
标记"这个请求刚写过" → 之后 N 秒内该会话的所有读都走主库
实现方式：
  · 会话粘性（同一次 HTTP 请求/同一个用户会话内刚写过 → 全走主库）
  · Redis 记录 user_id → 最后一次写时间，读之前先问一下
  · Cookie/Session 里带"刚写过"标记
```

**这是绝大多数互联网公司的实际做法**，比"强一致读"简单得多。

### ② 强制走主库（`/* master */` 注释）

```sql
SELECT /* master */ * FROM users WHERE id = 1;
```
中间件（如 ProxySQL、ShardingSphere）识别注释后强制路由到主库。

### ③ 判断 GTID 是否已重放（精确）⭐

```sql
-- 主库返回 GTID，从库检查自己是否已执行
SELECT WAIT_FOR_EXECUTED_GTID_SET('3E11FA47-71CA-11E1-9E33-C80AA9429562:1-5', 5);
--                                                  ↑ GTID 集合        ↑ 超时秒数
```

或比较位点：

```sql
-- 主库：SHOW MASTER STATUS → file + pos
-- 从库：SHOW SLAVE STATUS → Master_Log_File, Read_Master_Log_Pos 是否 >= 目标位点
```

### ④ 半同步复制 / MGR

要求主库等从库**确认收到**再返回 → 延迟窗口变小但**不能消除**（因为"收到"不等于"重放完"）⭐

**半同步的语义**：`AFTER_SYNC`（默认，等从库 ack 后才向客户端确认提交）比 `AFTER_COMMIT` 更安全。

### ⑤ 用缓存挡一下

写完后立刻写缓存（Cache-Aside）；读先读缓存 → 绕过从库延迟。

## 四、中间件延迟感知（ProxySQL）⭐

```sql
-- ProxySQL 配置：延迟超过 5s 的从库不再接收读流量
UPDATE mysql_replication_hostgroups
  SET max_replication_lag = 5
  WHERE writer_hostgroup = 10 AND reader_hostgroup = 20;
LOAD MYSQL SERVERS TO RUNTIME; SAVE MYSQL SERVERS TO DISK;
```

效果：**某个从库延迟大时自动把它踢出读池**，延迟恢复后再自动加回。这是生产环境的标配。

## 五、读写分离带来的其他问题

| 问题 | 说明 | 解决 |
|---|---|---|
| **延迟** | 见上 | 写后读主 / 延迟感知 |
| **事务一致性** ⭐ | 事务内混用主从会读到不一致 | **事务内全走主库** ⭐ |
| **从库资源争抢** | 从库还要跑备份/统计 | 分离出专用从库 |
| **故障切换** | 主库挂了要选新主 | MHA/Orchestrator/MGR |
| **连接数翻倍** | 主库+从库各自都要连接池 | 分别配置池 |
| **代理成为单点** | ProxySQL 挂了全站不可用 | ProxySQL 集群 + VIP |

## 六、架构演进路径 ⭐

```
阶段 1：单机（应用 + MySQL 同机）        ← 本项目当前
阶段 2：单机 MySQL + 定时备份            ← 低成本的第一道保险 ⭐
阶段 3：主从复制 + 读写分离（读扩展）
阶段 4：主从 + 从库只读 + 延迟感知中间件
阶段 5：MGR / 云 RDS 高可用版
阶段 6：分库分表 / NewSQL（TiDB）
```

**关键提醒**：**读写分离是"读扩展"方案，不是"写扩展"方案，也不是高可用方案**。它不能解决写瓶颈，也不能在毫秒级完成选主。**高可用请单独做**（MHA/Orchestrator/MGR）。

**一句话总结**：**读写分离实现不难，难的是"写完立刻读"**；最实用的解法是"**写后一段时间内走主库**"，其次是"**中间件延迟感知**"，精确校验（GTID 等待）只在关键路径上用。""",
    ),
    (
        "MySQL",
        "高可用,MHA,MGR,故障切换",
        3,
        r"""MySQL 高可用方案有哪些？主库故障时如何自动切换？""",
        r"""## 一、高可用的两个核心问题 ⭐

```
① 故障检测：怎么知道主库真的挂了（而不是网络抖动）？
② 选主与切换：谁来接管？怎么让应用无感？
```

**难点不在"切换"，而在"防脑裂（split-brain）"** ⭐ —— 网络分区时，两边都以为自己是主，会产生双主写入 → 数据冲突。

## 二、主要方案对比 ⭐

| 方案 | 原理 | RPO | RTO | 复杂度 | 适用 |
|---|---|---|---|---|---|
| **主从 + 手动切换** | 人工 | 有丢数据 | 分钟~小时 | 极低 | 小站/内部系统 ⭐ |
| **MHA** | 管理节点 + SSH 探测，选最完整的从库提升 | 近 0（配合半同步）| 10~30s | 中 | 传统主流（已停止维护）|
| **Orchestrator** | 探测 + 拓扑管理 + 自动/手动切换 | 近 0 | 秒级 | 中 | MHA 的现代替代 ⭐ |
| **MGR（组复制）** | Paxos 多数派，原生多主/单主 | **0**（强一致）| 秒级 | 中高 | 8.0 推荐 ⭐ |
| **PXC（Percona XtraDB Cluster）** | Galera 同步复制，多主 | 0 | 秒级 | 高 | 对写延迟敏感场景差 |
| **云 RDS 高可用版** | 厂商提供主备/多可用区 | 近 0 | 秒~分钟 | **极低** | 推荐 ⭐ |
| **ProxySQL + 编排脚本** | 代理层路由 + 健康检查 | 视复制方式 | 秒级 | 中 | 需自研 |
| **Keepalived + VIP** | 虚拟 IP 漂移 | — | 秒级 | 低 | 只解决"入口"，不解决"选主" ⚠️ |

## 三、MHA 的工作方式

```
       [MHA Manager]  ← 部署在独立机器，SSH 到所有节点
            │ 每 3 秒 ping 主库
            ↓
    [Master] ──复制──> [Slave1] 
                        [Slave2]
                        [Slave3]
```

**切换流程**：

```
① Manager 探测到 Master 无响应
② 尝试用 SSH 确认（避免误判）；若 SSH 可达 → 认为只是 MySQL 挂了，做"在线切换"
③ 从所有 Slave 中挑选：
   - 优先级（candidate_master=1）
   - binlog 位点最新（数据最完整）⭐
④ 把选中的 Slave 的 relay log 里未应用的部分补齐（save/apply relay log）
⑤ 提升为 Master，其他 Slave 用 CHANGE MASTER 指向新主
⑥ 通过 VIP 漂移或 ProxySQL 更新路由，让应用指向新主
⑦ 原 Master 恢复后自动作为 Slave 加入
```

**MHA 的问题**：依赖 SSH、无脑裂保护（需配合 VIP 或仲裁）、**已停止维护**（作者转做 Orchestrator 思路）。**新项目不推荐**。

## 四、Orchestrator（推荐）⭐

**优势**：

| 特性 | 说明 |
|---|---|
| **拓扑感知** | 用 SQL 探测（不需要 SSH）⭐ 更适合云环境/容器 |
| **RAFT 模式** | 多节点部署 Orchestrator，避免管理节点单点 |
| **灵活切换** | Web UI 一键切换、自动切换可选 |
| **支持多种拓扑** | 一主多从、多级复制、双主 |
| **钩子** | 切换后回调（更新 VIP、ProxySQL、发通知）⭐ |
| **检测更准** | 结合 `SHOW SLAVE STATUS` 判断真实延迟 |

这是 MHA 的实际替代品，社区活跃。

## 五、MGR（MySQL Group Replication）⭐

**原理**：基于 **Paxos 变体**（XCom），组内每个成员都参与投票，**多数派确认后事务才提交**。

**两种模式**：

| 模式 | 说明 |
|---|---|
| **单主模式（默认）** | 一个 Primary 写，其他 Secondary 只读；Primary 故障自动选举 |
| **多主模式** | 所有节点可写（**必须处理冲突**，业务难写）|

**关键特性**：

```
① 强一致性：多数派确认（RPO = 0，不丢已确认事务）⭐
② 自动选主：内置，不需要外部工具 ⭐
③ 成员自动加入/退出
④ 冲突检测：多主模式下乐观检测，冲突则回滚
⑤ 与 MySQL Shell / InnoDB Cluster 配合：一键部署、一键加节点
```

**配置要点**：

```sql
-- 必须用 GTID + ROW binlog + 唯一 server_id
gtid_mode = ON
enforce_gtid_consistency = ON
binlog_checksum = NONE
log_slave_updates = ON
binlog_format = ROW
-- 组内通信
group_replication_group_name = "aaaaaaaa-...-aaaa"
group_replication_start_on_boot = OFF
group_replication_local_address = "10.0.0.1:33061"
group_replication_group_seeds = "10.0.0.1:33061,10.0.0.2:33061,10.0.0.3:33061"
group_replication_single_primary_mode = ON
```

**启动：`START GROUP_REPLICATION;`** —— **注意：要求 `binlog_checksum=NONE`，这是最常见的启动失败原因** ⭐

**MGR 的限制** ⚠️：

| 限制 | 说明 |
|---|---|
| **表必须有主键** | 否则无法做冲突检测（认证）→ 报错 |
| **不支持外键** | 组复制环境下外键行为不可靠 |
| **不支持 `SERIALIZABLE` 的部分场景** | |
| **大事务是灾难** ⭐ | 事务太大超过 `group_replication_transaction_size_limit` 会被拒绝（默认 150MB）；且大事务会阻塞整组 |
| **DDL 要 `group_replication_consistency` 配合** | 8.0.27+ 才有更好的 DDL 一致性 |
| **写延迟** | 多数派确认要等网络往返 → **跨机房部署延迟显著** ⭐ |

## 六、Keepalived + VIP 的角色定位 ⚠️

**Keepalived 只解决"入口漂移"**（虚拟 IP 从旧主漂到新主），**不解决"谁来当新主"**。

```conf
vrrp_instance VI_1 {
    state BACKUP
    interface eth0
    virtual_router_id 51
    priority 100
    advert_int 1
    virtual_ipaddress { 10.0.0.100/24 }
    notify_master "/usr/local/bin/failover.sh"    # ⭐ 在脚本里做选主
}
```

**正确组合**：`Orchestrator（选主）+ Keepalived/VIP（入口）+ ProxySQL（路由）`

## 七、脑裂（Split-Brain）防范 ⭐

```
场景：主库与从库之间网络断了，但主库本身正常
      · 从库侧以为主库挂了 → 提升自己为新主
      · 主库侧仍在自己写
      → 两个"主"同时接受写入 → 数据冲突 ❌
```

**防范手段**：

| 手段 | 说明 |
|---|---|
| **仲裁节点（Witness）** | 奇数个节点，多数派才能决策 ⭐（MGR 天然具备）|
| **STONITH（Shoot The Other Node In The Head）** | 切换前先强制关闭旧主（fencing）⭐ |
| **只有多数派可见时才能当主** | MGR、PXC 的机制 |
| **代理层只允许一个写节点** | ProxySQL 的 `writer_hostgroup` 只有一个成员 ⭐ |
| **`read_only=ON` + `super_read_only=ON`** | 从库默认只读，即使误操作也不接受写 ⭐ |
| **应用层双主检测** | 写入时校验 `@@server_id` / `@@hostname` |
| **半同步 + 超时降级** | 减少"已提交但未同步"的窗口 |

**`super_read_only` 的重要作用**：`read_only=ON` 只阻止普通用户写，**`SUPER` 用户仍可写**；`super_read_only=ON` 连 SUPER 也阻止（除了复制线程）⭐ 从库一定要开这个。

## 八、灾难恢复的完整体系 ⭐

```
层次            措施                                     RPO/RTO
────────────────────────────────────────────────────────────────
① 单机          备份 + binlog PITR                       分钟~小时
② 主从          从库可提升                              秒~分钟
③ 高可用        自动选主（MGR/Orchestrator）             秒级 ⭐
④ 跨机房        同城双活 / 异地多活                      秒级
⑤ 云服务        多可用区 RDS + 只读实例                 秒~分钟（托管）
⑥ 终极          "数据可重建"（消息队列 + 幂等重放）⭐     0
```

**"终极方案"的思路** ⭐：核心业务写操作先进 MQ/MQ-like 的持久化日志（如 Kafka），DB 只是"物化视图"，DB 挂了可以从日志重建。这是真正的 RPO=0 做法，但对架构改造成本高。

## 九、选型建议 ⭐

| 场景 | 推荐 |
|---|---|
| 小站/内部系统（本项目）| **主从 + 手动切换 + 定时备份** ✅ 成本最低、最可控 |
| 一般互联网业务 | **云 RDS 高可用版**（最省事）或 **Orchestrator + ProxySQL** |
| 要求强一致 | **MGR / 云 RDS 三节点** |
| 已有云资源 | 直接用云托管，不要自建高可用 ⭐ |

**一句话总结**：**高可用的难点是"防脑裂"而不是"切换"**；技术上 **MGR（原生、强一致）> Orchestrator（灵活、成熟）> MHA（已过时）**，但**对绝大多数业务，云 RDS 高可用版 + 主从 + 备份 是性价比最高的组合**。""",
    ),
    (
        "MySQL",
        "诊断,InnoDB STATUS,监控",
        3,
        r"""`SHOW ENGINE INNODB STATUS` 的输出怎么读？遇到性能问题应该重点看哪些段落？""",
        r"""## 一、输出结构（按顺序）⭐

```
=====================================
2024-05-01 10:00:00 0x7f... INNODB MONITOR OUTPUT
=====================================
Per second averages calculated from the last 56 seconds
-----------------
BACKGROUND THREAD          ← 后台线程信息
-----------------
SEMAPHORES                 ← 信号量/等待（锁竞争）⭐
-----------------
LATEST FOREIGN KEY ERROR   ← 最近的外键错误
-----------------
LATEST DETECTED DEADLOCK   ← 最近一次死锁 ⭐
-----------------
TRANSACTIONS               ← 活跃事务 + 历史事务列表 ⭐
-----------------
FILE I/O                   ← IO 线程与待处理 IO ⭐
-----------------
INSERT BUFFER AND ADAPTIVE HASH INDEX
-----------------
LOG                        ← redo log 状态 ⭐
-----------------
BUFFER POOL AND MEMORY     ← Buffer Pool 命中率 ⭐
-----------------
ROW OPERATIONS             ← 行操作统计
-----------------
END OF INNODB MONITOR OUTPUT
```

## 二、重点段落逐一解读 ⭐

### ① SEMAPHORES —— 锁竞争 ⭐

```
SEMAPHORES
----------
OS WAIT ARRAY INFO: reservation count 15123
OS WAIT ARRAY INFO: signal count 13000
-- 若 reservation count 远大于 signal count → 等待多，可能有 latch 竞争 ⭐

Mutex spin waits 0, rounds 0, OS waits 0
RW-shared spins 0, rounds 0, OS waits 0
RW-excl spins 0, rounds 0, OS waits 0

-- 有竞争时会显示：
-- 例如 btr_search_latch 或 buf_pool->mutex
```

**判断**：`OS waits` 数值很大 → 内核态等待多（说明自旋没等到）→ **latch 竞争严重**。常见于：
- `buf_pool->mutex`：Buffer Pool 实例太少（调大 `innodb_buffer_pool_instances`）⭐
- `btr_search_latch`：自适应哈希索引竞争（可尝试 `innodb_adaptive_hash_index=OFF`）
- `lock_sys`：行锁竞争（`innodb_thread_concurrency` 或优化 SQL）

### ② LATEST DETECTED DEADLOCK —— 死锁现场 ⭐

```
------------------------
LATEST DETECTED DEADLOCK
------------------------
2024-05-01 09:59:00 0x7f...
*** (1) TRANSACTION:                 ← 事务 1
TRANSACTION 12345, ACTIVE 3 sec starting index read
mysql tables in use 1, locked 1
LOCK WAIT 2 lock struct(s), heap size 1136, 1 row lock(s)
MySQL thread id 100, OS thread handle 123, query id 456 localhost app updating
UPDATE t SET v=1 WHERE id=2         ← 它在等什么锁
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
RECORD LOCKS space id 5 page no 3 n bits 72 index PRIMARY of table `db`.`t`
trx id 12345 lock_mode X locks rec but not gap waiting
Record lock, heap no 2 PHYSICAL RECORD: n_fields 4; ...

*** (2) TRANSACTION:                 ← 事务 2
...
UPDATE t SET v=1 WHERE id=1
*** (2) HOLDS THE LOCK(S):           ← 它持有什么锁
RECORD LOCKS ... lock_mode X locks rec but not gap
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
...

*** WE ROLL BACK TRANSACTION (1)     ← 回滚了谁
```

**读法**：
1. 看两个事务**各自的 SQL** → 找出"访问顺序相反"的模式 ⭐
2. 看 `HOLDS THE LOCK(S)` 和 `WAITING FOR THIS LOCK` → 确认锁的**索引、页、模式**（`lock_mode X` = 排他，`locks gap before rec` = 间隙锁）
3. `WE ROLL BACK TRANSACTION (n)` → 知道谁是牺牲者

**默认只保留最后一次**；`innodb_print_all_deadlocks=ON` 可把所有死锁写入 error log ⭐

### ③ TRANSACTIONS —— 长事务 ⭐

```
TRANSACTIONS
------------
Trx id counter 123456
Purge done for trx's n:o < 123400 undo n:o < 0 state: running
History list length 0            ← ⭐ 关键指标！未 purge 的 undo 数量

---TRANSACTION 123450, ACTIVE 3600 sec     ← ⭐ ACTIVE 3600 秒 = 长事务！
2 lock struct(s), heap size 1136, 1 row lock(s), undo log entries 1
MySQL thread id 100, OS thread handle ..., query id ... 
Trx read view will not see trx with id >= 123451, sees < 123451   ← ⭐ 快照信息
```

**关键指标解读**：

| 指标 | 含义 | 危险阈值 |
|---|---|---|
| **`History list length`** ⭐ | 未 purge 的 undo 记录数 | **> 10000 要关注，> 100000 危险**（说明有长事务卡住了 purge）|
| **`ACTIVE N sec`** | 事务存活时长 | **> 60s 值得查，> 600s 必须处理** ⭐ |
| `undo log entries` | 该事务产生的 undo 数量 | 很大 → 大事务 |

**发现长事务的处理**：

```sql
SELECT trx_id, trx_started, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS sec,
       trx_state, trx_mysql_thread_id, trx_query
FROM information_schema.innodb_trx ORDER BY trx_started LIMIT 10;
-- 必要时 KILL <thread_id>
```

**`History list length` 高的连锁反应** ⭐：undo 不能 purge → 版本链变长 → 每次查询要遍历更多版本 → **查询越来越慢 + 系统表空间暴涨**。

### ④ FILE I/O —— IO 压力

```
FILE I/O
--------
I/O thread 0 state: waiting for completed aio requests (insert buffer thread)
I/O thread 1 state: waiting for completed aio requests (log thread)
...
Pending normal aio reads: [0, 0, 0, 0] , aio writes: [0, 0, 0, 0]
-- 非 0 说明有 IO 积压 ⭐
Pending flushes (fsync) log: 0; buffer pool: 0
2590 OS file reads, 15234 OS file writes, 1234 OS fsyncs
-- 
16.95 reads/s, 21 avg bytes/read, 99.2 writes/s, 45 avg bytes/read
```

**关注**：
- `Pending` 非零 → IO 跟不上
- `avg bytes/read` 远小于 16KB → **随机读多**（Buffer Pool 命中率低）⭐

### ⑤ LOG —— redo 与 checkpoint

```
LOG
---
Log sequence number 1234567890       ← 当前 LSN
Log buffer assigned up to 1234567890
Log buffer completed up to 1234567890
Log written up to 1234567890
Log flushed up to   1234567890       ← 已 fsync
Added dirty page to the flush list, 1234
Last checkpoint at  1234560000       ← ⭐ 上次 checkpoint 的 LSN

计算 checkpoint 落后量 = Log sequence number - Last checkpoint at
                       = 7890 bytes
-- 若这个差值接近 redo log 总容量 → checkpoint 压力大 → 提示 innodb_log_file_size 太小 ⭐
```

**`Log sequence number - Last checkpoint at`** 是判断"redo 是否够用"的核心指标 ⭐：
- 差值长期接近 `innodb_redo_log_capacity` → **频繁 checkpoint，性能抖动** → 调大日志容量
- 差值很大且稳定 → 正常（说明有足够的 redo 空间缓冲）

### ⑥ BUFFER POOL AND MEMORY —— 命中率 ⭐

```
BUFFER POOL AND MEMORY
----------------------
Total large memory allocated 4294967296     ← 分配的总内存
Dictionary memory allocated 1234567
Buffer pool size   262144                   ← 总页数（× 16KB = 4GB）
Free buffers       1000                     ← 空闲页
Database pages     260000
Old database pages 96000                    ← Old 区（3/8）
Modified db pages  5000                     ← ⭐ 脏页数

Pending reads 0
Pending writes: LRU 0, flush list 0, single page 0
Pages made young 123456, not young 1234     ← ⭐ young/not young 比例
0.00 youngs/s, 0.00 non-youngs/s
Pages read 1000000, created 50000, written 800000
-- 
100.00 reads/s, 50.00 creates/s, 90.00 writes/s
-- ⭐⭐⭐ 这一行是最关键的命中率指标：
Buffer pool hit rate 995 / 1000, young-making rate 1 / 1000 not 0 / 1000
Pages read ahead 0.00/s, evicted without access 0.00/s, Random read ahead 0.00/s
LRU len: 260000, unzip_LRU len: 0
I/O sum[0]:cur[0], unzip sum[0]:cur[0]
```

**关键指标** ⭐：

| 指标 | 含义 | 目标 |
|---|---|---|
| **`Buffer pool hit rate`** ⭐ | 页命中率 | **99.5%+ 为健康**；低于 99% 说明 Buffer Pool 不够大 |
| **`Modified db pages`** | 脏页数 | 不宜长期很高（`innodb_max_dirty_pages_pct` = 75%）|
| **`young-making rate`** | Old→Young 晋升率 | 远低于 hit rate 是正常的（说明预读污染控制起作用）|
| **`Pages made young / not young`** | 晋升/未晋升 | `not young` 大说明有页被淘汰但未被再次访问 → 预读浪费 |
| **`Pages evicted without access`** | 读了没用就被淘汰 | 大 → **预读过度**（`innodb_read_ahead_threshold` 调整）|

**经验阈值**：
```
hit rate >= 995/1000   → 健康 ✅
hit rate 在 990~995    → 需要关注，考虑加大 Buffer Pool
hit rate < 990         → Buffer Pool 明显不足 ⭐
```

### ⑦ ROW OPERATIONS

```
ROW OPERATIONS
-------------
0 queries inside InnoDB, 0 queries in queue   ← ⭐ 非 0 说明 InnoDB 内部排队
0 read views open inside InnoDB
Process ID=1234, Main thread id=..., state: sleeping
Number of rows inserted 1000000, updated 5000, deleted 100, read 5000000
-- 
0.00 inserts/s, 0.00 updates/s, 0.00 deletes/s, 0.00 reads/s
Number of system rows inserted 0, updated 0, deleted 0, read 0
```

**关注**：
- **`queries inside InnoDB` / `queries in queue` 非 0** → InnoDB 内部成为瓶颈（latch 竞争）
- **读/写比例**：如果 reads 远大于 writes → 读密集，优化索引

## 三、快速诊断流程 ⭐

```
性能问题 → SHOW ENGINE INNODB STATUS

按这个顺序看：

① Buffer pool hit rate        低？ → 加大 innodb_buffer_pool_size / 优化索引
② History list length         大？ → 有长事务，查 innodb_trx 并 KILL
③ TRANSACTIONS 里的 ACTIVE 秒数 长？ → 同上
④ LATEST DETECTED DEADLOCK    有？ → 分析访问顺序，统一加锁顺序
⑤ SEMAPHORES 的 OS waits      大？ → latch 竞争，加 buffer pool instances / 关 AHI
⑥ LOG 的 checkpoint 差值      接近容量？ → 加大 redo 容量
⑦ FILE I/O 的 Pending         非 0？ → IO 瓶颈，看 iostat
⑧ avg bytes/read << 16K       是？ → 随机读多，命中率低
```

## 四、配合的其他诊断工具 ⭐

```sql
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read%';
-- Innodb_buffer_pool_read_requests  逻辑读次数
-- Innodb_buffer_pool_reads          物理读次数
-- 命中率 = 1 - reads / read_requests   ⭐ 比 STATUS 里的瞬时值更准（累计值）

SHOW GLOBAL STATUS LIKE 'Innodb_rows%';     -- 行操作累计
SHOW GLOBAL STATUS LIKE 'Innodb_log%';      
SHOW GLOBAL STATUS LIKE 'Threads%';
SHOW GLOBAL STATUS LIKE 'Handler%';         -- Handler_read_rnd_next 大 = 全表扫描多 ⭐

SHOW GLOBAL VARIABLES LIKE 'innodb%';       -- 所有 InnoDB 参数
SHOW PROCESSLIST;                            -- 当前连接与状态（State 字段很有用）
SHOW FULL PROCESSLIST;                       -- 含完整 SQL
```

**`Handler_read_rnd_next` 是最容易被忽略的关键指标** ⭐：它表示"按顺序扫描下一行"的次数，**数值巨大 = 全表扫描多**。

## 五、一句话总结

**`SHOW ENGINE INNODB STATUS` 里最该盯的四项：`Buffer pool hit rate`（要不要加内存）、`History list length`（有没有长事务）、`LATEST DETECTED DEADLOCK`（加锁顺序问题）、`Log sequence number - Last checkpoint`（redo 够不够用）**。其余段落是深挖的线索。""",
    ),
    (
        "MySQL",
        "performance_schema,sys,监控",
        3,
        r"""`performance_schema` 是什么？`sys` 库能怎么帮我们定位慢 SQL？""",
        r"""## 一、`performance_schema` 的本质 ⭐

**定位**：MySQL 5.5 引入的**低开销运行时性能监控**引擎，通过**内存中的表**暴露服务器内部的各类"事件"（等待、语句、阶段、锁等）。

**关键特性**：

| 特性 | 说明 |
|---|---|
| **按需开启** ⭐ | `setup_instruments`（监控什么）+ `setup_consumers`（记录到哪张表），可以精确控制开销 |
| **内存表，不落盘** | 重启即清零；不会写磁盘 |
| **开销可控** | 默认只开部分 instrument；全开会有 5%~15% 开销 |
| **thread 维度** | 每个线程一组统计，可按 `THREAD_ID` 关联 |

```sql
SHOW VARIABLES LIKE 'performance_schema';    -- ON/OFF
SHOW VARIABLES LIKE 'performance_schema%';   -- 相关参数

-- 开启/关闭某个 instrument
UPDATE performance_schema.setup_instruments
  SET ENABLED='YES' WHERE NAME LIKE 'statement/%';
UPDATE performance_schema.setup_consumers
  SET ENABLED='YES' WHERE NAME LIKE '%history%';
```

## 二、核心表分类 ⭐

| 分类 | 表 | 内容 |
|---|---|---|
| **语句** ⭐ | `events_statements_current` / `_history` / `_history_long` / `_summary_by_digest` | SQL 语句的执行统计（**`by_digest` 最关键**）|
| **等待** | `events_waits_current` / `_summary_by_*` | 等待事件（IO、锁、网络、latch）|
| **阶段** | `events_stages_current` | SQL 执行阶段（解析、优化、排序、发送）|
| **锁** ⭐ | `data_locks`、`data_lock_waits`（8.0）| 当前锁与锁等待 |
| **事务** | `events_transactions_current` | 事务级统计 |
| **文件/IO** | `file_summary_by_instance`、`file_io_waits_summary_by_*` | 哪个文件 IO 最多 ⭐ |
| **内存** | `memory_summary_by_thread_by_event_name` | 各线程内存使用 ⭐ 排查内存泄漏 |
| **连接** | `session_variables`、`accounts`、`hosts`、`users` | 连接维度统计 |
| **复制** | `replication_*` | 复制状态与延迟 |
| **元数据锁** | `metadata_locks` | MDL 等待 ⭐ 排查"表被锁住" |

## 三、`sys` 库 —— 人话版的 performance_schema ⭐

**`sys` schema**（5.7+ 自带）把 `performance_schema` 的复杂数据**加工成易读的视图**，并做了单位换算（ps → ms/s）。

### 排查慢 SQL 的四张王牌 ⭐

```sql
-- ① 谁在消耗最多时间（按 SQL 模板聚合）⭐ 最常用
SELECT * FROM sys.statement_analysis LIMIT 10;
-- 字段：query, exec_count, total_latency, avg_latency,
--       rows_sent_avg, rows_examined_avg, tmp_tables, full_scans
-- 关注：
--   total_latency 大 → 高频 SQL（次数多）
--   avg_latency 大   → 单次慢 SQL ⭐
--   rows_examined_avg >> rows_sent_avg → 扫描了很多行只返回很少 → 缺索引 ⭐
--   full_scans > 0   → 有全表扫描
--   tmp_tables > 0   → 用了临时表

-- ② 按表聚合的 IO 压力
SELECT * FROM sys.io_global_by_file_by_bytes LIMIT 10;
-- 哪个文件读写最多（定位是数据文件 / binlog / redo）

-- ③ 哪些表被访问最多
SELECT * FROM sys.schema_table_statistics LIMIT 10;
SELECT * FROM sys.schema_table_statistics_with_buffer LIMIT 10;   -- 含 buffer 命中率 ⭐

-- ④ 全表扫描最多的表 ⭐
SELECT * FROM sys.schema_tables_with_full_table_scans;

-- ⑤ 没用到索引的 SQL ⭐
SELECT * FROM sys.statements_with_full_table_scans
  ORDER BY total_latency DESC LIMIT 10;
-- 输出含 query, exec_count, total_latency, no_index_used_count, no_good_index_used_count

-- ⑥ 产生临时表的 SQL
SELECT * FROM sys.statements_with_temp_tables ORDER BY total_latency DESC LIMIT 10;

-- ⑦ 排序很重的 SQL
SELECT * FROM sys.statements_with_sorting ORDER BY total_latency DESC LIMIT 10;

-- ⑧ 冗余/未使用索引 ⭐ 非常实用
SELECT * FROM sys.schema_redundant_indexes;         -- 冗余（前缀重复）索引
SELECT * FROM sys.schema_unused_indexes;            -- 从未被使用的索引 ⭐
-- ⚠️ 注意：unused_indexes 是"自 performance_schema 收集以来"的统计，重启会清零
--    删除前务必：ALTER TABLE t ALTER INDEX idx INVISIBLE; 观察一段时间再删 ⭐

-- ⑨ 当前锁等待
SELECT * FROM sys.innodb_lock_waits\G
-- 输出含 waiting_pid, waiting_query, blocking_pid, blocking_query, locked_table

-- ⑩ 内存使用 TOP
SELECT * FROM sys.memory_by_thread_by_current_bytes ORDER BY current_alloc DESC LIMIT 10;
SELECT * FROM sys.memory_global_by_current_bytes LIMIT 10;
```

## 四、`statement_analysis` 的实战解读 ⭐

```
mysql> SELECT query, exec_count, total_latency, avg_latency, rows_examined_avg,
              rows_sent_avg, full_scans
       FROM sys.statement_analysis ORDER BY total_latency DESC LIMIT 3\G

*************************** 1. row ***************************
           query: SELECT * FROM `posts` WHERE `status` = ? ORDER BY `created_at` DESC LIMIT ?
      exec_count: 125000                              ← 调用 12.5 万次
   total_latency: 2.50 min                            ← 累计耗时 150s ⭐
     avg_latency: 1.20 ms                             ← 单次不算慢
rows_examined_avg: 45000                             ← ⭐ 但每次扫 4.5 万行！
    rows_sent_avg: 20                                ← 只返回 20 行
       full_scans: 125000                            ← ⭐ 每次都全表扫描

→ 结论：缺索引 (status, created_at) ⭐
   加索引后 rows_examined 会降到 20，total_latency 降几个数量级
```

**核心判据**：**`rows_examined_avg / rows_sent_avg` 的比值** ⭐
- 接近 1 → 索引命中好
- 远大于 1（如 1000:1）→ **扫描效率极低，缺索引或索引不对** ⭐

**另一类**：`exec_count` 小但 `avg_latency` 很大 → 单条慢 SQL（可能是统计、报表 SQL），看 `tmp_tables`、`full_scans`、`sort_*`。

## 五、`sys` 库的分组视图（视图即文档）⭐

`sys` 库的视图**同名带前后缀**表示不同聚合维度，记住命名规律就不用背：

```
前缀/后缀            含义
────────────────────────────────────────────
x_ / _by_...        中间视图（被其他视图引用，一般不用直接查）
host_summary        按客户端主机聚合
user_summary        按用户聚合
schema_*            按库聚合
statement_analysis  按 SQL 模板聚合 ⭐
io_*                按 IO 聚合
memory_*            按内存聚合
wait_*              按等待事件聚合
```

## 六、开销与生产使用注意 ⭐

| 注意点 | 说明 |
|---|---|
| **默认开销小** | 语句摘要（digest）默认开启，开销约 1%~3%，**生产可以常开** ✅ |
| **全开代价大** | 打开 `events_waits_history_long` 等历史表会明显增加开销与内存 |
| **表有大小上限** | `_history` 表默认 10 行/线程，`_history_long` 10000 行（全局），旧数据被覆盖 |
| **重启清零** | 所以**不要把它当监控系统**，要长期数据须落盘（Prometheus + mysqld_exporter）⭐ |
| **`sys.schema_unused_indexes` 的陷阱** ⭐ | 统计窗口可能不完整（重启后清零、业务有周期性）；**删索引前先设为 INVISIBLE 观察** |
| **`statement_analysis` 里的 `?`** | 是 digest 归一化后的占位符，同一个 SQL 模板合并统计（这就是它比慢日志强的地方）⭐ |
| **长时间未重启的实例更准** | unused_indexes / statement_analysis 需要足够的采样窗口 |

## 七、完整的性能排查工具链 ⭐

```
层次              工具                                  回答什么问题
────────────────────────────────────────────────────────────────────────
① 系统层         top / vmstat / iostat / sar            CPU/内存/磁盘是否瓶颈
② 实例层         SHOW GLOBAL STATUS                     QPS/TPS/连接/命中率
                 SHOW ENGINE INNODB STATUS              锁/长事务/checkpoint ⭐
                 SHOW PROCESSLIST                       此刻有什么在跑
③ SQL 层         slow_query_log + pt-query-digest       历史慢 SQL 汇总 ⭐
                 performance_schema / sys               按模板聚合的 SQL 画像 ⭐
                 EXPLAIN / EXPLAIN ANALYZE              单条 SQL 的执行计划
④ 长期监控       Prometheus + mysqld_exporter           趋势与告警 ⭐
                 Grafana 看板                           可视化
                 PMM（Percona Monitoring）               开箱即用
⑤ 压测           sysbench / mysqlslap                   验证优化效果
```

**分层排查的关键**：**先确认瓶颈层次，再选工具**。系统层先看，不要一上来就扎进 SQL 里。

## 八、一句话总结

**`performance_schema` 是"原始数据"，`sys` 是"给人看的视图"**；排查 SQL 只需三张表：**`sys.statement_analysis`（谁最耗时间）、`sys.statements_with_full_table_scans`（谁在扫全表）、`sys.schema_unused_indexes`（哪些索引白建了）**。核心判据是 **`rows_examined_avg / rows_sent_avg` 的比值**。""",
    ),
    (
        "MySQL",
        "大事务,优化,运维",
        2,
        r"""什么是大事务？大事务有什么危害？怎么发现和处理？""",
        r"""## 一、什么是大事务 ⭐

**大事务**没有严格定义，一般指满足下列任一条：

| 判据 | 阈值 |
|---|---|
| 影响行数 | **几万行以上**（如全表 `UPDATE`）|
| 执行时长 | **> 10 秒**（`SELECT` 不算，主要指写事务）|
| 产生的 undo | `undo log entries` **数万** |
| binlog 大小 | 单个事务的 binlog **> 100MB** |

```sql
-- ❌ 典型大事务
BEGIN;
UPDATE orders SET status = 0 WHERE create_time < '2023-01-01';   -- 影响 500 万行
COMMIT;
```

## 二、七大危害 ⭐

### ① 长时间持锁 → 阻塞其他事务

`UPDATE` 500 万行，每行的锁要持有到 `COMMIT` 为止（虽然是"边走边放"的优化，但仍然是毫秒级以上的长窗口）。其他事务的写被阻塞，可能连锁成雪崩。⭐

### ② undo 无法 purge → 版本链暴涨 ⭐

大事务会生成海量 undo，**purge 线程在事务提交前无法回收**。
`History list length` 飙升 → 所有查询要遍历更长的版本链 → **全库变慢**。同时**系统表空间/undo 表空间暴涨**。

### ③ redo log 被顶满 → checkpoint 风暴

大事务会持续产生 redo，脏页疯狂刷盘，checkpoint 频繁触发，**IO 打满**。

### ④ 主从延迟 ⭐

主库执行 30s，binlog 传到从库，**从库 SQL 线程只能串行重放**（大事务无法拆成多个并行组）→ 从库延迟几分钟甚至几小时。

**这是大事务最典型的后果**：主库看起来正常，**从库延迟爆炸**，读写分离的读全挂了。

### ⑤ 回滚代价巨大

事务失败要回滚：**回滚时间 ≈ 或 > 执行时间**（要逆序应用 undo）。一个大事务回滚 10 分钟，期间锁还在、undo 还在涨。

### ⑥ binlog 膨胀 & 复制中断风险

单个事务 binlog 太大 → 从库 `max_allowed_packet` 不够会**复制中断**；`binlog_row_event_max_size` 限制。

### ⑦ MGR 直接拒绝 ⭐

组复制的 `group_replication_transaction_size_limit`（默认 **150MB**）会**拒绝**超过限制的事务。

## 三、怎么发现 ⭐

```sql
-- ① 活跃长事务（最直接）⭐
SELECT trx_id,
       trx_started,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS sec,
       trx_state,
       trx_mysql_thread_id,
       trx_rows_modified,        -- ⭐ 已修改行数
       trx_query
FROM information_schema.innodb_trx
ORDER BY trx_started
LIMIT 20;

-- ② 未 purge 的 undo 长度 ⭐
SHOW ENGINE INNODB STATUS\G
-- HISTORY LIST 段落：History list length 12345
-- > 10000 需关注；> 100000 危险

-- ③ 当前连接与状态
SELECT id, user, host, db, command, time, state, LEFT(info,100) AS sql
FROM information_schema.processlist
WHERE command <> 'Sleep' ORDER BY time DESC;

-- ④ binlog 里的大事务（事后分析）⭐
mysqlbinlog --base64-output=DECODE-ROWS -v mysql-bin.000012 \
  | awk '/GTID/{g=$0} /end_log_pos/{print}' | tail
-- 或用 pt-query-digest 分析 binlog：
pt-query-digest --type=binlog /var/lib/mysql/mysql-bin.000012

-- ⑤ 主动设置阈值告警（mysqld_exporter / 自研脚本）
-- 监控：information_schema.innodb_trx 里 trx_started 超过 N 秒的行数 ⭐
```

**推荐监控指标** ⭐：

| 指标 | 告警阈值 |
|---|---|
| 活跃事务最长时长 | > 60s |
| `History list length` | > 10000 |
| 单事务 binlog 大小 | > 100MB |
| `trx_rows_modified` | > 100000 |

## 四、怎么处理 ⭐

### 立即止血

```sql
-- 找到长事务的 thread id
SELECT trx_mysql_thread_id FROM information_schema.innodb_trx
WHERE TIMESTAMPDIFF(SECOND, trx_started, NOW()) > 300;
-- KILL（注意：KILL 会触发回滚，回滚期间锁依然持有！）⚠️
KILL <thread_id>;
```

**⚠️ KILL 大事务的注意点**：`KILL` 不会立即释放锁，**回滚过程仍要持有锁和 undo**。所以 KILL 一个跑了 10 分钟的大事务，可能还要再等 10 分钟才真正释放。**紧急情况下 KILL 是必要的，但要预期到这一点。**

### 根本治理：拆小 ⭐

**① 分批 UPDATE / DELETE** ⭐ 最常用

```sql
-- 循环执行，每批 1000 行，批间 sleep
DELETE FROM logs WHERE create_time < '2023-01-01' ORDER BY id LIMIT 1000;
-- 检查 affected rows，直到为 0
```

**用存储过程封装**：

```sql
DELIMITER $$
CREATE PROCEDURE clean_logs(IN p_batch INT)
BEGIN
    DECLARE affected INT DEFAULT 1;
    WHILE affected > 0 DO
        DELETE FROM logs WHERE create_time < '2023-01-01' ORDER BY id LIMIT p_batch;
        SET affected = ROW_COUNT();
        DO SLEEP(0.05);      -- ⭐ 让从库有机会追上
        COMMIT;              -- 若在事务里则不能 COMMIT
    END WHILE;
END$$
DELIMITER ;
CALL clean_logs(1000);
```

**按主键范围切分** ⭐（更高效，避免 `LIMIT` + 无索引扫描）：

```sql
-- 先查出 id 的范围，再按区间分批
SELECT MIN(id), MAX(id) FROM logs WHERE create_time < '2023-01-01';
-- 然后按 id 区间循环
DELETE FROM logs WHERE id BETWEEN 1 AND 100000 AND create_time < '2023-01-01';
DELETE FROM logs WHERE id BETWEEN 100001 AND 200000 AND create_time < '2023-01-01';
```

**② 用 `DROP PARTITION` 替代 `DELETE`** ⭐（如果是分区表，秒级完成）

```sql
ALTER TABLE logs DROP PARTITION p202301;
```

**③ 业务层拆分**

- 批量插入：每批 500~1000 条 `INSERT`，而不是一个事务插 10 万条。
- 批量更新：按 ID 分片，多个小事务。
- 把"一次性大操作"改成"异步任务 + 进度表"。

**④ 调整参数（辅助，不解决根本）**

| 参数 | 作用 |
|---|---|
| `innodb_undo_log_truncate=ON` | 允许自动截断 undo 表空间 |
| `innodb_max_undo_log_size` | undo 表空间上限 |
| `innodb_purge_threads` | 加大 purge 并发 |
| `binlog_group_commit_sync_delay` | 提高组提交效率（但不解决大事务本身）|
| `slave_parallel_workers` + `LOGICAL_CLOCK` | 提升从库并行（但单个大事务无法并行 ⭐）|

**注意**：**`slave_parallel_workers` 对大事务无效** —— 因为并行单位是"事务"，一个事务只能由一个 worker 重放。所以**只能靠"拆小"**。

## 五、预防（编码规范）⭐

| 规范 | 说明 |
|---|---|
| **事务只包必要的语句** | 不要在事务里做 RPC / 文件 IO / 长循环 |
| **批量操作分批** | 单事务影响行数控制在一万以内（可配置）|
| **DDL 用 `INSTANT` / `pt-osc` / `gh-ost`** | 避免元数据锁长期持有 |
| **`autocommit=1`** | 避免"忘了 COMMIT"造成的隐式长事务 ⭐ |
| **框架层加超时** | 事务超时后自动回滚（应用层计时器）⭐ |
| **代码评审关注事务边界** | 尤其是 `@Transactional` 标注的方法里有没有外部调用 |
| **不要用 `SELECT` 无索引的 `UPDATE`** | 会锁全表（Next-Key Lock 退化成锁所有行）|

**隐式长事务的陷阱** ⭐：

```cpp
// ❌ Crow 场景：每个请求一个连接，如果某处忘了 commit/rollback
mysql_query(conn, "START TRANSACTION");
// ... 中间抛异常/提前 return ...
// ← 没有 COMMIT 也没有 ROLLBACK ⇒ 事务一直挂着，直到连接被回收
```

**解法**：**RAII 事务守卫**（见"隔离级别"那题）——析构函数里保证 `ROLLBACK`。

## 六、一句话总结

**大事务的所有危害都源自"一次改动太多"** —— 锁持太久、undo 撑爆、从库串行重放、回滚成本高。**唯一的根本解法是"分批"**（`LIMIT` 循环 / 按主键区间 / `DROP PARTITION`）；**监控上盯住"活跃事务时长"和 `History list length` 两个指标**；应用层用 **RAII 保证事务一定被关闭**。""",
    ),
    (
        "MySQL",
        "碎片,OPTIMIZE,空间回收",
        1,
        r"""表碎片是怎么产生的？`DELETE` 后空间为什么不释放？怎么回收空间？""",
        r"""## 一、碎片的来源 ⭐

| 来源 | 说明 |
|---|---|
| **`DELETE` 标记删除** | InnoDB 删除行只是**打删除标记**（`deleted_flag`），**页和空间不立即归还** ⭐ |
| **页分裂**（随机写/乱序插入）| 插入到中间的页导致页分裂，产生**半满页** → 空间利用率下降 |
| **`UPDATE` 变长列变长** | 行变大，原页放不下 → 迁移到新页，老页留下空洞 |
| **碎片化（fragmentation）** | 数据页在物理上不连续 → 顺序扫描退化为随机 IO |

**核心区分** ⭐：

```
① 页内碎片（page internal fragmentation）
   DELETE 后页里的空洞 → 页没有满但也没被回收
   → 表现为"数据文件不变小"

② 页间碎片（page external fragmentation）
   叶子节点逻辑有序但物理不连续
   → 表现为"范围扫描/全表扫描变慢"

③ 页分裂残留
   分裂后两页都半满
   → 表现为"文件比数据实际需要的大很多"
```

## 二、为什么 `DELETE` 后空间不释放 ⭐

```
DELETE FROM posts WHERE id < 1000;   -- 删了 1000 行
SHOW TABLE STATUS LIKE 'posts';      -- Data_length / Data_free 几乎没变
```

**原因**：

| 层次 | 行为 |
|---|---|
| **InnoDB 层** | 行被标记删除，**页仍在表空间里**（`Data_free` 增加 = 页内空闲空间增加）|
| **`innodb_file_per_table=ON` 时** | 空间借用给了同表的其他页，**但没有归还给操作系统** ⭐ |
| **`innodb_file_per_table=OFF` 时** | 空间进入**共享表空间 `ibdata1`**，**永不会缩小**（`ibdata1` 只增不减）⚠️ |

**所以 `DELETE` 的结果是**：表内可用空间变多（`Data_free` 变大），**但 `.ibd` 文件大小不变**。

## 三、查看碎片 ⭐

```sql
-- ① 表状态（最常用）
SHOW TABLE STATUS LIKE 'posts'\G
-- Data_length       数据占用字节数（近似）
-- Index_length      索引占用
-- Data_free         ⭐ 碎片（回收不了的空闲空间）
-- 碎片率 ≈ Data_free / (Data_length + Index_length + Data_free)

-- ② 找出碎片最多的表 ⭐
SELECT table_schema, table_name,
       ROUND(data_length/1024/1024, 2)  AS data_mb,
       ROUND(index_length/1024/1024, 2) AS idx_mb,
       ROUND(data_free/1024/1024, 2)    AS free_mb,
       ROUND(data_free/(data_length+index_length+data_free)*100, 2) AS frag_pct,
       table_rows
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql','information_schema','performance_schema','sys')
  AND data_free > 0
ORDER BY data_free DESC LIMIT 20;

-- ③ 页级别的碎片（information_schema 于 8.0 已移除 innodb_sys_tablespaces 等；
--    8.0 用 innodb_tablespaces / innodb_tables）
SELECT name, file_size, allocated_size FROM information_schema.innodb_tablespaces
WHERE name LIKE 'blogdb/%';
```

**碎片率经验值**：

```
frag_pct < 20%    → 不用管
frag_pct 20~40%   → 可以考虑整理（低峰期）
frag_pct > 40%    → 明显浪费空间，建议整理 ⭐
```

## 四、回收空间的方案 ⭐

### ① `OPTIMIZE TABLE`（最直接）

```sql
OPTIMIZE TABLE posts;
-- 内部等价于：ALTER TABLE posts ENGINE=InnoDB  （重建表 + 重建索引）
```

| 特性 | 说明 |
|---|---|
| **原理** | 建新表 → 逐行拷贝 → 重建索引 → 原子替换 → **重放期间的新写入**（Online DDL 的 row log）|
| **锁** | 5.6+ 使用 `ALGORITHM=INPLACE, LOCK=NONE`（**不阻塞 DML**）⭐ 但需要**额外磁盘空间**（约等于原表大小）|
| **代价** | 大量 IO + CPU；大表可能跑几小时 |
| **效果** | 回收空间 + 消除页内碎片 + 重建索引（顺序化，提升范围扫描）⭐ |

### ② `ALTER TABLE ... ENGINE=InnoDB`（等价）

```sql
ALTER TABLE posts ENGINE=InnoDB;                 -- 同上
ALTER TABLE posts FORCE;                          -- 8.0.16+ 直接触发表重建 ⭐ 更简洁
ALTER TABLE posts ENGINE=InnoDB, ALGORITHM=INPLACE, LOCK=NONE;   -- 显式不锁
```

### ③ 重建 + 在线（大表必须）⭐

```bash
# pt-online-schema-change：影子表 + 触发器
pt-online-schema-change --alter "ENGINE=InnoDB" D=blogdb,t=posts --execute

# gh-ost：无触发器，从 binlog 同步
gh-ost --host=127.0.0.1 --database=blogdb --table=posts \
       --alter="ENGINE=InnoDB" --execute

# MySQL 8.0 的 Clone Plugin 也可以（整实例/单表克隆，但不释放原表空间）
```

### ④ 位移法（极端情况，`ibdata1` 巨大）⚠️

**共享表空间 `ibdata1` 一旦膨胀就无法收缩**（`innodb_file_per_table=OFF` 时代的历史遗留）。只能：

```
① mysqldump 全量导出
② 删掉所有 ibd + ibdata1（危险！先确认备份可用）⭐
③ 重新初始化 + 恢复
```

**建议**：`innodb_file_per_table=ON`（默认已经是），这样每表独立，至少能单表回收。

### ⑤ 用分区替代

时间序列表用 `RANGE` 分区，历史数据用 `DROP PARTITION` 而不是 `DELETE` → **空间立即回收**，且不会有碎片 ⭐

### ⑥ 升级到 8.0 的 `innodb_undo_log_truncate`

自动截断 undo 表空间（治的是 undo 膨胀，不是数据碎片）。

## 五、索引碎片 ⭐

```sql
-- 索引也会碎片化（B+ 树页分裂）
ANALYZE TABLE posts;              -- 更新统计信息（不重建）
OPTIMIZE TABLE posts;             -- 重建索引
ALTER TABLE posts DROP INDEX idx_x, ADD INDEX idx_x (x);   -- 只重建一个索引
```

**`ANALYZE TABLE` vs `OPTIMIZE TABLE`** ⭐：

| | `ANALYZE TABLE` | `OPTIMIZE TABLE` |
|---|---|---|
| 作用 | **只更新统计信息** | **重建表 + 索引，回收空间** |
| 开销 | 极小（采样）| 大（全表重建）|
| 何时用 | 统计信息不准导致优化器选错计划 | 碎片多、需要回收空间 |

**通用原则**：优化器选错索引时先 `ANALYZE TABLE`（便宜）；碎片多时才 `OPTIMIZE`（昂贵）。

## 六、什么时候不该做 ⭐

| 场景 | 原因 |
|---|---|
| **业务高峰** | 重建表占大量 IO |
| **磁盘剩余空间不足** | `OPTIMIZE` 期间需要约一倍原表空间 ⚠️ 这是最常见的翻车点 |
| **从库有延迟** | `OPTIMIZE` 会产生 binlog，进一步加剧延迟 |
| **`ibdata1` 巨大但无法停机** | 只能等维护窗口 |
| **表本身就是"临时/归档"表** | 直接 `DROP + CREATE` 更快 |

**操作前的检查清单**：

```
□ 磁盘剩余空间 > 表大小的 1.2 倍 ⭐
□ 已在低峰或维护窗口
□ 从库延迟正常（或临时停止从库重放）
□ 备份有效且已验证可恢复 ⭐
□ 有回滚方案（其实 OPTIMIZE 是原地替换，无法回滚，只能靠备份）
□ 用 pt-osc/gh-ost 时确认表有主键 ⭐
```

## 七、"空间不释放"的另一个原因：文件被占用 ⭐

**别忘了这一条**（见 Linux 那题）：

```
已删除的文件仍被进程持有 fd → 空间不释放
df 显示满，du 找不到
→ lsof +L1 定位 → 重启/重开日志/清空 fd
```

**判断方法**：

```
如果是"表内 Data_free 大但表变小了" → 是 InnoDB 碎片问题
如果是"du 和 df 差距大"           → 是文件被占用（lsof 排查）⭐
两者完全不同，先分清
```

## 八、一句话总结

**碎片的根源是"删除只标记 + 页分裂"，`DELETE` 只增加 `Data_free` 不减小文件**；回收靠 `OPTIMIZE TABLE`（8.0 可用更简洁的 `ALTER TABLE ... FORCE`），**大表必须用 pt-osc/gh-ost 且提前确认磁盘空间**；**时间序列表用分区 `DROP PARTITION` 是零碎片的更优解**。""",
    ),
    (
        "MySQL",
        "自增ID,溢出,分片",
        2,
        r"""自增主键会用尽吗？用尽了怎么办？分布式场景下怎么生成全局唯一 ID？""",
        r"""## 一、自增 ID 会溢出吗？⭐

**会**，而且比想象中更常见。

| 类型 | 上限 | 现实影响 |
|---|---|---|
| `INT UNSIGNED` | 42.9 亿 | 高频写入的表几年就用完 |
| `INT`（有符号）| **21.4 亿** | 日志/消息类表可能 1~2 年就到 ⭐ |
| `BIGINT UNSIGNED` | 1844 亿亿 | 基本用不完 |

**溢出的表现** ⭐：

```sql
-- AUTO_INCREMENT 达到上限后的行为：
-- ① 有符号 INT 到 2147483647 后
INSERT INTO t (col) VALUES ('x');
-- ERROR 1062 (23000): Duplicate entry '2147483647' for key 'PRIMARY'
-- ⚠️ 报的是"主键重复"而不是"溢出"！这个误导性极强 ⭐⭐⭐
```

**为什么会报主键重复**：MySQL 的自增计数器到达 `2^31-1` 后**不再增加**，继续插入就都拿同一个值 `2147483647` → 第二条就撞主键。

**其他溢出方式**：

| 方式 | 说明 |
|---|---|
| **`ALTER TABLE t AUTO_INCREMENT = 2147483647`** | 手动把计数器改到上限附近 |
| **`INSERT` 时显式给一个很大的 id** | 8.0 会把这个值记入计数器（**8.0 之前重启后会重置**，需要 `ALTER TABLE ... AUTO_INCREMENT` 修回）⭐ |
| **`innodb_autoinc_lock_mode`** | 只管并发，不管上限 |

## 二、用尽了怎么办 ⭐

```
情况 A：还在 INT 范围内，只是快到了
  → ALTER TABLE t MODIFY id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT;
  ⚠️ 注意：这是"改列类型"，是 COPY 算法 → 重建表，大表会锁很久 ⭐
  ⚠️ 而且会导致从库延迟

情况 B：已经溢出，插入失败（线上故障）
  → 只能紧急改列类型（重建表），或者
  → 用 pt-osc / gh-ost 在线重建表（把列类型一起改了）
  → 或者：把历史数据归档到另一张表，腾出 ID 空间（治标）

情况 C：预防胜于治疗
  → 新表一律用 BIGINT UNSIGNED 做主键 ⭐
```

**紧急改类型（用 gh-ost）** ⭐：

```bash
gh-ost --host=127.0.0.1 --database=blogdb --table=logs \
       --alter="MODIFY COLUMN id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" \
       --execute
```

**改成 `UNSIGNED` 能"立刻"多出一倍空间吗？** 不能 —— 已经有数据的情况下，改成 `UNSIGNED` 也是**改列类型**（重建表）。但如果**原本就是 `BIGINT`，只是从有符号改无符号**，可以用 **`ALGORITHM=INPLACE`**（8.0 支持部分类型变化的 INPLACE）—— 需要实测确认。

**"改回低值"的陷阱** ⚠️：`ALTER TABLE t AUTO_INCREMENT = 1` 只在**表里没有数据（或最大 id 小于目标值）**时才生效。否则 MySQL 会取 `MAX(id)+1`。

## 三、查看自增状态 ⭐

```sql
-- ① 表状态里的 AUTO_INCREMENT
SHOW TABLE STATUS LIKE 'posts'\G
-- Auto_increment: 12345

-- ② 从 information_schema 批量查（找出快溢出的表）⭐
SELECT table_schema, table_name, auto_increment,
       CASE
         WHEN auto_increment > 1500000000 THEN 'DANGER: INT 快满'
         WHEN auto_increment > 1000000000 THEN 'WARN'
         ELSE 'OK'
       END AS risk
FROM information_schema.tables
WHERE auto_increment IS NOT NULL
ORDER BY auto_increment DESC LIMIT 20;
```

**⚠️ `SHOW TABLE STATUS` / `information_schema` 里的 `Auto_increment` 是估算值**（InnoDB 从内存中的计数器读，可能不准）。**精确值**：

```sql
SELECT MAX(id) FROM t;    -- 但这是主键的最大值，会自动用索引，非常快 ⭐
```

## 四、分布式全局唯一 ID ⭐

自增 ID 在分库分表下会**冲突**（每个分片都从 1 开始）。方案对比：

| 方案 | 原理 | 优点 | 缺点 |
|---|---|---|---|
| **UUID** | 随机 128 位 | 完全去中心化 | ⚠️ **随机 → 页分裂 + 索引膨胀**（见"为什么不用 UUID"）|
| **雪花算法 Snowflake** ⭐ | `1bit符号 + 41bit时间戳 + 10bit机器ID + 12bit序列号` | **趋势递增**（时间在高位）、本地生成、高性能 | 依赖时钟；要管理机器 ID |
| **号段模式（Leaf-segment）** ⭐ | 从 DB 批量取一段（如 1万~2万），本地分配 | 高性能（一次取一批）、趋势递增 | 取号段时应用重启会浪费一段；依赖 DB |
| **Redis `INCR`** | 原子递增 | 简单快 | 依赖 Redis；持久化配置不当会重号 ⚠️ |
| **DB 自增表** | 中央表发号 | 简单 | DB 成瓶颈和单点 |
| **MySQL 8.0 `UUID_TO_BIN(uuid, 1)`** | 转成二进制 + **时间高位重排** ⭐ | 有序 UUID（减少页分裂）| 16 字节仍偏大 |
| **ULID / 有序 UUID** | 时间戳 + 随机 | 趋势递增，字符串友好 | 20/26 字节 |

### 雪花算法细节 ⭐

```
 0 | 0000000000 0000000000 0000000000 0000000000 0 | 0000000000 | 000000000000
 ↑ |                   41 bit 毫秒时间戳              |  10 bit    |   12 bit
符号|        (可用 69 年)                            |  机器 ID    | 序列号（同毫秒内 4096 个）
```

- **趋势递增** → B+ 树插入集中在最后一页，**页分裂少** ✅
- **时钟回拨处理** ⭐：回拨时①等待回拨时间过去 ②抛异常让上游重试 ③用备用位（如把序列号借一位做扩展）
- **机器 ID 分配**：手工配置 / 从 ZooKeeper/etcd 分配 / 从 IP 后缀推导

**Snowflake 的容量**：单机 **409.6 万 ID/秒**，4096 台机器，可用 69 年。

### 号段模式（Leaf）细节 ⭐

```sql
-- 中央表
CREATE TABLE leaf_alloc (
    biz_tag     VARCHAR(128) PRIMARY KEY,
    max_id      BIGINT NOT NULL,
    step        INT    NOT NULL DEFAULT 2000,   -- 每次取多少
    updated_at  TIMESTAMP
);

-- 取一个号段（原子）
UPDATE leaf_alloc SET max_id = max_id + step WHERE biz_tag = 'order';
SELECT max_id, step FROM leaf_alloc WHERE biz_tag = 'order';
-- 应用缓存 [max_id - step + 1, max_id] 这段，本地内存分配 ⭐
```

**优化**：**双 buffer** —— 当前号段用到 10% 时异步预取下一段，避免取号段时的 DB 等待。

### 选型建议 ⭐

```
单库单表        → 自增主键（BIGINT UNSIGNED）⭐
分库分表        → 雪花算法 或 号段模式 ⭐
需要严格有序    → 号段模式 / 中央发号
需要无依赖      → 雪花算法（本地生成）
兼容 MySQL 索引 → 统一用 BIGINT（8 字节），把全局 ID 存成 BIGINT 而不是 VARCHAR
```

**关键实践**：**全局 ID 用 `BIGINT` 存，不要用 `VARCHAR`** ⭐ —— 因为二级索引叶子节点会存主键，`VARCHAR(32)` 的主键会让每个二级索引膨胀 4 倍。

## 五、一句话总结

**自增 ID 用尽后报的是"主键重复"而不是"溢出"，这个误导性极强**；**新表一律 `BIGINT UNSIGNED`**；分布式下优先 **雪花算法（趋势递增 + 本地生成）** 或 **号段模式（批量取号 + 双 buffer）**，**绝不要用纯随机 UUID 做主键**。""",
    ),
    (
        "MySQL",
        "统计信息,优化器,执行计划",
        3,
        r"""优化器是怎么选择执行计划的？统计信息不准会怎样？怎么干预优化器？""",
        r"""## 一、优化器的工作方式 ⭐

```
SQL → 解析（语法树） → 预处理（语义校验、权限） → 优化器 → 执行器
                                                      ↑
                          基于【代价模型 costing】从多个候选计划里选最便宜的
```

**代价模型的两大成本**：

| 成本 | 说明 |
|---|---|
| **IO 成本** | 读页的代价（`innodb` 引擎的页读取）|
| **CPU 成本** | 处理行的代价（比较、排序、聚合）|

**关键常量**（8.0 默认，页在内存中的场景）：

```
cost = io_cost × 1.0  +  cpu_cost × 0.2
```

**优化器可选的路径**：

```
① 单表访问路径：
   · 全表扫描（table scan）
   · 索引扫描（index scan）
   · 索引等值查找（ref / eq_ref / const）
   · 索引范围扫描（range）
   · 覆盖索引（index only）
   · 索引下推（ICP）
   · 松散索引扫描（loose index scan，用于 GROUP BY 优化）
   · 跳跃扫描（index skip scan，8.0）
   · 多范围读（MRR）

② 连接顺序：n 张表有 n! 种顺序 → 用【贪心/动态规划】搜索
   表数 ≤ 7 时用穷举（optimal）；> 7 时用启发式（greedy）⭐
   这就是"多表 JOIN 容易选错计划"的原因

③ 连接算法：NLJ / BNL / BKA / Hash Join
```

**控制搜索范围的参数**：

| 参数 | 说明 |
|---|---|
| `optimizer_search_depth` | 搜索深度（默认 62，自动调整；**越小越快但可能选错**）|
| `optimizer_prune_level` | 剪枝（默认 1 = 启用启发式剪枝）⭐ |
| `eq_range_index_dive_limit` | 等值范围下，超过这个数量就不做索引统计（避免采样太慢），改用统计信息估算。默认 **200** ⭐ |

## 二、统计信息 ⭐

**两种统计信息**：

| 类型 | 内容 | 何时更新 |
|---|---|---|
| **表统计** | 行数（`cardinality` 基数）、页数 | `ANALYZE TABLE`、或**自动触发**（`innodb_stats_auto_recalc=ON`，变化 > 10% 时异步更新）|
| **索引统计** | 每个索引的**基数**（不重复值数）| 同上 |
| **直方图**（8.0）⭐ | 列值的**分布**（等宽/等高）| 手动 `ANALYZE TABLE ... UPDATE HISTOGRAM ON col` |

**基数（cardinality）**：

```sql
SHOW INDEX FROM posts\G
-- Cardinality 列 = 估算的不重复值数
-- 选择性 = Cardinality / 行数，越接近 1 越好
```

**⚠️ 重要：`Cardinality` 是估算值**，通过**随机采样 8 个叶子页**计算（`innodb_stats_persistent_sample_pages`，默认 20）⭐。所以：

- **严重倾斜的数据**（如 99% 的行 status=0）→ 采样可能完全估错 ❌
- **数据量小但长期没 ANALYZE** → 估算偏差大

**统计信息不准的后果** ⭐：

```
① 选了错误的驱动表（大表驱动小表）→ JOIN 慢几百倍
② 该用索引却走了全表扫描（以为要返回很多行）
③ 该全表扫描却用了索引（以为只返回几行，实际上回表更多 → 更慢）
④ 选错连接算法（该 NLJ 却用 BNL）
⑤ `rows` 估算与实际相差几个数量级 → 后续的代价计算全错
```

**判断统计信息准不准** ⭐：

```sql
-- 对比估算与实际（EXPLAIN ANALYZE 会直接给出对比）⭐
EXPLAIN ANALYZE SELECT * FROM posts WHERE status = 1;
-- 输出：
--   (cost=... rows=10) (actual time=0.1..5.2 rows=45000 loops=1)
--                      ↑ 估算 10 行  ↑ 实际 45000 行 → 差了 4500 倍！❌
```

## 三、直方图（8.0）⭐

**用途**：给**没有索引的列**提供分布信息，帮助优化器更准地估算 `WHERE col = ?`（尤其数据倾斜时）。

```sql
-- 创建直方图（bucket 数 1~1024）
ANALYZE TABLE posts UPDATE HISTOGRAM ON status WITH 64 BUCKETS;

-- 查看
SELECT * FROM information_schema.column_statistics
WHERE table_name='posts' AND column_name='status'\G
-- 输出含 histogram（JSON）与 number-of-buckets-specified

-- 删除
ANALYZE TABLE posts DROP HISTOGRAM ON status;
```

**自动维护**：`histogram_generation_max_mem_size` 控制采样内存；表数据变化后需要**手动重新 ANALYZE**。

**适用场景** ⭐：`status`、`category` 这类**选择性差但分布极倾斜**的列（Pareto 分布）。

## 四、如何干预优化器 ⭐

### ① `ANALYZE TABLE`（最便宜）

```sql
ANALYZE TABLE posts;                          -- 更新统计信息
ANALYZE TABLE posts UPDATE HISTOGRAM ON status;   -- 加直方图
ANALYZE TABLE posts, comments;                 -- 多表
```

### ② 索引提示（Index Hint）⭐

```sql
-- 建议使用某索引（软提示，可能被忽略）
SELECT * FROM posts USE INDEX (idx_status);

-- 忽略某索引
SELECT * FROM posts IGNORE INDEX (idx_status);

-- 强制使用某索引（更硬）
SELECT * FROM posts FORCE INDEX (idx_status);

-- 8.0：优化器提示（更细粒度）⭐
SELECT /*+ INDEX(posts idx_status) */ * FROM posts WHERE status=1;
SELECT /*+ NO_INDEX(posts idx_status) */ * FROM posts WHERE status=1;
SELECT /*+ JOIN_ORDER(a, b) */ * FROM a JOIN b ON ...;      -- 强制连接顺序
SELECT /*+ JOIN_PREFIX(a) */ ...;                            -- 让 a 先连接
SELECT /*+ SET_VAR(sort_buffer_size = 16M) */ ...;           -- 临时改会话变量 ⭐
SELECT /*+ MERGE(t) */ ...;                                  -- 让派生表不强物化
SELECT /*+ NO_MERGE(t) */ ...;
SELECT /*+ BKA(t) */ ...;                                    -- 强制 BKA
SELECT /*+ NO_BNL(t) */ ...;                                 -- 禁止 BNL
SELECT /*+ HASH_JOIN(a, b) */ ...;                           -- 8.0.18+ 强制 hash join
```

**8.0 的 hint 比老式 hint 更好**：因为老式 hint 写在表名后面，语义模糊且不支持 JOIN 顺序等。

### ③ `STRAIGHT_JOIN`（强制连接顺序）

```sql
SELECT * FROM small_table STRAIGHT_JOIN big_table ON small_table.id = big_table.sid;
-- 强制 small_table 为驱动表 ⭐
```

### ④ 会话级开关 `optimizer_switch`

```sql
SELECT @@optimizer_switch\G     -- 查看所有开关
SET SESSION optimizer_switch = 'index_condition_pushdown=on,mrr=on,block_nested_loop=off';
-- 常用开关：
--   index_condition_pushdown   ICP
--   index_merge                索引合并
--   index_merge_intersection
--   mrr                        多范围读
--   batched_key_access         BKA
--   block_nested_loop          BNL
--   semijoin                   半连接优化（IN 子查询）
--   materialization            子查询物化
--   derived_merge              派生表合并
--   duplicateweedout
--   hash_join                  8.0.18+
```

### ⑤ 改写 SQL（往往比 hint 更好）⭐

```sql
-- ❌ 优化器选错驱动表
SELECT * FROM big JOIN small ON ...;
-- ✅ 改用子查询固定顺序，或显式 STRAIGHT_JOIN
SELECT * FROM small STRAIGHT_JOIN big ON ...;

-- ❌ 函数导致无法用索引
WHERE DATE(created_at) = '2024-05-01'
-- ✅ 改成范围
WHERE created_at >= '2024-05-01' AND created_at < '2024-05-02'

-- ❌ OR 导致无法用索引
WHERE a = 1 OR b = 2
-- ✅ 改 UNION ALL
SELECT * FROM t WHERE a = 1
UNION ALL
SELECT * FROM t WHERE b = 2 AND a <> 1;    -- 注意去重逻辑
```

**原则**：**优先改 SQL / 加索引 → 其次 ANALYZE TABLE → 最后才用 hint**。hint 是"把优化器的锅扛到 SQL 里"，维护成本高（数据分布变了要改 SQL）⭐

## 五、`EXPLAIN` 与 `EXPLAIN ANALYZE` 配合 ⭐

```sql
-- 只看估算（不执行）
EXPLAIN SELECT ...;
EXPLAIN FORMAT=JSON SELECT ...;    -- 8.0：含每个候选路径的 cost 明细 ⭐
EXPLAIN FORMAT=TREE SELECT ...;    -- 树形展示，8.0 默认风格

-- 真实执行并对比估算（8.0.18+）⭐ 最有价值
EXPLAIN ANALYZE SELECT ...;
-- 输出含 (actual time=... rows=... loops=...)，能直接看出估算偏差
```

**`FORMAT=JSON` 里能看到**：

```json
"query_cost": "1234.56",           // 总代价
"table": {
  "access_type": "ALL",            // 全表扫描
  "rows_examined_per_scan": 45000,
  "filtered": 2.22,                // 过滤后剩 2.22%
  "cost_info": { "read_cost": "...", "eval_cost": "...", "prefix_cost": "..." }
},
"considered_execution_plans": [ ... ]   // ⭐ 优化器考虑过的其他计划及代价
```

**`considered_execution_plans` 是金矿** ⭐：能看到优化器**比较过哪些计划**、为什么没选（代价更高），从而判断是"统计信息错"还是"模型本身不合理"。

## 六、优化器"选错"的常见原因与对策 ⭐

| 原因 | 判断方法 | 对策 |
|---|---|---|
| **统计信息过时** | `EXPLAIN ANALYZE` 估算 vs 实际差很多 | `ANALYZE TABLE` ⭐ |
| **采样偏差**（数据倾斜）| `Cardinality` 明显不合理 | 加直方图 / 调大 `innodb_stats_persistent_sample_pages` ⭐ |
| **代价模型不适配**（SSD vs HDD 差异）| 优化器总选全表扫描 | 8.0 的 `optimizer_cost_model` 或用 hint |
| **多表 JOIN 搜索空间爆炸** | JOIN 顺序不合理 | 减少表数 / `STRAIGHT_JOIN` / 拆成多步查询 |
| **`eq_range_index_dive_limit` 触发** | `IN` 里值很多时估算失真 | 调大该值（默认 200）|
| **隐式类型转换** | `EXPLAIN` 里 `key=NULL` | 修正类型/字符集 ⭐ |
| **`force index` 遗留** | SQL 里写着老 hint | 清理过期的 hint |
| **子查询/派生表被物化** | `EXPLAIN` 有 `DERIVED` | 改写为 JOIN，或用 `MERGE` hint |

## 七、一句话总结

**优化器 = 代价模型 + 统计信息 + 搜索算法**；统计信息（尤其 `Cardinality` 的采样估算）不准是"选错计划"的头号原因，**先用 `EXPLAIN ANALYZE` 对比"估算行数 vs 实际行数"**，然后按 **`ANALYZE TABLE` → 加直方图 → 改 SQL → 索引 hint** 的顺序处理。**hint 是最后手段**，因为它把"数据分布的假设"硬编码进了 SQL。""",
    ),
    (
        "MySQL",
        "日志,error log,慢查询",
        1,
        r"""MySQL 有哪几种日志？各自的作用、位置和常用参数是什么？""",
        r"""## 一、日志总览 ⭐

| 日志 | 层次 | 作用 | 默认 |
|---|---|---|---|
| **error log**（错误日志）| Server | 启动/关闭/错误/警告 | **ON** ⭐ |
| **slow query log**（慢查询日志）| Server | 记录超时 SQL | OFF（**必须开**）⭐ |
| **general log**（通用查询日志）| Server | 记录**所有**收到的 SQL | OFF（会爆炸）⚠️ |
| **binlog**（二进制日志）| Server | 复制 + PITR | **8.0 默认 ON** ⭐ |
| **relay log**（中继日志）| Slave | 从库暂存主库的 binlog | 从库自动 |
| **redo log**（重做日志）| **InnoDB** | 崩溃恢复（WAL）| 一直有，不可关 |
| **undo log**（回滚日志）| **InnoDB** | 回滚 + MVCC | 一直有 |
| **audit log**（审计日志）| 插件 | 记录谁做了什么 | 需装插件 |
| **DDL log** | Server | `metadata` 目录下的 DDL 记录 | 自动 |

## 二、error log ⭐

**作用**：记录**启动、关闭、严重错误、警告、说明信息**。**排查"服务起不来"的第一站**。

```ini
[mysqld]
log_error = /var/log/mysql/error.log
log_error_verbosity = 2      # 8.0：1=errors, 2=errors+warnings(默认), 3=+notes
log_error_services = 'log_filter_internal; log_sink_internal'   # 8.0 可加 JSON sink
```

```sql
SHOW VARIABLES LIKE 'log_error';
```

**常见内容**：

```
[ERROR] 无法启动（端口占用、数据目录权限、配置错误）
[Warning] Aborted connection ... (Got timeout reading communication packets)
[Warning] InnoDB: page_cleaner: 1000ms intended loop took ... ms   ← IO 跟不上 ⭐
[Note] /usr/sbin/mysqld: ready for connections.
[ERROR] InnoDB: mmap(137363456 bytes) failed; errno 12        ← 内存不足
[Note] 死锁信息（innodb_print_all_deadlocks=ON 时）
```

**技巧**：

```bash
# 看启动过程
tail -f /var/log/mysql/error.log
# 只看错误
grep -i -E '\[ERROR\]|\[Warning\]' /var/log/mysql/error.log | tail -50
# systemd 环境下也可能进 journald
journalctl -u mysqld -n 100 --no-pager
```

## 三、slow query log ⭐（必开）

**作用**：记录执行时间超过阈值的 SQL，是**定位慢 SQL 的起点**。

```ini
[mysqld]
slow_query_log = ON
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 1                    # 秒，可带小数（如 0.5）
log_queries_not_using_indexes = ON      # 记录没用索引的 SQL ⚠️ 高并发下日志会爆炸
min_examined_row_limit = 100            # 扫描行数少的不记（配合上一项，过滤噪声）⭐
log_slow_admin_statements = ON          # 记录慢的 ALTER/ANALYZE 等
log_slow_extra = ON                     # 8.0：记录更多字段（如 rows_examined）
log_slow_slave_statements = ON          # 从库也记录
log_output = FILE                       # 或 TABLE（写入 mysql.slow_log 表）
```

**分析工具** ⭐：

```bash
# ① 自带（简陋）
mysqldumpslow -s t -t 10 /var/log/mysql/slow.log      # 按总时间排序 Top10
mysqldumpslow -s c -t 10 /var/log/mysql/slow.log      # 按次数
mysqldumpslow -s at -t 10 /var/log/mysql/slow.log     # 按平均时间

# ② Percona Toolkit（推荐）⭐
pt-query-digest /var/log/mysql/slow.log > slow_report.txt
# 输出包含：
#   Profile（按总耗时排序，占比%）
#   每条 SQL 的 pct / total / min / max / avg / 95% / count
#   EXPLAIN 建议、示例、表信息
```

**`log_queries_not_using_indexes` 的坑** ⭐：**小表全表扫描会被记录**（很吵）。生产环境建议**关闭**，或配合 `min_examined_row_limit` 过滤。

**日志条目的读法** ⭐：

```
# Time: 2024-05-01T10:00:00.123456+08:00
# User@Host: app[app] @ 10.0.0.5 []  Id: 12345
# Query_time: 12.345678  Lock_time: 0.000123  Rows_sent: 20  Rows_examined: 4500000
   ↑ 执行时间             ↑ 锁等待时间      ↑ 返回行数    ↑ 扫描行数 ⭐
SET timestamp=1714528800;
SELECT * FROM posts WHERE status = 1 ORDER BY created_at DESC LIMIT 20;
```

**关键指标解读**：

| 指标 | 说明 |
|---|---|
| **`Query_time`** | 总执行时间 |
| **`Lock_time`** | **锁等待**时间（大 → 有锁竞争）⭐ |
| **`Rows_sent`** | 返回行数 |
| **`Rows_examined`** ⭐ | **扫描行数** —— `Rows_examined / Rows_sent` 比值大 = 索引不好 |
| `Rows_affected` | 影响行数（DML）|
| `Bytes_sent` | 返回数据量（大 → 可能返回了超大字段）|

## 四、general log ⚠️

**作用**：记录**所有**到达 MySQL 的语句（包括 `Sleep` 连接的 `Connect`/`Quit` 事件）。

```sql
SET GLOBAL general_log = ON;      -- ⚠️ 别在生产长时间开！
SELECT @@general_log_file;        -- 默认 /var/lib/mysql/hostname.log
```

**代价** ⭐：**QPS 越高日志越大越快**（高并发下每秒几百 MB 很正常），会**打满磁盘**并显著拖慢性能。

**正确用法**：

```
① 只在排查"应用到底发了什么 SQL"时**临时开几秒**
② 更好的替代：抓包（tcpdump port 3306）或用 performance_schema 的 statement 表 ⭐
③ 若要长期审计，用 audit_log 插件（可控、有格式）
```

## 五、binlog（回顾要点）⭐

```ini
[mysqld]
log_bin = /var/lib/mysql/mysql-bin
binlog_format = ROW                       # 推荐
binlog_row_image = MINIMAL                # 减小日志体积
expire_logs_days = 7                      # 8.0.11+ 建议用 binlog_expire_logs_seconds
binlog_expire_logs_seconds = 604800
max_binlog_size = 1G
sync_binlog = 1
```

```sql
SHOW BINARY LOGS;                         -- 列出所有 binlog
SHOW MASTER STATUS\G                       -- 当前写入位置
PURGE BINARY LOGS BEFORE '2024-05-01';    -- 清理（⚠️ 确认从库已应用）
FLUSH LOGS;                                -- 切新 binlog
```

**用途**：主从复制、PITR、**数据变更订阅（Canal/Debezium）用于缓存同步** ⭐

## 六、`log_output = TABLE` 的取舍

```sql
SET GLOBAL log_output = 'TABLE';    -- 日志写 mysql.slow_log / mysql.general_log
SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;
```

| | FILE | TABLE（CSV 引擎）|
|---|---|---|
| 分析工具支持 | ✅ pt-query-digest 等 | ❌ 大多不支持 |
| 查询方便 | 需 grep | ✅ SQL 查 ⭐ |
| 性能 | 好 | 略差；表会变大 |

**建议**：默认 FILE（便于用 pt-query-digest）；临时排查可以 TABLE。

## 七、日志相关的常见问题 ⭐

| 问题 | 原因 | 处理 |
|---|---|---|
| **磁盘被日志打满** | general log 开了、binlog 不清理、慢日志暴涨 | `du -sh /var/lib/mysql/*` 定位；清理 binlog；关 general log；`log_queries_not_using_indexes=OFF` ⭐ |
| **慢日志文件巨大** | 阈值太低 or 记录无索引 SQL | 提高 `long_query_time`，开 `min_examined_row_limit` |
| **binlog 无法清理** | 从库未同步（`Purge` 会等从库） | 检查从库状态；确认后可强制 `PURGE` |
| **日志时间不对（差 8 小时）** | 时区配置 | `log_timestamps = SYSTEM`（默认 UTC）⭐ 改成 SYSTEM 让日志用本地时间 |
| **看不到错误细节** | `log_error_verbosity` 太低 | 调成 3 |
| **error log 里有大量 aborted connection** | 客户端连接被中断 | 检查 `wait_timeout`、`max_allowed_packet`、网络 |

**`log_timestamps` 是常踩的坑** ⭐：默认 `UTC`，所以如果服务器是 CST（+8），日志文件里的时间会比本地**早 8 小时**，容易被误判为"日志没更新"。改成 `log_timestamps = SYSTEM` 即可。

## 八、一句话总结

**必开：error log（默认）+ slow query log + binlog**；**别开：general log（除非临时排查）**；慢日志用 **`pt-query-digest`** 分析，核心看 **`Rows_examined / Rows_sent` 比值** 和 `Lock_time`；最容易踩的坑是 **`log_timestamps` 默认 UTC 导致时间对不上** 和 **`log_queries_not_using_indexes` 把日志写爆**。""",
    ),
    (
        "MySQL",
        "sql_mode,严格模式,兼容",
        2,
        r"""`sql_mode` 是什么？有哪些重要模式？为什么升级后老 SQL 会报错？""",
        r"""## 一、`sql_mode` 是什么 ⭐

**它是一组"语法与数据校验规则"的开关集合**，决定 MySQL 对**不合规 SQL/数据**的态度：**报错拒绝** 还是 **静默转换**。

```sql
SELECT @@sql_mode;
-- 8.0 默认：
-- ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,
-- ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION
```

**为什么重要** ⭐：**同一份 SQL 在不同 `sql_mode` 下可能"一个报错、一个静默改数据"**。所以：
- **升级 MySQL 版本后老 SQL 报错**，十之八九是 `sql_mode` 变严了。
- **主从库 `sql_mode` 不一致会导致主从不一致** ⚠️（从库报错、主库静默通过）。

## 二、重要模式详解 ⭐

### 严格模式（最重要）⭐

| 模式 | 作用 |
|---|---|
| **`STRICT_TRANS_TABLES`** ⭐ | 对**事务表**启用严格模式：数据类型不对/超长/缺 `NOT NULL` 无默认值 → **直接报错**（而不是截断/填默认值）|
| **`STRICT_ALL_TABLES`** | 对所有表（含 MyISAM）严格 |

**对比示例**：

```sql
CREATE TABLE t (a INT, b VARCHAR(5) NOT NULL);

-- 关闭 strict：
SET sql_mode = '';
INSERT INTO t VALUES ('abc', NULL);
-- Warning (不是 Error)：'abc' 被转成 0，NULL 被转成 ''
SELECT * FROM t;   →  a=0, b=''    ⚠️ 数据被静默改了！

-- 开启 STRICT_TRANS_TABLES：
INSERT INTO t VALUES ('abc', NULL);
-- ERROR 1366 (HY000): Incorrect integer value: 'abc' for column 'a' at row 1  ✅ 拒绝
```

**严格模式的价值**：**避免"数据被悄悄改动"**。这是**必须开**的。

### `ONLY_FULL_GROUP_BY` ⭐（升级报错的头号原因）

```sql
-- 关闭时：MySQL 5.7 之前允许"查询不在 GROUP BY 里的列"，取任意一行的值
SELECT dept, name, COUNT(*) FROM emp GROUP BY dept;
-- 结果里 name 是不确定的（MySQL 随便挑一个）⚠️ 结果不可预测

-- 开启时（5.7+ 默认，8.0 仍默认）：
-- ERROR 1055 (42000): Expression #2 of SELECT list is not in GROUP BY clause
--                     and contains nonaggregated column 'emp.name'
--                     which is not functionally dependent on columns in GROUP BY clause
```

**正确写法**：

```sql
-- ✅ 用聚合函数
SELECT dept, MAX(name), COUNT(*) FROM emp GROUP BY dept;
-- ✅ 或用窗口函数（8.0）
SELECT dept, name, COUNT(*) OVER (PARTITION BY dept) FROM emp;
-- ✅ 或明确取哪一行
SELECT dept, SUBSTRING_INDEX(GROUP_CONCAT(name ORDER BY id), ',', 1) FROM emp GROUP BY dept;
```

**为什么这是好事** ⭐：老的宽松行为会让**结果依赖执行计划**（可能今天和明天不一样），是隐蔽的 bug 源。`ONLY_FULL_GROUP_BY` 强制你写**语义确定**的 SQL。

### 其他重要模式

| 模式 | 作用 | 建议 |
|---|---|---|
| **`NO_ZERO_DATE`** | 不允许 `'0000-00-00'` 日期 | 开 ⭐ |
| **`NO_ZERO_IN_DATE`** | 不允许 `'2024-00-01'` 这种部分为 0 的日期 | 开 |
| **`ERROR_FOR_DIVISION_BY_ZERO`** | 除零报错（否则返回 NULL + Warning）| 开 |
| **`NO_ENGINE_SUBSTITUTION`** ⭐ | 指定引擎不可用时**报错**，而不是悄悄换成默认引擎 | **必须开**（否则 `ENGINE=MyISAM` 会被静默替换成 InnoDB）|
| **`NO_AUTO_CREATE_USER`** | 5.7：`GRANT` 不自动建用户 | 8.0 已移除相关语法 |
| **`NO_BACKSLASH_ESCAPES`** | 禁用反斜杠转义 | ⚠️ **不要开**（会让 `\` 变成普通字符，影响转义逻辑）⭐ |
| **`ANSI_QUOTES`** | 用 `"` 表示标识符（而非字符串）| ⚠️ 慎用（很多 ORM 会出问题）|
| **`PIPES_AS_CONCAT`** | `\|\|` 作为字符串连接（Oracle 风格）| 兼容迁移时用 |
| **`ANSI`** | 组合模式（`REAL_AS_FLOAT, PIPES_AS_CONCAT, ANSI_QUOTES, ONLY_FULL_GROUP_BY`）| 兼容 ANSI SQL |
| **`TRADITIONAL`** | 组合模式（含严格模式全套）| 最严格 |
| **`IGNORE_SPACE`** | 函数名和 `(` 之间允许空格 | |
| **`HIGH_NOT_PRECEDENCE`** | `NOT` 优先级变化 | |
| **`ALLOW_INVALID_DATES`** | 允许非法日期（如 `2024-02-30`）| 不开 |
| **`NO_UNSIGNED_SUBTRACTION`** | 无符号减法报错而非回绕 | 视情况 |
| **`REAL_AS_FLOAT`** | `REAL` 作为 `FLOAT` | 兼容 |

## 三、`sql_mode` 是分层的 ⭐

```sql
-- ① 启动默认（命令行/配置文件）
[mysqld]
sql_mode = ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION

-- ② 全局（运行时）
SET GLOBAL sql_mode = '...';     -- 新连接生效 ⚠️ 重启后丢失（除非写进配置文件）

-- ③ 会话
SET SESSION sql_mode = '...';    -- 当前连接生效
-- 或
SET sql_mode = '...';            -- 等价于 SESSION
```

**配置文件优先级**：命令行 `--sql-mode` > 配置文件 > 编译默认。

**关键实践** ⭐：**主从库必须配置完全一样的 `sql_mode`**。否则同一事务在主库成功、从库报错 → **复制中断**（`Last_SQL_Error`）。

**检查从库的 `sql_mode`**：

```sql
SHOW VARIABLES LIKE 'sql_mode';   -- 主库
SHOW SLAVE STATUS\G               -- 看 Slave_SQL_Running_State 是否正常
-- 从库也要执行 SHOW VARIABLES LIKE 'sql_mode' 对比
```

## 四、升级时的排查流程 ⭐

```sql
-- 1. 目标版本（8.0）的默认 sql_mode
-- ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,
-- ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION

-- 2. 在 5.7 上临时改成 8.0 的默认值，跑全量回归 ⭐
SET GLOBAL sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
-- 然后跑业务回归 → 看有哪些 SQL 报错

-- 3. 用 mysqlsh 的 upgrade checker
--    mysqlsh -- util check-for-server-upgrade root@host:3306

-- 4. 修复报错 SQL 后，再正式升级
```

**常见的升级报错及修法** ⭐：

| 报错 | 原因 | 修法 |
|---|---|---|
| `ERROR 1055 ... not in GROUP BY` | `ONLY_FULL_GROUP_BY` | 补 `GROUP BY` 或改聚合函数/窗口函数 ⭐ |
| `ERROR 1366 Incorrect ... value` | 严格模式 | 修数据 or 修代码（不要再依赖隐式转换）⭐ |
| `ERROR 1364 Field doesn't have a default value` | 严格模式 + `NOT NULL` 无默认值 | 给列加默认值，或插入时显式赋值 |
| `ERROR 1292 Incorrect datetime value` | `NO_ZERO_DATE` | 不要把 `'0000-00-00'` 当哨兵值，用 `NULL` ⭐ |
| `ERROR 1524 Plugin ... not loaded` | 8.0 认证插件变化 | 改驱动或改用户认证方式 |
| 保留字冲突 | 8.0 新增 `RANK`/`GROUPS`/`LEAD` 等 | 加反引号 |

## 五、"不要为了兼容而关掉严格模式" ⭐

**常见的错误做法**：

```sql
-- ❌ 升级后一堆 SQL 报错 → 直接把 sql_mode 清空
SET GLOBAL sql_mode = '';
```

**为什么错**：

```
① 报错说明那些 SQL 本来就在"静默改数据"或"产生不确定结果" → 是 bug 而不是兼容问题
② 清空后：截断/填默认值会继续发生，数据质量无从保证
③ 主从可能不一致（一边严格一边宽松）
④ 后续版本会更严格，早晚还得改
```

**正确做法**：**保留严格模式，修 SQL 和数据**。如果确实有历史包袱，可以**暂时只关掉最痛的一个子模式**（如 `ONLY_FULL_GROUP_BY`），并记 TODO 逐步整改 ⭐。

## 六、一句话总结

**`sql_mode` 决定 MySQL 对不合规数据是"报错"还是"静默修改"**；**`STRICT_TRANS_TABLES` 和 `NO_ENGINE_SUBSTITUTION` 必须开**，`ONLY_FULL_GROUP_BY` 是升级报错的头号原因但**不要为了省事关掉它**；**主从必须配一致的 `sql_mode`**，否则会复制中断；迁移前用 `mysqlsh upgrade checker` 加上"临时改成目标默认值跑回归"来提前发现问题。""",
    ),
    (
        "MySQL",
        "时区,时间,datetime",
        2,
        r"""MySQL 里时区怎么处理？`NOW()` 和 `SYSDATE()` 有什么区别？跨时区系统怎么设计时间字段？""",
        r"""## 一、`DATETIME` vs `TIMESTAMP` 的时区行为 ⭐

| | `DATETIME` | `TIMESTAMP` |
|---|---|---|
| 存储 | **字面值**（`'2024-05-01 10:00:00'` 原样存）| **UTC 时间戳**（写入时按 `time_zone` 转成 UTC 存）|
| 读取 | **原样返回**，与时区无关 ⭐ | 按当前 `time_zone` 转回本地时间 |
| 范围 | 1000~9999 | 1970~**2038** ⚠️ |
| 自动更新 | 需显式写 `DEFAULT/ON UPDATE` | 默认就有 `ON UPDATE CURRENT_TIMESTAMP` ⚠️ |

**关键例子** ⭐：

```sql
SET time_zone = '+08:00';
INSERT INTO t (dt, ts) VALUES ('2024-05-01 10:00:00', '2024-05-01 10:00:00');

SET time_zone = '+00:00';
SELECT dt, ts FROM t;
-- dt = '2024-05-01 10:00:00'   ← ✅ 原样（DATETIME 不受时区影响）
-- ts = '2024-05-01 02:00:00'   ← ⚠️ 变了！(TIMESTAMP 按时区转换)
```

**结论** ⭐：**`DATETIME` 的行为可预测（存什么读什么），`TIMESTAMP` 会自动做时区转换。**

## 二、`NOW()` vs `SYSDATE()` ⭐

| | `NOW()`（= `CURRENT_TIMESTAMP`）| `SYSDATE()` |
|---|---|---|
| 取值时机 | **语句开始执行时**取值，**语句内恒定** ⭐ | **函数被调用时**取值，**每次调用可能不同** |
| 用途 | 一般用这个 | 需要"真实当前时间"时 |

```sql
SELECT NOW(), SLEEP(2), NOW(), SYSDATE(), SLEEP(2), SYSDATE();
-- 结果：
-- NOW() = 10:00:00  ... NOW() = 10:00:00   ← ⭐ 两次相同（语句开始时间）
-- SYSDATE() = 10:00:02        SYSDATE() = 10:00:04   ← 随执行时间变化
```

**⚠️ 重要陷阱** ⭐：

| 陷阱 | 说明 |
|---|---|
| **`NOW()` 在主从复制中安全** | 因为它取的是"语句开始时间"，主从执行同一条 SQL 时……**注意：实际是主库的时间被写进 binlog（ROW 格式下写的是值，安全）**；STATEMENT 格式下 `NOW()` 也是安全的（binlog 里记录的是主库执行的时刻）⭐ |
| **`SYSDATE()` 在 STATEMENT 复制下不安全** ⚠️ | 主从执行时间不同 → 结果不同 → **主从不一致**。所以 `binlog_format=STATEMENT` 时**不要用 `SYSDATE()`** ⭐ |
| **`NOW()` 在函数/触发器中** | 也是语句级常量 |

**建议**：**统一用 `NOW()`**，避免 `SYSDATE()`。

## 三、时区相关变量与函数 ⭐

```sql
-- 查看
SELECT @@global.time_zone, @@session.time_zone;
SELECT NOW(), UTC_TIMESTAMP(), CURDATE(), CURTIME();
SELECT TIMEDIFF(NOW(), UTC_TIMESTAMP()) AS tz_offset;   -- ⭐ 反推当前时区偏移

-- 设置（三种形式）
SET GLOBAL time_zone = 'SYSTEM';        -- 跟随操作系统时区 ⭐ 推荐
SET GLOBAL time_zone = '+08:00';        -- 固定偏移
SET GLOBAL time_zone = 'Asia/Shanghai'; -- 命名时区（需导入时区表）⭐

-- ⚠️ 命名时区需要先导入时区数据（否则报 "Unknown or incorrect time zone"）
--  Linux: mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root mysql
--  或在 my.cnf 里写 time_zone = '+08:00' 避免依赖时区表
```

**配置文件**：

```ini
[mysqld]
default-time-zone = '+08:00'      # 或 'Asia/Shanghai' 或 'SYSTEM'
log_timestamps = SYSTEM            # ⭐ 让日志用本地时间（默认 UTC，容易误判）
```

**`TIMESTAMP` 相关的转换函数**：

```sql
SELECT CONVERT_TZ('2024-05-01 10:00:00', '+08:00', '+00:00');   -- '2024-05-01 02:00:00'
SELECT UNIX_TIMESTAMP('2024-05-01 10:00:00');                    -- 秒数（按会话时区解释）
SELECT FROM_UNIXTIME(1714528800);                                -- 按会话时区格式化
```

**⚠️ `CONVERT_TZ` 用命名时区时需要时区表**，否则返回 `NULL`。

## 四、跨时区系统的设计建议 ⭐

### 方案 A：统一存 UTC（推荐给国际化系统）⭐⭐

```
① 数据库 time_zone = '+00:00'（或 UTC）
② 时间字段用 DATETIME(3)，存 UTC
③ 应用层负责：输入时把用户本地时间转 UTC 再存；输出时把 UTC 转用户时区再显示
④ 用 BIGINT 存 Unix 时间戳也可以（无时区语义，最不容易出错）
```

**优势**：**存储层完全没有时区歧义**；换时区不用改数据。

### 方案 B：统一存业务本地时间（推荐给单区域系统）⭐

```
① 数据库和应用都设为同一时区（如 '+08:00'）
② 用 DATETIME(3)，存本地时间
③ 显示时直接用（不需要转换）
```

**优势**：简单直观，SQL 里 `DATE(created_at)`、`WHERE created_at >= CURDATE()` 都很好用。
**劣势**：将来要国际化就得改。

**本项目（博客系统）** 属于单区域，**方案 B 足够**，但要注意：

```
① 服务器、MySQL、应用三处时区必须一致 ⭐
② 用 DATETIME(3) 而不是 TIMESTAMP（避免 2038 和自动改值）
③ 在配置文件里显式写 default-time-zone，不要依赖"服务器当前时区"
```

### 方案 C：全球用户但只有展示层需要时区

```
存 UTC（方案 A），同时单独存用户的时区偏好（user.timezone）
渲染时按用户时区转换
```

## 五、常见坑 ⭐

| 坑 | 现象 | 解决 |
|---|---|---|
| **服务器时区改了但 MySQL 没重启** | `time_zone=SYSTEM` 只在启动时解析一次 | 重启 mysqld，或显式设 `+08:00` |
| **命名时区报错** | `Unknown or incorrect time zone: 'Asia/Shanghai'` | 导入时区表，或改用偏移量 `+08:00` ⭐ |
| **日志时间差 8 小时** | `log_timestamps=UTC`（默认）| 改 `log_timestamps=SYSTEM` ⭐ |
| **`TIMESTAMP` 自动改值** | 每次 `UPDATE` 都把 `updated_at` 改了（即使没动它）| 用 `DATETIME` + 显式 `ON UPDATE CURRENT_TIMESTAMP` 控制 ⭐ |
| **`TIMESTAMP` 2038 溢出** | 存 2039 年的时间报错 | 用 `DATETIME` |
| **`DATE(created_at)` 导致索引失效** | 时间范围查询慢 | 改成 `created_at >= '2024-05-01' AND created_at < '2024-05-02'` ⭐ |
| **`NOW()` 有时区语义** | 会话时区不同 → 结果不同 | 明确统一会话时区（连接串或 `SET time_zone`）|
| **`FROM_UNIXTIME` 与会话时区耦合** | 应用以为存的是 UTC | 显式 `SET time_zone='+00:00'` 或用 `CONVERT_TZ` |
| **应用和 DB 时区不一致** ⭐ | 写入时差 8 小时 | 在连接串/连接初始化时显式设置时区 |
| **`TIMESTAMP` 的 `DEFAULT 0`** | 老数据里的 `0000-00-00 00:00:00` | 迁移成 `NULL`（`NO_ZERO_DATE` 模式下不允许）|

**应用连接时区（C API / 连接串）** ⭐：

```cpp
// C API：连接后立即设置时区
mysql_query(conn, "SET time_zone = '+08:00'");
// 或者修改会话变量
```

```
# JDBC
jdbc:mysql://host:3306/db?serverTimezone=Asia/Shanghai&useSSL=false
# 或统一 UTC
jdbc:mysql://host:3306/db?serverTimezone=UTC
```

**最稳的做法** ⭐：**不要靠"应用连接串的时区"和"服务器时区"偶然一致**，而是在**连接初始化时显式 `SET time_zone`**，或者**完全用 UTC + 应用层转换**。

## 六、时间精度 ⭐

```sql
-- 毫秒精度（推荐）
created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
-- 微秒
updated_at DATETIME(6) ...
```

**为什么需要毫秒精度**：高并发下同一秒内多条记录，**只有秒级精度会导致排序不稳定**（`ORDER BY created_at DESC` 的结果不唯一）→ 分页可能重复/漏数据 ⭐ 这在"每日一题"这种按时间排序的场景很关键。

**精度与索引**：`DATETIME(3)` 占 7 字节（`DATETIME` 是 5 字节；每增加 1~2 位小数多 1 字节）。

## 七、一句话总结

**`DATETIME` 存字面值（不受时区影响），`TIMESTAMP` 存 UTC（自动时区转换且 2038 溢出）**；**用 `DATETIME(3)`，用 `NOW()` 而不是 `SYSDATE()`**；时区要么**全栈统一本地时区**（单区域，简单），要么**全栈 UTC + 应用层转换**（国际化，最不容易错）；**三处时区（OS/MySQL/应用）必须一致，且在连接初始化时显式设置**；别忘了 `log_timestamps=SYSTEM`，否则日志时间会让你怀疑人生。""",
    ),
    (
        "MySQL",
        "归档,冷热分离,数据生命周期",
        2,
        r"""历史数据越来越多该怎么办？冷热数据怎么分离？归档方案怎么设计？""",
        r"""## 一、为什么必须做数据生命周期管理 ⭐

```
表越大 → ① B+ 树越高（IO 次数多）② 索引越大（内存放不下）
       ③ 备份/DDL 时间越来越长 ④ 统计信息失真 ⑤ 查询优化器更容易选错
```

**现实**：绝大多数业务的查询是**"最近的数据最热"**（帕累托分布）。

```
访问分布（典型）：最近 7 天 ~ 80% 的查询
                  最近 30 天 ~ 95%
                  30 天以上 ~ 5%
```

**所以"把冷数据挪走"是性价比极高的优化** ⭐

## 二、冷热分离的四个层次 ⭐

| 层次 | 做法 | 复杂度 |
|---|---|---|
| **① 分区 + DROP PARTITION** ⭐ | 时间序列表按月分区 | 低 |
| **② 冷热分表（同库）** | `posts` + `posts_archive` | 低 |
| **③ 冷热分库（历史库）** | 历史数据搬到只读实例/低配实例 | 中 |
| **④ 数据湖 / 数仓** | 归档到对象存储 + 离线分析 | 高 |

## 三、方案一：分区表 + `DROP PARTITION` ⭐（首选）

```sql
-- 按月 RANGE 分区（日志、流水、消息类表）⭐
CREATE TABLE access_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    dt DATE NOT NULL,
    url VARCHAR(500),
    ip VARCHAR(45),
    PRIMARY KEY (id, dt)          -- ⚠️ 分区键必须在所有唯一键里
) ENGINE=InnoDB
PARTITION BY RANGE COLUMNS(dt) (
    PARTITION p202404 VALUES LESS THAN ('2024-05-01'),
    PARTITION p202405 VALUES LESS THAN ('2024-06-01'),
    PARTITION pmax    VALUES LESS THAN (MAXVALUE)
);

-- 每天/每月维护任务：
-- ① 提前建未来分区
ALTER TABLE access_log REORGANIZE PARTITION pmax INTO (
    PARTITION p202406 VALUES LESS THAN ('2024-07-01'),
    PARTITION pmax    VALUES LESS THAN (MAXVALUE)
);
-- ② 删除过期分区（秒级！不产生大量 undo/binlog）⭐
ALTER TABLE access_log DROP PARTITION p202401;
```

**优势** ⭐：
- **`DROP PARTITION` 是元数据操作，秒级完成**（对比 `DELETE` 要几分钟到几小时）
- **不产生大量 binlog** → 不会拖垮从库
- **不需要额外磁盘**（不像 `OPTIMIZE`）
- **无碎片**

**维护脚本思路**（可用 Event Scheduler 或外部 cron）：

```sql
-- 每天 03:00 跑
-- 1. 建下个月的分区（幂等：先判断是否存在）
-- 2. 删 N 个月前的分区
-- 3. 记录日志
```

**怎么判断分区是否存在**：

```sql
SELECT COUNT(*) FROM information_schema.partitions
WHERE table_schema='blogdb' AND table_name='access_log' AND partition_name='p202406';
```

## 四、方案二：冷热分表（同库）⭐

**适用于：单表数据量大，但业务查询天然区分冷热**。

```sql
-- 热表：保留最近 N 天/N 个月
CREATE TABLE orders        LIKE orders_archive;   -- 结构相同
-- 归档流程（分批 + 事务）：
-- 1. 从热表按主键范围取一批
-- 2. INSERT INTO orders_archive SELECT ... 
-- 3. DELETE FROM orders WHERE id IN (...)
-- 4. 循环直到完成
```

**安全归档的注意点** ⭐：

| 注意点 | 说明 |
|---|---|
| **先写后删** | 必须"先成功插入归档表，再删热表"，**顺序不能反** ⭐ |
| **同一事务** | 保证"插了必删、删了必插"，避免数据丢失/重复 |
| **按主键范围分批** | 避免大事务（见"大事务"题）⭐ |
| **批间 sleep** | 让从库追上 |
| **记录进度** | 用一张进度表，支持中断续跑 |
| **幂等** | 重复执行同一批不产生重复数据（用 `INSERT IGNORE` 或 `REPLACE`）|
| **限速** | 控制每分钟归档行数，避免打满 IO |
| **查两边** ⭐ | 应用查询需要 union 或路由（按时间范围决定查哪张表）|

**归档存储过程示例**：

```sql
DELIMITER $$
CREATE PROCEDURE archive_orders(IN p_before DATE, IN p_batch INT)
BEGIN
    DECLARE v_affected INT DEFAULT 1;
    DECLARE v_min_id BIGINT; DECLARE v_max_id BIGINT;
    
    SELECT MIN(id), MAX(id) INTO v_min_id, v_max_id
    FROM orders WHERE created_at < p_before;
    
    WHILE v_min_id <= v_max_id DO
        START TRANSACTION;
        -- ⭐ 先插后删，同一事务
        INSERT IGNORE INTO orders_archive
        SELECT * FROM orders
        WHERE id BETWEEN v_min_id AND v_min_id + p_batch - 1
          AND created_at < p_before;
        DELETE FROM orders
        WHERE id BETWEEN v_min_id AND v_min_id + p_batch - 1
          AND created_at < p_before;
        COMMIT;
        
        SET v_min_id = v_min_id + p_batch;
        DO SLEEP(0.05);      -- 让从库追上 ⭐
    END WHILE;
END$$
DELIMITER ;
```

**⚠️ 应用层的路由问题** ⭐：归档后"查某用户的所有订单"要**同时查热表和归档表**（并做合并分页）。解决方案：

```
① 应用层按时间范围路由（"最近 3 个月"→热表，"更早"→归档表）⭐
② 用 union 视图（但性能差，且不能带索引优化）
③ 维护一张"归档索引表"记录"哪些数据在哪个表"
④ 产品层面限制："只保留最近 N 个月的记录可查"
```

## 五、方案三：冷热分库 ⭐

**思路**：历史数据搬到**独立的实例**（低配、只读、可与分析混用）。

```
主库（热）：orders（最近 3 个月）
归档库（冷）：orders_all（全部）+ 只读实例
              ↑ 查询历史走这个，减轻主库压力
```

**怎么搬**：

| 方式 | 说明 |
|---|---|
| **`mysqldump` 单表导出 + 导入** | 简单，需要停写窗口或分批 |
| **`SELECT INTO OUTFILE` + `LOAD DATA`** ⭐ | 最快（比 INSERT 快数倍），适合大批量 |
| **binlog 订阅（Canal/Debezium）** | 实时同步到归档库（可做成"主库删、归档库留"）|
| **原生工具** `mysqlsh util copy` | 8.0 支持 |

**`SELECT INTO OUTFILE` 的注意点**：

```sql
-- ⚠️ 需要 FILE 权限 + secure_file_priv 目录
SELECT * FROM orders WHERE created_at < '2023-01-01'
INTO OUTFILE '/var/lib/mysql-files/orders_2023.tsv'
FIELDS TERMINATED BY '\t' ENCLOSED BY '"'
LINES TERMINATED BY '\n';

-- 归档库导入（比 INSERT 快 10~20 倍）
LOAD DATA INFILE '/var/lib/mysql-files/orders_2023.tsv' INTO TABLE orders_archive;
```

## 六、方案四：数仓/数据湖 ⭐（大数据量）

```
MySQL（热数据） 
     │ 每日增量同步（binlog / Airbyte / Canal / DataX）
     ↓
数仓（Hive/ClickHouse/Doris）  ← 全量历史，列存，适合分析
     │ 
     ↓
BI / 报表
```

**好处**：主库永远只留热数据；历史查询完全不占主库资源；分析查询可以很复杂（列存、MPP）。
**代价**：需要额外组件与同步链路。

## 七、其他配套手段 ⭐

| 手段 | 说明 |
|---|---|
| **软删除代替硬删除** | `deleted_at`，保留数据；但要注意唯一索引冲突（见"表设计"题）|
| **冗长大字段分离** | 把 `content`（TEXT）拆到独立表，主表保持精简 ⭐ 这是很有效的"轻量化" |
| **列表页不读大字段** | 用 `summary` 冗余列，避免列表查询拉出 `MEDIUMTEXT` |
| **摘要表/汇总表** | 统计类查询定时汇总（昨天/上周），避免每次扫全表 |
| **物化视图替代（定时任务）** | MySQL 无物化视图，用定时任务维护汇总表 |
| **读缓存（Redis）** | 热门查询结果缓存，减少 DB 压力 |
| **搜索引擎（ES）** | 全文检索/复杂筛选走 ES，DB 只负责事务性读写 ⭐ |

## 八、归档的完整决策流程 ⭐

```
① 数据增速评估：每月增长多少行/多少 GB？
② 访问分布评估：多少查询落在"最近 N 天"？（用慢查询日志/performance_schema 统计）
③ 选出"冷数据"的时间边界（如 3 个月）
④ 选方案：
   · 纯时间序列表（日志/流水）        → 分区 + DROP PARTITION ⭐ 最优
   · 有业务查询但可分流（订单/消息）  → 冷热分表 + 应用层路由
   · 需要长期保留+分析               → 归档库 / 数仓
   · 只需满足"可查询但不常用"        → 冷表 + 只读账号
⑤ 设计归档任务：分批、幂等、限速、可中断续跑、有进度记录 ⭐
⑥ 设计应用路由：查询怎么知道该查哪张表
⑦ 设计验证：归档前后行数、关键数据抽样对比
⑧ 设计回滚：归档出错了怎么恢复（从归档表往回搬）
```

## 九、一句话总结

**冷热分离的收益极高（80% 的查询只需 20% 的数据），首选"时间时序表用分区 + `DROP PARTITION`"**；需要保留可查时用"**冷热分表 + 应用层按时间路由**"；再大就上**归档库/数仓**。归档任务的铁律是：**先写后删、同一事务、按主键分批、批间 sleep、幂等可续跑、有进度记录**。""",
    ),
    (
        "MySQL",
        "索引管理,冗余索引,审计",
        2,
        r"""怎么发现冗余索引和从未使用的索引？删索引有什么风险、怎么做才安全？""",
        r"""## 一、冗余索引的判定 ⭐

**冗余（Redundant）**：**一个索引是另一个索引的"前缀"**，且没有额外价值。

```
索引 A: (a)        索引 B: (a, b)
  → A 是 B 的前缀 → A 冗余 ⭐（B 能完全替代 A 的定位能力）

索引 A: (a, b)     索引 B: (b, a)
  → 不冗余（前缀关系不成立，各有各的用途）
```

**为什么冗余有害**：

| 危害 | 说明 |
|---|---|
| **写放大** ⭐ | 每次 INSERT/UPDATE/DELETE 要维护**所有**索引 → 写性能下降 |
| **空间浪费** | 索引占空间（可能比数据还大）|
| **优化器困惑** | 候选计划变多 → 可能选错 |
| **DDL 变慢** | 重建表时要重建更多索引 |

**部分冗余的判定**：

```
索引 A: (a, b)   索引 B: (a, b, c)
  → A 是 B 的前缀 → A 冗余 ⭐

索引 A: (a, b)   主键 PK: (id)
索引 C: (a, b, id)  ← ⚠️ 注意：二级索引叶子本来就带主键
  → 显式加 id 到尾部的联合索引是"隐式冗余"（InnoDB 的二级索引自动附带主键）⭐
```

## 二、如何发现冗余索引 ⭐

### 方法 1：`sys` 库（最简单）⭐

```sql
SELECT * FROM sys.schema_redundant_indexes\G
-- 输出字段：
--   table_schema, table_name
--   redundant_index_name          ← 冗余的索引
--   redundant_index_columns
--   dominant_index_name           ← 能替代它的索引
--   dominant_index_columns
--   sql_drop_index                ← ⭐ 直接给出 DROP 语句！
```

**一条命令拿到可执行的 `DROP INDEX` 语句**，非常实用。

### 方法 2：手工分析（理解原理）

```sql
-- 列出所有索引的列（按顺序）
SELECT table_name, index_name, seq_in_index, column_name, non_unique
FROM information_schema.statistics
WHERE table_schema = 'blogdb' AND table_name = 'posts'
ORDER BY index_name, seq_in_index;
```

**判定规则**：

```
① 单列索引 (a) 与 (a, ...) 并存 → 单列的冗余
② (a, b) 与 (a, b, c) 并存 → (a,b) 冗余
③ 索引数与表列数相当 → 大概率过度索引
④ 注意主键：二级索引尾部隐式包含主键，所以 (a) 与 (a, id) 等价 ⭐
```

## 三、如何发现未使用的索引 ⭐

```sql
SELECT * FROM sys.schema_unused_indexes;
-- 输出：object_schema, object_name, index_name
```

**⚠️ 这个视图的巨大陷阱** ⭐：

| 陷阱 | 说明 |
|---|---|
| **统计窗口不完整** | 数据来自 `performance_schema`（内存表），**实例重启后清零** ⭐ 所以刚重启两天的实例，结论毫无意义 |
| **周期性业务未覆盖** | 月末结算、季度报表的 SQL 可能几个月才跑一次 ⭐ |
| **主从角色不同** | 从库的读模式和主库不同 |
| **唯一索引永远"被使用"** | 因为写入时要做唯一性检查，不算"未使用"（但可能仍可删）|
| **主键索引不会被列为 unused** | |
| **`performance_schema` 未开** | `table_io_waits_summary_by_index_usage` 需要在重启后运行足够久 |

**所以**：`schema_unused_indexes` 只作为**线索**，**绝不能直接照它删索引** ⭐

## 四、安全删索引的流程 ⭐⭐

**这是本问题的核心：删索引必须有"观察期"。**

```
① 先确认候选：sys.schema_unused_indexes + 人工核对（结合业务知识）
② 检查约束：这个索引是唯一索引吗？是主键吗？是外键需要的吗？⭐
③ 设为不可见（INVISIBLE），而不是直接删 ⭐⭐
   ALTER TABLE posts ALTER INDEX idx_x INVISIBLE;
④ 观察 N 天（至少覆盖一个业务周期，建议 2~4 周）⭐
   监控指标：慢查询数量、P99 延迟、错误率
⑤ 无异常 → 真正删除
   ALTER TABLE posts DROP INDEX idx_x;      （8.0 也可 ALTER INDEX idx_x INVISIBLE 后 DROP）
⑥ 有异常 → 立即恢复可见（秒级，无需重建表！）⭐
   ALTER TABLE posts ALTER INDEX idx_x VISIBLE;
```

**`INVISIBLE` 索引的价值** ⭐：

| 特性 | 说明 |
|---|---|
| **优化器忽略它** | 查询计划里不会选它（等价于"删了"）|
| **但仍在维护** | 写入时仍会更新它（**唯一区别：写入开销不省**）⚠️ |
| **秒级恢复可见** | 真正的 `DROP` 后要重建表（大表几小时）|
| **可查看影响** | `EXPLAIN` 看有没有计划变化 |

**⚠️ `INVISIBLE` 的代价**：索引**仍被维护**，所以**没有省下写开销和空间**。它的价值是**"安全试错"**——确认无用后再 `DROP` 才真正省下开销。

```sql
-- 检查哪些索引不可见
SELECT table_name, index_name, is_visible
FROM information_schema.statistics
WHERE is_visible = 'NO';

-- 建索引时直接设不可见
CREATE INDEX idx_new (col) INVISIBLE;
-- 然后手动让它可见（等价于"预热"一个新索引）
ALTER TABLE t ALTER INDEX idx_new VISIBLE;
```

**主键不能设为 INVISIBLE** ⚠️；**唯一索引可以**（但设为不可见后唯一约束**仍然生效**！因为约束不是靠索引查找实现的）⭐

## 五、索引审计的常规做法 ⭐

**定期（每季度）做一次索引体检**：

```sql
-- ① 冗余索引
SELECT * FROM sys.schema_redundant_indexes;

-- ② 未使用索引（仅供线索）
SELECT * FROM sys.schema_unused_indexes;

-- ③ 索引数量过多的表
SELECT object_name AS tbl, COUNT(DISTINCT index_name) AS idx_cnt
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE object_schema='blogdb'
GROUP BY object_name ORDER BY idx_cnt DESC LIMIT 20;
-- 一般单表索引数 > 6 就要审视 ⭐

-- ④ 索引空间占用 TOP
SELECT table_name, index_name,
       ROUND(SUM(stat_value * @@innodb_page_size)/1024/1024, 2) AS idx_mb
FROM mysql.innodb_index_stats
WHERE stat_name='size' AND database_name='blogdb'
GROUP BY table_name, index_name
ORDER BY idx_mb DESC LIMIT 20;   -- ⭐ 找出最占空间的索引

-- ⑤ 低选择性的索引（Cardinality 接近行数说明选择性差）
SELECT table_name, index_name, cardinality,
       (SELECT table_rows FROM information_schema.tables t2
         WHERE t2.table_schema=statistics.table_schema
           AND t2.table_name=statistics.table_name) AS rows_est,
       ROUND(cardinality / NULLIF((SELECT table_rows FROM information_schema.tables t2
             WHERE t2.table_schema=statistics.table_schema
               AND t2.table_name=statistics.table_name),0), 4) AS selectivity
FROM information_schema.statistics
WHERE table_schema='blogdb' AND seq_in_index=1
ORDER BY selectivity ASC LIMIT 20;   -- ⭐ 选择性最差的索引排最前
```

**选择性差的索引（< 0.01）通常没用**（如 `status` 只有 3 个值）—— **除非它出现在联合索引的第一位用于"低基数前缀 + 高基数后续列"的组合**，或配合 ICP 使用。

## 六、写索引的正确姿势 ⭐

| 原则 | 说明 |
|---|---|
| **优先联合索引** | 一个 `(a,b,c)` 常常能替代 `(a)`、`(a,b)`、`(a,b,c)` 三个 ⭐ |
| **高频查询优先** | 只为"出现频率高 + 单次耗时长"的查询建索引（用 `sys.statement_analysis` 找）|
| **覆盖索引控制列数** | 覆盖列太多会让索引膨胀 |
| **避免为低选择性列单独建索引** | `is_deleted`、`status` |
| **主键列不要重复加进二级索引尾部** | InnoDB 已隐式附带 ⭐ |
| **索引总数控制** | 单表 ≤ 5~6 个；写密集型表更要少 |
| **外键列要建索引** | MySQL 不自动为外键列建索引（与 Oracle 不同）⚠️ 这会导致父表删除时锁表 |
| **不要在相同列上建 (a) 和 (a, b)** | 典型冗余 |
| **字符集/collation 一致** | 否则 JOIN 时索引失效（见字符集题）|
| **命名规范** | `idx_表_列` / `uk_表_列`，便于审计 ⭐ |
| **变更走变更流程** | 用 `pt-osc`/`gh-ost`/`INVISIBLE`，不要直接从生产删 ⭐ |

## 七、外键索引的坑 ⭐

```sql
-- MySQL 建外键时会自动创建所需索引吗？
-- ⚠️ 只有当外键列上"没有可用索引"时才会自动创建；
--    如果已有索引但"前缀不匹配"，就会出问题
CREATE TABLE orders (
    id BIGINT PRIMARY KEY,
    user_id BIGINT,
    KEY idx_user_created (user_id, created_at),   -- 前缀匹配 user_id ✅ 可以
    FOREIGN KEY (user_id) REFERENCES users(id)
);
-- 子表上有 (user_id, ...) 的索引即可 ✅

-- ❌ 危险情况：子表外键列没有以该列开头的索引
--    → 删除父表记录时，子表要全表扫描确认无引用 → 长时间锁表 ⭐⭐
```

**实践建议**：互联网业务**尽量不用外键**，改在应用层保证引用完整性；如果用了，**务必给外键列建索引**。

## 八、一句话总结

**冗余索引 = "一个索引是另一个的前缀"，用 `sys.schema_redundant_indexes`（直接给 DROP 语句）检测**；**未使用的索引用 `sys.schema_unused_indexes`，但它重启就清零、有周期性盲区，绝不能照它直接删** ⭐；**安全删索引的唯一正确流程是"先 `INVISIBLE` 观察一个业务周期，再 `DROP`"**（`INVISIBLE` 秒级可回滚，但仍被维护所以不省开销）。""",
    ),
    (
        "MySQL",
        "C++,C API,后端集成,踩坑",
        3,
        r"""用 C/C++ 通过 MySQL C API 访问数据库有哪些常见坑？（结合 Crow 博客项目实战）""",
        r"""## 一、资源管理：必须成对释放 ⭐

| 资源 | 释放函数 | 常见泄漏点 |
|---|---|---|
| `MYSQL*` | `mysql_close()` | 异常/提前 return 时漏掉 |
| `MYSQL_RES*` | `mysql_free_result()` | **最常见** ⭐ 每次 `mysql_store_result` 都要释放 |
| `MYSQL_ROW` | 无需单独释放（属于 RES）| — |
| `MYSQL_STMT*` | `mysql_stmt_close()` | 预处理语句 |
| **`MYSQL_RES` 未释放的后果** | 内存泄漏 + **连接会一直处于"结果集未读完"状态**，后续查询报 `Commands out of sync` ⭐ |

**正解：RAII 包装** ⭐

```cpp
// 智能指针 + 自定义删除器
using ResPtr = std::unique_ptr<MYSQL_RES, decltype(&mysql_free_result)>;
using ConnPtr = std::unique_ptr<MYSQL, decltype(&mysql_close)>;

// 或包装成一个小 RAII 类
class QueryResult {
    MYSQL_RES* res_ = nullptr;
public:
    explicit QueryResult(MYSQL_RES* r) : res_(r) {}
    ~QueryResult() { if (res_) mysql_free_result(res_); }
    QueryResult(const QueryResult&) = delete;
    QueryResult& operator=(const QueryResult&) = delete;   // 防止重复释放 ⭐
    MYSQL_RES* get() const { return res_; }
};
```

## 二、`mysql_store_result` vs `mysql_use_result` ⭐

| | `mysql_store_result` | `mysql_use_result` |
|---|---|---|
| 行为 | **一次性把结果全拉到客户端内存** | 逐行从服务器读 |
| 内存 | 结果集大小（大结果集可能 OOM）⚠️ | 一行 |
| 速度 | 快（一次网络往返）| 慢（多往返）|
| 是否阻塞连接 | ✅ 可以立刻发下一条查询 | ❌ 结果没读完前**不能发其他查询** ⭐ |
| 适用 | 一般查询（结果集不大）| 超大结果集（导表）|

**坑**：用 `mysql_use_result` 时如果结果没读完就发别的查询 → `Commands out of sync; you can't run this command now` ⭐

**判断是否有结果集**：

```cpp
if (mysql_field_count(conn) > 0) {
    MYSQL_RES* res = mysql_store_result(conn);
    // SELECT 类语句
} else {
    // INSERT/UPDATE/DELETE，无结果集
    // 用 mysql_affected_rows(conn) 获取影响行数
}
```

**⚠️ `mysql_store_result` 返回 NULL 有两种情况** ⭐：

```cpp
MYSQL_RES* res = mysql_store_result(conn);
if (!res) {
    if (mysql_field_count(conn) == 0) {
        // ✅ 正常：这不是 SELECT（无结果集）
    } else {
        // ❌ 真的出错了
        std::cerr << mysql_error(conn) << std::endl;
    }
}
```

**不做这个区分就会误判"查询失败"**。

## 三、错误处理 ⭐

```cpp
if (mysql_query(conn, sql.c_str()) != 0) {
    // 用 mysql_error 拿可读信息，mysql_errno 拿错误码 ⭐
    std::cerr << "SQL error " << mysql_errno(conn) << ": " << mysql_error(conn)
              << " | SQL: " << sql << std::endl;
}
```

**要点**：

| 要点 | 说明 |
|---|---|
| **一定要在日志里带上 SQL** | 否则无法定位 ⭐（但**要注意脱敏**，别把密码写进日志）|
| **错误信息不要返回给前端** | 会泄露表名/结构（见安全那题）|
| **区分错误码做业务处理** ⭐ | `1062` = 唯一键冲突（可提示"已存在"）、`1213` = 死锁（可重试）、`1205` = 锁等待超时（可重试）、`1040` = 连接过多、`2006/2013` = 连接断开 |
| **`mysql_errno` 不能用于连接级错误** | 连接断开时要用 `mysql_errno` 的 2000+ 段（客户端错误）；`mysql_error` 依然可用 |

**错误码处理示例** ⭐：

```cpp
int err = mysql_errno(conn);
if (err == 1062) {                      // 唯一键重复
    return error(409, "记录已存在");
} else if (err == 1213 || err == 1205) { // 死锁 / 锁超时
    retry();                             // 有限次重试
} else if (err == 2006 || err == 2013) { // server gone away / lost connection
    reconnect();                         // 重连并重试
}
```

## 四、字符集（本项目实战重灾区）⭐⭐

```cpp
// 连接后必须确认/设置字符集
mysql_options(conn, MYSQL_SET_CHARSET_NAME, "utf8mb4");   // 在 mysql_real_connect 之前调用
mysql_real_connect(conn, host, user, pass, db, port, NULL, 0);
// ⚠️ 某些环境/版本下 MYSQL_SET_CHARSET_NAME 未生效！
// 兜底：连接后显式执行 ⭐
mysql_query(conn, "SET NAMES utf8mb4");
```

**本项目踩过的完整链条**（详见"字符集"那题）：

```
① 老表数据是"经 latin1 连接写入"的 → 存的是 UTF-8 字节的 cp1252 转义
② 应用连接恰好是 latin1 → 读老表正常显示（整站靠这个巧合工作）
③ questions 表是 mysql CLI 以 utf8mb4 导入的真中文 → latin1 连接读 → 逐字符变 ?
④ 判据：1 汉字 : 1 ? ⇒ MySQL 字符集转换；1 汉字 : 3 ? ⇒ 程序按字节处理
```

**教训** ⭐：

| 教训 | 说明 |
|---|---|
| **连接字符集必须显式验证** | 用 `SHOW VARIABLES LIKE 'character_set_client'` 确认，别假设 `MYSQL_SET_CHARSET_NAME` 生效了 ⭐ |
| **不要凭 UI 截图判断** | 必须用 `curl` / `HEX()` 这类非视觉证据 |
| **诊断命令要能"测出差异"** | `HEX(LEFT(question,4))` 取到的是 ASCII 前缀 `std:`（恒为 `7374643A`），测不出问题 ⭐⭐ |
| **迁移顺序：备份 → 迁数据 → 再部署新二进制** | 反过来部署 = 整站立刻乱码 |
| **换解释方式 ≠ 重新编码** | 用 `CONVERT(... USING latin1) → CAST AS BINARY → CONVERT(... USING utf8mb4)`，**不要用 `ALTER TABLE ... CONVERT TO`** ⭐ |

## 五、SQL 注入防护 ⭐

见"权限与安全"那题，这里只强调 **C API 特有的两点**：

| 要点 | 说明 |
|---|---|
| **不要开 `CLIENT_MULTI_STATEMENTS`** | 否则一条 SQL 里能用 `;` 执行多条 → 注入危害翻倍 ⭐ |
| **`mysql_real_escape_string` 依赖连接字符集** ⭐ | 连接字符集不对（如 latin1）时会**漏转义**某些多字节字符 → 注入风险。**必须先 `SET NAMES utf8mb4` 再转义** |
| **`mysql_stmt_*` 预处理更安全** | 结构/数据分离，原理上不可能注入 ⭐ |
| **`mysql_real_escape_string` 需要有效连接** | 传 NULL 连接会失败 |

**预处理 + 缓冲区的正确写法**（容易漏 `buffer_length`）⭐：

```cpp
MYSQL_BIND bind = {};
std::string val = "abc";
unsigned long len = val.size();
bind.buffer_type   = MYSQL_TYPE_STRING;
bind.buffer        = const_cast<char*>(val.data());
bind.buffer_length = static_cast<unsigned long>(val.size());  // ⭐ 必须设，否则可能读越界
bind.length        = &len;                                     // ⭐ 变长类型需 length 指针
mysql_stmt_bind_param(stmt, &bind);
```

## 六、连接与线程安全 ⭐⭐

**这是 C++ 多线程服务（如 Crow 的 `multithreaded()` 模式）最容易出事的地方**：

| 要点 | 说明 |
|---|---|
| **`mysql_init` 必须在 `mysql_thread_init` 之后** | 通常自动调用；但**手动创建线程时**要在该线程里调用 `mysql_thread_init()` ⭐ |
| **一个 `MYSQL*` 连接不能被多个线程同时使用** ⭐⭐ | 连接是**非线程安全**的！多线程共享同一连接会导致协议错乱、结果串包、崩溃 |
| **正确做法：每线程一个连接，或连接池** ⭐ | 池化时注意"借出的连接只能被借出它的线程用" |
| **`mysql_library_init` / `mysql_library_end`** | 进程级初始化/清理（`mysql_init` 会自动调用前者）|
| **`mysql_thread_end()`** | 线程退出前调用，释放线程局部存储（否则内存泄漏）⭐ |
| **Crow 场景** | Crow 的 handler 在**事件循环线程**里执行 → 建议按线程维护连接，或用**带锁的连接池** |

**本项目（Crow 多线程）的正确架构** ⭐：

```
方案 A（简单）：每个 worker 线程一个 MYSQL* 连接（thread_local）
    thread_local MYSQL* conn = nullptr;
    if (!conn) { conn = mysql_init(nullptr); ... mysql_real_connect(...); }
    → 每个线程独立连接，天然无竞争 ✅
    ⚠️ 缺点：连接数 = 线程数（Crow 默认线程数较多，连接数会偏多）

方案 B（推荐）：连接池
    维护一个 std::vector<MYSQL*> + mutex + condition_variable
    借出时从池取，用完归还
    ⚠️ 归还前必须把连接"清理干净"：确保上一条查询的结果集已 free
    ⚠️ 检测到连接断开（2006/2013）时丢弃并新建

方案 C：每次请求新建连接
    ❌ 性能差（握手 + 认证开销），高并发下会打满 max_connections
```

**连接池归还前的清理** ⭐（极易忽略）：

```cpp
void ConnPool::release(MYSQL* c) {
    // ⭐ 关键：确保没有未读完的结果集，否则下个使用者会拿到 "Commands out of sync"
    while (mysql_next_result(c) == 0) {          // 处理多结果集
        MYSQL_RES* r = mysql_store_result(c);
        if (r) mysql_free_result(r);
    }
    // 重置会话状态（防止 SET 语句污染下一个使用者）
    // mysql_query(c, "ROLLBACK");   // 若启用了事务
    { std::lock_guard<std::mutex> lk(mu_); idle_.push_back(c); }
    cv_.notify_one();
}
```

## 七、其他容易踩的点 ⭐

| 坑 | 说明 |
|---|---|
| **`mysql_real_connect` 的 `client_flag`** | 不要开 `CLIENT_MULTI_STATEMENTS`；需要事务可用 `CLIENT_FOUND_ROWS`（让 `affected_rows` 返回"匹配的行数"而非"实际改变的行数"）⭐ |
| **`Wait_timeout` 断连** | 空闲太久连接被服务端断掉 → 报 2006/2013。**池要设 `max_lifetime` < `wait_timeout`**，并做"借出前探活"（`mysql_ping`）⭐ |
| **`MYSQL_OPT_RECONNECT`** | 自动重连**有陷阱**（重连后会丢会话状态：临时表、用户变量、事务）→ 官方不推荐依赖它 ⭐ 应该自己管理重连 |
| **`mysql_ping` 开销** | 每次借出都 ping 会多一次往返；可用 `mysql_options(..., MYSQL_OPT_CONNECT_TIMEOUT)` + 定期探活 |
| **`max_allowed_packet`** | 插入大文本/BLOB 超过限制会断连 → 调大服务端参数，并注意客户端 `MYSQL_OPT_MAX_ALLOWED_PACKET` ⭐ |
| **`mysql_affected_rows` 的语义** | `UPDATE` 时返回**实际被改变的行数**；若值没变则返回 0（容易误判"更新失败"）→ 需要"匹配行数"就开 `CLIENT_FOUND_ROWS` ⭐ |
| **`mysql_insert_id` 类型** | 返回 `my_ulonglong`，不要截断成 `int` ⭐ |
| **`MYSQL_ROW` 里的 NULL** | 用 `mysql_fetch_lengths` 判断：**长度为 0 且指针为 NULL 才是 SQL NULL**；长度 0 但指针非 NULL 是空串 ⭐ 这是很难发现的坑 |
| **大结果集 + `mysql_store_result`** | 内存胀大（尤其 `content` 这类 TEXT）→ 用 `LIMIT` 或 `use_result` |
| **`mysql_query` 与 `mysql_real_query`** | 有二进制数据（含 `\0`）时必须用 `mysql_real_query` 并传长度 ⭐ |
| **`MYSQL_OPT_CONNECT_TIMEOUT` / `READ_TIMEOUT` / `WRITE_TIMEOUT`** | 必须设置，避免请求线程被卡死 ⭐ |

**NULL 判断的正确写法** ⭐：

```cpp
MYSQL_ROW row = mysql_fetch_row(res);
unsigned long* lengths = mysql_fetch_lengths(res);
// NULL 判断：
bool is_null = (row[i] == nullptr);
// 空串：
bool is_empty = (row[i] != nullptr && lengths[i] == 0);
// 取值（必须用 lengths，不能用 strlen —— 二进制数据含 \0）
std::string val(row[i], lengths[i]);   // ⭐ 正确
// std::string val(row[i]);            // ❌ 遇到 \0 会截断
```

**注意 `MYSQL_OPT_RECONNECT` 的官方立场** ⭐：MySQL 8.0.34+ 中该选项已被标记为 **deprecated**，官方明确建议**不要依赖自动重连**，而应在应用层实现重连逻辑（因为重连会静默丢失会话状态）。

## 八、一句话总结

**C API 的坑集中在四类：资源（RAII 保证 `free_result`/`close`）、字符集（显式 `SET NAMES` 并验证）、线程安全（连接非线程安全，多线程必须每线程连接或池化）、错误处理（错误码分支 + 池归还前清理结果集）**；本项目尤其要注意 **`mysql_store_result` 返回 NULL 的双重含义**、**连接字符集与老数据形态的匹配**、以及 **Crow 多线程下每个线程独立连接**。""",
    ),
    (
        "MySQL",
        "云数据库,RDS,选型",
        2,
        r"""自建 MySQL 和云数据库（RDS）怎么选？云 RDS 有哪些隐藏的坑？""",
        r"""## 一、对比总表 ⭐

| 维度 | **自建 MySQL** | **云 RDS** |
|---|---|---|
| **初始成本** | 低（自己装）| 略高（含托管费）|
| **运维人力** ⭐ | **高**（备份、监控、扩容、故障、升级、安全）| **低**（厂商托管）|
| **高可用** | 要自己搭 MHA/MGR ⭐ | 一键多可用区 ⭐ |
| **备份** | 自己写脚本 + 验证 | 自动备份 + 时间点恢复 ⭐ |
| **监控** | 自己搭 Prometheus + Grafana | 自带看板 + 告警 ⭐ |
| **权限** ⭐ | **完全控制**（可改任意参数、装插件、`SUPER` 权限）| **受限**（部分参数不可改、无 `SUPER`、不能装任意插件）⚠️ |
| **版本与内核** | 任意版本、可编译 Percona 版 | 仅厂商支持版本 |
| **成本弹性** | 需预留峰值资源 | 按需升降配 ⭐ |
| **数据主权** | 完全自己掌握 | 数据在厂商（可用加密/专有云缓解）⭐ |
| **延迟** | 内网极低 | 同可用区较低，跨可用区有额外延迟 |
| **常见场景** | 有 DBA、有特殊需求、成本敏感的大规模部署 | 中小团队、快速上线、无专职 DBA ⭐ |

## 二、成本真相（容易被忽略）⭐

```
自建的真实成本 = 机器 + 磁盘 + 机房/带宽 + 备份存储
                 + 【人力成本】⭐ + 【故障损失】

云 RDS 的成本 = 实例费 + 存储费 + 备份费 + 流量费
                + 【跨可用区/只读实例的额外费用】⚠️
```

**关键判断**：

| 场景 | 建议 |
|---|---|
| **没有专职 DBA** + 业务重要 | **云 RDS** ✅ |
| 有 DBA + 规模很大（几十个实例） | 自建可能更省（但要算人力和故障成本）|
| 有特殊内核/插件需求 | 自建（或用云上的"专属实例"）|
| 只是练手/博客/小工具 | **自建**或云上最低配 ✅ |
| 需要极致成本优化 | 自建裸金属 |

## 三、云 RDS 的"隐藏坑" ⭐

### 1. 参数受限 ⭐

| 受限项 | 影响 |
|---|---|
| **无 `SUPER` 权限** | 很多诊断和运维操作做不了 |
| **`sync_binlog` / `innodb_flush_log_at_trx_commit` 不可改** | 厂商为了保证高可用，通常**强制双 1** → 写入性能比自建可调的差 ⭐ |
| **不能装插件** | 审计插件、`semisync` 等要看厂商是否支持 |
| **某些参数有上下限** | `max_connections`、`innodb_buffer_pool_size` 与所选规格绑定 ⭐（小规格实例的 buffer pool 很小，性能上不去）|
| **不能直接访问底层文件** | 无法手动拷数据文件（但 Clone 插件可能可用）|

**实践建议**：**买之前先看厂商的"参数白名单"文档**，确认关键参数（`sql_mode`、`character_set_*`、`transaction_isolation`、`binlog_format`、`slow_query_log`）能改 ⭐

### 2. 规格与性能不成正比 ⭐

```
⚠️ 云 RDS 的"规格"通常同时决定 CPU、内存、连接数上限、IOPS
   → 小规格实例可能"连接数上限只有几十" → 业务莫名报 Too many connections ⭐
   → 存储 IOPS 与容量挂钩（容量小 → IOPS 低 → 慢查询）⚠️
```

**要检查的三项**：CPU 核数、内存、**最大连接数**、**存储 IOPS 上限** ⭐

### 3. 跨可用区/多可用区的延迟 ⭐

```
主可用区 A ←→ 备可用区 B
   · 同步复制（半同步）→ 每次提交多一个跨 AZ 的 RTT（可能 1~3ms）⭐
   · 高并发小事务场景，这个延迟会显著降低 TPS
   · 单可用区（无高可用）延迟低但故障会中断
```

**权衡**：**关键业务用多可用区（可接受延迟换取高可用）；极致延迟场景用单可用区 + 云盘快照**。

### 4. 只读实例的坑 ⭐

| 坑 | 说明 |
|---|---|
| **延迟不可控** | 官方通常只保证"最终一致"，延迟可能秒级 |
| **按规格计费** | 只读实例也是钱 ⚠️ |
| **不支持所有引擎/版本组合** | |
| **连接地址不同** | 应用要改配置 |

### 5. 备份与恢复 ⭐

| 坑 | 说明 |
|---|---|
| **备份保留期有限**（通常 7~30 天）| 长期归档要自己导出 ⭐ |
| **跨地域备份要额外付费** | |
| **恢复到新实例耗时**（可能几十分钟到几小时）| RTO 要实测 ⭐ |
| **逻辑备份（mysqldump）在云上受限** | 可能没有 `FILE` 权限（`INTO OUTFILE` 不可用）⭐ |
| **`pt-*` 工具部分受限** | 需要 `SUPER` 或特定权限的场景会失败 |

### 6. 其他

| 坑 | 说明 |
|---|---|
| **版本升级不可随意** | 厂商可能只支持特定版本的升级路径 |
| **大版本升级要停机**或走"建新实例 + DTS 迁移" |
| **云盘突发性能耗尽** | 某些云盘有"突发 IOPS 额度"，用完就掉速 ⚠️ |
| **公网访问** | 默认仅内网；开公网要额外配置且有安全风险 |
| **账号体系** | 通常有"高权限账号"和"普通账号"两级；**高权限账号仍不是 root** ⭐ |
| **跨云迁移成本** | 数据导出、格式兼容、停机窗口 ⭐ |
| **计费陷阱** | 快照存储、跨区域流量、备份存储都可能额外计费 ⚠️ |

## 四、选型决策树 ⭐

```
开始
 │
 ├─ 有专职 DBA 吗？
 │    ├─ 没有 → 【云 RDS】⭐
 │    └─ 有 →
 │         ├─ 实例数 > 20 且规模大吗？
 │         │    ├─ 是 → 自建可能更省（但要算故障成本）
 │         │    └─ 否 → 【云 RDS】更省心 ⭐
 │
 ├─ 有特殊需求吗（特定内核/插件/任意参数）？
 │    ├─ 有 → 自建 或 云的"专属/独享"实例
 │    └─ 无 → 【云 RDS】
 │
 ├─ 预算极紧 且 数据可容忍短时中断？
 │    ├─ 是 → 自建单机 + 定时备份 ⭐（本项目场景）
 │    └─ 否 → 【云 RDS 高可用版】
 │
 └─ 需要全球部署？
      ├─ 是 → 多云/多区域方案（更复杂，可能自建+云混合）
      └─ 否 → 【云 RDS】
```

## 五、折中方案 ⭐

| 方案 | 说明 |
|---|---|
| **云主机 + 自建 MySQL** ⭐ | 便宜、可控，但**要自己做高可用和备份**（本项目就在这条路上）|
| **云 RDS + 自建从库** | 主库用 RDS（托管高可用），从库自建（便宜，用于分析/备份）|
| **混合云** | 核心数据 RDS，日志/分析自建 |
| **Serverless 数据库** | 按用量计费（如 Aurora Serverless、云原生 Serverless MySQL），适合间歇性负载 ⭐ |
| **NewSQL**（TiDB Cloud / OceanBase）| 原生分布式，免分库分表 ⭐ 但成本高 |
| **托管 + 只读实例 + 分析型数据库** | 事务在 RDS，分析在 ClickHouse/Doris ⭐ |

## 六、本项目（博客系统）的定位 ⭐

**当前**：云主机 + 自建 MySQL + systemd 部署（`blog.service` → `task_server` :8080）

**这个选择是合理的**，因为：

```
✔ 流量小，单机足够
✔ 成本敏感
✔ 需要完全控制（改字符集、参数、直接访问文件、用 mysql CLI 导入种子 SQL）⭐
✔ 没有专职 DBA，但运维复杂度可控
```

**应该补的三件事**（成本极低、收益极高）⭐：

| 事项 | 做法 |
|---|---|
| **① 定时备份 + 验证恢复** | `mysqldump` + cron 到对象存储；**每月真实恢复演练一次** ⭐ |
| **② 创建最小权限的应用账号** | 别用 root 跑应用（本项目 README 提到 `blog` 账号但服务器只有 root —— 应该真的创建它）⭐ |
| **③ 慢查询日志开启** | `slow_query_log=ON`, `long_query_time=1`，定期看 ⭐ |

**如果要升级**：加一个从库（异地/同机房）做备份 + 只读查询，成本很低但能显著提升可用性。

## 七、迁移到云的注意点 ⭐

```
① 版本兼容：云上的版本可能与自建不同 → 先测 sql_mode、字符集、认证插件 ⭐
② 权限模型：从 root 改成云的高权限账号 → 应用连接串要改，且某些 SQL 会失败
③ 参数差异：云**强制双 1**，写入性能可能下降
④ 字符集：**迁移必须用 --default-character-set=utf8mb4 导出** ⭐ 否则乱码（本项目刚踩过）
⑤ 网络：内网打通（VPC）、白名单、SSL
⑥ 停机窗口：用 DTS/双写减少停机
⑦ 验证：迁移后逐表对比行数与校验和（pt-table-checksum）
⑧ 回滚方案：保留自建实例一段时间 ⭐
```

**导出命令的字符集参数是本项目的血泪教训** ⭐：

```bash
mysqldump -u root -p --default-character-set=utf8mb4 \
  --single-transaction --routines --triggers --events \
  --hex-blob blogdb > blogdb_$(date +%F).sql
# ⚠️ 不写 --default-character-set 很可能导出乱码
```

## 八、一句话总结

**没有专职 DBA 就用云 RDS（备份/高可用/监控都是白送的）**；云 RDS 的坑集中在 **参数受限（尤其强制双 1）、规格与连接数/IOPS 绑定、跨可用区延迟、备份保留期**；**小站（如本项目）用"云主机 + 自建 MySQL"完全合理，但必须补上"定时备份 + 恢复演练 + 最小权限账号 + 慢查询日志"这四件低成本高收益的事**。""",
    ),
    (
        "MySQL",
        "执行流程,架构,Server层",
        2,
        r"""一条 SQL 从客户端发出到返回结果，中间经历了哪些阶段？Server 层和引擎层各自负责什么？""",
        r"""## 一、整体链路 ⭐

```
客户端 → 【连接器】→ 查询缓存(8.0已移除) → 【解析器】→ 【预处理器】→ 【优化器】→ 【执行器】
                                                                                    ↓
                                                                        【存储引擎层 InnoDB】
                                                                                    ↓
                                                             Buffer Pool / redo / undo / 数据页
```

## 二、逐层拆解 ⭐

### ① 连接器（Connection Layer）

```
· TCP 握手 → 认证（账号密码 + host）→ 权限表查询 → 分配线程
· 读取该用户的权限，缓存到会话（⚠️ 之后改权限不影响已建立的连接）
```

**关键点**：

| 点 | 说明 |
|---|---|
| **连接是"重量级"的** ⭐ | 需 TCP + 认证 + 分配线程 + 会话内存（200KB~1MB），所以要用连接池 |
| **`wait_timeout`** | 空闲超过该时间连接被断开（默认 28800s）|
| **权限缓存** | 会话建立后改权限不生效，需 `FLUSH PRIVILEGES` + 重连 ⭐ |
| **一个连接一个线程** | 这就是 `max_connections` 与内存挂钩的原因 |
| **8.0 的 `caching_sha2_password`** | 首次认证较重，之后有缓存 |

### ② 查询缓存（已废弃）⚠️

```
5.7 及之前：以 SQL 文本 + 数据库为 key 缓存结果，命中直接返回
问题：
  · 任何对该表的写操作都会让所有相关缓存失效 → 命中率极低 ⭐
  · 额外的加锁与内存管理开销
  · 很多人的经验是"开了更慢"
→ 【MySQL 8.0 彻底移除】⭐
```

**现状**：缓存交给应用层/Redis/ProxySQL。

### ③ 解析器（Parser）

```
① 词法分析：把 SQL 拆成 token（关键字、标识符、字面量、运算符）
② 语法分析：生成【语法树（parse tree）】
③ 若语法错误 → ERROR 1064 (You have an error in your SQL syntax) ⭐
```

**注意**：**解析阶段不做语义校验**（表存不存在、列对不对是下一步）。

### ④ 预处理器（Preprocessor）

```
① 语义校验：表/列是否存在？别名是否冲突？权限是否足够？
② 把 `SELECT *` 展开为具体列
③ 处理视图（展开视图定义）
④ 生成"规范化的语法树"
```

**这一步会报的典型错误**：`ERROR 1146 Table doesn't exist`、`ERROR 1054 Unknown column` ⭐

### ⑤ 优化器（Optimizer）⭐

```
① 逻辑优化：子查询上拉/物化、外连接转内连接、常量折叠、谓词下推、
              等价类推导、`GROUP BY` 优化（松散索引扫描）
② 物理优化：基于【代价模型】选择
   · 访问路径（全表 / 索引 / 覆盖索引 / ICP / MRR）
   · 连接顺序（表数 ≤ 7 穷举，> 7 贪心启发式）⭐
   · 连接算法（NLJ / BNL / BKA / Hash Join）
③ 生成【执行计划】
```

**关键**：**优化器只做"逻辑等价"的改写，不改语义**。它的选择依赖**统计信息**（见"统计信息与优化器"那题）。

### ⑥ 执行器（Executor）

```
① 检查权限（表级/列级）—— 权限校验在优化器之后 ⭐ 有点反直觉
② 按执行计划"自顶向下"调用存储引擎接口
③ 逐行处理：
   · 若无索引 → 用 InnoDB 的"全表扫描接口"（read_first_row / read_next_row）
   · 若有索引 → 用"索引扫描接口"（index_first / index_next）
   · 判断是否满足 WHERE → 满足则加入结果集
④ 把结果集返回客户端
```

**执行器只用 4 类接口** ⭐：`read_first_row`、`read_next_row`、`index_first`、`index_next`。这就是"**MySQL 执行器与引擎之间的握手协议**"。

## 三、Server 层 vs 引擎层 ⭐

| 层次 | 组件 | 职责 |
|---|---|---|
| **Server 层** | 连接器、查询缓存、解析器、优化器、执行器 | **所有引擎共有的逻辑**：SQL 解析、优化、执行调度 |
| **引擎层（InnoDB）** | 数据读写、事务、锁、MVCC、redo/undo | **数据的存与取** |
| **Server 层还有** | **binlog**（所有引擎共用）| 复制与恢复 ⭐ |
| **InnoDB 还有** | **redo log / undo log**（引擎私有）| 崩溃恢复 / 回滚 ⭐ |

**Server 层独有的关键概念**：

```
· 视图、触发器、存储过程、函数、事件
· binlog（与引擎无关）
· 表定义/权限/字符集
· `SET` 类语句（会话变量）
· `SELECT` 里的表达式求值、函数计算
· 排序、临时表、`GROUP BY`、`DISTINCT` 的 Server 层实现
```

**引擎层独有的**：

```
· 索引组织（B+ 树、聚簇/二级索引）
· 事务与隔离级别实现（MVCC、Next-Key Lock）
· 锁的粒度（行锁/表锁/意向锁）
· redo log / undo log
· 双写缓冲、Buffer Pool、Change Buffer、AHI
· 崩溃恢复
```

**一句话区分** ⭐：**"SQL 语义归 Server 层，数据语义归引擎层"**。

## 四、`SELECT` 的完整实例 ⭐

```sql
SELECT id, title FROM posts WHERE status = 1 ORDER BY created_at DESC LIMIT 20;
```

```
① 连接器：认证、分配线程
② （5.7 的查询缓存：key = 整个 SQL 文本，未命中）
③ 解析器：生成语法树（SELECT / FROM / WHERE / ORDER BY / LIMIT 节点）
④ 预处理器：查表存在？列存在？权限够？展开 `*`（本例已显式列名）
⑤ 优化器：
   · 候选 1：全表扫描 + 排序 → cost = 45000（假设 45000 行）
   · 候选 2：用 idx(status, created_at) 索引 → cost = 25 ✅ 选它
   · 生成计划：index scan on idx_status_created, 带 LIMIT 提前终止
⑥ 执行器：
   · 调 InnoDB 的 index_first/index_next 遍历 idx(status, created_at)
   · status=1 满足 → 取 (id, title)（若索引含这两列则覆盖索引，否则回表）
   · 每拿到一行就检查 ORDER BY 是否天然满足 → 满足则直接输出 ⭐
   · 累积到 20 行 → LIMIT 提前终止，不再扫描 ⭐
⑦ 返回结果集给客户端
```

**注意两个优化点**：**覆盖索引免回表** + **LIMIT 提前终止**（这是 INDEX + ORDER BY 命中时能很快的原因）。

## 五、`UPDATE` 的完整流程 ⭐

```sql
UPDATE posts SET views = views + 1 WHERE id = 100;
```

```
①~⑥ 同上（Server 层解析/优化/执行）
⑦ 执行器调用 InnoDB 接口：先"当前读" id=100 的行（加 X 锁）⭐
⑧ InnoDB：
   · 从 Buffer Pool 找页；不在则从 .ibd 读入
   · 写 undo log（记录旧值，供回滚 + MVCC）⭐
   · 修改 Buffer Pool 中的页（标脏）
   · 写 redo log 到 Log Buffer
⑨ Server 层写 binlog（事务提交时）
⑩ 提交：
   · 【两阶段提交】：redo prepare → 写 binlog → redo commit ⭐
   · 按 `innodb_flush_log_at_trx_commit` 和 `sync_binlog` 刷盘
⑪ 返回 affected_rows 给客户端
⑫ 脏页由 Page Cleaner 异步刷盘（可能很久之后）
```

## 六、常见的"阶段相关"错误排查 ⭐

| 报错/现象 | 阶段 | 原因 |
|---|---|---|
| `ERROR 1064` 语法错误 | 解析器 | SQL 写错了（**注意：8.0 新增保留字如 `RANK`/`LEAD` 要加反引号**）⭐ |
| `ERROR 1054 Unknown column` | 预处理器 | 列不存在（可能是 `sql_mode` 或视图展开问题）|
| `ERROR 1146 Table doesn't exist` | 预处理器 | 表不存在 / 选错库 |
| `ERROR 1142 command denied` | 执行器（权限校验）| 权限不足 |
| **SQL 慢但 `EXPLAIN` 看起来正常** | 优化器 | 统计信息失真，选了次优计划 ⭐ |
| **`Rows_examined` 很大** | 执行器 | 扫描行数多（索引不好）⭐ |
| **`Commands out of sync`** | 连接器/协议 | 上一条语句的结果集没读完（C API 场景）|
| **`Too many connections`** | 连接器 | 连接打满 |

## 七、一句话总结

**一条 SQL 的路径是"连接器 → （旧版查询缓存）→ 解析器 → 预处理器 → 优化器 → 执行器 → 引擎层"**；**Server 层负责"SQL 语义"（解析/优化/调度/binlog），引擎层负责"数据语义"（读写/事务/锁/MVCC/redo/undo）**；**优化器是性能的关键节点**（依赖统计信息，容易选错计划），**执行器只有 4 个引擎接口**（`read_first/read_next/index_first/index_next`）。""",
    ),
    (
        "MySQL",
        "慢查询,实战,优化清单",
        3,
        r"""线上发现一条慢 SQL，完整的排查与优化流程是什么？""",
        r"""## 一、标准流程（七步）⭐

```
① 确认现象 → ② 采集证据 → ③ 分析执行计划 → ④ 定位根因
                                        ↓
                   ⑧ 回归验证 ← ⑦ 上线灰度 ← ⑥ 实施 ← ⑤ 制定方案
```

## 二、① 确认现象 ⭐

| 问题 | 要问清楚的 |
|---|---|
| 什么时候慢 | 一直慢 / 偶发 / 高峰期 |
| 有多慢 | P50 / P95 / P99（**平均值会掩盖长尾**）⭐ |
| 影响什么 | 单个接口 / 整个站点 |
| 数据量 | 表多少行、结果集多大 |
| 最近有变化吗 | 上线？数据增长？索引被删？ |

**判断"一直慢"还是"偶发慢"极其重要** ⭐：
- **一直慢** → 索引/写法问题 → `EXPLAIN`
- **偶发慢** → 锁等待、IO 抖动、统计信息、缓冲区冷、主从延迟 ⭐

## 三、② 采集证据 ⭐

```sql
-- 1. 慢查询日志（最直接）⭐
SHOW VARIABLES LIKE 'slow_query_log';
SHOW VARIABLES LIKE 'long_query_time';
-- 日志条目里的关键字段：
--   Query_time  总耗时
--   Lock_time   锁等待（大 → 锁竞争）⭐
--   Rows_sent   返回行数
--   Rows_examined  扫描行数 ⭐ Rows_examined/Rows_sent 比值是关键判据

-- 2. 此刻正在跑什么
SHOW FULL PROCESSLIST;
SELECT id, user, host, db, command, time, state, LEFT(info,200) sql
FROM information_schema.processlist
WHERE command <> 'Sleep'
ORDER BY time DESC LIMIT 20;      -- ⭐ time 大 = 长耗时

-- 3. 按 SQL 模板聚合（比慢日志更强）⭐
SELECT query, exec_count, total_latency, avg_latency,
       rows_examined_avg, rows_sent_avg, tmp_tables, full_scans
FROM sys.statement_analysis
ORDER BY total_latency DESC LIMIT 10;

-- 4. 全表扫描的 SQL
SELECT * FROM sys.statements_with_full_table_scans ORDER BY total_latency DESC LIMIT 10;

-- 5. 索引使用情况
SELECT * FROM sys.schema_unused_indexes;         -- 白建的索引
SELECT * FROM sys.schema_redundant_indexes;      -- 冗余索引

-- 6. 锁等待现场（偶发慢的头号嫌疑）⭐
SELECT * FROM sys.innodb_lock_waits\G
-- 输出：waiting_pid, waiting_query, blocking_pid, blocking_query

-- 7. InnoDB 内部状态
SHOW ENGINE INNODB STATUS\G
-- 看：History list length（长事务）、Buffer pool hit rate（内存）、
--     LATEST DETECTED DEADLOCK、Log sequence number - Last checkpoint
```

## 四、③ 分析执行计划 ⭐

```sql
EXPLAIN <SQL>;                        -- 基础
EXPLAIN FORMAT=JSON <SQL>;            -- 含 cost 明细与"考虑过的其他计划" ⭐
EXPLAIN FORMAT=TREE <SQL>;            -- 树形，8.0 默认风格
EXPLAIN ANALYZE <SQL>;                -- ⭐ 真实执行，对比"估算行数 vs 实际行数"
SHOW WARNINGS;                        -- 看优化器改写后的 SQL（很有用）
```

**`EXPLAIN ANALYZE` 的输出解读** ⭐：

```
-> Limit: 20 row(s)  (cost=... rows=20) (actual time=0.05..8234 rows=20 loops=1)
                                        ↑ 估算           ↑ 实际（8234ms！）
    -> Index scan on posts using idx_status  (cost=... rows=20) (actual time=0.04..8230 rows=450000 loops=1)
                                                                              ↑ 实际扫了 45 万行 ⭐
```

**关键判据** ⭐：

| 现象 | 结论 |
|---|---|
| **估算行数 ≪ 实际行数** | **统计信息失真** → `ANALYZE TABLE`、加直方图 ⭐ |
| **`rows_examined ≫ rows_sent`** | 索引不好 → 加/改索引 |
| **`type=ALL`** | 全表扫描 → 需要索引或改写 |
| **`Using filesort`** | 额外排序 → 让索引覆盖 `ORDER BY` ⭐ |
| **`Using temporary`** | 临时表（`GROUP BY`/`DISTINCT`）→ 优化索引或改写 |
| **`Using join buffer`** | 被驱动表无索引 → 给连接列建索引 ⭐ |
| **`key=NULL`** | 没用索引 → 找原因（隐式转换/函数/字符集/最左前缀）|

## 五、④ 定位根因（对照表）⭐

| 根因 | 典型 `EXPLAIN` 特征 | 证据 |
|---|---|---|
| **缺索引** | `type=ALL`，`Rows_examined` 极大 | 慢日志 |
| **索引失效（函数/运算）** | `WHERE DATE(col)=...` | 看 SQL 写法 |
| **隐式类型转换** ⭐ | 字符串列与数字比较 → `key=NULL` | `SHOW WARNINGS` 会提示 |
| **隐式字符集转换** ⭐ | JOIN 两表字符集/collation 不同 | `SHOW CREATE TABLE` 对比 |
| **违反最左前缀** | 联合索引只用了一部分（看 `key_len`）| 索引定义 vs WHERE |
| **深分页** | `LIMIT 1000000, 20` | SQL 里有大 offset ⭐ |
| **锁等待** ⭐ | `Lock_time` 大 | `sys.innodb_lock_waits` ⭐ |
| **主从延迟导致读到…** | 查询本身快但整体慢 | `SHOW SLAVE STATUS` |
| **统计信息失真** | 估算与实际差几个数量级 | `EXPLAIN ANALYZE` ⭐ |
| **返回数据量太大** | `Bytes_sent` 很大 | 慢日志 + 有 TEXT/BLOB |
| **大排序/大临时表** | `Using filesort` + `Using temporary` | `tmp_table_size` 溢出到磁盘 |
| **锁竞争的偶发慢** | P99 高但 P50 正常 | `SHOW ENGINE INNODB STATUS` 的 SEMAPHORES ⭐ |
| **缓冲区冷启动** | 重启后一段时间慢 | 观察 `Buffer pool hit rate` |
| **IO 抖动（云盘突发耗尽）** | 周期性慢 | `iostat -xz 1` |

## 六、⑤⑥ 制定方案与实施（按性价比排序）⭐

```
优先级 1：加 / 改索引            ← 收益最大、风险最小 ⭐
优先级 2：改写 SQL              ← 零风险，立竿见影
优先级 3：调整表结构            ← 适度反范式、加冗余列
优先级 4：改参数               ← Buffer Pool、tmp_table_size 等
优先级 5：加缓存（Redis）        ← 绕过 DB
优先级 6：读写分离 / 归档 / 分片  ← 架构级，成本最高
```

### 加索引的实战模板 ⭐

```sql
-- 场景：WHERE status=1 AND category='x' ORDER BY created_at DESC LIMIT 20
-- 索引设计：等值列在前（顺序无关），排序列在后，覆盖列最后
CREATE INDEX idx_post_list ON posts (status, category, created_at);
--                                     等值     等值        排序

-- 如果还需要 title（列表页展示），做覆盖索引
CREATE INDEX idx_post_list_cover ON posts (status, category, created_at, title);
-- EXPLAIN → Extra: Using index，且无 Using filesort ✅
```

**大表加索引必须用在线工具** ⭐：

```bash
# 8.0 加二级索引本身支持 INPLACE + LOCK=NONE，一般可直接加
ALTER TABLE posts ADD INDEX idx_x (...), ALGORITHM=INPLACE, LOCK=NONE;
# 但更大更复杂的变更用 pt-osc / gh-ost 更稳
```

### 改写 SQL 的实战模板 ⭐

```sql
-- ① 函数包裹索引列 → 改成范围
❌ WHERE DATE(created_at) = '2024-05-01'
✅ WHERE created_at >= '2024-05-01' AND created_at < '2024-05-02'

-- ② 深分页 → 键集分页
❌ SELECT * FROM posts ORDER BY id LIMIT 1000000, 20
✅ SELECT * FROM posts WHERE id > 1000000 ORDER BY id LIMIT 20

-- ③ 深分页（保留 offset 语义）→ 延迟关联
✅ SELECT p.* FROM posts p
   JOIN (SELECT id FROM posts ORDER BY id LIMIT 1000000, 20) t ON p.id = t.id

-- ④ OR → UNION ALL（+ 排除重复）
❌ WHERE a = 1 OR b = 2
✅ SELECT * FROM t WHERE a = 1
   UNION ALL
   SELECT * FROM t WHERE b = 2 AND a <> 1

-- ⑤ IN 子查询 → EXISTS 或 JOIN（视 MySQL 优化能力）
❌ SELECT * FROM a WHERE id IN (SELECT a_id FROM b WHERE ...)
✅ SELECT DISTINCT a.* FROM a JOIN b ON a.id = b.a_id WHERE ...

-- ⑥ COUNT(*) 优化 → 走最小二级索引 或 用汇总表
✅ 加一个最小的二级索引让 COUNT(*) 扫它

-- ⑦ 大字段拖累 → 列表页不读大字段
❌ SELECT * FROM posts WHERE status=1         （带出 MEDIUMTEXT content）
✅ SELECT id, title, summary FROM posts WHERE status=1   （summary 是冗余的摘要列）⭐
```

## 七、⑦⑧ 验证与灰度 ⭐

```
① 在从库或测试环境先跑：EXPLAIN ANALYZE 对比优化前后
② 用压测工具量化（sysbench / mysqlslap / 业务压测）
   对比指标：P50 / P95 / P99、QPS、Rows_examined
③ 索引上线：8.0 可先 INVISIBLE 观察，或直接加（INPLACE 不锁）
④ 灰度观察：慢日志、P99、错误率、主从延迟 ⭐
⑤ 加索引后记得 ANALYZE TABLE 更新统计信息 ⭐
⑥ 回滚预案：DROP INDEX（或 INVISIBLE → VISIBLE）
```

## 八、一个完整的实战案例 ⭐

**现象**：文章列表接口 P99 = 8s，高峰期更差。

```
① 采集：慢日志发现
   Query_time: 8.01  Lock_time: 0.00  Rows_sent: 20  Rows_examined: 4520000
   SQL: SELECT * FROM posts WHERE status=1 ORDER BY created_at DESC LIMIT 20;

② EXPLAIN：
   type=ALL  key=NULL  rows=4520000  Extra=Using where; Using filesort ❌
   → 全表扫描 + 文件排序

③ 根因：只有 (id) 主键索引，(status, created_at) 无索引
   Rows_examined/Rows_sent = 226000 : 1  → 典型的"扫描效率极低"

④ 方案：
   a) 加索引 CREATE INDEX idx_status_created ON posts (status, created_at);
   b) 顺便消除回表：改为覆盖索引 (status, created_at, id, title, summary)
      （用 summary 冗余列，避免列表页拉 MEDIUMTEXT content）⭐

⑤ 验证：EXPLAIN → type=range, key=idx_status_created, Extra=Using index ✅
   EXPLAIN ANALYZE → actual rows=20 loops=1（只扫 20 行）

⑥ 上线：ALTER TABLE ... ADD INDEX ..., ALGORITHM=INPLACE, LOCK=NONE; ANALYZE TABLE posts;

⑦ 结果：P99 从 8s 降到 12ms（约 660 倍提升）
```

## 九、防复发机制 ⭐

| 机制 | 说明 |
|---|---|
| **慢查询日志常开** | `long_query_time=1`，每日自动汇总（pt-query-digest）|
| **SQL 上线评审** | 新 SQL 必须过 `EXPLAIN`，禁止 `type=ALL` 的大表查询 ⭐ |
| **DDL/索引变更走流程** | 用 pt-osc/gh-ost/INVISIBLE，避免误删索引 |
| **监控告警** | 慢查询数、`Threads_running`、主从延迟、`History list length` ⭐ |
| **定期索引体检** | 每季度跑 `sys.schema_redundant_indexes` / `unused_indexes` |
| **压测常态化** | 大促前压测，提前发现容量问题 |
| **框架层防护** | 强制分页上限、禁止无 `LIMIT` 的大查询 ⭐ |

## 十、一句话总结

**慢 SQL 的排查是一条固定链路：慢日志/`sys` 表采集 → `EXPLAIN ANALYZE` 看"估算 vs 实际" → 对照根因表定位 → 按"索引 > 改写 SQL > 表结构 > 参数 > 缓存 > 架构"的顺序优化 → 压测量化 → 灰度观察**。两个最快的判据是 **`Rows_examined / Rows_sent` 比值** 和 **`EXPLAIN ANALYZE` 的估算/实际行数差**。""",
    ),
    (
        "MySQL",
        "监控,指标,告警",
        2,
        r"""MySQL 应该监控哪些指标？各自的含义和告警阈值是什么？""",
        r"""## 一、监控的四个层次 ⭐

```
① 资源层（OS）：CPU / 内存 / 磁盘 IO / 网络 / 文件句柄
② 实例层（MySQL）：连接、QPS/TPS、线程、缓冲池
③ 存储引擎层（InnoDB）：锁、事务、redo、undo、IO
④ 业务层：慢查询、错误率、主从延迟
```

**排查原则**：**自下而上** —— 先确认 OS 没瓶颈，再看实例，最后看 SQL ⭐

## 二、资源层（OS）⭐

| 指标 | 健康范围 | 告警阈值 | 说明 |
|---|---|---|---|
| **CPU 使用率** | < 70% | > 80% 持续 5min | MySQL 是 CPU 密集型，但要区分 `%us` / `%sy` / `%wa` ⭐ |
| **iowait（%wa）** | < 10% | > 20% | 高 → 磁盘瓶颈 |
| **磁盘 `%util`** | < 70% | **> 90%** ⭐ | `iostat -xz 1`，接近 100% 就是打满 |
| **磁盘 `await`** | < 10ms（SSD）| > 50ms | 单次 IO 平均等待 |
| **磁盘剩余空间** | > 30% | **< 20%** ⭐ | 满了会导致写失败、复制中断 |
| **内存可用** | `MemAvailable` 充足 | 触发 swap ⚠️ | **swap 是性能杀手**，应尽量禁用或设极低 `vm.swappiness` |
| **网络** | — | 重传率高 | 影响复制延迟 |
| **文件句柄数** | 远小于上限 | > 80% | `open_files_limit` 耗尽会导致无法建连接 ⭐ |
| **load average** | < 核数 | > 核数 × 2 ⭐ | 结合 `nproc` 判断 |

## 三、实例层（MySQL 状态）⭐

### 连接类

```sql
SHOW GLOBAL STATUS LIKE 'Threads%';
SHOW GLOBAL STATUS LIKE 'Max_used_connections';
SHOW GLOBAL STATUS LIKE 'Aborted%';
SHOW GLOBAL STATUS LIKE 'Connection%';
```

| 指标 | 含义 | 告警阈值 |
|---|---|---|
| **`Threads_connected`** | 当前连接数 | > `max_connections` × 0.8 |
| **`Threads_running`** ⭐ | **正在执行的线程**（最该盯的）| **> 核数 × 2** ⭐ |
| **`Max_used_connections`** | 历史峰值 | `Max_used / max_connections` > 85% ⭐ |
| **`Aborted_connects`** | 握手失败次数 | 持续增长 → 网络/认证问题 |
| **`Aborted_clients`** | 非正常断开的客户端 | 持续增长 → 客户端没 quit/超时 |
| **`Connections`** | 累计连接数 | 增长速度 = 建连频率 |

**为什么 `Threads_running` 比 `Threads_connected` 重要** ⭐：连接多不等于忙，但**正在执行的线程多 = 真的忙**。`Threads_running` 长期高 → CPU 争抢，说明需要优化 SQL 而不是加连接。

### 吞吐类

```sql
SHOW GLOBAL STATUS LIKE 'Queries';        -- 累计查询数 → 计算 QPS ⭐
SHOW GLOBAL STATUS LIKE 'Com_commit';     -- 累计提交
SHOW GLOBAL STATUS LIKE 'Com_rollback';   -- ⭐ 回滚比例高说明有大量失败事务
SHOW GLOBAL STATUS LIKE 'Com_select';
SHOW GLOBAL STATUS LIKE 'Com_insert';
SHOW GLOBAL STATUS LIKE 'Com_update';
SHOW GLOBAL STATUS LIKE 'Com_delete';
```

| 指标 | 含义 |
|---|---|
| **QPS** | `Queries` 的每秒增量 ⭐ |
| **TPS** | `(Com_commit + Com_rollback)` 的每秒增量 ⭐ |
| **读写比** | `Com_select / (Com_insert+Com_update+Com_delete)` |
| **回滚率** ⭐ | `Com_rollback / (Com_commit + Com_rollback)`；高 → 大量 SQL 失败（锁冲突/唯一键冲突）|

**注意：QPS 高低本身没有绝对健康值**，要看趋势和与业务量的匹配。**突然的毛刺比高 QPS 更值得关注** ⭐

### 查询质量类 ⭐

```sql
SHOW GLOBAL STATUS LIKE 'Handler%';
```

| 指标 | 含义 | 告警 |
|---|---|---|
| **`Handler_read_rnd_next`** ⭐ | 按顺序读下一行（**全表扫描的标志**）| **增长快 = 全表扫描多** ⭐⭐ |
| `Handler_read_key` | 按索引读取 | 越大越好 |
| `Handler_read_next` | 按索引顺序读下一行 | 范围扫描 |
| `Handler_read_rnd` | 随机读（排序后回表）| 大 → 排序 + 回表多 |
| `Handler_read_first` | 读索引第一行（全索引扫描）| 大 → 有 `SELECT COUNT(*)` 之类的操作 |
| `Handler_commit` / `Handler_rollback` | 提交/回滚 | — |
| `Handler_update` / `Handler_delete` | 更新/删除行数 | — |

**`Handler_read_rnd_next` 是最容易被忽略的关键指标** ⭐ —— 它直接反映"有多少次全表扫描式的顺序读"。**如果它的增速远超业务量，说明缺索引**。

### 临时表与排序类 ⭐

```sql
SHOW GLOBAL STATUS LIKE 'Created_tmp%';
SHOW GLOBAL STATUS LIKE 'Sort%';
SHOW GLOBAL STATUS LIKE 'Select%';
```

| 指标 | 含义 | 告警 |
|---|---|---|
| **`Created_tmp_disk_tables` / `Created_tmp_tables`** ⭐ | **落在磁盘的临时表比例** | **> 25% 需要优化** ⭐（`tmp_table_size` 太小或有 `GROUP BY` 大结果集）|
| `Created_tmp_tables` | 临时表总数 | 高 → 有 `GROUP BY`/`DISTINCT`/`UNION` |
| **`Sort_merge_passes`** ⭐ | 排序需要多轮归并（说明 `sort_buffer_size` 不够）| 增长快 → 调大 `sort_buffer_size` |
| `Sort_scan` / `Sort_range` | 排序次数 | |
| `Select_full_join` ⭐ | **无索引的 JOIN 次数** | **应为 0** ⭐ 非 0 → 缺索引 |
| `Select_scan` | 全表扫描次数 | 增长快 → 缺索引 |
| `Select_range_check` | 范围检查（JOIN 无索引）| 应为 0 |

**`Select_full_join` 和 `Handler_read_rnd_next` 是"缺索引"的两个最直接证据** ⭐

## 四、InnoDB 层 ⭐⭐

```sql
SHOW GLOBAL STATUS LIKE 'Innodb%';
```

### Buffer Pool（最重要）

| 指标 | 含义 | 告警 |
|---|---|---|
| **`Innodb_buffer_pool_read_requests`** | 逻辑读次数 | — |
| **`Innodb_buffer_pool_reads`** | **物理读次数** ⭐ | — |
| **命中率** ⭐ | `1 - reads / read_requests` | **< 99% 需关注，< 98% 明显不足** ⭐⭐ |
| `Innodb_buffer_pool_pages_free` | 空闲页 | 长期为 0 → 池已满 |
| `Innodb_buffer_pool_pages_dirty` | 脏页数 | 长期 > `max_dirty_pages_pct` → 刷脏压力大 ⭐ |
| **`Innodb_buffer_pool_wait_free`** ⭐ | **等待空闲页的次数** | **应恒为 0** ⭐ 非 0 → Buffer Pool 不够或刷脏太慢 |
| `Innodb_buffer_pool_pages_flushed` | 刷脏页数 | |

**命中率计算（累计值，比瞬时值可靠）** ⭐：

```sql
SELECT
  ROUND(100 - (s1.v / s2.v * 100), 3) AS hit_rate_pct
FROM (SELECT VARIABLE_VALUE v FROM performance_schema.global_status
      WHERE VARIABLE_NAME='Innodb_buffer_pool_reads') s1,
     (SELECT VARIABLE_VALUE v FROM performance_schema.global_status
      WHERE VARIABLE_NAME='Innodb_buffer_pool_read_requests') s2;
```

**`Innodb_buffer_pool_wait_free > 0` 是"必须加大 Buffer Pool"的强信号** ⭐

### 日志与刷盘

| 指标 | 含义 | 告警 |
|---|---|---|
| `Innodb_log_waits` ⭐ | **等 Log Buffer 空间的次数** | **应恒为 0** ⭐ 非 0 → `innodb_log_buffer_size` 太小 |
| `Innodb_log_write_requests` | 写 redo 请求数 | |
| `Innodb_log_writes` | 实际写 redo 次数 | |
| `Innodb_os_log_fsyncs` | redo fsync 次数 ⭐ | 增长极快 → 每次提交都刷（`=1`），可用组提交优化 |
| `Innodb_os_log_pending_fsyncs` | 待处理的 fsync | 非 0 → IO 跟不上 |

### 行操作

| 指标 | 含义 |
|---|---|
| `Innodb_rows_read` | 读行数 ⭐ |
| `Innodb_rows_inserted/updated/deleted` | 写行数 |
| `Innodb_rows_read / (rows_inserted+updated+deleted)` | **读写比** —— 比值异常大 → 可能有全表扫描 ⭐ |

### 其他 InnoDB 指标

| 指标 | 含义 | 告警 |
|---|---|---|
| `Innodb_row_lock_waits` | 行锁等待次数 | 增长快 → 锁竞争 ⭐ |
| `Innodb_row_lock_time_avg` | **平均锁等待时间（ms）** | **> 100ms 需关注** ⭐ |
| `Innodb_row_lock_time_max` | 最大锁等待时间 | > 1s 需查 |
| `Innodb_deadlocks` ⭐ | 死锁次数 | **任何非 0 增长都要查** ⭐ |
| `Innodb_data_reads` / `Innodb_data_writes` | 数据文件读/写次数 | |
| `Innodb_data_read` / `Innodb_data_written` | 读/写字节数 | |
| `Innodb_data_fsyncs` | fsync 次数 | |
| `Innodb_data_pending_reads/writes/fsyncs` ⭐ | 待处理 IO | **非 0 → IO 积压** ⭐ |
| `Innodb_pages_created/read/written` | 页操作 | |

### `SHOW ENGINE INNODB STATUS` 里的衍生指标 ⭐

| 指标 | 来源 | 告警 |
|---|---|---|
| **`History list length`** ⭐⭐ | TRANSACTIONS 段 | **> 10000 关注，> 100000 危险**（长事务堵塞 purge）|
| **`Buffer pool hit rate`** | BUFFER POOL 段 | < 995/1000 需关注 |
| **`Log sequence number - Last checkpoint`** ⭐ | LOG 段 | 接近 redo 容量 → 频繁 checkpoint |
| **最长的活跃事务时长** | TRANSACTIONS 段 | > 60s ⭐ |
| **`OS waits`（SEMAPHORES）** | SEMAPHORES 段 | 大 → latch 竞争 |

**这四个指标在 `SHOW ENGINE INNODB STATUS` 里，但很多监控工具不采集** ⭐ 建议自己写脚本采集并落盘。

## 五、复制层（主从）⭐

```sql
SHOW SLAVE STATUS\G
```

| 指标 | 含义 | 告警 |
|---|---|---|
| **`Slave_IO_Running`** | IO 线程状态 | **必须 Yes** ⭐ |
| **`Slave_SQL_Running`** | SQL 线程状态 | **必须 Yes** ⭐ |
| **`Seconds_Behind_Master`** ⭐ | 延迟秒数 | **> 10s 关注，> 60s 告警** ⭐ 但**为 0 不代表真同步**（IO 断了也可能是 NULL/0）|
| **`Retrieved_Gtid_Set` vs `Executed_Gtid_Set`** ⭐ | 拉取 vs 执行 | 差集大 → 有延迟（GTID 模式下更准）|
| `Last_IO_Error` / `Last_SQL_Error` | 最近错误 | 非空 → 复制中断 ⭐ |
| `Master_Log_File / Read_Master_Log_Pos` vs `Relay_Master_Log_File / Exec_Master_Log_Pos` | 位点对比 | 差距 → 延迟 |
| `Relay_Log_Space` | relay log 占用 | 持续增大 → SQL 线程跟不上 ⭐ |

**⚠️ `Seconds_Behind_Master` 的局限** ⭐：
```
① 它是"主库写入时间 - 从库执行时间"，时钟不同步会影响
② IO 线程断了时它可能返回 NULL 或 0（假健康）⚠️
③ 大事务重放期间可能一直是 0，然后突然跳到很大
→ 更可靠：用 pt-heartbeat 注入心跳表，精度到毫秒 ⭐
```

## 六、业务层 ⭐

| 指标 | 说明 |
|---|---|
| **慢查询数量**（每分钟）| `Slow_queries` 状态变量 ⭐ 突增 → 有问题 |
| **`Slow_queries / Questions`** | 慢查询占比 ⭐ 比绝对数更能反映健康度 |
| **错误率** | 连接失败、SQL 报错、`Aborted_*` |
| **`Table_locks_waited`** | 表锁等待（MyISAM 或 DDL 场景）|
| **`Table_open_cache_hits / misses`** | 表缓存命中率，misses 高 → 调大 `table_open_cache` |
| **`Open_tables` / `Opened_tables`** | 当前打开的 / 累计打开的表 |
| **`Qcache_*`** | 5.7 才有（8.0 已移除）|

**`Slow_queries` 是最实用的业务指标** ⭐

## 七、告警阈值总表（可直接用）⭐

| 指标 | 警告 | 严重 |
|---|---|---|
| CPU 使用率 | > 70% 5min | > 90% 5min |
| 磁盘 `%util` | > 70% | > 90% |
| 磁盘剩余 | < 30% | < 15% |
| `Threads_running` | > 2×核数 | > 4×核数 |
| `Max_used_connections / max_connections` | > 75% | > 85% |
| **Buffer Pool 命中率** ⭐ | < 99% | < 97% |
| **`Innodb_buffer_pool_wait_free` 增量** | > 0 | > 10/min |
| **`Innodb_deadlocks` 增量** | > 0 | > 5/min |
| `Innodb_row_lock_time_avg` | > 100ms | > 500ms |
| `Created_tmp_disk_tables / Created_tmp_tables` | > 25% | > 50% |
| `Select_full_join` 增量 | > 0 | > 10/min |
| **`History list length`** ⭐ | > 10000 | > 100000 |
| 最长活跃事务 | > 60s | > 600s |
| 主从延迟 | > 10s | > 60s |
| `Slave_IO_Running` / `Slave_SQL_Running` | — | ≠ Yes |
| `Slow_queries` 增速 | 突增 2× | 突增 10× |
| `Aborted_connects` 增速 | 突增 | 持续增长 |
| swap 使用 | > 0 | > 100MB |

## 八、工具链 ⭐

| 层 | 工具 |
|---|---|
| **采集** | `mysqld_exporter`（Prometheus）、`node_exporter`（OS）、PMM、Zabbix |
| **存储与告警** | Prometheus + Alertmanager ⭐ / Zabbix / Grafana |
| **可视化** | Grafana 看板（社区有现成 MySQL 看板）⭐ |
| **开箱即用** | **PMM（Percona Monitoring and Management）** ⭐ 自带看板 + 慢查询分析 |
| **慢查询** | `pt-query-digest`、`sys.statement_analysis` |
| **压测** | `sysbench`、`mysqlslap` |

**告警设计原则** ⭐：

```
① 告警必须"可行动"（收到告警知道该干什么），否则会被忽略 ⭐
② 分级：Warning（看板） / Critical（电话）
③ 避免抖动：持续时间 + 恢复延迟 双阈值
④ 关键指标双人确认（避免误报疲劳）
⑤ 告警要关联"最近变更"（上线、DDL）
```

## 九、一句话总结

**必盯的五项：① Buffer Pool 命中率（要不要加内存）② `Threads_running`（真的忙吗）③ `Innodb_deadlocks` / 行锁等待（锁竞争）④ `History list length` + 最长活跃事务（长事务）⑤ 主从延迟 + `Slave_*_Running`（复制健康）**；再加上 **`Handler_read_rnd_next` / `Select_full_join`** 监控"缺索引"，**`Created_tmp_disk_tables` 比例**监控"排序/临时表溢出"，**磁盘剩余空间**监控"最基础的生存条件"。""",
    ),
    (
        "MySQL",
        "容量规划,压测,sysbench",
        3,
        r"""如何做 MySQL 容量规划？压测该怎么做才有意义？""",
        r"""## 一、容量规划要回答的四个问题 ⭐

```
① 现在能扛多少？（当前容量）
② 什么时候会不够？（增长预测）
③ 需要什么规格？（CPU / 内存 / 磁盘 IOPS / 存储容量）
④ 什么时候该扩容/分片？（水位线）
```

## 二、容量评估的输入 ⭐

| 输入 | 来源 |
|---|---|
| **当前 QPS / TPS** | `Queries`、`Com_commit` 增速 |
| **读写比** | `Com_select` vs 写 |
| **数据量** | 各表 `data_length + index_length` |
| **日增长量** | 每日新增行数/字节数 |
| **热数据比例** ⭐ | 多大数据量能满足 99% 的查询（决定 Buffer Pool 大小）|
| **峰值系数** | 峰值 QPS / 平均 QPS（通常 3~10 倍）|
| **单行大小 / 单请求读写行数** | 决定 IO 量 ⭐ |
| **业务增长预期** | 产品规划 |

## 三、CPU 与内存的估算 ⭐

### 内存

```
总内存分配方案（专用 MySQL 服务器）：
  · Buffer Pool:        50% ~ 80%（核心）
  · 每连接私有内存:      连接数 × (sort_buffer + join_buffer + read_buffer + ...)
                        ⚠️ 这是"每连接"的，容易被忽略 ⭐
  · 其他（dict、log buffer、临时表）: 5% ~ 10%
  · 留给 OS（page cache、网络栈）:    5% ~ 10%

例：32GB 内存
  innodb_buffer_pool_size = 22GB
  连接 500 × 每连接 2MB = 1GB
  其他 = 2GB
  OS = 7GB
```

**Buffer Pool 该多大？** ⭐

```
经验公式：Buffer Pool ≈ 热数据大小 × 1.2

热数据大小怎么估：
  ① 看 innodb_buffer_pool_reads（物理读）—— 若持续 > 0 且命中率 < 99% → 不够
  ② 看 innodb_buffer_pool_wait_free —— 出现 > 0 → 必须加大 ⭐
  ③ 白盒估：data_length + index_length 里"最近 30 天数据"的大小
```

**⚠️ 唯一正确的方法是"观察指标"而不是"套公式"** ⭐：命中率和 `wait_free` 是直接信号。

### CPU

```
MySQL 每核的 QPS 能力（经验，SSD + 良好索引）：
  · 简单主键查询:      5000 ~ 30000 QPS/核
  · 带 JOIN/排序的查询: 500 ~ 2000 QPS/核
  · 写操作（TPS）:      500 ~ 5000 TPS/核

→ 结论：**必须先压测**，经验值只能用来做粗估 ⭐
```

**核数的作用**：
- **少于 8 核** → 高并发下线程争抢明显
- **16~32 核** → 主流规格
- **> 32 核** → 需要特别注意 `innodb_buffer_pool_instances`、`innodb_thread_concurrency`、NUMA ⭐

## 四、磁盘的估算 ⭐（最容易低估）

```
① 容量
   数据 + 索引 + binlog + redo + undo + 临时文件
   ⚠️ 还要留：备份文件、DDL/OPTIMIZE 的临时空间（约 1~2 倍表大小）⭐
   → 建议预留 40% 以上空闲

② IOPS ⭐
   计算：写 IOPS ≈ TPS × 每事务平均脏页数 × (1 + 索引数/10)
        读 IOPS ≈ (QPS × 每查询平均页读) × (1 - 命中率)  ← 命中率关键
   
   例：QPS=5000，命中率 99% → 读 IOPS ≈ 5000 × 5 × 0.01 = 250
       TPS=500，每事务 3 个脏页 → 写 IOPS ≈ 1500
   → 总需 ~2000 IOPS

③ 吞吐（MB/s）
   写吞吐 ≈ TPS × 每事务字节（含 redo + binlog + 数据页）
```

**SSD vs 云盘的坑** ⭐：

| 项 | 注意 |
|---|---|
| **云盘 IOPS 与容量挂钩** ⭐ | 容量小 → IOPS 上限低 → 即使 CPU/内存够也慢 |
| **突发 IOPS 额度** | 某些云盘有"突发积分"，用完掉速 ⚠️ |
| **网络盘延迟** | 比本地 SSD 高（0.5~2ms vs 0.1ms）|
| **`innodb_io_capacity` 要匹配** ⭐ | 告诉 InnoDB 磁盘能力；设小了刷脏慢，设大了打满盘 |

## 五、压测的正确做法 ⭐

### 工具

| 工具 | 特点 |
|---|---|
| **`sysbench`** ⭐ | 最标准的 MySQL 压测工具（OLTP 场景）|
| `mysqlslap` | MySQL 自带，简单 |
| `tpcc-mysql` | TPC-C 标准（更贴近真实业务）|
| `BenchmarkSQL` | TPC-C 的 Java 实现 |
| JMeter / Locust | 可做端到端（含应用层）|
| **业务真实流量回放** ⭐ | 最准确（用生产 SQL 的采样回放）|

### `sysbench` 的标准流程 ⭐

```bash
# 1. 准备数据（表数、表大小要与生产接近）⭐
sysbench oltp_read_write \
  --mysql-host=127.0.0.1 --mysql-user=root --mysql-db=test \
  --tables=10 --table-size=10000000 \
  --threads=64 \
  prepare

# 2. 预热（把数据加载进 Buffer Pool）⭐ 关键！
sysbench oltp_read_write --tables=10 --table-size=10000000 \
  --threads=64 --time=60 --rate=0 run

# 3. 正式压测
sysbench oltp_read_write --tables=10 --table-size=10000000 \
  --threads=64 --time=300 \
  --report-interval=10 \
  --rand-type=uniform \
  run

# 4. 阶梯加压找拐点 ⭐
for t in 8 16 32 64 128 256; do
  sysbench oltp_read_write --tables=10 --table-size=10000000 \
    --threads=$t --time=120 run | tee /tmp/bench_$t.txt
done
```

**关键输出指标** ⭐：

```
transactions:    50000 (166.62 per sec.)      ← TPS
queries:         1000000 (3332.41 per sec.)   ← QPS
latency (ms):
         min:                                   1.20
         avg:                                   3.84   ← 平均值会掩盖长尾 ⚠️
         max:                                 512.33   ← 要看这个 ⭐
         95th percentile:                       8.21   ← ⭐ 95 分位
         sum:                              192000.00

errors: 0                    ← ⭐ 错误必须为 0
reconnects: 0
```

**必须同时监控服务器** ⭐：压测时要有 `vmstat`、`iostat -xz 1`、`SHOW GLOBAL STATUS` 的采样，否则只知道"慢"不知道"为什么慢"。

### 压测的六个铁律 ⭐

| # | 铁律 |
|---|---|
| **① 数据量与生产同数量级** ⭐ | 100 万行的表和 1 亿行的表，索引深度、缓存命中率完全不同。**数据量不够 = 结论无效** |
| **② 必须预热** ⭐ | 冷 Buffer Pool 的第一次压测毫无意义（都是物理读）|
| **③ 压测机不能与被测机同机** | 压测工具本身要消耗 CPU/网络 |
| **④ 看 P95/P99 而不是平均值** ⭐ | 平均值掩盖长尾；业务的痛点在 P99 |
| **⑤ 阶梯加压找"拐点"** ⭐ | 并发从 8 加到 256，找 QPS 不再增长、延迟开始飙升的点 |
| **⑥ 一次只改一个变量** | 改参数后重新压测，否则不知道是谁的功劳 |
| **⑦ 复现生产的数据分布** | `--rand-type`：`uniform`（均匀）vs `zipfian`（倾斜，更真实）⭐ |
| **⑧ 用真实 SQL 回放** ⭐ | 最准（从慢日志采样，或用 `sys.statement_analysis` 得到 SQL 模板和占比）|

## 六、找"拐点"（容量拐点）⭐

```
并发  QPS    P99延迟    CPU    %util   结论
  8   8000ms  2ms      12%    15%    资源充足
 32  28000    5ms      40%    45%    线性增长 ✅
 64  45000    12ms     65%    70%    接近线性
128  52000    45ms     85%    88%    ⚠️ 增长放缓，开始竞争
256  54000   180ms     96%    95%    ❌ 拐点已过，加并发只涨延迟
512  51000   600ms     98%   100%    ❌ 吞吐下降，过载
```

**结论**：**这个实例的安全容量约在 128 并发 / 52000 QPS**，留 30% 余量 → **生产目标 90 并发 / 36000 QPS** ⭐

**拐点后的三个典型现象**：
- QPS 不再增长（或下降）
- P99 延迟指数上升
- CPU/IO 有一个打满，另一个还在等

## 七、容量水位线与扩容策略 ⭐

| 水位 | 含义 | 动作 |
|---|---|---|
| **< 50%** | 健康 | — |
| **50%~70%** | 正常 | 关注增长趋势 |
| **70%~85%** | 预警 | 制定扩容计划 ⭐ |
| **> 85%** | 危险 | 立即扩容（加从库/升配/分片）⭐ |
| **触顶** | 过载 | 限流降级，防止雪崩 |

**水位怎么算** ⭐：

```
以 QPS 为例：
  实测拐点 = 52000 QPS
  留 30% 余量 → 安全容量 = 36000 QPS
  当前峰值 = 30000 QPS
  水位 = 30000 / 36000 = 83%  → ⚠️ 危险，需要扩容
```

**同样的方法用于**：TPS、磁盘 IOPS、磁盘容量、连接数、Buffer Pool 命中率。

**增长预测**：

```
按当前增速：每月峰值涨 8%
当前 83% 水位 → 1 个月后 90%（已超警戒）
→ 估算：3 个月内必须扩容 ⭐
```

## 八、扩容的优先级 ⭐

```
① 加索引 / 优化 SQL          ← 成本 0，收益最大
② 加缓存（Redis）            ← 挡住 80% 的读
③ 升配（CPU/内存/磁盘）      ← 最直接，但有上限且成本高 ⭐
④ 加从库 + 读写分离          ← 读扩展
⑤ 归档冷数据                 ← 释放单表压力
⑥ 垂直分库                   ← 业务解耦
⑦ 水平分片                   ← 最后手段，成本最高 ⭐
```

**关键**：**先做 ①②，再做 ③④，最后才 ⑦**。很多团队跳过 ① 直接分片，结果分片后还是慢（因为索引依然不好）⚠️

## 九、监控与容量管理的关系 ⭐

```
容量管理是"持续过程"，不是"一次性任务"：

① 常态化压测：大促前、大版本前、架构变更后必压 ⭐
② 常态化监控：QPS/TPS/水位/延迟/P99 → 自动告警 ⭐
③ 季度体检：数据增长、索引审计、慢查询 TOP10
④ 应急预案：过载时如何限流/降级/切从库
⑤ 演练：真实恢复演练 + 切库演练 ⭐
```

## 十、一句话总结

**容量规划 = "观测指标定当前容量 + 压测找拐点定安全容量 + 增长预测定扩容时间"**；**压测的八条铁律里最重要的是"数据量与生产同量级"和"必须预热"**（否则结论无效）；**扩容优先级永远是"优化 SQL/索引 → 缓存 → 升配 → 从库 → 归档 → 分片"**，跳步直接分片是最常见的昂贵错误。""",
    ),
    (
        "MySQL",
        "故障处理,应急,实战",
        3,
        r"""线上 MySQL 常见故障有哪些？各自的应急处置和根因排查是什么？""",
        r"""## 一、故障分类总览 ⭐

| 类别 | 典型现象 |
|---|---|
| **连接类** | `Too many connections`、连接建立慢、连接被断开 |
| **性能类** | QPS 骤降、响应变慢、CPU/IO 打满 |
| **锁与并发类** | 大量锁等待、死锁频发、SQL 被阻塞 |
| **空间类** | 磁盘满、undo/ibdata1 暴涨 |
| **复制类** | 主从延迟大、复制中断 |
| **数据类** | 误删数据、数据不一致、乱码 |
| **可用性类** | 实例挂了、无法启动 |

**应急处理的三条原则** ⭐：

```
① 先止血，后定位（恢复业务优先，但保留现场证据）
② 保留证据（SHOW ENGINE INNODB STATUS、processlist、日志快照）
    ⚠️ 一旦重启，很多现场信息就没了 ⭐
③ 根因不查清绝不收工（否则会再犯）
```

## 二、连接类故障 ⭐

### `ERROR 1040: Too many connections` ⭐

```sql
-- 现场：先看谁占了连接
SHOW PROCESSLIST;
SELECT user, host, db, command, COUNT(*) cnt
FROM information_schema.processlist GROUP BY user, host, db, command ORDER BY cnt DESC;

-- 找出长时间 Sleep 的连接
SELECT id, user, host, db, command, time, state
FROM information_schema.processlist
WHERE command='Sleep' ORDER BY time DESC LIMIT 20;

-- 找出长时间运行的查询（真凶）
SELECT id, user, host, time, state, LEFT(info,200) sql
FROM information_schema.processlist
WHERE command <> 'Sleep' ORDER BY time DESC LIMIT 20;
```

**应急处置** ⭐：

```sql
-- ① 快速腾出连接（用有 SUPER/CONNECTION_ADMIN 的账号登录 —— 8.0 会保留一个给管理员）
KILL <id>;                    -- 杀单个连接
-- 批量杀 Sleep 超过 300 秒的
SELECT CONCAT('KILL ', id, ';') FROM information_schema.processlist
WHERE command='Sleep' AND time > 300;
-- 复制输出并执行

-- ② 临时提高上限（⚠️ 也要考虑内存）
SET GLOBAL max_connections = 1000;

-- ③ 从库/其他实例分流（如果有）
```

**根因与长效对策** ⭐：

| 根因 | 对策 |
|---|---|
| **没有连接池** | 上连接池 |
| **连接泄漏** | RAII 保证归还；开 `leakDetectionThreshold` ⭐ |
| **慢 SQL 拖住连接** | 优化慢 SQL；设置查询超时 ⭐ |
| **`wait_timeout` 太长 + 客户端异常退出** | 调小 `wait_timeout` |
| **业务量增长** | 升配 or 分库 |
| **应用多实例各自连很多** | 总量规划：`Σ(池上限) × 1.3 < max_connections` ⭐ |

### 连接被断开（`ERROR 2006/2013`）

```
现象：MySQL server has gone away / Lost connection during query
根因：
  ① 空闲连接被 wait_timeout 断开 → 池里是死连接 ⭐
  ② 查询包超过 max_allowed_packet 被拒
  ③ 网络抖动 / 防火墙超时
  ④ 服务端 OOM 或重启
对策：
  ① 池的 maxLifetime < wait_timeout ⭐
  ② 调大 max_allowed_packet
  ③ 借出前探活（mysql_ping）或用 keepalive
```

## 三、性能类故障 ⭐

### QPS 骤降 / 响应变慢（最紧急）⭐

**应急处置（5 分钟内）**：

```sql
-- ① 看此刻在跑什么
SHOW FULL PROCESSLIST;         -- 找 time 大、state 异常的
-- ② 看 InnoDB 内部
SHOW ENGINE INNODB STATUS\G    -- ⭐ 保留现场（复制输出到文件）
-- ③ 看有没有长事务
SELECT trx_id, trx_started, TIMESTAMPDIFF(SECOND,trx_started,NOW()) sec,
       trx_state, trx_mysql_thread_id, trx_query
FROM information_schema.innodb_trx ORDER BY trx_started;
-- ④ 看锁等待链
SELECT * FROM sys.innodb_lock_waits\G   -- ⭐ 找出"堵住一切的元凶"
-- ⑤ 看系统层
--    top / vmstat 1 / iostat -xz 1
```

**快速止血手段** ⭐：

| 手段 | 说明 |
|---|---|
| **KILL 掉"堵住一切"的长事务** ⭐ | 找 `blocking_pid`，杀掉它；⚠️ 大事务 KILL 后还要回滚很久 |
| **限流** | 在应用/网关层降级，先保核心业务 ⭐ |
| **临时提高 buffer pool 相关参数** | 治标 |
| **切读流量到从库** | 减轻主库 |
| **重启** | **最后手段**（会丢现场、恢复慢、可能长时间崩溃恢复）⚠️ |

**根因排查矩阵** ⭐：

| 现象 | 首要怀疑 |
|---|---|
| CPU 打满（%us 高）| 缺索引导致全表扫描；SQL 复杂度；并发过高 |
| CPU 打满（%sy 高）| 上下文切换多（连接过多）；锁竞争 |
| iowait 高 / %util 100% | Buffer Pool 太小；刷脏风暴；大查询；备份任务抢 IO ⭐ |
| 大量锁等待 | 长事务；缺索引导致锁全表；访问顺序不一致 |
| `Threads_running` 高但 QPS 低 | 大量 SQL 在等待资源（锁/IO/latch）⭐ |
| 突然大量 `Aborted_connects` | 网络问题、认证问题、连接池配置错误 |

### 磁盘 IO 打满 ⭐

```
常见原因：
  ① buffer pool 太小（命中率低）→ 物理读多
  ② checkpoint 风暴（redo 太小）
  ③ 备份/统计/DDL 在跑 ⭐
  ④ 云盘 IOPS 额度耗尽
  ⑤ 大查询（无索引的全表扫描）
  ⑥ change buffer merge 积压（重启后）
对策：
  ① 加大 innodb_buffer_pool_size ⭐
  ② 加大 innodb_redo_log_capacity（8.0）/ innodb_log_file_size
  ③ 把备份/DDL 挪到低峰 + 限速（pt-osc 的 --max-load / --critical-load）⭐
  ④ 优化慢查询
  ⑤ 检查 innodb_io_capacity 是否匹配磁盘
```

## 四、锁与并发类故障 ⭐

### 死锁频发（`ERROR 1213`）

```sql
SHOW ENGINE INNODB STATUS\G     -- 看 LATEST DETECTED DEADLOCK
-- 开启全量记录（排查期）
SET GLOBAL innodb_print_all_deadlocks = ON;   -- 所有死锁写入 error log ⭐

-- 8.0 更精确的锁信息
SELECT * FROM performance_schema.data_locks;
SELECT * FROM performance_schema.data_lock_waits;
```

**根因与对策** ⭐：

| 根因 | 对策 |
|---|---|
| **访问顺序不一致** | 统一顺序（如都按主键升序）⭐ |
| **缺索引导致间隙锁范围过大** | 给 WHERE 条件加索引 ⭐ |
| **RR 的间隙锁** | 考虑改用 RC（需配合 binlog=ROW）⭐ |
| **长事务** | 缩短事务 |
| **批量操作顺序不同** | 批量更新前对 ID 排序 ⭐ |
| **应用无重试** | 捕获 1213/1205 后有限次重试 ⭐ |

### 大量锁等待（`ERROR 1205: Lock wait timeout exceeded`）

```sql
-- 找等待链
SELECT * FROM sys.innodb_lock_waits\G
-- waiting_pid / waiting_query / blocking_pid / blocking_query / locked_table
-- ⭐ 沿着 blocking_pid 往上找，直到找到"根阻塞者"（它没人阻塞它）
KILL <root_blocker_pid>;      -- 杀掉根阻塞者，整条链解开 ⭐
```

### `Metadata lock`（MDL）等待 ⭐ 比行锁更常见

**现象**：一个 `ALTER TABLE` 卡住，然后**所有对这张表的访问全部排队** ⚠️⚠️

```sql
-- 查看 MDL 等待（5.7+）
SELECT * FROM performance_schema.metadata_locks WHERE lock_status='PENDING';
SELECT * FROM sys.schema_table_lock_waits\G   -- ⭐ 8.0 更好用
```

**根因**：`ALTER TABLE` 需要 MDL 排他锁，但**有未提交的事务/长查询**持着 MDL 共享锁 → `ALTER` 等待 → 后续所有请求排队。**这就是"一个 DDL 卡死整个业务"的机制**。

**对策**：

```
① 紧急：KILL 掉持有 MDL 共享锁的长事务 ⭐
② 长效：
   · 用 pt-osc / gh-ost（减少 DDL 持锁时间）⭐
   · 设置 lock_wait_timeout（DDL 的超时）
   · DDL 在低峰做
   · 监控 information_schema.innodb_trx 的长事务
```

## 五、空间类故障 ⭐

### 磁盘满（`ERROR 1114 / 1030: Disk full`）

```bash
df -h
du -sh /var/lib/mysql/* | sort -h | tail -20
# 找大文件：
#  · ibdata1（通用表空间，只增不减）⚠️
#  · undo_001/undo_002（undo 膨胀）
#  · binlog（未清理）
#  · 大表 .ibd
#  · slow.log / general.log
#  · 临时文件（大排序产生）
```

**应急处置** ⭐：

```sql
-- ① 清理 binlog（⚠️ 确认从库已应用！）
PURGE BINARY LOGS BEFORE DATE_SUB(NOW(), INTERVAL 3 DAY);
-- 或
PURGE BINARY LOGS TO 'mysql-bin.000123';

-- ② 触发生成可回收文件
FLUSH LOGS;                 -- 切 binlog
FLUSH TABLES;               -- 必要时

-- ③ 截断 undo 表空间
SET GLOBAL innodb_undo_log_truncate = ON;
SET GLOBAL innodb_max_undo_log_size = 1073741824;

-- ④ 关掉 general_log（如果开着）⚠️
SET GLOBAL general_log = OFF;
```

```bash
# ⑤ 清理慢日志/通用日志（先备份再清）
: > /var/log/mysql/slow.log
```

**⚠️ 不要把 `ibdata1` 或 `.ibd` 删掉！**（那是数据）

**长效**：容量水位告警、日志切割、binlog 定期清理、`innodb_undo_log_truncate=ON`。

### undo / History list length 暴涨

```
根因：长事务阻塞 purge ⭐
处置：
  ① 找并 KILL 长事务
  ② 调大 innodb_purge_threads
  ③ 确认 innodb_undo_log_truncate=ON
  ④ 检查有没有"忘了提交"的代码（RAII 保证）⭐
```

## 六、复制类故障 ⭐

### 主从延迟大

```
应急处置：
  ① 看从库负载（是否被其他查询拖住）
  ② 看是否有大事务/DDL 在重放
  ③ 临时把读流量切回主库 ⭐
  ④ 必要时跳过（⚠️ 危险）

长效：
  ① 拆小事务 ⭐
  ② 并行复制（slave_parallel_workers + LOGICAL_CLOCK / WRITESET）⭐
  ③ 从库配置不低于主库
  ④ 从库不做重查询（单独分析实例）⭐
  ⑤ ProxySQL 的 max_replication_lag 自动摘除延迟从库 ⭐
```

### 复制中断（`Last_SQL_Error` / `Slave_SQL_Running: No`）⭐

```sql
SHOW SLAVE STATUS\G
-- 看 Last_SQL_Error 与 Last_SQL_Errno

-- 常见错误与处理：
-- ① 1062 主键冲突 → 数据已不一致
--    处理：确认从库已有的数据是否与主库一致 → 一致则跳过
SET GLOBAL SQL_SLAVE_SKIP_COUNTER = 1;   -- 老语法
STOP SLAVE; START SLAVE;                   -- 8.0 可用 GTID 跳过
-- GTID 模式：
SET GTID_NEXT='<出错的 GTID>';
BEGIN; COMMIT;
SET GTID_NEXT='AUTOMATIC';
START SLAVE;
-- ⚠️ 跳过是"止血"，之后必须做数据校验（pt-table-checksum）⭐

-- ② 1032 行不存在 → 从库缺数据
-- ③ 1064 语法错误 → 版本不兼容（如 8.0 主库 → 5.7 从库）⭐
-- ④ 1114 磁盘满 → 清理空间
-- ⑤ 1594 relay log 损坏 → 重新做从库
```

**⚠️ 铁律**：**跳过错误后必须做一致性校验**，否则不一致会越积越多。

### 重新搭建从库（最彻底的方案）⭐

```bash
# 方案 A：物理克隆（最快）⭐
# 主库执行
CLONE INSTANCE FROM 'user'@'host':3306 IDENTIFIED BY 'pass';
# 或独立工具
xtrabackup --backup --target-dir=/backup/full
# 拷到从库 → --prepare → --copy-back → 配 replication → START SLAVE

# 方案 B：mysqldump（小库）
mysqldump --single-transaction --master-data=2 --source-data=2 ...
```

## 七、数据类故障 ⭐

### 误删数据 ⭐

```
① 立即停止写入（或至少判断写入是否会覆盖要恢复的位置）
② 用 binlog 做 PITR（时间点恢复）⭐
   mysqlbinlog --start-position=... --stop-datetime='误操作前一刻' \
     mysql-bin.000012 | mysql -u root -p
   ⚠️ 先用 `> recover.sql` 落成文件，用编辑器去掉误操作那段，再执行 ⭐
③ 用备份恢复 + binlog 补齐
④ 如果是从库误删 → 从主库/其他从库重建 ⭐
```

**预防**：`sql_safe_updates=ON`（禁止无 WHERE 的 UPDATE/DELETE）⭐、`super_read_only`、权限最小化、DDL 审核。

### 中文乱码（`?` 或 `åŠŸèƒ½`）⭐

见"字符集"那题。**关键判据：1 汉字 : 1 `?` ⇒ MySQL 字符集转换；1 汉字 : 3 `?` ⇒ 程序按字节处理**。**先分清"MySQL 转换"还是"程序处理"，再决定迁移方案，绝不要盲目 `ALTER ... CONVERT TO`** ⭐

## 八、可用性类故障 ⭐

### 实例无法启动

```bash
# ① 看 error log（第一站）⭐
tail -100 /var/log/mysql/error.log
journalctl -u mysqld -n 100 --no-pager

# 常见原因：
#  · 端口被占用          → ss -lntp | grep 3306
#  · 数据目录权限不对    → chown -R mysql:mysql /var/lib/mysql
#  · 配置文件语法错误    → mysqld --validate-config
#  · redo/undo 损坏       → innodb_force_recovery（从 1 逐步到 6）⚠️
#  · 磁盘满
#  · InnoDB 崩溃恢复中   → 耐心等（看 error log 的进度），别急着重启
```

**`innodb_force_recovery` 的使用警告** ⚠️：只能在**数据抢救**场景临时用（`=1` 到 `=6` 递增，越大越危险），**必须立即备份数据**，之后重建实例。**不要在 `force_recovery > 0` 的情况下继续长期运行**。

### 崩溃恢复太慢

```
根因：redo log 太大（要重放很久）+ 双写缓冲
对策：
  ① 恢复期耐心等并监控 error log
  ② 长效：控制 redo 容量（不要过大），或依赖更高可用架构（MGR / 云多可用区）⭐
```

## 九、故障应急的通用方法论 ⭐

```
【黄金三步】

① 止血（分钟级）
   · 限流 / 降级 / 切流 / KILL 阻塞者 / 扩容临时资源
   · 目标：恢复核心业务可用
   · ⚠️ 保留现场（复制相关输出到文件）⭐

② 定位（小时级）
   · 用 processlist / innodb status / sys 表 / 系统工具
   · 自下而上：OS → 实例 → 引擎 → SQL
   · 找到"根因"而不是"表象"

③ 修复与防复发（天级）
   · 长效修复（架构/代码/索引/参数）
   · 加监控告警（能提前发现同类问题）⭐
   · 写复盘文档（含时间线、根因、改进项）⭐
   · 演练（确保下次更快）

【必备的"故障工具箱"（提前准备好）】
  □ 高权限应急账号（或在 my.cnf 里预留）
  □ 一键采集现场脚本（dump 关键状态到文件）⭐
  □ 从库/备份可用且已验证
  □ 限流/降级开关（应用层）
  □ 回滚方案（发布回滚、数据回滚）
  □ 值班联系方式与升级路径
```

## 十、一句话总结

**MySQL 故障处理的核心是"先止血保业务，同时保留现场，再查根因"**；最常见的四类根因是 **缺索引导致的全表扫描、长事务导致的锁/purge 阻塞、`max_connections` 与连接池不匹配、主从延迟/中断**；**必备的应急手段是 KILL 根阻塞者、限流降级、切读流量到从库**；**最容易踩的坑是"'已经重启了但现场没保留'和'KILL 大事务后以为立刻就好了（实际还要回滚很久）'"**。""",
    ),
    (
        "MySQL",
        "缓存,一致性,Redis",
        3,
        r"""缓存和数据库怎么保证一致性？为什么"先删缓存再更新数据库"会有问题？""",
        r"""## 一、四种模式对比 ⭐

| 模式 | 读 | 写 | 问题 |
|---|---|---|---|
| **Cache-Aside（旁路缓存）** ⭐ | 先读缓存，miss 查 DB 回填 | **先更新 DB，再删缓存** | 有短暂不一致窗口 |
| **Read-Through** | 缓存组件自己回源 | 同 | 需缓存组件支持 |
| **Write-Through** | — | 写缓存时同步写 DB | 写延迟高 |
| **Write-Behind（写回）** | — | 写缓存，异步批量写 DB | **一致性弱，可能丢数据** ⚠️ |

**实践：绝大多数系统用 Cache-Aside** ⭐

## 二、四个经典错误组合 ⭐

### ① ❌ 先更新 DB，再更新缓存

```
T1: A 更新 DB 为 1
T2: B 更新 DB 为 2
T3: B 更新缓存为 2
T4: A 更新缓存为 1        ← ⚠️ 缓存最终是 1，DB 是 2 → 不一致！
```
**问题**：两个并发的"更新"操作**顺序交错**（DB 和缓存的更新顺序不一定一致）。

**另一个问题**：如果缓存值需要复杂计算（多表 JOIN 拼装），**"更新缓存"的成本很高**，而且可能"写了根本没人读"（浪费）→ **应该删缓存而不是更新缓存** ⭐

### ② ❌ 先删缓存，再更新 DB ⭐（经典问题）

```
T1: A 删除缓存
T2: B 读缓存 miss → 读 DB（旧值 100）→ 回填缓存 100     ← ⚠️ 把旧值写回来了！
T3: A 更新 DB 为 200
结果：DB = 200，缓存 = 100 → 长期不一致（直到缓存过期）❌
```

**根因**：**"删缓存"和"读 DB 回填"之间有时间窗口**，读请求趁机把旧值塞回缓存。这个窗口越大（DB 查询慢），越容易出问题 ⭐

### ③ ❌ 先更新 DB，再删缓存 ⭐（推荐，但仍有极小概率）

```
T1: A 读缓存 miss → 读 DB（旧值 100）
T2: A 被阻塞（GC / 网络 / 调度）
T3: B 更新 DB 为 200
T4: B 删除缓存
T5: A 恢复 → 把读到的旧值 100 写入缓存      ← ⚠️ 写入旧值
结果：DB = 200，缓存 = 100 → 不一致 ❌
```

**为什么仍推荐这个方案** ⭐：**出现条件极其苛刻** —— 需要"读线程在 `读DB` 和 `写缓存` 之间被阻塞，且阻塞时间超过一个完整的写事务"。现实中要求：

```
① 读操作先到，读 DB 拿到旧值
② 读操作在写缓存之前被长时间阻塞（GC/网络抖动/线程调度）
③ 写操作在阻塞期间完成"更新 DB + 删缓存"
④ 读操作恢复后才写缓存
```

**概率极低**，而且**缓存有过期时间兜底**（最终一致）。所以这是**工业界的默认选择**。

### ④ ⚠️ 只删缓存不更新 DB（显然错）

## 三、一致性等级 ⭐

| 等级 | 手段 | 代价 |
|---|---|---|
| **强一致** | 不用缓存 / 缓存只读不写 / 分布式锁 | 性能差 |
| **准强一致**（秒级） | 先更新 DB 再删缓存 + **延迟双删** ⭐ | 低 |
| **最终一致**（毫秒~秒） | 缓存设 TTL + **binlog 订阅同步** ⭐⭐ | 中 |
| **弱一致** | 定时刷新 | 可能差几分钟 |

**实践结论** ⭐：**没有"强一致 + 高并发"的缓存方案**。要根据业务容忍度选：

```
· 商品详情、文章列表 → 最终一致足够（延迟双删 + TTL）
· 库存、余额 → 不要用缓存，直接读 DB（或只缓存"粗粒度"的数量）⭐
· 配置、字典 → 长 TTL + 主动失效
```

## 四、工业界的三套方案 ⭐⭐

### 方案 A：先更新 DB，再删缓存 + 延迟双删 ⭐

```cpp
// 1. 更新数据库
updateDB(...);
// 2. 立即删缓存
delCache(key);
// 3. ⭐ 延迟一小段时间后再删一次（覆盖"读请求回填旧值"的窗口）
scheduleAfter(500ms, [key]() { delCache(key); });

// 延迟时间怎么定：
//    > 读请求"读DB + 写缓存"的总耗时 ⭐
//    经验值：写库耗时 + 几百毫秒（通常 500ms ~ 1s）
```

**为什么"延迟双删"有效**：它把"读请求回填旧值"的那个窗口**关掉**——第二次删除会把这个旧值清掉 ⭐

**缺点**：延迟删除是异步的，需要可靠的任务调度（线程池 / 延时队列 / 消息队列的延时消息）⭐

### 方案 B：binlog 订阅 + 异步删除（最可靠）⭐⭐

```
业务代码：只更新 DB（不管缓存）
                ↓
            MySQL binlog
                ↓
        Canal / Debezium / Maxwell（伪装成从库）
                ↓
        消息队列（Kafka/RocketMQ）
                ↓
            消费者删除/更新缓存
```

**优势** ⭐：

| 优势 | 说明 |
|---|---|
| **业务代码完全解耦** | 不用在业务里写缓存维护逻辑 |
| **顺序性** | binlog 天然有序，可按主键 hash 到同一分区保证顺序 ⭐ |
| **可靠性** | MQ 保证至少一次，可重试 |
| **覆盖所有写入** | 包括手动 SQL、其他服务的写入 ⭐（这是"业务代码里删缓存"做不到的）|
| **可追溯** | 有变更日志 |

**这才是大厂的标准方案** ⭐。本项目若要加缓存，也应该走这条路线（或先用简单的 TTL 兜底）。

### 方案 C：读写都加锁（成本太高，很少用）

```
读：加锁 → 读缓存/DB → 解锁
写：加锁 → 更新 DB → 删缓存 → 解锁
```
分布式锁会成为瓶颈 ⚠️

## 五、缓存三大问题（必考）⭐

### ① 缓存穿透（查不存在的数据）⭐

```
现象：大量请求查"不存在"的 key → 缓存永远 miss → 全部打到 DB
      （典型：恶意攻击用不存在的 id 刷接口）⚠️
```

| 方案 | 说明 |
|---|---|
| **缓存空值** ⭐ | 查不到也缓存一个 `NULL`（短 TTL，如 60s）→ 挡住重复查询。**简单有效** |
| **布隆过滤器** ⭐ | 前置拦截"一定不存在"的 key（**有假阳性但无假阴性**）→ 拦截绝大多数无效请求 |
| **参数校验** | 在入口层校验 id 格式、范围（如自增 id 必须 > 0）⭐ |
| **限流 + 黑名单** | 防攻击 |

### ② 缓存击穿（热点 key 过期瞬间）⭐

```
现象：某个超热 key 过期 → 瞬间大量请求同时查 DB → DB 被打崩
```

| 方案 | 说明 |
|---|---|
| **互斥锁（只让一个请求回源）** ⭐ | `SETNX lock` 成功者去查 DB 并回填，其他请求短暂 sleep 后重试 |
| **逻辑过期** ⭐ | 缓存**永不物理过期**，value 里存"逻辑过期时间"；发现逻辑过期时由**一个线程异步重建**，其他请求先返回旧值 |
| **热点 key 永不过期 + 后台定时刷新** ⭐ | 运维上用定时任务刷新 |

**逻辑过期是推荐的方案**（不阻塞请求，可用性最好）：

```
value = { data: {...}, expireAt: 1714528800 }

读：
  if (now < expireAt) → 直接返回 data ✅
  else → 返回 data（旧值，用户无感）⭐
       → 异步：抢锁 → 重建缓存 → 更新 value
```

### ③ 缓存雪崩（大量 key 同时过期 / 缓存服务挂了）⭐

```
现象 A：大量 key 设置了相同的过期时间 → 同一时刻集体失效 → DB 被冲垮 ⚠️
现象 B：Redis 集群挂了 → 所有请求直达 DB → DB 被冲垮 ⚠️
```

| 方案 | 说明 |
|---|---|
| **过期时间加随机抖动** ⭐ | `TTL = base + rand(0, 300s)` —— **最简单有效** |
| **多级缓存** ⭐ | 本地缓存（Caffeine/进程内 LRU）+ Redis；本地缓存抖动用本地兜底 |
| **熔断降级** | 检测到 DB 压力过大 → 限流/返回兜底数据 ⭐ |
| **预热** | 上线/重启前提前把热点数据加载进缓存 |
| **Redis 高可用** | 主从 + 哨兵 / Cluster |
| **持久化 + 快速恢复** | RDB/AOF 让 Redis 重启能快速恢复 |

## 六、缓存的通用实践清单 ⭐

| 项 | 建议 |
|---|---|
| **key 设计** | `业务:实体:标识`，如 `post:detail:123`；**避免大 key / 热 key** ⭐ |
| **TTL 必设** | **所有缓存都要有过期时间**（兜底最终一致）⭐ |
| **TTL 加抖动** | 防雪崩 ⭐ |
| **大 key 拆分** | 单个 value > 10KB 考虑拆分；集合元素 > 5000 考虑分片 ⭐ |
| **热 key 打散** | 加随机后缀分散到多个 key（`hot:123:0~9`）|
| **不要缓存敏感数据** | 或加密 + 短 TTL |
| **缓存命中率监控** | 命中率骤降 → 有异常（可能是穿透攻击）⭐ |
| **降级预案** | 缓存不可用时如何兜底（DB 只读 + 限流）⭐ |
| **序列化统一** | JSON / MessagePack / Protobuf，团队统一 |
| **避免"缓存全量数据"** | 内存有限，只缓存热点 |

## 七、`Redis` 与 `MySQL` 的数据边界 ⭐

**一个实用的划分原则**：

```
MySQL 掌管：
  ✔ 事务性数据（订单、支付、库存的最终值）
  ✔ 需要强一致的约束（唯一性）
  ✔ 复杂查询 / JOIN / 聚合
  ✔ 数据持久性要求高的数据

Redis 掌管：
  ✔ 热点读（列表页、详情页、排行榜）
  ✔ 计数器（浏览量、点赞数）  ← 但要注意异步落库 ⭐
  ✔ 会话（Session、Token）
  ✔ 分布式锁
  ✔ 限流 / 去重
  ✔ 排行榜（ZSet）
  ✔ 消息队列（Stream / List）
```

**关键**：**Redis 是缓存和加速层，不是"数据的第二份真相"** ⭐。**任何"只在 Redis 里的数据"都要问一句："Redis 挂了会丢什么？"**

## 八、本项目（博客系统）的缓存建议 ⭐

```
当前状态：无缓存（直接查 MySQL）

优先级 1（成本极低、收益高）：
  ✔ 文章详情：`post:detail:<id>` 缓存 10min + 更新后删除
  ✔ 文章列表第一页：`post:list:page:1` 缓存 1min
  ✔ 每日一题：当天题目几乎不变 → 缓存到当天结束 ⭐（和项目的"懒生成"机制天然契合）
  ✔ 站点统计（总文章数、总访问量）：缓存 5min

实现方式（本项目 Crow 场景，没有 Redis 时）：
  ✔ 进程内 LRU 缓存（C++ 用 std::unordered_map + 过期时间戳 + mutex）
  ✔ 或简单的 "map + 定时清理"
  ⚠️ 多线程要注意加锁；且"更新文章"时要清对应的缓存项 ⭐

有 Redis 后：
  ✔ 按上面 Cache-Aside + 先更新 DB 再删缓存
  ✔ TTL 兜底（哪怕删除逻辑有 bug，最坏也就脏 N 分钟）⭐
```

**关键提醒** ⭐：本项目**文章发布/编辑**后必须**清掉列表页缓存**（因为列表会变），否则用户看不到自己的新文章 —— 这是"缓存导致用户困惑"的最典型场景。

## 九、一句话总结

**"先更新 DB 再删缓存"是主流方案（出现不一致的条件极其苛刻）**，配合 **延迟双删** 可基本消除；**最可靠的是 "binlog 订阅 + 异步删缓存"**（业务解耦、覆盖所有写入、顺序可保证）⭐⭐；**缓存三大问题的解法分别是"空值缓存/布隆过滤器"、"互斥锁/逻辑过期"、"TTL 加随机抖动 + 多级缓存"**；**所有缓存必须设 TTL 作为最终一致的兜底**。""",
    ),
    (
        "MySQL",
        "全文索引,搜索,ES",
        2,
        r"""MySQL 的全文索引怎么用？什么时候该换成 Elasticsearch？""",
        r"""## 一、全文索引基础 ⭐

**全文索引（FULLTEXT）** 专为**文本分词检索**设计，解决 `LIKE '%keyword%'` 无法用索引、只能全表扫描的问题。

| 支持情况 | 说明 |
|---|---|
| **InnoDB** | **5.6+ 支持** ⭐（之前只有 MyISAM）|
| **MyISAM** | 支持（老方案）|
| **适用列类型** | `CHAR` / `VARCHAR` / `TEXT` |
| **中文分词** | ⚠️ **默认分词器不支持中文**（见下文）|

```sql
-- 建全文索引
ALTER TABLE posts ADD FULLTEXT INDEX ft_posts (title, content) WITH PARSER ngram;

-- 或建表时
CREATE TABLE posts (
    ...
    FULLTEXT KEY ft_posts (title, content) WITH PARSER ngram
) ENGINE=InnoDB;

SHOW INDEX FROM posts WHERE Index_type='FULLTEXT';
```

## 二、三种查询模式 ⭐

```sql
-- ① 自然语言模式（默认）
SELECT * FROM posts WHERE MATCH(title, content) AGAINST('数据库 索引');
-- 特点：按相关性排序，忽略停用词和 <50% 的词（MyISAM 限制）

-- ② 布尔模式 ⭐（最常用，可控性强）
SELECT * FROM posts
WHERE MATCH(title, content) AGAINST('+MySQL -Redis' IN BOOLEAN MODE);
-- 运算符：
--   +word   必须包含
--   -word   必须不包含
--   word*   前缀匹配
--   "a b"   短语（必须相邻）
--   >word   提高权重   <word 降低权重
--   ~word   降低该词的相关性贡献
--   (a b)   分组
--   ""      引号内为短语

-- ③ 查询扩展模式
SELECT * FROM posts
WHERE MATCH(title, content) AGAINST('数据库' WITH QUERY EXPANSION);
-- 先用原词查，再用结果中的高频词二次查询（扩大召回，但可能引入噪声）
```

**相关性打分**：

```sql
SELECT id, title,
       MATCH(title, content) AGAINST('MySQL 索引' IN BOOLEAN MODE) AS score
FROM posts
WHERE MATCH(title, content) AGAINST('MySQL 索引' IN BOOLEAN MODE)
ORDER BY score DESC LIMIT 20;
```

## 三、中文分词：`ngram` 解析器 ⭐⭐（关键）

**默认分词器按"空格/标点"切词** → 中文整句变成一个 token → **`MATCH` 几乎失效** ⚠️

**解决：`ngram` 解析器**（MySQL **5.7.6+** 内置）⭐

```sql
CREATE FULLTEXT INDEX ft_posts ON posts (title, content) WITH PARSER ngram;

-- 控制 n-gram 长度（默认 2，即 bigram）
-- 写进 my.cnf
[mysqld]
ngram_token_size = 2      # ⚠️ 建索引后修改必须重建索引才生效
```

**行为**：`ngram_token_size=2` 时，"数据库索引" → `数据` / `据库` / `库索` / `索引`

```sql
-- 中文查询
SELECT * FROM posts WHERE MATCH(title, content) AGAINST('索引' IN BOOLEAN MODE);
-- ✅ 生效

-- ⚠️ 单字查询在 ngram_token_size=2 时搜不到！
SELECT * FROM posts WHERE MATCH(title, content) AGAINST('索' IN BOOLEAN MODE);
-- 因为 token 最小是 2 字 → "索"不是有效 token ❌
-- 解决：用 LIKE 兜底，或把 ngram_token_size 设为 1（索引会变大）⭐
```

**关键参数**：

| 参数 | 默认 | 说明 |
|---|---|---|
| `ngram_token_size` | **2** | 分词长度；**改动后需重建所有 FULLTEXT 索引** ⭐ |
| `innodb_ft_min_token_size` | 3 | 英文最小词长（英文场景）|
| `innodb_ft_max_token_size` | 84 | 最大词长 |
| `innodb_ft_enable_stopword` | ON | 停用词 |
| `innodb_ft_result_cache_limit` | 2G | 结果缓存上限 |

**`ngram` 的坑** ⭐：

| 坑 | 说明 |
|---|---|
| **相关性打分不准** | bigram 分词导致相关性排序不如专业引擎 |
| **索引体积大** | 每个 2 字组合都是 token → 索引可能比数据还大 ⚠️ |
| **写入慢** | 维护大量 token |
| **不支持同义词/词干** | "数据库"与"DB"不算同义 ⚠️ |
| **不支持拼音/错字容错** | ⚠️ |

## 四、全文索引的限制 ⭐

| 限制 | 说明 |
|---|---|
| **必须整列匹配** | `MATCH(col1, col2) AGAINST(...)` 里的列必须与索引定义**完全一致**（顺序也要一致）⚠️ |
| **不能与其他条件复用同一索引** | `MATCH(...) AND status=1` 时，`status` 需要另一个索引 → 优化器可能选一个而不用另一个 |
| **MyISAM 的 50% 阈值** | MyISAM 下，出现频率 > 50% 的词视为停用词（**InnoDB 已取消此限制**）⭐ |
| **停用词表** | `INFORMATION_SCHEMA.INNODB_FT_DEFAULT_STOPWORD`（可自定义 `innodb_ft_user_stopword_table`）|
| **`ngram_token_size` 改动要重建索引** ⚠️ | |
| **不支持"必须存在"与"模糊"混合的复杂查询** | 复杂查询语法有限 |
| **不擅长多维过滤 + 排序** | 如"分类=X 且 价格 100~200 且 按销量排序" → 全文索引帮不上 |

**检查停用词**：

```sql
SELECT * FROM INFORMATION_SCHEMA.INNODB_FT_DEFAULT_STOPWORD;
-- 自定义
SET GLOBAL innodb_ft_user_stopword_table = 'blogdb/my_stopwords';   -- 需先建表
```

**分词结果调试**（很有用）⭐：

```sql
SET GLOBAL innodb_ft_aux_table = 'blogdb/posts';
SELECT * FROM INFORMATION_SCHEMA.INNODB_FT_INDEX_TABLE LIMIT 50;
-- 能看到实际分了哪些 token、出现在哪个文档、位置 ⭐ 排查"为什么搜不到"的利器
```

## 五、什么时候换 Elasticsearch ⭐⭐

### 用 MySQL FULLTEXT 就够的情况 ✅

```
✔ 数据量小（几十万行以内）
✔ 只需要"关键词匹配"，不需要复杂的相关性排序
✔ 查询简单（不涉及多维过滤 + 排序 + 聚合的组合）
✔ 不想引入额外的中间件与运维负担 ⭐
✔ 数据一致性要求高（避免"MySQL 与 ES 数据不一致"）⭐
```

### 该换 ES 的情况 ❌

| 需求 | 为什么 FULLTEXT 做不了 |
|---|---|
| **复杂相关性排序**（TF-IDF/BM25 + 字段权重 + 时间衰减）| FULLTEXT 打分能力弱 ⭐ |
| **同义词、词干、拼音、错字容错** | 不支持（ES 有丰富的 analyzer）⭐ |
| **高亮（highlight）** | ES 原生支持 |
| **多维过滤 + 排序 + 聚合 + 分面（facet）** | "分类+价格+品牌+评分排序" → ES 原生 |
| **数据量大（千万级以上）** | FULLTEXT 索引体积与写入开销过大 ⚠️ |
| **搜索日志与效果分析** | ES 有搜索分析能力 |
| **中文分词质量要求高** | ES 有 IK / jieba / THULAC 等成熟分词器 ⭐ |
| **近实时搜索（NRT）+ 高并发查询** | ES 专为此设计 |
| **地理位置搜索** | ES 有 geo 类型 |

### 引入 ES 的代价 ⚠️（必须权衡）

| 代价 | 说明 |
|---|---|
| **运维复杂度** | 又一个集群（ES 对内存/磁盘要求高）⭐ |
| **数据同步** ⭐ | MySQL → ES 的同步链路（Canal/Logstash/自研），要处理**一致性、延迟、失败重试** |
| **一致性挑战** ⭐ | MySQL 写了但 ES 还没同步 → 用户"刚发布的搜不到"（和主从延迟同类问题）|
| **成本** | 机器 + 人力 |
| **调试难度** | 分词器、mapping、查询 DSL 都有学习成本 |

**结论** ⭐：**"搜索是核心功能"才上 ES；"搜索是辅助功能"用 MySQL FULLTEXT + LIKE 兜底**。

## 六、推荐的演进路径 ⭐

```
阶段 1：数据量小 → LIKE 'kw%'（前缀匹配，能用索引）
         ⚠️ 但 '%kw%' 用不了索引，只能全表扫

阶段 2：需要关键词检索，数据量 < 100 万
         → MySQL FULLTEXT + ngram ⭐ 零额外运维

阶段 3：搜索体验要求提高（相关性、高亮、纠错）
         → 引入 Elasticsearch + IK 分词 ⭐
         → 用 binlog 订阅（Canal/Debezium）保持同步

阶段 4：搜索是核心业务
         → ES 集群 + 搜索质量评估体系 + AB 测试
```

**中间方案的变体** ⭐：

| 方案 | 说明 |
|---|---|
| **ES 只存检索必需字段** | 倒排索引 + 少量展示字段；详情仍查 MySQL（避免 ES 成为数据源）⭐ |
| **搜索走 ES，回表走 MySQL** | 典型两段式：ES 返回 id 列表 → MySQL 批量查详情 ⭐ |
| **本地缓存 + FULLTEXT 混合** | 热搜索词结果缓存，冷词走 FULLTEXT |
| **云搜索服务** | 阿里云 OpenSearch / 腾讯云 ES（省运维）⭐ |

## 七、本项目（博客）的建议 ⭐

```
场景：博客搜索 —— 按标题/正文/标签搜文章

数据量：几百到几千篇 → ⭐ **MySQL FULLTEXT 完全够用**

具体方案：
① 建 ngram 全文索引
   ALTER TABLE posts ADD FULLTEXT INDEX ft_posts (title, summary, content) WITH PARSER ngram;
   ⚠️ 注意：与已有索引的列顺序要一致

② 查询（布尔模式，支持多词与排除）
   SELECT id, title, summary,
          MATCH(title, summary, content) AGAINST(? IN BOOLEAN MODE) AS score
   FROM posts
   WHERE status = 1
     AND MATCH(title, summary, content) AGAINST(? IN BOOLEAN MODE)
   ORDER BY score DESC, created_at DESC
   LIMIT 20;

③ 参数要考虑 ngram_token_size = 2 → 用户输入单字搜不到
   → 前端限制最少输入 2 个字，或对单字走 LIKE 兜底 ⭐

④ 用户输入的运算符要转义/白名单（`+`、`-`、`"` 在布尔模式下有语义）⭐
   ⚠️ 这是安全与体验的双重问题

⑤ 写入开销：全文索引会让 INSERT/UPDATE 变慢
   → 用 summary 而不是 content 全文索引？或分离到独立表 ⭐

⑥ 备选（不引入 ES 的"加料"方案）：
   · 标题权重高于正文 → 分别查两次，标题命中加权 ⭐
   · 搜索词高亮 → 应用层做（拿到结果后用正则加 <mark>）
   · 搜索历史/热词 → Redis
```

**`MATCH ... AGAINST` 与 `status=1` 的索引冲突** ⭐：优化器通常只能用一个索引。如果 `status=1` 过滤后行数很少，可能选 `idx_status` + 逐行 `MATCH` 过滤（慢）；反之可能用 `ft_posts` 再过滤 status。**用 `EXPLAIN` 确认，必要时用 hint 或改成两段式查询**（先全文检索出 id，再按 status 过滤）。

## 八、一句话总结

**MySQL FULLTEXT 的价值是"零额外运维的关键词检索"，中文必须配 `ngram` 解析器（且 `ngram_token_size=2` 意味着单字搜不到）⭐**；**当需求升级到"复杂相关性 + 同义词 + 高亮 + 多维过滤聚合"或数据量到千万级时，才值得引入 ES** —— 但要同时接受 **"数据同步链路 + 一致性延迟 + 运维成本"** 这三项代价；**博客这种量级，FULLTEXT 完全够用**。""",
    ),
    (
        "MySQL",
        "空间数据,GIS,索引原理",
        2,
        r"""MySQL 支持空间数据吗？空间索引的原理是什么？和 B+ 树有什么区别？""",
        r"""## 一、MySQL 的空间数据类型 ⭐

| 类型 | 说明 |
|---|---|
| **`GEOMETRY`** | 通用几何（可存任意类型）|
| **`POINT`** | 点（经纬度）⭐ |
| **`LINESTRING`** | 线（路径、轨迹）|
| **`POLYGON`** | 多边形（区域、围栏）⭐ |
| **`MULTIPOINT` / `MULTILINESTRING` / `MULTIPOLYGON`** | 复合 |
| **`GEOMETRYCOLLECTION`** | 混合集合 |

**核心特性**：

| 特性 | 说明 |
|---|---|
| **SRID**（空间参考系统标识）| 8.0 起支持；**必须指定 SRID 才能做正确的距离计算** ⭐ |
| **WGS84（SRID 4326）** | 常用经纬度坐标系（GPS）|
| **SRID 0** | 笛卡尔平面（无地理语义）|
| **内部格式** | 二进制（WKB/内部格式），比 WKT 文本更紧凑 ⭐ |

```sql
CREATE TABLE shops (
    id    BIGINT PRIMARY KEY,
    name  VARCHAR(100),
    loc   POINT NOT NULL SRID 4326,          -- ⭐ 8.0 语法
    SPATIAL INDEX idx_loc (loc)              -- 空间索引
) ENGINE=InnoDB;
```

## 二、`SRID` 的重要作用 ⭐⭐

```sql
-- ❌ 没有 SRID 时，"距离"是平面上的欧几里得距离（错误的经纬度距离）
-- ✅ 指定 SRID 4326 后，距离按球面计算

-- 8.0 正确写法
INSERT INTO shops (id, name, loc) VALUES (1, 'A', ST_SRID(POINT(116.397, 39.908), 4326));
-- 或
INSERT INTO shops (id, name, loc) VALUES (1, 'A', ST_GeomFromText('POINT(116.397 39.908)', 4326));

-- 距离查询（球面，单位"米"）⭐
SELECT id, name,
       ST_Distance_Sphere(loc, ST_SRID(POINT(116.400, 39.910), 4326)) AS meters
FROM shops
ORDER BY meters LIMIT 10;
```

**⚠️ `ST_Distance_Sphere` 是 MySQL 内置的球面距离（Haversine 变体），单位是米** ⭐ 这是地理场景最常用的函数。

## 三、空间索引的原理：R 树 ⭐⭐

### 为什么不能用 B+ 树？

**B+ 树只能索引"一维有序"的数据**。二维坐标有**两个维度**，无法用一个标量排序同时保持两维的局部性：

```
问题：按经度排序后，纬度就乱了；按纬度排序，经度又乱了
     → B+ 树无法同时支持"经度范围 + 纬度范围"的查询 ⚠️
```

### R 树（R-Tree）的核心思想 ⭐

**用"最小外包矩形（MBR, Minimum Bounding Rectangle）"组织数据，形成层级包围盒**：

```
                    ┌─────────────────────────┐
        根节点：     │  R1 (整个区域的外包框)     │
                    └─────────────────────────┘
                     /                       \
        ┌──────────────────┐      ┌──────────────────┐
   中层：│ R2 (覆盖左半区域) │      │ R3 (覆盖右半区域) │
        └──────────────────┘      └──────────────────┘
           /        \                    /       \
      ┌───────┐ ┌───────┐          ┌───────┐ ┌───────┐
叶子：│P1 P2  │ │P3 P4  │          │P5 P6  │ │P7 P8  │
      └───────┘ └───────┘          └───────┘ └───────┘
      每个叶子存实际对象（点/线/多边形）
```

**查询过程**（以"找某个矩形区域内的所有点"为例）：

```
① 从根节点开始，检查哪些子节点的 MBR 与查询区域**相交**
② 不相交的整个子树**直接剪枝**（这是 R 树的威力所在）⭐
③ 相交的继续向下递归
④ 到叶子节点后，对每个对象做**精确的几何判断**
   （MBR 相交 ≠ 对象真的相交，MBR 只是"粗筛"）⭐
```

**关键概念：过滤（filter）+ 精炼（refine）两阶段** ⭐

```
阶段 1（Filter）：用 MBR 做粗筛，快速排除大量无关数据 → 利用 R 树索引
阶段 2（Refine）：对候选集做精确几何计算（ST_Contains / ST_Intersects）
```

**InnoDB 的空间索引实际上用的是 B+ 树 + MBR 的混合实现** ⭐：InnoDB 没有独立的 R 树实现，而是**在 B+ 树的键上存 MBR**（把 MBR 编码成可比较的形式）。所以它是"**B+ 树形态的 R 树语义**"。

### R 树 vs B+ 树 ⭐

| | **B+ 树** | **R 树（空间索引）** |
|---|---|---|
| 数据维度 | **一维**（有序值）| **多维**（通常 2D）|
| 节点内容 | 键值区间 | **最小外包矩形（MBR）** |
| 重叠 | 无（区间可完全划分）| **子节点的 MBR 可能重叠** ⚠️ |
| 查询 | 范围/等值 | **空间相交/包含/邻近** |
| 更新代价 | 低 | **较高**（重插可能导致 MBR 重算、分裂）⚠️ |
| 最优性 | 有保证 | **启发式**（插入策略影响性能）|

**R 树的关键弱点** ⭐：**MBR 之间的重叠导致剪枝效率下降**。如果数据分布差（如大量细长的对象），MBR 会大面积重叠 → 剪枝失效 → 退化为全扫。这就是"空间索引不如 B+ 树高效"的根本原因。

### 其他空间索引算法（了解）

| 算法 | 特点 |
|---|---|
| **R 树 / R\* 树** | 主流（MySQL、PostGIS 用）|
| **四叉树（Quadtree）** | 递归四分空间；简单，适合均匀分布 ⭐ |
| **Geohash** ⭐ | 把二维坐标编码成一维字符串（前缀越长越精确）→ **可以用普通 B+ 树索引！** ⭐ |
| **Hilbert 曲线** | 空间填充曲线，保持更好的局部性 ⭐ |
| **网格索引** | 把空间划成网格，每个网格记录包含的对象 |

**Geohash 是最实用的"绕过 R 树"方案** ⭐：

```
原理：把经纬度递归二分并编码，得到一串 base32 字符串
      前缀相同的点在空间上相邻（或者说，前缀相同 → 在同一个格子内）

"wx4g0b" → 精度约 1.2km × 0.6km
"wx4g0"  → 精度约 4.9km × 4.9km

查询"附近的点"：
  ① 算出目标点的 geohash 前缀（如 6 位）
  ② 查 `WHERE geohash LIKE 'wx4g0b%'` → 能用普通 B+ 树索引 ⭐
  ③ 对结果做精确距离计算（ST_Distance_Sphere 或 Haversine）
  ④ ⚠️ 要注意"格子边界"问题：需要同时查**相邻 8 个格子** ⭐
```

**Geohash vs R 树**：

| | Geohash | R 树 |
|---|---|---|
| 索引类型 | **普通 B+ 树** ⭐ | 空间索引 |
| 实现 | 简单（应用层或生成列）| 数据库原生 |
| 边界问题 | ⚠️ 需要查 9 个格子 | 无需处理 |
| 精度调整 | 改前缀长度 | — |
| 适合 | **"附近的点"查询** ⭐ | 任意空间关系 |

## 四、空间查询函数 ⭐

```sql
-- 构造
ST_GeomFromText('POINT(116.4 39.9)', 4326)
ST_SRID(POINT(116.4, 39.9), 4326)
ST_GeomFromGeoJSON('{"type":"Point","coordinates":[116.4,39.9]}')

-- 转换
ST_AsText(geom)          -- 转 WKT 文本
ST_AsGeoJSON(geom)       -- 8.0+，转 GeoJSON ⭐ 前端友好
ST_X(point) / ST_Y(point)  -- 取坐标
ST_SRID(geom)

-- 距离与关系 ⭐
ST_Distance_Sphere(g1, g2)      -- 球面距离（米）⭐
ST_Distance(g1, g2)             -- SRID 0 时是欧氏距离；4326 时也是球面（8.0）
ST_Contains(polygon, point)     -- 包含
ST_Within(point, polygon)       -- 在内部
ST_Intersects(g1, g2)           -- 相交
ST_Equals(g1, g2)               -- 相等
ST_Touches / ST_Crosses / ST_Overlaps

-- 构造与分析
ST_Buffer(geom, 100)            -- 缓冲（半径 100）
ST_Envelope(geom)               -- 最小外包矩形（MBR）⭐
ST_ConvexHull(geom)             -- 凸包
ST_Centroid(geom)               -- 质心
ST_Area(geom)                   -- 面积
ST_Length(line)                 -- 长度
ST_MakeEnvelope(lng1, lat1, lng2, lat2)   -- 8.0，构造矩形 ⭐

-- 判断是否为 MBR 相交（粗略，可用于索引粗筛）
MBRContains(g1, g2)
MBRIntersects(g1, g2)
```

**⚠️ SRID 必须一致** ⚠️：`ST_Distance_Sphere` / `ST_Contains` 等函数要求两个几何的 SRID 相同，否则报错。

## 五、空间索引的使用限制 ⚠️

| 限制 | 说明 |
|---|---|
| **列必须 `NOT NULL`** ⭐ | 空间索引不支持 NULL 值（建索引时要求列非空）|
| **引擎限制** | **MyISAM 和 InnoDB 都支持**（InnoDB 5.7+）|
| **每表只能一个空间索引？** | 实际上可以多个，但一般只建一个 |
| **`WHERE` 必须用空间函数** | ⚠️ **只有包含 `ST_*` / `MBR*` 函数的条件才能用空间索引**；`WHERE lng BETWEEN ... AND lat BETWEEN ...` **用不了** ⭐⭐ |
| **函数参数顺序有讲究** | 索引列应该是函数的**第一个参数**才能命中索引 ⭐ |
| **多条件混合** | 空间索引 + 其他条件（如 `status=1`）→ 优化器可能只用一个 |
| **不能用于 `ORDER BY`** | 空间索引不提供排序能力 |
| **更新代价高** | 频繁更新的表慎用 ⚠️ |

**关键：用 MBR 函数让优化器用上空间索引** ⭐：

```sql
-- ❌ 用不了空间索引（BETWEEN 不受支持）
SELECT * FROM shops
WHERE lng BETWEEN 116.39 AND 116.41 AND lat BETWEEN 39.90 AND 39.92;

-- ✅ 用 MBRContains 或 ST_Within 才能用到 ⭐
SELECT * FROM shops
WHERE MBRContains(ST_MakeEnvelope(116.39, 39.90, 116.41, 39.92), loc);
-- 或（SRID 一致时）
SELECT * FROM shops
WHERE ST_Within(loc, ST_MakeEnvelope(116.39, 39.90, 116.41, 39.92, 4326));
```

**"附近的人/店"的标准写法** ⭐：

```sql
-- 用 MBR 先粗筛（走空间索引），再做精确距离计算
SELECT id, name,
       ST_Distance_Sphere(loc, ST_SRID(POINT(116.400, 39.910), 4326)) AS meters
FROM shops
WHERE MBRContains(
        ST_MakeEnvelope(
            116.400 - 0.01, 39.910 - 0.009,   -- ⚠️ 经度要按纬度做 cos 修正
            116.400 + 0.01, 39.910 + 0.009
        ), loc)
ORDER BY meters
LIMIT 10;
```

**⚠️ 经度修正** ⭐：1 度经度的实际距离随纬度变化（`111.32 km × cos(纬度)`）。在北纬 40° 附近，1 度经度约 85 km，1 度纬度约 111 km。**用固定偏移会导致搜索区域是"椭圆"而不是"圆"**。

## 六、MySQL 空间 vs PostGIS ⭐

| | **MySQL** | **PostGIS（PostgreSQL）** |
|---|---|---|
| 功能丰富度 | 基础（够用）| **极强**（行业标准）⭐ |
| 空间索引 | B+ 树 + MBR | **真正的 GiST / R 树** ⭐ |
| 函数数量 | 约 100 个 | **上千个** |
| 坐标系支持 | SRID 支持有限 | **完整 PROJ 支持** |
| 拓扑/栅格 | ❌ | ✅ |
| 性能（复杂空间查询）| 一般 | **优秀** |
| 适用 | **简单 LBS 需求**（附近的点、区域包含）⭐ | 专业 GIS |

**结论**：**"附近的 XX" 用 MySQL 足够；专业 GIS（路网、拓扑分析、轨迹）用 PostGIS**。

## 七、其他替代方案 ⭐

| 方案 | 说明 |
|---|---|
| **Redis GEO** ⭐ | 底层是 **Geohash + ZSet（sorted set）**；`GEOADD` / `GEOSEARCH` / `GEODIST` 非常简单高效 ⭐ 适合"附近的点"+ 高频读 |
| **Elasticsearch geo_point / geo_shape** ⭐ | 支持空间查询 + 与全文检索组合；底层用 **BKD 树** |
| **MongoDB 2dsphere** | 地理索引；`$near` / `$geoWithin` |
| **专业地图服务** | 高德/百度/腾讯地图的 POI 搜索 API ⭐ 免维护 |
| **PostGIS** | 专业 GIS |
| **Geohash + 普通索引** ⭐ | 最轻量的自研方案（不需要空间索引）|

**选型建议** ⭐：

```
需求：查"我附近的商铺（1km 内）"
  · 数据量小 + 查询不多 → MySQL 空间索引（或 Geohash + B+ 树）⭐
  · 高频查询 + 已用 Redis → Redis GEO ⭐
  · 需要与关键词搜索组合（"附近的火锅店"）→ Elasticsearch ⭐
```

## 八、一句话总结

**空间索引（R 树）的核心是"最小外包矩形（MBR）分层剪枝 + 过滤/精炼两阶段"**，它解决的是"B+ 树只能索引一维"的根本限制；**MySQL 的"附近的点"查询必须用 `MBRContains`/`ST_Within` 这类空间函数才能命中索引（`BETWEEN` 用不了）⭐**，且必须**明确 SRID 4326** 才能得到正确的球面距离；**轻量替代是 Geohash + 普通 B+ 树索引（注意边界要查 9 个格子）或 Redis GEO**；专业 GIS 场景应该用 PostGIS。""",
    ),
    (
        "MySQL",
        "ORM,误区,实践",
        2,
        r"""ORM 有哪些常见误区？手写 SQL 和 ORM 该怎么选？""",
        r"""## 一、ORM 的价值与代价 ⭐

**价值**：

| 价值 | 说明 |
|---|---|
| **开发效率** | 不用手写 CRUD |
| **防注入（通常）** | 参数绑定 ⭐ |
| **可移植性** | 换数据库只改方言（但现实中很少真的换）|
| **关联管理** | 级联、懒加载 |
| **类型安全**（现代 ORM）| 编译期检查 |

**代价** ⚠️：

| 代价 | 说明 |
|---|---|
| **"看不见的 SQL"** ⭐⭐ | 最难排查的性能问题都藏在这里（N+1、隐式全表扫描）|
| **生成的 SQL 可能很蠢** | 复杂查询时 ORM 生成的 SQL 往往不如手写 ⭐ |
| **学习成本** | 每个 ORM 都有自己的"魔法" |
| **优化困难** | 想加个 hint / 改写 SQL 要绕过 ORM |
| **`SELECT *` 倾向** | 默认拉全部列（包括 TEXT/BLOB）⚠️ |

## 二、七大常见误区 ⭐⭐

### ① N+1 查询（最经典、最致命）⭐⭐

```python
# ❌ N+1：1 次查列表 + N 次查关联
posts = Post.objects.all()              # 1 次
for p in posts:
    print(p.author.name)                # 每篇一次 → N 次
# 100 篇文章 = 101 次查询 ⚠️

# ✅ 解法：预加载（JOIN / IN 批量查）
posts = Post.objects.select_related('author').all()   # 1 次（JOIN）
posts = Post.objects.prefetch_related('tags').all()   # 2 次（列表 + IN）
```

**为什么致命**：**每次查询都是一个网络往返**（即使只查 1 行，也要 RTT + 解析 + 优化）。100 次查询 = 100 个 RTT，即使每次 1ms 也是 100ms，而一次 JOIN 只要 2ms ⭐

**怎么发现** ⭐：**用慢日志/`sys` 表看"同一个 SQL 模板的执行次数"** —— `sys.statement_analysis` 里 `exec_count` 异常高的 `SELECT ... WHERE id = ?` 就是 N+1 的信号。

### ② 懒加载陷阱 ⭐

```python
# 序列化时触发懒加载（在"渲染/JSON 化"时才发 SQL）
class PostSerializer:
    author_name = serializers.CharField(source='author.name')   # 懒加载 ⚠️
# 在循环外看不出来，序列化时才爆发 N+1
```

**对策**：**在查询层显式预加载**；开启"检测懒加载"的开发模式（如 Rails 的 `bullet`、Django 的 `nplusone`）。

### ③ 隐式类型转换 / 隐式 JOIN ⚠️

```python
# ORM 可能生成你意想不到的 SQL
Post.objects.filter(author__name='x')     # 生成 JOIN，可能没走索引
Post.objects.filter(id__in=ids)            # 大 IN 列表 → SQL 极长 ⚠️
Post.objects.filter(created_at__date=today)  # 生成 DATE(col)=... → 索引失效 ⚠️
```

**对策**：**开 SQL 日志，审查生成的 SQL** ⭐（几乎所有 ORM 都支持打印 SQL）。

### ④ 默认 `SELECT *` 带出大字段 ⚠️

```python
Post.objects.all()    # 把 content（MEDIUMTEXT）也拉出来了
```

**对策**：**用 `.only()` / `.values()` / 投影指定列** ⭐ 列表页只取需要的列。

### ⑤ 在循环里逐条写（批量操作没批量）

```python
# ❌ N 条 INSERT
for p in posts: p.save()

# ✅ 批量插入 ⭐
Post.objects.bulk_create(posts, batch_size=500)
```

**对策**：用 ORM 的 bulk 接口；或直接用驱动/`LOAD DATA`。

### ⑥ 在事务里做非数据库操作 ⚠️

```python
with transaction.atomic():
    order.save()
    requests.post('https://payment.example.com/pay')   # ⚠️ 网络调用，可能超时 30s
    order.status = 'paid'
```

**后果**：**事务持有锁 30 秒** → 其他写被阻塞 → 可能雪崩 ⭐（见"大事务"题）

**对策**：**事务里绝不放 RPC / 文件 IO / 长循环**；拆成"先写状态 → 事务外调用 → 再写结果"。

### ⑦ 忽略 ORM 的"隐式提交"

很多 ORM 的 `save()` 会**自动提交**（autocommit），导致你以为在一个事务里其实是多条独立事务 ⚠️

**对策**：**显式声明事务边界**（`transaction.atomic()` / `@Transactional`），并确认 ORM 的事务模型。

## 三、其他容易踩的点 ⭐

| 坑 | 说明 |
|---|---|
| **迁移（Migration）工具生成的 DDL 很差** ⚠️ | 常生成"COPY 算法"的 DDL（重建表）→ 必须人工审查并改用 `ALGORITHM=INPLACE` 或 pt-osc ⭐ |
| **迁移文件与真实表结构漂移** | 手工改过库 → migration 与实际不一致 ⚠️ 用 `makemigrations --check` 检测 |
| **`save()` 全量更新** | ORM 往往 `UPDATE` 所有列（即使只改了一个字段）→ 增大 binlog 与锁范围 ⭐ |
| **`NULL` 与空串混用** | 不同 ORM 对 `null`/`blank` 的处理不同 ⚠️ |
| **时区处理** | ORM 的时区配置与 MySQL 的 `time_zone` 不一致 → 差 8 小时 ⭐ |
| **字符集未指定** | 连接字符集不对 → 乱码（本项目踩过）⭐ |
| **连接池配置** | ORM 自带池的 `maxLifetime` 与 `wait_timeout` 不匹配 → 死连接 ⭐ |
| **软删除与唯一索引冲突** | 软删除后无法插入同唯一值 ⭐ |
| **`count()` 很慢** | ORM 的 `count()` 生成 `SELECT COUNT(*)` → 大表慢 ⭐ |
| **`exists()` vs `count()`** | 判断存在性用 `exists()`（`LIMIT 1`）而不是 `count()` ⭐ |
| **分页用 `OFFSET`** | 深分页慢；ORM 通常只支持 offset ⭐ |
| **`save()` 的竞态** | "读-改-写"应改成原子 SQL（`UPDATE ... SET n = n + 1`）⭐ |

## 四、手写 SQL vs ORM 的选型 ⭐

| 场景 | 推荐 |
|---|---|
| **简单 CRUD** | **ORM** ⭐（效率高）|
| **复杂分析查询**（多表 JOIN + 聚合 + 窗口函数）| **手写 SQL** ⭐ |
| **批量操作** | 手写 SQL / `LOAD DATA` ⭐ |
| **报表/统计** | 手写 SQL（或专门的分析库）⭐ |
| **需要 hint / 强制索引** | 手写 SQL ⭐ |
| **性能关键路径** | 手写 SQL + 审查执行计划 ⭐ |
| **数据迁移/一次性脚本** | 手写 SQL / 脚本 |
| **管理后台的通用查询** | ORM（开发效率优先）|

**最佳实践：ORM 为主 + 关键路径手写 SQL（ORM 都支持"原生 SQL 转义"）** ⭐

```
Django: Post.objects.raw('...')  / cursor.execute
Rails:  Post.find_by_sql('...')  / ActiveRecord::Base.connection.execute
TypeORM: query() / createQueryBuilder
MyBatis: XML 里的 SQL（本质是手写 SQL + 参数绑定）⭐

→ 注意：手写 SQL 时**必须用参数绑定**，不要字符串拼接 ⭐
```

## 五、C++ 场景的对应讨论 ⭐（本项目）

**C++ 的 ORM 生态相对较弱**（没有 Django/Rails 那种成熟的"全栈 ORM"）：

| 库 | 类型 | 特点 |
|---|---|---|
| **原始 MySQL C API** | 驱动 | 最底层，最灵活，需手写 SQL + 参数绑定 ⭐（本项目用的就是这个）|
| **mysql-connector-c++** | 驱动 | C++ 接口，支持 `PreparedStatement` ⭐ |
| **sqlpp11** | 类型安全查询构建器 | 编译期检查列名/类型 ⭐ |
| **SOCI** | 通用数据库抽象 | 支持多后端 |
| **ODB** | 真正的 C++ ORM | 需要代码生成（编译器插件），学习成本高 |
| **sqlite_orm / sqlpp11** | 轻量 ORM | 模板元编程，编译慢 |

**本项目的合理选择** ⭐：

```
✔ 直接用 C API（当前方案）+ 手写 SQL + 参数绑定
  · 性能最好、可控性最强
  · 适合少量、明确的查询（博客的 CRUD 不复杂）

✔ 关键纪律：
  ① 所有用户输入走 mysql_real_escape_string 或 mysql_stmt_* 预处理 ⭐
  ② 表名/列名/排序方向用白名单（无法参数化）⭐
  ③ MYSQL_RES 必须 free（RAII 包装）⭐
  ④ 连接字符集显式 SET NAMES utf8mb4 ⭐
  ⑤ 每线程独立连接（Crow 多线程）⭐
  ⑥ 事务用 RAII 守卫保证提交/回滚 ⭐
```

**"ORM 化的思想"可以借鉴**：

```
✔ 把"表 → 结构体"的映射集中在少数函数里（`rowToPost(MYSQL_ROW)`）
✔ 把 SQL 集中在少数文件/区域（不要散落在业务逻辑里）
✔ 提供参数化的查询构建小工具（如 `selectPostsByStatus(int status)`）
✔ 用统一的错误处理（错误码 → 业务异常）
```

## 六、无论用不用 ORM 都必须做的三件事 ⭐⭐

```
① 打印/审查生成的 SQL ⭐
   · ORM 必开 SQL 日志（至少开发环境）
   · 上线前对关键查询跑 EXPLAIN

② 保证参数绑定（防注入）⭐
   · ORM 通常自动做
   · 手写 SQL 必须显式用参数/转义
   · 表名/列名/排序方向用白名单

③ 监控 SQL 的执行次数与耗时 ⭐
   · 用 sys.statement_analysis / 慢日志
   · 找 exec_count 异常高的 SQL → N+1
   · 找 avg_latency 高的 SQL → 慢查询
```

## 七、一句话总结

**ORM 的误区集中在"N+1 查询"和"看不见的 SQL"**；**手写 SQL 与 ORM 不是二选一，而是"ORM 做常规 CRUD + 手写 SQL 做复杂/性能关键查询"**；**无论用哪个，都必须保证"参数绑定防注入 + 审查生成的 SQL + 监控执行次数"这三件事**；**C++ 场景（如本项目）用 C API + 手写 SQL + 预处理是合理选择，但必须用 RAII 管资源、白名单管标识符、显式设字符集**。""",
    ),
    (
        "MySQL",
        "undo,purge,版本链治理",
        3,
        r"""undo log 膨胀（History list length 很大）是怎么回事？怎么治理？""",
        r"""## 一、undo log 的作用回顾 ⭐

| 作用 | 说明 |
|---|---|
| **事务回滚** | 记录旧值，回滚时反向应用 |
| **MVCC** | 提供历史版本，供快照读沿 `DB_ROLL_PTR` 遍历版本链 |

**undo 的存在周期**：
- 事务**提交前**：必须存在（回滚需要）
- 事务**提交后**：**只要还有 Read View 需要看到更老的版本，就必须保留** ⭐
- **无人需要时**：由 **purge 线程**回收

## 二、`History list length` 是什么 ⭐⭐

```sql
SHOW ENGINE INNODB STATUS\G
-- TRANSACTIONS 段
-- History list length 12345
```

**语义**：**"已提交但尚未被 purge 的 undo 记录数"**（准确说是 undo 页/记录的积压量）。

**它为什么重要** ⭐：**这是"系统健康度"的廉价指标** —— 正常情况下应该保持在很小的值（几百到几千）。

| 数值 | 状态 |
|---|---|
| **< 1000** | 健康 ✅ |
| **1000 ~ 10000** | 正常偏大，关注 |
| **10000 ~ 100000** | ⚠️ 警告：有长事务或 purge 跟不上 |
| **> 100000** | 🔴 危险：查询会系统性变慢，未提交事务或长事务严重 |

## 三、膨胀的根因 ⭐⭐

### ① 长事务（头号原因）⭐⭐

```
只要有一个事务开了很久还没提交：
  · 它的 Read View 会"钉住"一个很老的时间点
  · purge 线程判断"还有 Read View 需要这个版本" → 不敢删 ⭐
  · 于是从该事务开始之后的所有 undo 都必须保留 ⚠️
```

**关键机制**：`purge` 只能回收到**最老活跃 Read View 所需位置**为止（这部分叫 **`purge boundary`**）。一个长事务就能让边界冻住不动。

**长事务的常见来源** ⭐：

| 来源 | 说明 |
|---|---|
| **显式 `BEGIN` 后忘了 `COMMIT`/`ROLLBACK`** | 应用 bug（异常路径没回滚）⭐ |
| **事务里做了慢操作** | RPC 调用、文件 IO、等待用户输入、长循环 |
| **`SELECT ... FOR UPDATE` 后长时间不提交** | 拿锁后做业务计算 |
| **ORM 的隐式长事务** | `@Transactional` 包了一个很慢的方法 |
| **从库的大事务重放** | 从库 SQL 线程持有一个大事务 |
| **备份工具** | `mysqldump --single-transaction` 在备份期间**持有一个长事务** ⭐（大库备份几小时 → undo 积压几小时）|
| **`autocommit=0`** | 忘记设置，导致所有语句都在一个隐式事务里 ⭐ |

### ② purge 线程跟不上 ⭐

```
undo 产生速度 > purge 回收速度
原因：
  · innodb_purge_threads 太少（默认 4）
  · purge 是"单线程遍历 undo 段"的部分存在瓶颈
  · 磁盘 IO 慢（purge 需要读 undo 页）
  · 大量 UPDATE/DELETE 产生海量 undo
```

### ③ 大事务制造海量 undo

```sql
UPDATE big_table SET col = 1 WHERE ...;   -- 影响 500 万行 → 500 万条 undo
```

### ④ 长查询（一致性读）

一个跑了 10 分钟的 `SELECT`（大报表查询）也持有 Read View → **同样会阻塞 purge** ⭐（这一点常被忽略！不只是"写事务"，**长查询**也会）

## 四、膨胀的连锁危害 ⭐⭐

```
History list length 大
        ↓
① 每次快照读要沿版本链遍历更多版本 → 单个查询变慢 ⭐
② 需要读取更多 undo 页 → 物理读增加 → IO 压力大
③ undo 表空间（undo_001/undo_002）持续增长 → 磁盘占满 ⚠️
④ 系统表空间（ibdata1）也可能增长（历史原因）
⑤ 极端情况下 purge 崩溃 → 实例直接不可用 🔴
```

**"查询系统性变慢"是它最隐蔽的表现** ⭐ —— 不是某条 SQL 慢，而是**所有查询都慢了**（因为每条都要遍历更长的版本链）。这种"全局变慢"很难归因，所以**必须监控 `History list length`**。

## 五、排查流程 ⭐⭐

```sql
-- ① 看当前积压
SHOW ENGINE INNODB STATUS\G   -- TRANSACTIONS 段的 History list length

-- ② 找出所有活跃事务（按开始时间排序）⭐
SELECT trx_id,
       trx_started,
       TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS age_sec,
       trx_state,                    -- RUNNING / LOCK WAIT / COMMITTING
       trx_mysql_thread_id,          -- ⭐ 用这个 KILL
       trx_isolation_level,
       trx_rows_modified,            -- 已修改行数 ⭐
       trx_rows_locked,
       trx_tables_locked,
       LEFT(trx_query, 200) AS query
FROM information_schema.innodb_trx
ORDER BY trx_started;                -- ⭐ 最老的排最前

-- ③ 找出长查询（SELECT 也会阻塞 purge）⭐
SELECT id, user, host, db, command, time, state, LEFT(info,200) sql
FROM information_schema.processlist
WHERE command <> 'Sleep' AND time > 60
ORDER BY time DESC;

-- ④ 看 undo 表空间占用 ⭐
SELECT name, file_size, allocated_size, state
FROM information_schema.innodb_tablespaces
WHERE name LIKE '%undo%';
-- 或
ls -lh /var/lib/mysql/undo_*

-- ⑤ 看 purge 线程状态
SHOW GLOBAL STATUS LIKE 'Innodb_purge%';
-- Innodb_purge_rseg_truncate_frequency
-- Innodb_purge_mark_delete / rseg_truncate ...
SELECT * FROM information_schema.innodb_metrics
WHERE name LIKE 'purge%';

-- ⑥ 看是否有人在跑备份（mysqldump --single-transaction 是长事务）⭐
SELECT id, user, host, db, command, time, LEFT(info,100)
FROM information_schema.processlist
WHERE info LIKE '%SELECT%' AND info NOT LIKE '%information_schema%'
ORDER BY time DESC;
```

**定位长事务的"根阻塞者"** ⭐：

```sql
-- 找到最老的活跃事务 —— 它就是 purge 的边界 ⭐
SELECT trx_id, trx_started, trx_mysql_thread_id, trx_rows_modified, trx_query
FROM information_schema.innodb_trx
ORDER BY trx_started ASC LIMIT 1;
-- KILL 它，purge 就能往前推进
```

## 六、治理方案 ⭐⭐

### 立即止血

```sql
-- ① KILL 长事务（⚠️ 大事务 KILL 后还要回滚很久，锁依然持有）
KILL <trx_mysql_thread_id>;

-- ② KILL 长查询（大报表 SELECT）
KILL <id>;

-- ③ 确认 purge 推进（观察 History list length 是否下降）
SHOW ENGINE INNODB STATUS\G
```

### 参数治理 ⭐

```ini
[mysqld]
# ① purge 并发（8 核以上建议 4~8）
innodb_purge_threads = 4                     # 默认 4，可调到 8

# ② 允许自动截断 undo 表空间 ⭐
innodb_undo_log_truncate = ON                # 默认 ON（8.0）
innodb_max_undo_log_size = 1073741824        # 1GB，超过则截断
innodb_undo_tablespaces = 2                  # 至少 2 个（截断需要轮换）⚠️ 只能初始化时设
innodb_purge_rseg_truncate_frequency = 128   # 截断频率（越小越频繁）

# ③ 撤销日志相关的历史参数
innodb_undo_directory = /var/lib/mysql/      # undo 文件位置（可放独立盘）
```

**⚠️ `innodb_undo_tablespaces` 只能在初始化时设置**（8.0 起由 `innodb_undo_tablespaces` 与 `innodb_undo_log_truncate` 共同控制；某些版本的变更需重建实例）。

**undo 表空间截断的条件**（必须全部满足）：

```
① innodb_undo_log_truncate = ON
② undo 表空间大小 > innodb_max_undo_log_size
③ 至少有 2 个 undo 表空间（截断需要"轮换"：截断当前未使用的那个）
④ purge 线程能空闲出来处理截断
```

### 应用层治理（根本）⭐⭐

| 措施 | 说明 |
|---|---|
| **事务要短** | 事务里绝不放 RPC / 文件 IO / 长循环 ⭐ |
| **RAII 保证提交/回滚** ⭐ | C++ 用析构函数；Java 用 `try-with-resources`；防"忘了提交" |
| **`autocommit=1`** | 避免隐式长事务 ⭐ |
| **批量操作分批** | 大 `UPDATE`/`DELETE` 改成 `LIMIT` 循环 ⭐ |
| **加事务超时** | 应用层计时器，超时强制回滚 ⭐ |
| **ORM 事务边界审查** | 检查 `@Transactional` 方法里有没有外部调用 |
| **大报表查询走从库/离线库** | 避免长查询阻塞 purge ⭐ |
| **备份策略调整** | `mysqldump --single-transaction` 备份大库会长时间持有 Read View ⭐ → 改用 **XtraBackup（物理备份，几乎不影响 purge）** 或 Clone Plugin ⭐ |

**⚠️ 备份工具的隐藏影响** ⭐：大库用 `mysqldump --single-transaction` 备份时**会持有一个长事务**，导致备份期间 undo 无法回收。**这是很常见的"莫名的 History list length 高"的原因**。改用 XtraBackup 就解决了。

## 七、监控与告警 ⭐

```sql
-- 定期采集（脚本 + Prometheus mysqld_exporter）
-- ① History list length（从 SHOW ENGINE INNODB STATUS 解析，或用 innodb_metrics）
SELECT COUNT AS history_list_length
FROM information_schema.innodb_metrics
WHERE NAME = 'trx_rseg_history_len';       -- ⭐ 8.0 有专门指标！

-- ② 最长老事务时长（自研 SQL 采集）
SELECT MAX(TIMESTAMPDIFF(SECOND, trx_started, NOW())) AS max_trx_age_sec
FROM information_schema.innodb_trx;

-- ③ 最长查询时长
SELECT MAX(time) AS max_query_sec FROM information_schema.processlist
WHERE command <> 'Sleep';
```

**告警阈值建议** ⭐：

| 指标 | Warning | Critical |
|---|---|---|
| `trx_rseg_history_len` | > 10000 | > 100000 ⭐ |
| 最长活跃事务 | > 60s | > 600s ⭐ |
| 最长非 Sleep 查询 | > 300s | > 1800s |
| undo 表空间总大小 | > 10GB | > 50GB |
| `Innodb_purge_*` 是否有积压 | — | — |

## 八、一个典型事故复盘 ⭐

```
现象：
  · 网站"整体变慢"，所有接口 P99 从 20ms 涨到 800ms ⭐（不是某一条 SQL 慢！）
  · 磁盘告警：io 使用率高，undo_001 涨到 30GB ⚠️

排查：
  ① SHOW ENGINE INNODB STATUS → History list length 1280000 🔴
  ② information_schema.innodb_trx → 发现一个 RUNNING 状态、已持续 4.5 小时的
     事务（trx_rows_modified = 320000000）⭐
  ③ 查该连接的 processlist → 是运维的 mysqldump 备份任务（--single-transaction）⚠️

根因：
  备份任务持有一个长 Read View → purge 边界冻住 4.5 小时
  → 期间所有 CONMT/DELETE/UPDATE 的 undo 都无法回收
  → 版本链暴长 → 所有快照读变慢 → 全局变慢

处置：
  ① KILL 备份连接（改到维护窗口重跑）
  ② History list length 在几分钟内从 128 万降到几千 ✅
  ③ 接口 P99 恢复到 20ms ✅

防复发：
  ① 备份改用 XtraBackup（物理备份，不做长事务）⭐
  ② 监控 History list length + 最长老事务，加告警 ⭐
  ③ 备份任务限制运行时长 / 加限速
  ④ 备份时间挪到绝对低峰
```

**这个案例的核心教训** ⭐：**"全局变慢"往往是 undo 膨胀的信号，而 undo 膨胀的根因常常是"长查询/长事务"而不是"慢 SQL"** —— 排查方向完全不同。

## 九、一句话总结

**`History list length` = "已提交但未 purge 的 undo 数"，它是系统健康度的廉价指标**；**膨胀的根因是"长事务或长查询冻结了 purge 边界"（注意 `mysqldump --single-transaction` 也是一个长事务 ⭐）**；**危害是"全局性查询变慢"（不是单条 SQL 慢）+ undo 表空间撑爆**；**治理靠"KILL 长事务/长查询 + 应用层保证事务短小（RAII）+ 分批操作 + 换 XtraBackup 备份 + 监控 `trx_rseg_history_len` 告警"**。""",
    ),
    (
        "MySQL",
        "面试题,大表,方案设计",
        3,
        r"""线上有一张 5000 万行的订单表，查询越来越慢，请给出一套完整的优化方案。""",
        r"""## 一、先问清楚的四个问题 ⭐

**面试时一定要先澄清需求和约束，不要直接给方案**：

```
① 慢在哪？        某几个接口慢，还是整体慢？P50/P95/P99 各是多少？
② 什么查询模式？  按用户查？按时间查？按状态查？统计类查询？
③ 写入量？        每天新增多少行？是否有更新/删除？
④ 约束条件？      能否停机？能否改表结构？能否加机器？能否改应用？
```

**这些问题的答案会导向完全不同的方案** ⭐

## 二、第一步：采集证据（不猜）⭐

```sql
-- ① 慢 SQL 分布（按模板聚合）⭐
SELECT query, exec_count, total_latency, avg_latency,
       rows_examined_avg, rows_sent_avg, tmp_tables, full_scans
FROM sys.statement_analysis ORDER BY total_latency DESC LIMIT 20;

-- ② 全表扫描的 SQL
SELECT * FROM sys.statements_with_full_table_scans ORDER BY total_latency DESC LIMIT 10;

-- ③ 表规模与索引
SELECT table_name, table_rows,
       ROUND(data_length/1024/1024/1024, 2) AS data_gb,
       ROUND(index_length/1024/1024/1024, 2) AS idx_gb,
       ROUND(data_free/1024/1024/1024, 2) AS free_gb
FROM information_schema.tables WHERE table_name='orders';

SHOW INDEX FROM orders;

-- ④ 索引使用情况（有没有白建的索引）⭐
SELECT * FROM sys.schema_unused_indexes WHERE object_name='orders';
SELECT * FROM sys.schema_redundant_indexes WHERE table_name='orders';

-- ⑤ Buffer Pool 是否够（5000 万行能不能全装进内存）⭐
SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read%';
-- 计算命中率 = 1 - reads/read_requests
SHOW ENGINE INNODB STATUS\G   -- LOOK: Buffer pool hit rate、History list length

-- ⑥ 系统层
-- top / vmstat 1 / iostat -xz 1
```

**5000 万行的关键估算** ⭐：

```
假设每行 500 字节 → 数据约 25GB，加索引可能 40~60GB
若 Buffer Pool 只有 8GB → 命中率必然低 → 大量物理随机读 ❌
→ 这是"表大了就慢"的物理根源：索引树变深 + 缓存装不下
```

## 三、第二步：按代价从低到高执行 ⭐⭐

### 层 1：索引优化（成本最低，收益最大）⭐⭐

```sql
-- 先搞清查询模式，再设计索引
-- 假设主要查询是：
--   A) WHERE user_id=? AND status=? ORDER BY created_at DESC LIMIT 20
--   B) WHERE status=? AND created_at BETWEEN ? AND ?
--   C) WHERE order_no=?                            -- 唯一

-- 设计：
CREATE INDEX idx_user_status_created ON orders (user_id, status, created_at);
--                                            等值     等值       排序
CREATE INDEX idx_status_created ON orders (status, created_at);
--                              （若 A 已覆盖前缀，B 可能需要单独索引）
-- order_no 已是唯一索引 ✅

-- 覆盖索引（消灭回表）⭐
CREATE INDEX idx_user_status_created_cover
  ON orders (user_id, status, created_at, order_no, amount, created_at);
--                                                     ↑ 覆盖列（仅取值）

-- EXPLAIN 验证：
--   期望 type=range/ref, key=idx_..., Extra: Using index（无 Using filesort）✅
EXPLAIN ANALYZE SELECT order_no, amount FROM orders
WHERE user_id=1 AND status=1 ORDER BY created_at DESC LIMIT 20;
```

**这一步通常能解决 70% 的问题** ⭐。注意：

| 要点 | 说明 |
|---|---|
| **大表加索引要用 INPLACE/在线工具** ⭐ | `ALTER TABLE ... ADD INDEX ..., ALGORITHM=INPLACE, LOCK=NONE`（8.0 加二级索引支持）|
| **加完 `ANALYZE TABLE`** | 更新统计信息 ⭐ |
| **删无用索引** | 减少写放大（用 `INVISIBLE` 观察后再删）⭐ |
| **控制索引数量** | 单表 5~6 个以内 |

### 层 2：SQL 改写（零风险，见效快）⭐

```sql
-- ① 深分页 → 键集分页 ⭐
❌ SELECT * FROM orders ORDER BY id LIMIT 1000000, 20
✅ SELECT * FROM orders WHERE id > 1000000 ORDER BY id LIMIT 20

-- ② 深分页（保留 offset）→ 延迟关联
✅ SELECT o.* FROM orders o
   JOIN (SELECT id FROM orders WHERE ... ORDER BY id LIMIT 1000000, 20) t ON o.id=t.id

-- ③ 函数包裹索引列 → 范围
❌ WHERE DATE(created_at)='2024-05-01'
✅ WHERE created_at >= '2024-05-01' AND created_at < '2024-05-02'

-- ④ 大 IN 列表 → 拆分 / 临时表 / JOIN
❌ WHERE id IN (5000 个 id)
✅ 分批（每批 500）+ 或 JOIN 临时表

-- ⑤ COUNT(*) 优化 → 走最小二级索引 / 汇总表 ⭐
-- 或产品层面去掉"总数"

-- ⑥ 列表页不读大字段 ⭐
❌ SELECT * FROM orders ...          （带出 remark TEXT 等）
✅ SELECT id, order_no, amount, status, created_at ...

-- ⑦ OR → UNION ALL
-- ⑧ 子查询 → JOIN（或用 EXISTS）
-- ⑨ 避免 SELECT * 
```

### 层 3：架构层面（成本高，效果大）⭐⭐

#### 3.1 冷热分离 ⭐⭐（对订单表最有效）

```
观察：99% 的查询落在"最近 3 个月"
→ 把 3 个月前的订单归档

方案 A：分区表（新表设计）⭐
   RANGE COLUMNS(created_at) 按月分区
   → 老数据 DROP PARTITION（秒级）
   ⚠️ 但"改造已存在的 5000 万行表为分区表"需要重建表

方案 B：冷热分表 + 应用层路由 ⭐
   orders（最近 3 个月，约 500 万行）  ← 热
   orders_archive（历史，4500 万行）  ← 冷
   查询路由：按时间范围决定查哪张表
   ⚠️ 需要改应用代码

方案 C：归档到独立实例 ⭐
   历史数据搬到低配只读实例
   查询历史走那个实例（或走数仓）
```

**冷热分离的效果估算** ⭐：

```
5000 万行 → 500 万行热表（缩小 10 倍）
· B+ 树从 4 层降到 3 层 → IO 次数减少
· 缓存命中率大幅提升（500 万行可能全装进内存）⭐
· 索引也缩小 10 倍
```

#### 3.2 读写分离

```
主库写 + 从库读（订单查询走从库）
⚠️ 必须解决"下单后立刻查订单查不到" → 写后读主 ⭐
```

#### 3.3 加缓存（Redis）

```
缓存"订单详情"、"订单列表第一页"
⚠️ 订单状态会变 → 更新时要删缓存（先更新 DB 再删缓存 + TTL 兜底）⭐
```

#### 3.4 汇总表（统计类查询）⭐

```sql
-- 日报/月报统计不要实时算
CREATE TABLE order_daily_stats (
    dt DATE PRIMARY KEY,
    order_count INT, total_amount DECIMAL(18,2), ...
);
-- 定时任务（每天凌晨）汇总
-- 或用 binlog 订阅实时增量更新
```

#### 3.5 垂直拆分

```
orders（主表，精简）      ← 高频字段
order_ext（扩展表，1:1）  ← 备注、大字段、JSON
→ 主表变小 → 一页放更多行 → 查询更快 ⭐
```

#### 3.6 分库分表（最后手段）⭐

```
前提：单表 > 2000 万行 且 已做完上述所有优化 且 单机已到极限
分片键：user_id（因为"按用户查订单"是最高频查询）⭐
预分片：一次性分 1024 个逻辑片
分裂问题：
  · 后台按 order_no 查 → 需要【异构索引表】(order_no → user_id) ⭐
  · 跨片统计 → 走汇总表 / 数仓
  · 全局唯一 ID → 雪花算法
  · 分布式事务 → 尽量避免
工具：ShardingSphere / 或直接用 TiDB（免改造）⭐
```

### 层 4：硬件与参数 ⭐

```
① 加大 innodb_buffer_pool_size（最直接的性能提升）⭐
   若内存有限：优先保证 Buffer Pool，减少连接数与每连接 buffer
② 换 SSD（随机读 IOPS 提升几倍到几十倍）
③ innodb_buffer_pool_instances（按 buffer pool 大小 / 1G，减少 latch 竞争）
④ innodb_io_capacity 匹配磁盘
⑤ innodb_flush_method = O_DIRECT
⑥ SSD 上 innodb_flush_neighbors = 0
⑦ 考虑 innodb_page_size = 8K（大行、SSD 场景）
⑧ 归档 + OPTIMIZE TABLE 消除碎片（⚠️ 需要额外磁盘）
```

## 四、推荐的执行顺序（路线图）⭐

```
【第 1 周】证据采集 + 索引优化
  · 用 sys.statement_analysis 找出 TOP 慢 SQL
  · 设计/补索引（INPLACE 在线加）
  · 删无用索引（先 INVISIBLE 观察）
  · ANALYZE TABLE
  · 预期收益：70% 的问题解决 ⭐

【第 2 周】SQL 改写 + 应用层改造
  · 深分页改键集分页
  · 列表页去掉大字段（用冗余摘要列）
  · 统计类查询改汇总表
  · 预期收益：再解决 15%

【第 3~4 周】冷热分离 + 缓存
  · 归档 3 个月前的数据（分批、幂等、可续跑）⭐
  · 关键查询上缓存（延迟双删 + TTL）⭐
  · 预期收益：再解决 10%

【第 2~3 月】架构级（按需）
  · 读写分离（延迟感知）
  · 垂直拆分（大字段分离）
  · 加大 buffer pool / 换 SSD
  · 预期收益：最后的 5%

【长期】分库分表（仅在前述都不够时）
  · 或者迁移到 TiDB（应用无改造）⭐
```

**关键**：**每做一步都要压测/灰度验证，量化收益**（P99 从多少降到多少）⭐

## 五、必须同时做的三件事 ⭐

### ① 备份与可恢复性

```
5000 万行的表必须有：
  ✔ 定时全量备份（XtraBackup 物理备份 ⭐ 比 mysqldump 快得多）
  ✔ binlog 保留（PITR 用）
  ✔ 定期恢复演练（否则备份等于没有）⭐
  ⚠️ 用 mysqldump --single-transaction 备份大表会长时间持有 Read View
     → 导致 undo 膨胀、全局变慢 ⭐ 必须换 XtraBackup
```

### ② 监控与告警

```
必盯：
  · Buffer Pool 命中率（< 99% 告警）⭐
  · 慢查询数（突增告警）
  · 最长活跃事务 + History list length（长事务告警）⭐
  · 主从延迟
  · 磁盘水位（< 30% 告警）⭐
  · QPS/TPS 与 P99
```

### ③ 防复发

```
  · 新 SQL 上线必须过 EXPLAIN 评审 ⭐
  · 禁止无 LIMIT 的大表查询（框架层强制分页上限）
  · 禁止 SELECT * （lint 规则）
  · 定期索引体检（每季度）
  · 大表查询统一走"按用户/按时间"的路由层 ⭐
```

## 六、面试答题的结构化模板 ⭐

```
① 先澄清需求（4 个问题）—— 显得专业，避免答偏 ⭐
② 采集证据（不猜）：慢日志、sys 表、EXPLAIN ANALYZE
③ 分层给方案，按代价排序：
   索引 → SQL → 架构（冷热分离/缓存/读写分离/汇总表/垂直拆）→ 硬件参数 → 分片
④ 给出量化预期（"冷热分离后热表缩小 10 倍，命中率从 94% 提到 99.8%"）
⑤ 说明风险与回滚（在线 DDL 用 INPLACE，删索引先 INVISIBLE）
⑥ 补充"必须同时做的"（备份、监控、防复发）
⑦ 最后说明"什么情况下才考虑分库分表" —— 体现不滥用
```

## 七、一句话总结本题

**5000 万行变慢的物理根源是"B+ 树变高 + 缓存装不下"**；**解决顺序必须是"先索引（解决 70%）→ 再 SQL 改写 → 再冷热分离/缓存（对订单表最有效）→ 最后才考虑读写分离和分库分表"**；**对订单表而言，"按时间冷热分离"通常是收益最大的单步操作**（热表缩小 10 倍，缓存能全装下）；**同时必须补上 XtraBackup 备份、`History list length` 等监控、以及 SQL 上线 EXPLAIN 评审来防复发**。""",
    ),
    (
        "MySQL",
        "内存,配置,资源管理",
        2,
        r"""MySQL 的内存都花在哪了？为什么连接数一多内存就爆？怎么规划内存分配？""",
        r"""## 一、内存的两大类 ⭐⭐

```
MySQL 内存 = 【全局共享内存】 + 【每连接私有内存】
                ↑                    ↑
          与连接数无关            ⚠️ 与连接数成正比
```

**这是"连接数一多内存就爆"的根本原因** ⭐

## 二、全局共享内存 ⭐

| 组件 | 说明 | 参数 |
|---|---|---|
| **InnoDB Buffer Pool** ⭐⭐ | 缓存数据页/索引页，**占大头** | `innodb_buffer_pool_size`（通常 50%~80%）|
| **InnoDB Log Buffer** | 缓存 redo log | `innodb_log_buffer_size`（默认 16M）|
| **InnoDB 额外缓冲** | AHI、锁信息、数据字典 | `innodb_additional_mem_pool_size`（已废弃，8.0 自动）|
| **Tmp Table（内存临时表）** | 全局上限 | `max_heap_table_size`（每个临时表的上限）|
| **Table Cache** | 打开表的缓存 | `table_open_cache` ⭐ |
| **Thread Cache** | 复用线程 | `thread_cache_size` |
| **Key Buffer** | MyISAM 索引缓存 | `key_buffer_size`（InnoDB 表用不到）|
| **Binary Log Cache** | 每个会话有，但会话间复用 | `binlog_cache_size`（**每会话**，算在半私有里）|
| **Query Cache** | 5.7 之前 | `query_cache_size`（8.0 已移除）|

## 三、每连接私有内存 ⭐⭐（关键）

**每个连接都会分配**：

| 缓冲 | 参数 | 默认 | 说明 |
|---|---|---|---|
| **`sort_buffer_size`** ⭐ | 排序缓冲 | **256KB** | ⚠️ **不是共享的！每连接可能分配多份**（多表排序时每个表一份）|
| **`join_buffer_size`** ⭐ | JOIN 缓冲（BNL 用）| **256KB** | ⚠️ **每个 JOIN 一份**（3 表 JOIN 可能 2 份）|
| **`read_buffer_size`** | 顺序扫描缓冲 | 128KB | 每个被顺序扫描的表一份 |
| **`read_rnd_buffer_size`** | 随机读缓冲（排序后回表）| 256KB | |
| **`binlog_cache_size`** | 事务的 binlog 缓存 | 32KB | 每个有事务的会话一份 |
| **`tmp_table_size` / `max_heap_table_size`** | 内存临时表 | 16M/16M | 每个会话可能建多个临时表 ⚠️ |
| **连接栈** | `thread_stack` | 256KB~1MB | 每个线程 |
| **net buffer** | `net_buffer_length` | 16KB | 起手就分配，按需增长到 `max_allowed_packet` ⚠️ |
| **`net_buffer_length`（增长到）** | — | — | 大查询可能涨到 `max_allowed_packet`（默认 64M）⚠️⚠️ |
| **预处理语句缓冲** | 每个 `MYSQL_STMT` | — | 用预处理的连接内存更高 ⭐ |
| **表缓存条目** | — | — | 每个连接持有的表句柄 |

**⚠️ 最容易被低估的三个** ⭐：

```
① sort_buffer_size 与 join_buffer_size 是"每连接 × 可能多份"
   → 设 4M 的话，100 个连接、平均 2 份 = 800MB ⚠️
② tmp_table_size 每个会话可能建多个临时表
   → 设 256M 的话，20 个会话各建 3 个临时表 = 15GB 🔴
③ max_allowed_packet（默认 64M）—— 大查询的连接会真的涨到这么大 ⚠️
```

## 四、内存估算公式 ⭐⭐

```
总内存需求 ≈ innodb_buffer_pool_size
           + innodb_log_buffer_size
           + table_open_cache × 每表句柄（约 1~4KB）
           + max_connections × (sort_buffer + join_buffer + read_buffer
                                + read_rnd_buffer + binlog_cache + thread_stack
                                + net_buffer 增长 + 临时表可能性)
           + 其他固定开销

⚠️ "max_connections × 每连接"是【最坏情况】，实际是"同时在跑的连接 × 每连接"
   —— 但必须按最坏情况规划（否则可能 OOM）⭐
```

**实例计算**（16GB 内存，8 核）：

```
要保证：峰值不 OOM + 留足余量

方案 A（保守，推荐）⭐
  innodb_buffer_pool_size = 10GB
  连接相关：
    假设每连接峰值 3MB（含临时表）
    max_connections = 500 → 1.5GB
  其他（log buffer、table cache、thread cache）= 1GB
  OS 预留 = 2GB
  ─────────────────────
  合计 14.5GB ✅ 有余量

方案 B（激进，危险）⚠️
  innodb_buffer_pool_size = 12GB
  每连接 sort_buffer = 8M, join_buffer = 8M
  max_connections = 1000
  → 连接相关最坏 = 1000 × 20MB = 20GB 🔴 直接 OOM
```

**关键原则** ⭐：**"宁可 Buffer Pool 大、连接私有 buffer 小"** —— 因为 Buffer Pool 是**共享且必然被用到**的，而每连接 buffer 只在特定查询时才分配，**但一旦分配就会按配置的大小一次性分配** ⚠️

## 五、`sort_buffer_size` / `join_buffer_size` 的正确设法 ⭐⭐

```ini
[mysqld]
# ⚠️ 这两个参数是"每连接"的，绝不能设大！
sort_buffer_size     = 1M        # 默认 256K；一般 1M 足够
join_buffer_size     = 1M        # 默认 256K
read_buffer_size     = 512K
read_rnd_buffer_size = 512K
# 8.0 新增：限制 JOIN 缓冲总量（防止一个连接占用过多）⭐
join_buffer_size     = 1M
# 8.0.18+ 可限制单个 JOIN 的缓冲池总量
```

**为什么不能设大** ⭐：

```
sort_buffer_size 的真实分配行为：
  · 只有需要排序的查询才会分配
  · ⚠️ 但如果一条 SQL 有多个排序（如多表 JOIN 每个表都要排序），
     可能分配多份
  · 它是在"需要时"按配置大小一次性分配，不是按需增长 ⚠️
  → 设 16M 时，10 个并发排序查询 = 160MB（看起来还好）
  → 但 500 个并发排序查询 = 8GB 🔴
```

**正确诊断方法** ⭐：

```sql
-- 用 performance_schema 看实际用了多少
SELECT * FROM sys.memory_by_thread_by_current_bytes ORDER BY current_alloc DESC LIMIT 10;
SELECT * FROM sys.memory_global_by_current_bytes LIMIT 20;
-- ⭐ 直接告诉你"谁在吃内存"

-- 也可以按事件名看
SELECT EVENT_NAME, CURRENT_NUMBER_OF_BYTES_USED
FROM performance_schema.memory_summary_global_by_event_name
ORDER BY CURRENT_NUMBER_OF_BYTES_USED DESC LIMIT 20;
```

## 六、`tmp_table_size` 与临时表 ⭐

**临时表的两种形态**：

```
① 内存临时表（Heap/Memory 引擎）—— 快
   条件是：临时表大小 ≤ MIN(tmp_table_size, max_heap_table_size)
② 磁盘临时表（InnoDB 或 Aria）—— 慢 ⚠️
   超出限制就落盘
```

**触发临时表的语句** ⭐：

```sql
GROUP BY（没有合适索引时）、DISTINCT、UNION、
ORDER BY（有 filesort 时的中间结果）、
子查询物化、派生表、窗口函数
```

**监控**（见"监控"题）：

```sql
SHOW GLOBAL STATUS LIKE 'Created_tmp%';
-- Created_tmp_tables       总临时表数
-- Created_tmp_disk_tables  落盘的临时表数 ⭐
-- 磁盘比例 = disk / total，> 25% 需要优化 ⭐
```

**⚠️ 大 `tmp_table_size` 的风险** ⭐：

```
设 tmp_table_size = 256M
若 20 个会话各建 2 个临时表 → 20 × 2 × 256M = 10GB 🔴 内存爆
→ 建议 64M ~ 128M，并用索引/改写 SQL 来避免临时表 ⭐
```

## 七、`max_connections` 与内存的关系 ⭐⭐

```
问题："我要提高并发 → 调大 max_connections"

真相：max_connections 不是"并发能力"的旋钮，而是"内存风险"的旋钮 ⚠️
     真正的并发能力受 CPU 核数限制
```

**正确的扩容顺序** ⭐：

```
① 先优化 SQL（减少每个查询的资源消耗）
② 加连接池（复用连接，减少连接数需求）
③ 减少每连接的 buffer（sort/join/tmp_table）
④ 再考虑调大 max_connections
⑤ 都不够 → 升配 / 加从库 / 分片
```

**"每连接内存"监控** ⭐：

```sql
-- 平均每连接占用内存
SELECT ROUND(
    (SELECT VARIABLE_VALUE FROM performance_schema.global_status
     WHERE VARIABLE_NAME='Threads_connected') AS conn,
    ...
);
-- 更直接：用 sys.memory_by_thread_by_current_bytes 求平均
SELECT AVG(current_alloc) AS avg_per_conn FROM (
    SELECT THREAD_ID, SUM(CURRENT_NUMBER_OF_BYTES_USED) AS current_alloc
    FROM performance_schema.memory_summary_by_thread_by_event_name
    GROUP BY THREAD_ID
) t;
```

## 八、OS 层的内存（别忘了）⭐

```
MySQL 之外，OS 也要内存：
  · 文件系统 page cache（⚠️ 用 innodb_flush_method=O_DIRECT 可避免双重缓存）
  · 网络栈缓冲
  · mysqld 可执行文件与共享库
  · 其他进程

⚠️ 最危险的：swap
  一旦 MySQL 内存被换到 swap → 性能断崖式下跌 ⚠️
  建议：
    · 专用服务器：vm.swappiness = 1（尽量不用 swap）⭐
    · 或干脆不配 swap（但要确保内存充足，否则 OOM Killer 直接杀进程）⭐
    · ⚠️ OOM Killer 杀 mysqld 是很常见的事故
```

**监控** ⭐：

```bash
free -h                    # MemAvailable 才是真正的可用内存
vmstat 1                   # si/so 非 0 = 在用 swap ⚠️
dmesg | grep -i 'oom'      # 看有没有被 OOM Killer 杀过 ⭐
cat /proc/meminfo
```

## 九、内存配置模板 ⭐

### 小内存（4GB，开发/小站）

```ini
[mysqld]
innodb_buffer_pool_size = 2G
innodb_buffer_pool_instances = 1
innodb_log_buffer_size = 16M
max_connections = 100
sort_buffer_size = 512K
join_buffer_size = 512K
read_buffer_size = 256K
read_rnd_buffer_size = 256K
tmp_table_size = 32M
max_heap_table_size = 32M
table_open_cache = 400
thread_cache_size = 30
performance_schema = OFF          # ⭐ 小内存可关掉省内存
```

### 中内存（16GB）

```ini
[mysqld]
innodb_buffer_pool_size = 10G
innodb_buffer_pool_instances = 8   # ⭐ 每实例约 1G，减少 latch 竞争
innodb_log_buffer_size = 32M
max_connections = 500
sort_buffer_size = 1M
join_buffer_size = 1M
read_buffer_size = 512K
read_rnd_buffer_size = 512K
tmp_table_size = 64M
max_heap_table_size = 64M
table_open_cache = 2000
thread_cache_size = 100
```

### 大内存（64GB+）

```ini
[mysqld]
innodb_buffer_pool_size = 48G
innodb_buffer_pool_instances = 16
innodb_log_buffer_size = 64M
max_connections = 2000
sort_buffer_size = 1M              # ⚠️ 仍是 1M！不要因为机器大就设大
join_buffer_size = 1M
tmp_table_size = 128M
max_heap_table_size = 128M
table_open_cache = 4000
thread_cache_size = 200
```

**注意** ⭐：**从 16GB 到 64GB，变的是 Buffer Pool，不是每连接 buffer**。

## 十、内存问题排查清单 ⭐

| 现象 | 排查 |
|---|---|
| **内存持续上涨** | `sys.memory_by_thread_by_current_bytes` 找哪个线程吃内存；检查是否有连接泄漏 ⭐ |
| **OOM Killer 杀了 mysqld** | `dmesg \| grep -i oom`；`max_connections × 每连接` 是否超了 ⭐ |
| **用 swap 了** | `vmstat 1` 的 si/so；调 `vm.swappiness=1` ⭐ |
| **瞬时内存尖峰** | 大查询（大排序、大临时表、大 JOIN）；`tmp_table_size` 设置过大 ⭐ |
| **`Created_tmp_disk_tables` 比例高** | 临时表落盘 → 改 SQL / 加 `tmp_table_size`（小心别太大）⭐ |
| **内存没满但性能差** | Buffer Pool 可能不够（看命中率）；或 double cache（`innodb_flush_method`）⭐ |
| **每连接内存很高** | `sort_buffer_size` / `join_buffer_size` / `tmp_table_size` 设大了 ⭐ |

**一键查看内存分布** ⭐：

```sql
-- 全局内存（按事件类型）
SELECT EVENT_NAME,
       FORMAT_BYTES(CURRENT_NUMBER_OF_BYTES_USED) AS used
FROM performance_schema.memory_summary_global_by_event_name
ORDER BY CURRENT_NUMBER_OF_BYTES_USED DESC LIMIT 15;

-- 按线程
SELECT t.PROCESSLIST_ID, t.PROCESSLIST_USER,
       FORMAT_BYTES(SUM(m.CURRENT_NUMBER_OF_BYTES_USED)) AS mem
FROM performance_schema.memory_summary_by_thread_by_event_name m
JOIN performance_schema.threads t USING (THREAD_ID)
GROUP BY t.PROCESSLIST_ID, t.PROCESSLIST_USER
ORDER BY SUM(m.CURRENT_NUMBER_OF_BYTES_USED) DESC LIMIT 15;   -- ⭐
```

## 十一、一句话总结

**MySQL 内存分"全局共享"（Buffer Pool 是大头）和"每连接私有"（sort/join/read/tmp_table 缓冲）**；**"连接数一多就爆内存"的根因是后者是"每连接 × 可能多份"且"按配置大小一次性分配"** ⭐；**规划原则是"Buffer Pool 尽量大、每连接 buffer 尽量小"**，用 `sys.memory_by_*` 视图看真实占用而不是套公式；**别忘了 OS 层的 swap 与 page cache（用 `O_DIRECT` 避免双重缓存）**，以及 **OOM Killer 杀 mysqld 是常见事故**。""",
    ),
    (
        "MySQL",
        "三范式,反范式,设计案例",
        2,
        r"""请用一个具体案例说明三范式的应用，以及什么时候应该反范式。""",
        r"""## 一、一个"错误起点"：把所有数据放一张表 ⭐

**电商订单的"大宽表"（反面教材）**：

```sql
CREATE TABLE bad_orders (
    id          BIGINT PRIMARY KEY,
    user_id     BIGINT,
    user_name   VARCHAR(50),      -- 用户信息
    user_phone  VARCHAR(20),
    user_email  VARCHAR(100),
    product_ids VARCHAR(500),     -- ⚠️ "1,2,3" 逗号分隔（违反 1NF）
    product_names VARCHAR(1000),  -- ⚠️ 冗余
    product_prices VARCHAR(500),  -- ⚠️ 冗余
    total_amount DECIMAL(18,2),
    addr_province VARCHAR(30),
    addr_city   VARCHAR(30),
    addr_detail VARCHAR(200),
    pay_no      VARCHAR(64),
    pay_time    DATETIME,
    ...
);
```

**问题清单**：

| 问题 | 说明 |
|---|---|
| **违反 1NF** | `product_ids` 用逗号分隔（不是原子值）→ 无法索引、无法 JOIN、`FIND_IN_SET` 只能全表扫 ⚠️ |
| **违反 2NF/3NF** | `user_name` 依赖 `user_id`（传递依赖）；`product_names` 依赖 `product_ids` |
| **更新异常** | 用户改名要更新**所有**他的订单行 ⚠️（可能几百万行）|
| **插入异常** | 没有订单就不能存商品信息 |
| **删除异常** | 删掉唯一订单会丢失商品信息 |
| **NULL 泛滥** | 未支付的订单 `pay_*` 全是 NULL |
| **单行过大** | 一页放不下几行 → 查询效率低 |

## 二、按三范式重构 ⭐

### 1NF：原子性 —— 拆掉逗号分隔

```
坏：product_ids = "1,2,3"
好：拆成 order_items 表（一商品一行）⭐
```

### 2NF：消除部分依赖

```
坏：(order_id, product_id) → product_name
    product_name 只依赖 product_id（主键的一部分）
好：product_name 放在 products 表 ⭐
```

### 3NF：消除传递依赖

```
坏：order.user_id → user_name（user_name 依赖 user_id，而 user_id 依赖 order.id）
好：user_name 放在 users 表 ⭐

坏：order.total_amount 依赖 order_items（汇总值）
好：可由 order_items 计算得出 → 不存（或明确作为"快照"存）⭐
```

### 重构结果 ⭐

```sql
-- 用户表
CREATE TABLE users (
    id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(32) NOT NULL,
    phone    VARCHAR(20)  NULL,
    email    VARCHAR(100) NULL,
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 商品表
CREATE TABLE products (
    id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name    VARCHAR(200) NOT NULL,
    price   DECIMAL(18,2) NOT NULL,
    stock   INT UNSIGNED NOT NULL DEFAULT 0,
    KEY idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 订单表（只放"订单自身的属性"）
CREATE TABLE orders (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_no    VARCHAR(32) NOT NULL,
    user_id     BIGINT UNSIGNED NOT NULL,
    status      TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0待支付 1已支付 2已发货 3完成 4取消',
    total_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    UNIQUE KEY uk_order_no (order_no),
    KEY idx_user_created (user_id, created_at),      -- ⭐ 覆盖"我的订单"查询
    KEY idx_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 订单明细（一对多）
CREATE TABLE order_items (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id   BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    quantity   INT UNSIGNED NOT NULL,
    -- ⭐ 关键：这里的 price 是"下单时的价格快照"，不是冗余！
    unit_price DECIMAL(18,2) NOT NULL COMMENT '下单时的单价快照',
    amount     DECIMAL(18,2) NOT NULL,
    KEY idx_order (order_id),
    KEY idx_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 收货地址（订单的"地址快照"，不是引用 users_address 的 id）⭐
CREATE TABLE order_addresses (
    order_id   BIGINT UNSIGNED PRIMARY KEY,
    receiver   VARCHAR(50)  NOT NULL,
    phone      VARCHAR(20)  NOT NULL,
    province   VARCHAR(30)  NOT NULL,
    city       VARCHAR(30)  NOT NULL,
    detail     VARCHAR(200) NOT NULL,
    KEY idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 支付记录（与订单 1:1，但单独成表，因为很多订单未支付）⭐
CREATE TABLE order_payments (
    order_id   BIGINT UNSIGNED PRIMARY KEY,
    pay_no     VARCHAR(64) NOT NULL,
    pay_time   DATETIME(3) NOT NULL,
    UNIQUE KEY uk_pay_no (pay_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**重构收益** ⭐：

| 收益 | 说明 |
|---|---|
| **无更新异常** | 用户改名只改 `users` 一行 ⭐ |
| **无删除异常** | 删订单不影响用户和商品 |
| **可索引** | 每个字段都可单独索引 |
| **单行小** | 一页放更多行 → 查询快 |
| **避免 NULL** | 支付信息独立成表，未支付就是"没有这行" ⭐ |

## 三、什么时候应该反范式 ⭐⭐

**判断标准：这个冗余是"为了读性能的必要代价"吗？**

### 应该反范式的场景 ✅

| 场景 | 冗余什么 | 为什么 |
|---|---|---|
| **下单时的价格快照** ⭐⭐ | `order_items.unit_price` | **这不是冗余，是业务必需** —— 商品后来降价了，历史订单必须保留当时价格 ⭐ |
| **订单地址快照** ⭐⭐ | `order_addresses` | 用户改了地址，历史订单的收货地址不能变 ⭐ |
| **列表页需要的摘要** ⭐ | `posts.summary` | 避免列表页拉 `MEDIUMTEXT content`（溢出页 IO）⭐ |
| **高频 JOIN 的展示字段** ⭐ | `orders.user_name`（可接受）| "我的订单"列表要显示用户名，避免每行 JOIN。**但要保证用户名变更时同步** |
| **统计汇总** ⭐ | `order_daily_stats` | 实时算 `SUM` 太贵，用定时任务/触发器维护汇总表 |
| **计数器** ⭐ | `posts.views`、`posts.comment_count` | 避免每次 `COUNT(*)`。⚠️ 用原子 SQL 更新 |
| **搜索用的拼装字段** | `search_text`（标题+标签拼接）| 配合全文索引 |
| **多级分类的路径** ⭐ | `category.path = "1/5/23"` | 避免递归查询 |

### 不应反范式的场景 ❌

| 场景 | 为什么 |
|---|---|
| **用户表的字段冗余到订单表**（除了用户名这种展示字段）| 用户信息变更频繁，同步成本高、易不一致 ⚠️ |
| **商品价格实时冗余到订单** | 应该冗余**快照**而不是"当前值" |
| **为了"少写一个 JOIN"而冗余大部分字段** | 收益 < 同步成本 |
| **冗余"可以算出来"的字段但又不保证同步** | 数据会不一致 ⭐ |

## 四、反范式的代价与维护策略 ⭐⭐

**核心问题：一致性怎么保证？**

| 策略 | 说明 | 适用 |
|---|---|---|
| **同一事务内一起改** ⭐ | 改 `users.username` 时，同时更新 `orders.user_name` | 小范围冗余、低频变更 |
| **异步同步（消息队列 / binlog 订阅）** ⭐ | 用户改名后发消息，异步刷订单表 | 大范围冗余、高频变更 |
| **定时任务全量重刷** | 每天凌晨重算 | 统计类汇总表 ⭐ |
| **只读时容忍短暂不一致** ⭐ | 缓存 + TTL 兜底 | 展示类字段 |
| **不做冗余，用 JOIN** | 最安全 | 冗余收益不明显时 |

**⚠️ 反范式的黄金判断** ⭐：

```
收益（读性能的提升） > 代价（同步复杂度 + 一致性风险）？
且
有明确的"一致性能容忍多久"的答案？
→ 都是"是"才做反范式
```

## 五、真实案例：本项目（博客）的表设计 ⭐

```sql
-- 文章表：适度反范式
CREATE TABLE posts (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title      VARCHAR(200) NOT NULL,
    summary    VARCHAR(500) NOT NULL DEFAULT '' COMMENT '⭐ 反范式：列表页摘要，避免读 content',
    content    MEDIUMTEXT   NULL     COMMENT '正文 markdown',
    category   VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '分类（可接受不建表，因为几乎不变）',
    tags       VARCHAR(200) NOT NULL DEFAULT '' COMMENT '⭐ 反范式：少量标签用逗号分隔，配合全文索引',
    views      INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '⭐ 反范式：计数器',
    comment_cnt INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '⭐ 反范式：避免 COUNT(*)',
    status     TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '0草稿 1已发布',
    created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_status_created (status, created_at),
    FULLTEXT KEY ft_search (title, summary, tags) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

**这里的反范式决策与理由** ⭐：

| 字段 | 是否反范式 | 理由 |
|---|---|---|
| `summary` | ✅ 是 | **避免列表页拉 MEDIUMTEXT** ⭐ 收益明显（避免溢出页 IO）|
| `tags` | ✅ 是 | 标签是"文章属性"而非独立实体（博客场景）；数量少且几乎不变；配合全文索引更好用 |
| `views` | ✅ 是 | 计数器，避免每次统计；**用 `UPDATE posts SET views = views + 1` 原子更新** ⭐ |
| `comment_cnt` | ✅ 是 | 避免 `SELECT COUNT(*) FROM comments WHERE post_id=?`；⚠️ 但**必须保证评论增删时同步**（同一事务）⭐ |
| `category` | ⚠️ 半反范式 | 严格 3NF 应有 `categories` 表；但博客分类少且极少改，**用字符串更简单** |
| `content` | ❌ 不冗余 | 属于文章本体 |

**`comment_cnt` 的陷阱** ⭐：如果评论是异步/宽松的（比如防刷），可能偶尔不同步。**应该提供一个"后台重算"的修复任务**：

```sql
-- 修复 SQL（定时跑或手工跑）
UPDATE posts p
LEFT JOIN (SELECT post_id, COUNT(*) c FROM comments GROUP BY post_id) x
  ON p.id = x.post_id
SET p.comment_cnt = IFNULL(x.c, 0);
# ⚠️ 大表要分批 + 用 pt-osc 思路；或只修 comment_cnt 与真实值不符的行
```

## 六、范式化的实践清单 ⭐

| 原则 | 说明 |
|---|---|
| **先 3NF，再按需反范式** ⭐ | 不要一上来就冗余 |
| **快照 vs 引用** ⭐⭐ | 历史数据要**快照**（订单价格），实时数据可以**引用**（用户当前头像）|
| **反范式必须有维护策略** ⭐ | 每次冗余都要回答"怎么保证一致" |
| **冗余字段加注释说明来源** | `COMMENT '冗余自 users.username，用户改名时需同步'` ⭐ |
| **统计类冗余用汇总表 + 定时任务** | 而不是在业务表里塞聚合结果 |
| **避免存"可推导"的字段** | 除非明确是快照 |
| **计数器用原子 SQL** ⭐ | `SET n = n + 1` 而不是"读出来加一再写回"（后者有竞态）⭐ |
| **写代码前先想清楚查询模式** ⭐ | 表结构服务于查询，不是反过来 |

## 七、一句话总结

**三范式的目标是"消除更新/插入/删除异常"，反范式的目标是"减少 JOIN 与 IO"**；**关键区分是"快照"与"冗余"** —— **订单里的商品价格不是冗余而是业务必需的快照** ⭐；**反范式只在"读性能收益 > 同步成本"且"有一致性维护策略"时才做**，且**必须在字段注释里写明来源与同步方式**；**实践路线是"先 3NF 建表，再按真实查询模式做有策略的反范式"**。""",
    ),
    (
        "MySQL",
        "资源组,CPU,NUMA",
        3,
        r"""MySQL 8.0 的资源组（Resource Group）是什么？NUMA 架构下有什么注意事项？""",
        r"""## 一、资源组（Resource Group）⭐

**目的**：**把不同类型的工作负载隔离**，防止"报表查询/备份任务把 OLTP 业务的 CPU 抢光"。

```sql
-- 查看现有资源组
SELECT * FROM information_schema.resource_groups;
-- 默认有两个：
--   USR_default（前台线程）
--   SYS_default（后台线程）

-- 创建资源组 ⭐
CREATE RESOURCE GROUP rg_oltp
  TYPE = USER
  VCPU = 0-7                  -- ⭐ 绑定到 CPU 0~7
  THREAD_PRIORITY = 0         -- 优先级（-20 ~ 19，越小优先级越高）
  ENABLE;                     -- 启用

CREATE RESOURCE GROUP rg_report
  TYPE = USER
  VCPU = 8-15
  THREAD_PRIORITY = 19        -- ⭐ 最低优先级
  ENABLE;

-- 修改
ALTER RESOURCE GROUP rg_oltp VCPU = 0-3 THREAD_PRIORITY = 0;

-- 把线程分配到资源组
SET RESOURCE GROUP rg_report;              -- 当前会话
SET RESOURCE GROUP rg_report FOR 1234;      -- 指定线程 ID ⭐
-- 也可以在连接串/初始化时设置（应用侧指定）

-- 删除
DROP RESOURCE GROUP rg_report;

-- 禁用（保留定义）
ALTER RESOURCE GROUP rg_report DISABLE;
```

**关键特性**：

| 特性 | 说明 |
|---|---|
| **`VCPU`** | 指定可用的 CPU 核（`0-7` 或 `0,2,4`）|
| **`THREAD_PRIORITY`** | 线程优先级（`-20` 最高 ~ `19` 最低）|
| **`TYPE`** | `USER`（前台）或 `SYSTEM`（后台线程，如 purge、page cleaner）⭐ |
| **绑定范围** | ⚠️ **只影响该资源组内的线程**；未分配的走 `USR_default`（不限制）|
| **权限** | 需要 `RESOURCE_GROUP_ADMIN` / `RESOURCE_GROUP_USER` |

**典型用途** ⭐：

```
✓ 把"报表查询"绑到低优先级 + 少数核，避免影响 OLTP
✓ 把"批量导入"和"在线业务"隔离
✓ SYSTEM 组可以把 purge 线程绑到特定核，避免和前台争抢 ⭐
✓ 多租户场景下隔离不同业务的资源
```

**注意** ⚠️：

| 注意点 | 说明 |
|---|---|
| **VCPU 不重叠则强隔离** | 两个组设不同的核 → 真正的物理隔离 |
| **CPU 亲和有内核开销** | 频繁切换可能影响缓存局部性 |
| **不是"限流"** | 它不限制 QPS，只限制"用哪些核"与优先级 |
| **需要 OS 支持** | Linux 上通过 `sched_setaffinity` 与 `setpriority` 实现 |
| **在容器里可能受限** | cgroup 的 cpuset 会限制可用核 ⚠️ |

## 二、NUMA 架构 ⭐⭐

### 什么是 NUMA

```
【UMA（SMP，老架构）】
  所有 CPU 通过同一条总线访问同一块内存
  → 核多了，总线成为瓶颈 ⚠️

【NUMA（Non-Uniform Memory Access）】
  ┌─────────────────┐        ┌─────────────────┐
  │  Node 0          │        │  Node 1          │
  │  CPU 0-15        │◄─QPI──►│  CPU 16-31       │
  │  本地内存 64GB    │        │  本地内存 64GB    │
  └─────────────────┘        └─────────────────┘
  CPU 0 访问 Node 0 内存 = 本地访问（快，约 100ns）⭐
  CPU 0 访问 Node 1 内存 = 远程访问（慢，约 1.5~2 倍延迟）⚠️
```

**核心问题**：**如果 CPU 频繁访问"远程内存"，性能会显著下降**（延迟高、而且 QPI/UPI 带宽有限）。

### NUMA 对 MySQL 的影响 ⭐⭐

```
问题 1：内存分配"跨节点"
  · 如果 mysqld 启动时只在一个节点分配了 Buffer Pool
    但线程在任何节点都可能运行 → 一半的线程在"远程访问" ⚠️

问题 2：线程漂移
  · OS 调度器可能把线程在 NUMA 节点间迁移
    → 每次迁移后内存访问都变远程 ⚠️

问题 3：内存带宽瓶颈
  · 所有内存压力集中在一个节点时，该节点的内存带宽成为瓶颈 ⚠️
```

**判断是否在 NUMA 上** ⭐：

```bash
lscpu | grep -i numa
numactl --hardware
# 输出会显示 node 0 cpus / node distances 等
#   若 "NUMA node(s): 1" → 单节点（或 NUMA 已禁用）
#   若 "NUMA node(s): 2" → 双路服务器，需要处理 ⭐

# 查看 mysqld 的内存分布
numastat -p $(pidof mysqld)      # ⭐ 关键命令
# 输出每个 node 的本地/远程分配量
#   若 "Other" 或某 node 的 "Total" 高得不均衡 → 有问题
```

### 处理方案 ⭐⭐

**方案 A：BIOS 层关闭 NUMA（最简单，但放弃 NUMA 优势）**

```
BIOS → Node Interleaving = Enabled
效果：内存被交错分配（interleaved），所有 CPU 访问所有内存"等距"
     → 消除了"远程访问"，但也失去了 NUMA 的本地性优势
     → 对 MySQL 这种"内存访问密集但不太热点集中"的工作负载通常更稳 ⭐
```

**方案 B：`numactl --interleave=all`（Linux 层交错）⭐**

```bash
# 启动 mysqld 时用交错模式
numactl --interleave=all /usr/sbin/mysqld ...

# systemd 服务里配置
[Service]
ExecStart=/usr/bin/numactl --interleave=all /usr/sbin/mysqld ...
```

**效果**：Buffer Pool 被交错分配到所有节点 → 每个 CPU 都能"就近访问一部分"，**避免单个节点内存带宽成为瓶颈** ⭐

**这是 MySQL 社区对 NUMA 最广泛推荐的方案** ⭐

**方案 C：本地绑定（`--cpunodebind` + `--membind`）**

```bash
# 把 mysqld 完全绑到一个 NUMA 节点
numactl --cpunodebind=0 --membind=0 /usr/sbin/mysqld ...
```

**适用**：多实例部署（每个实例绑一个节点）⭐ 这是**多实例场景的标准做法**：

```
双路 32 核 128GB 机器，跑 2 个 MySQL 实例：
  实例 A：numactl --cpunodebind=0 --membind=0  （用 CPU 0-15 + 内存 0-63GB）
  实例 B：numactl --cpunodebind=1 --membind=1  （用 CPU 16-31 + 内存 64-127GB）
→ 每个实例完全本地访问，互不干扰 ⭐
```

**方案 D：内核参数**

```bash
# 减少 NUMA 自动平衡带来的线程迁移
sysctl kernel.numa_balancing=0        # ⚠️ 会禁用自动 NUMA 平衡
# 或
echo 0 > /proc/sys/kernel/numa_balancing

# vm.zone_reclaim_mode = 0（避免在本地内存紧张时过度回收，宁可远程分配）
sysctl vm.zone_reclaim_mode=0         # ⭐ 推荐 0
```

**`vm.zone_reclaim_mode` 的坑** ⭐：

```
默认在某些内核上为 1 或更高 → 本地内存不足时会"强制回收本地页"
  → 导致大量 swap 或页回收开销 ⚠️
设为 0 → 本地不足时直接用远程内存
  → 对数据库通常是更好的选择 ⭐（远程延迟好过 swap）
```

## 三、其他 CPU 相关的调优 ⭐

| 项 | 说明 |
|---|---|
| **CPU 电源策略** ⭐ | BIOS/OS 设为 **Performance**（不要 Power Saving）—— 频率降档会显著影响 DB 延迟 |
| **`cpupower frequency-set -g performance`** | Linux 下固定性能模式 |
| **C-State / C1E** | 关闭深度睡眠状态（避免唤醒延迟）⚠️ 极端场景才需要 |
| **超线程（HT）** ⭐ | MySQL 在 HT 上表现**通常有提升但不如物理核**；且 `innodb_thread_concurrency` 等按"逻辑核"计数要注意 ⚠️ |
| **`innodb_thread_concurrency`** | 8.0 默认 **0（不限）**；高并发争抢严重时可设 核数×2 ⭐ |
| **`innodb_read_io_threads` / `write_io_threads`** | IO 线程数，8 核以上建议 4~8 |
| **`innodb_page_cleaners`** | 应等于 `innodb_buffer_pool_instances` ⭐ |
| **`innodb_purge_threads`** | 4~8 |
| **`innodb_adaptive_hash_index`** | 高并发下 AHI 的 btr latch 竞争可能拖慢 → 有时应关闭 ⭐ |
| **中断亲和** ⭐ | 网卡/磁盘中断绑定到固定核（`irqbalance` 或手工），避免中断与 DB 线程抢同一核 |
| **隔离核心** ⭐ | 内核参数 `isolcpus=` 把某些核留给 MySQL，把 OS 任务赶走（极端场景）|

## 四、实践配置示例 ⭐

### 单实例（双路 NUMA）⭐

```ini
# /etc/systemd/system/mysqld.service.d/override.conf
[Service]
ExecStart=
ExecStart=/usr/bin/numactl --interleave=all /usr/sbin/mysqld --defaults-file=/etc/my.cnf

# /etc/my.cnf
[mysqld]
innodb_buffer_pool_size = 96G          # 128GB 内存的机器
innodb_buffer_pool_instances = 16
innodb_thread_concurrency = 0
innodb_read_io_threads = 8
innodb_write_io_threads = 8
innodb_page_cleaners = 16              # = buffer_pool_instances ⭐
innodb_purge_threads = 4
innodb_io_capacity = 4000              # NVMe SSD
innodb_flush_method = O_DIRECT
innodb_flush_neighbors = 0             # SSD ⭐
# ⚠️ innodb_numa_interleave 已被废弃（8.0 移除），改用 numactl ⭐
```

### 多实例（每个实例绑一个 NUMA 节点）⭐⭐

```bash
# 实例 A
numactl --cpunodebind=0 --membind=0 /usr/sbin/mysqld --defaults-file=/etc/my_3306.cnf
# 实例 B
numactl --cpunodebind=1 --membind=1 /usr/sbin/mysqld --defaults-file=/etc/my_3307.cnf
```

**这是"大机器跑多实例"的推荐方式**：每个实例用 CPU + 内存都本地的资源，**完全避免 NUMA 远程访问**，且实例间天然隔离 ⭐

## 五、容器环境（Docker/K8s）的注意点 ⚠️

| 注意点 | 说明 |
|---|---|
| **容器 CPU 限制** ⭐ | `--cpus=8` 限制的是"时间片比例"，不是"独占 8 核"；若要真隔离需要 `--cpuset-cpus` ⭐ |
| **`cpuset` 与 NUMA** ⭐ | `--cpuset-cpus=0-7` 会同时限制 `membind`（与 cpuset 绑定的内存节点），**这是好事** ✅ |
| **内存限制与 OOM** ⭐⭐ | `--memory=16g` 时，**MySQL 必须按 16G 规划**，而不是宿主机的 128G ⚠️ 否则 OOM Kill |
| **`innodb_buffer_pool_size` 要按 cgroup 限制设** ⭐ | 一个常见事故：容器限 8G，但 buffer pool 设了 16G → 启动就 OOM |
| **cgroup v2 的内存统计** | `/sys/fs/cgroup/memory.current` |
| **`innodb_flush_method`** | 容器里 `O_DIRECT` 可能受 overlayfs 限制 ⚠️ 需实测 |
| **`performance_schema` 开销** | 容器 CPU 少时更明显，可考虑关掉 |

**容器里看真实资源限制** ⭐：

```bash
cat /sys/fs/cgroup/memory.max            # cgroup v2 内存上限
cat /sys/fs/cgroup/cpu.max               # CPU 配额
nproc                                     # 可能显示宿主机的核数（不对！）⚠️
# 用 cgroup 里的数据算真实可用核数
```

**⚠️ 最常见的容器事故** ⭐：`nproc` 返回宿主机核数（如 32），导致 MySQL 按 32 核配置（如 `innodb_read_io_threads=8`、`innodb_page_cleaners=16`），但实际只分到 4 核 → 线程过多、争抢严重、性能反而差。

## 六、诊断命令汇总 ⭐

```bash
# NUMA
lscpu | grep -i numa
numactl --hardware
numastat -p $(pidof mysqld)          # ⭐ 看内存分布
cat /proc/$(pidof mysqld)/numa_maps | head

# CPU
lscpu
cat /proc/cpuinfo | grep -E 'processor|model name|MHz' | head -40
top -H -p $(pidof mysqld)             # ⭐ 看各线程的 CPU 占用（找出热点线程）
pidstat -t -p $(pidof mysqld) 1       # 按线程统计
perf top -p $(pidof mysqld)            # ⭐ 看内核态/用户态热点函数
mpstat -P ALL 1                        # ⭐ 每个核的使用率（看是否不均衡）
turbostat                              # CPU 频率与 C-state

# 中断
cat /proc/interrupts | head
systemctl status irqbalance

# 容器
cat /sys/fs/cgroup/cpu.max
cat /sys/fs/cgroup/memory.max
cat /sys/fs/cgroup/cpuset.cpus.effective
```

**`mpstat -P ALL 1` 是关键** ⭐：如果发现**某些核 100% 而其他核空闲**，说明有 CPU 热点（可能是单线程瓶颈，如 purge、page cleaner，或 latch 竞争）→ 这才是真正的优化方向。

## 七、一句话总结

**资源组（8.0）用 `VCPU` + `THREAD_PRIORITY` 把不同工作负载隔离**（报表/备份 vs OLTP）；**NUMA 的核心问题是"远程内存访问延迟高 1.5~2 倍"**，**单实例推荐 `numactl --interleave=all`（交错分配，避免单节点内存带宽瓶颈）**，**多实例推荐"每个实例 `--cpunodebind=N --membind=N`"**（完全本地化 + 天然隔离）⭐⭐；**容器里必须按 cgroup 限制配置 MySQL（`nproc` 会骗你）**，并注意 `cpuset` 与内存节点的绑定关系。""",
    ),
    (
        "MySQL",
        "版本,升级,选型",
        2,
        r"""MySQL 该选哪个版本？5.7 升 8.0 的完整流程和风险点是什么？""",
        r"""## 一、版本选择 ⭐

| 系列 | 状态 | 建议 |
|---|---|---|
| **5.6** | 已 EOL（2021-02）| ❌ 不要用 |
| **5.7** | 已 EOL（2023-10）| ⚠️ 存量系统尽快迁 |
| **8.0** | **当前主力（LTS 级别）** ⭐ | ✅ 新项目首选 |
| **8.4 LTS** | 较新 LTS | ✅ 可选（生态稍新）|
| **9.x** | Innovation 版 | ⚠️ 生产谨慎 |
| **Percona Server** | 8.0 分支 | 更多诊断特性（`pt-*` 配套）⭐ |
| **MariaDB** | 分支（已与 MySQL 分道）| ⚠️ 兼容性有差异，不能随意互换 |

**推荐** ⭐：

```
新项目               → MySQL 8.0（或 8.4 LTS）
需要更多诊断/工具    → Percona Server 8.0 ⭐
云上                → 厂商支持的版本（通常是 8.0）
极致性能 + 新特性    → 8.4（但要验证生态）
```

**⚠️ 不要选**：`-debug` 版本（性能差）、非 LTS 的最新版（Innovation 版生命周期短）。

## 二、升级前的六项检查 ⭐⭐

### ① `sql_mode` 变化（头号报错源）⭐

```sql
-- 8.0 默认 sql_mode：
-- ONLY_FULL_GROUP_BY, STRICT_TRANS_TABLES, NO_ZERO_IN_DATE, NO_ZERO_DATE,
-- ERROR_FOR_DIVISION_BY_ZERO, NO_ENGINE_SUBSTITUTION

-- ⭐ 在 5.7 上先临时改成 8.0 的默认值，跑全量回归
SET GLOBAL sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
-- 然后跑业务回归，把所有报错的 SQL 修掉
```

**预期报错**：`ERROR 1055 (GROUP BY)`、`ERROR 1366 (严格模式)`、`ERROR 1292 (日期格式)`。

### ② 默认字符集与排序规则变化 ⭐

```
5.7 默认：latin1 / latin1_swedish_ci
8.0 默认：utf8mb4 / utf8mb4_0900_ai_ci

风险：
  · 新建表若不显式指定 collation → 用 0900_ai_ci
  · 与老表（可能是 utf8mb4_general_ci 或 utf8mb4_unicode_ci）JOIN 时
    会发生 COLLATE 转换 → 索引失效 ⚠️
  · ORDER BY 结果可能与旧规则不同 ⚠️
对策：
  · 建表**显式指定 collation**（全库统一）⭐
  · 已有表如果 collation 不统一，评估是否统一（⚠️ 改 collation 是 COPY 算法）
```

### ③ 认证插件变化 ⭐

```
5.7：mysql_native_password
8.0：caching_sha2_password（默认）

风险：老版本客户端驱动连不上 8.0 的账号 ⚠️
对策：
  · 升级驱动（首选）⭐
  · 或给需要的老账号改回：
    ALTER USER 'app'@'%' IDENTIFIED WITH mysql_native_password BY '<pwd>';
```

### ④ 已移除的功能 ⭐

| 移除项 | 替代 |
|---|---|
| **查询缓存（Query Cache）** | Redis / ProxySQL ⭐ |
| `utf8` 作为默认 | `utf8mb4` |
| `innodb_locks` / `innodb_lock_waits` 表 | `performance_schema.data_locks` / `data_lock_waits` ⭐ |
| `\N`（NULL 别名）| `NULL` |
| `PASSWORD()` 函数 | `CREATE USER` |
| `GRANT ... IDENTIFIED BY` | 分离 `CREATE USER` + `GRANT` |
| `PROCEDURE ANALYSE()` | — |
| `SQL_CALC_FOUND_ROWS`（弃用）| 单独 `COUNT(*)` ⭐（**这个弃用是好事，它本来就慢**）|

### ⑤ 新增保留字 ⭐

```
RANK, DENSE_RANK, ROW_NUMBER, LEAD, LAG, GROUPS, OVER, WINDOW,
CUME_DIST, NTILE, PERCENT_RANK, FIRST_VALUE, LAST_VALUE, ...
→ 老表若用这些做列名，升级后必须加反引号 或 改名 ⚠️
```

**检查方法**：

```sql
-- 找出所有可能冲突的列名
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE LOWER(column_name) IN ('rank','dense_rank','row_number','lead','lag','groups','over',
                             'window','cume_dist','ntile','percent_rank','first_value','last_value')
ORDER BY table_schema, table_name;
```

### ⑥ 复制兼容性 ⭐

```
8.0 从库 ✅ 可以复制 5.7 主库
5.7 从库 ❌ 不能复制 8.0 主库（单向兼容）

→ 升级顺序：先升从库（此时从库 8.0 复制 5.7 主库 ✅）
  再切主从角色，最后升原主库 ⭐
```

**其他复制注意**：

```
· 8.0 的 binlog 事件格式与 5.7 在老事件上兼容，但新特性事件老从库不认
· 认证插件不同可能影响复制账号
· GTID 模式下要检查 gtid_executed 一致性
```

## 三、升级流程（推荐路径）⭐⭐

```
【Stage 0：准备（1~2 周）】
  ① 全量备份（XtraBackup 物理备份）并**验证可恢复** ⭐
  ② 在测试环境升级一份数据副本，跑全量回归
  ③ 用 mysqlsh 的 upgrade checker 扫描 ⭐
     mysqlsh -- util check-for-server-upgrade root@host:3306 \
       --outputFormat=TEXT --outputDir=/tmp/upgrade_check
  ④ 处理 sql_mode / collation / 保留字 / 认证插件问题
  ⑤ 确认应用驱动兼容 8.0

【Stage 1：升级从库（低风险）】
  ① 停从库复制
  ② 备份从库
  ③ 原地升级从库（in-place upgrade）
     systemctl stop mysqld
     # 替换二进制（yum update 或手动）
     mysqld --defaults-file=/etc/my.cnf --upgrade=FORCE   # 或启动时自动升级
     systemctl start mysqld
  ④ 检查 SHOW SLAVE STATUS 是否正常
  ⑤ 观察一段时间（延迟、错误日志、慢查询）⭐

【Stage 2：切换（计划内停机，通常分钟级）】
  ① 停止写入（应用只读或停服）
  ② 确认主从无延迟
  ③ 提升 8.0 从库为主库（或直接升级原主库）
  ④ 应用切换到新主库
  ⑤ 恢复写入

【Stage 3：升级原主库】
  ① 用 Stage 1 的流程升级
  ② 作为从库加回新主库

【Stage 4：观察与收尾】
  ① 监控 1~2 周（慢查询、错误日志、复制延迟、性能指标）⭐
  ② 处理残留的 sql_mode/兼容问题
  ③ 更新文档与运维手册
```

**原地升级 vs 逻辑迁移** ⭐：

| | 原地升级（in-place）| 逻辑迁移（dump/load 或 Clone）|
|---|---|---|
| 速度 | 快（分钟~小时，取决于数据字典升级）| 慢（要重建）|
| 回滚 | ❌ **难（升级后不能降级！）** ⚠️ | ✅ 易（删新实例即可）|
| 适用 | 数据量大、停机窗口短 | 数据量小 或 需要保留回滚能力 ⭐ |
| 风险 | 不可逆 ⚠️ | 低 |

**⚠️ 8.0 升级后不能降级到 5.7**（数据字典格式变了）。所以**必须保留可用的全套备份**，并准备好"用备份重建回 5.7"的最坏方案 ⭐

**升级用 `--upgrade` 参数**：

```bash
# 显式升级数据字典
mysqld --upgrade=FORCE    # 强制升级（忽略版本标记）
--upgrade=MINIMAL          # 只升级必要部分（更快，但某些功能不可用）
--upgrade=AUTO             # 自动（默认）
```

## 四、`mysqlsh upgrade checker` 的检查内容 ⭐

```bash
mysqlsh -- util check-for-server-upgrade root@127.0.0.1:3306 --outputFormat=JSON
```

**它会检查**：

| 类别 | 内容 |
|---|---|
| **保留字冲突** | 表名/列名/别名用了 8.0 新增保留字 ⭐ |
| **已移除/弃用函数** | `PASSWORD()`、`ENCRYPT()`、`SQL_CALC_FOUND_ROWS` 等 |
| **`sql_mode` 差异** | 会报错的具体模式 |
| **字符集** | `utf8mb3` 使用、collation 不统一 ⭐ |
| **认证插件** | 非默认插件 |
| **表结构问题** | 索引过长、行格式、分区限制 ⭐ |
| **引擎** | 非 InnoDB 表 |
| **复制配置** | GTID、binlog 格式 |
| **配置参数** | 已移除的参数 ⚠️（启动会失败）|

**这是升级前最有价值的工具** ⭐ 一定要用。

## 五、升级后的必做事项 ⭐

```sql
-- ① 更新统计信息（升级后统计信息可能过时）⭐
-- 对所有表执行（大表用 pt-index-usage 或分批）
SELECT CONCAT('ANALYZE TABLE ', table_schema, '.', table_name, ';')
FROM information_schema.tables
WHERE table_schema NOT IN ('mysql','information_schema','performance_schema','sys');

-- ② 检查所有表健康
-- myisamchk（MyISAM）/ CHECK TABLE（InnoDB）
-- mysqlcheck -u root -p --all-databases

-- ③ 确认字符集/排序规则（新建表会继承新默认值）⭐
SHOW VARIABLES LIKE 'character_set%';
SHOW VARIABLES LIKE 'collation%';
SELECT table_name, table_collation FROM information_schema.tables
WHERE table_schema='blogdb';   -- 检查是否统一 ⭐

-- ④ 确认关键参数（有些参数默认值变了）⭐
SHOW VARIABLES LIKE 'innodb%';
SHOW VARIABLES LIKE '%timeout%';
SHOW VARIABLES LIKE 'sql_mode';

-- ⑤ 检查账户与权限（认证插件）⭐
SELECT user, host, plugin FROM mysql.user;
```

**常见"升级后才发现"的问题** ⭐：

| 问题 | 原因 | 处理 |
|---|---|---|
| **慢查询变得更快或更慢** | 优化器改进 / 统计信息变化 ⭐ | `ANALYZE TABLE` + 重新审查执行计划 |
| **JOIN 变慢** | collation 不统一 → 索引失效 ⭐ | 统一 collation |
| **应用连不上** | 认证插件 ⚠️ | 改驱动或改插件 |
| **某些 SQL 报错** | `sql_mode` 变严 | 修 SQL |
| **启动失败** | 配置文件里有已移除的参数 ⚠️ | 用 upgrade checker 提前发现 |
| **备份脚本失败** | `mysqldump` 参数变化（如 `--master-data` 被废弃为 `--source-data`）⚠️ | 更新脚本 |
| **`utf8mb3` 警告刷屏** | 老表用了 `utf8` | 迁移到 `utf8mb4` |

## 六、本项目（博客系统）的建议 ⭐

```
现状：自建 MySQL + systemd 部署

升级建议（如果还在 5.7 或更早）：
  ① 优先级不高（流量小），但 5.7 已 EOL（无安全补丁）⚠️ → 建议升级
  ② 升级前必须做的：
     □ XtraBackup 全量备份 + 验证恢复 ⭐
     □ 用 --default-character-set=utf8mb4 导出（否则乱码）⭐
     □ 检查 sql_mode / collation / 保留字（本项目列名正常）
     □ 检查认证插件（应用是 C API，看驱动版本）⚠️
  ③ 本项目有特殊点：
     · 曾经有"latin1 连接 + cp1252 转义数据"的历史 ⭐
       升级时**务必先核对连接字符集与新数据的形态**
     · 若曾执行过 charset 迁移，确认已迁完再升
     · 升级后**重新验证 FAQ/每日一题的中文显示**（用 curl + HEX 而非截图）⭐
  ④ 升级方式建议：
     · 数据量小 → 逻辑迁移（mysqldump 到新实例）更安全、可回滚 ⭐
     · 有停机窗口 → 简单直接
```

## 七、一句话总结

**新项目上 8.0（或 8.4 LTS）**；**升级的六项检查是"`sql_mode` 变严、默认字符集/collation 变化、认证插件、已移除功能、新增保留字、复制单向兼容"** ⭐；**升级前必用 `mysqlsh -- util check-for-server-upgrade` 扫描，并在 5.7 上临时改成 8.0 的 `sql_mode` 跑回归** ⭐⭐；**强烈注意"8.0 升级后不可降级"** → 必须保留可验证的物理备份作为退路；**升级顺序是"先升从库、再切主、最后升原主库"**。""",
    ),
    (
        "MySQL",
        "会话变量,连接池,污染",
        3,
        r"""数据库连接被连接池复用时，会话状态会互相污染吗？有哪些会话级状态需要清理？""",
        r"""## 一、为什么会话状态是"连接级"的 ⭐⭐

MySQL 的很多设置是**会话（session）级**的，**绑定在连接上**。连接池复用连接时，**上一个使用者留下的状态会被下一个使用者继承** ⚠️

```
时间线：
  请求 A：SET SESSION sql_mode = '';               ← 改了会话变量
          执行查询... (正常返回)
  ──────── 连接归还到池 ────────
  请求 B：借到同一个连接
          执行 UPDATE ... (意外地没有严格模式！) ⚠️⚠️
          → 数据被静默截断/转换，而且没人知道为什么
```

**这是"偶发、难以复现"的 bug 的典型来源** ⭐⭐

## 二、会话级状态清单 ⭐⭐

### ① 会话变量（`SET SESSION ...` / `SET @var`）

| 类型 | 例子 | 污染影响 |
|---|---|---|
| **系统变量（会话级）** ⭐ | `sql_mode`、`autocommit`、`time_zone`、`optimizer_switch`、`sort_buffer_size`、`group_concat_max_len`、`transaction_isolation`、`foreign_key_checks`、`unique_checks` | 影响后续查询的**行为与结果** ⚠️ |
| **用户变量** ⭐ | `SET @x = 1` | 残留值可能被后续 SQL 引用（`WHERE id = @x`）→ **结果完全错误** ⚠️⚠️ |
| **`@` 变量的隐式使用** | 老的"用户变量模拟窗口函数"技巧 | |

**最危险的三个** ⭐：

```sql
SET SESSION sql_mode = '';                -- ⭐⭐ 关闭严格模式（静默改数据）
SET SESSION foreign_key_checks = 0;       -- ⭐ 关闭外键检查（可能写入脏数据）
SET SESSION autocommit = 0;               -- ⭐⭐ 后续所有语句都在隐式事务里！
SET SESSION sql_log_bin = 0;              -- ⚠️ 关闭 binlog → 主从不一致！❗
SET SESSION unique_checks = 0;            -- 跳过唯一性检查（导入数据时的加速技巧）
```

**`sql_log_bin = 0` 尤其危险** ⚠️：如果连接池复用时它残留着，**后续的写入不会进 binlog → 从库永远缺这些数据 → 主从静默不一致** ❗

### ② 未提交的事务 ⭐⭐

```
如果借出的连接上还有一个未提交的事务（上一个使用者忘了 commit/rollback）：
  · 后续使用者的操作会被"卷进"这个老事务 ⚠️
  · 老的锁还持有 → 可能死锁
  · 提交时会一起提交（语义错误）⚠️
```

**这是最严重的污染之一**。**连接归还前必须确保事务已结束**。

### ③ 未读完的结果集 ⭐

```
如果上一个使用者用 mysql_use_result 但没有读完：
  → 连接处于"结果集未结束"状态
  → 下一个使用者执行任何语句都会报
    ERROR 2014: Commands out of sync; you can't run this command now ⚠️
```

**用 `mysql_store_result` 也有类似问题**：如果 `MYSQL_RES` 没 `free`，连接会持有它。

### ④ 临时表 ⭐

```sql
CREATE TEMPORARY TABLE tmp_xxx (...);   -- 会话级，连接关闭才消失
-- 池复用 → 下一个使用者可能：
--   · 意外看到/覆盖同名临时表 ⚠️
--   · 或 collide 报错 (Table already exists)
```

### ⑤ 预处理语句（Prepared Statement）

```
每个 MYSQL_STMT 是会话级的：
  · 未关闭会占内存（连接归还后仍占）⚠️
  · 某些池实现会缓存 prepared statement，需确认语义
```

### ⑥ 锁 / `GET_LOCK`

```sql
SELECT GET_LOCK('mylock', 10);       -- ⚠️ 命名锁是会话级的
-- 归还连接后如果没 RELEASE_LOCK → 锁一直被持有 ❗ 其他人全都拿不到
```

### ⑦ 其他会话状态

| 状态 | 说明 |
|---|---|
| **`LAST_INSERT_ID()`** | 会话级；新语句会覆盖，但 `SELECT LAST_INSERT_ID()` 不覆盖 ⭐ 需谨慎 |
| **`FOUND_ROWS()`** / `ROW_COUNT()` | 会话级 |
| **当前数据库（`USE db`）** ⭐ | 会话级！上一个使用者 `USE other_db` 后归还 → 下一个使用者可能查错库 ❗ |
| **字符集（`SET NAMES`）** ⭐ | 会话级（`character_set_client/connection/results`）|
| **`SET time_zone`** ⭐ | 会话级（影响 `NOW()`、`TIMESTAMP` 转换）|
| **`SET SESSION TRANSACTION ISOLATION LEVEL`** | 会话级 ⭐ |
| **`SELECT ... INTO @var`** | 用户变量 |
| **`SET SESSION innodb_lock_wait_timeout`** | 会话级 |
| **警告/错误栈** | `SHOW WARNINGS` 的内容 |

## 三、`USE db` 的污染 ⭐⭐（常被忽略）

```cpp
// 连接池借出连接
mysql_query(conn, "USE blog_a");          // 上一个使用者
// ... 归还
// 下一个使用者以为自己在 blogdb，实际在 blog_a ❗
mysql_query(conn, "SELECT * FROM posts"); // 查错了库！
```

**对策**：**连接初始化时显式 `mysql_select_db()`**，或**所有 SQL 都带库名前缀**（`blogdb.posts`）⭐

## 四、`SET time_zone` 的污染 ⭐⭐

```
上一个使用者：SET time_zone = '+00:00';
归还后：
  下一个使用者：SELECT NOW();              → 返回 UTC 时间 ⚠️
                INSERT ... created_at = NOW() → 存入 UTC ⚠️
                TIMESTAMP 列读取会按 UTC 转换 → 时间全都差 8 小时 ❗
```

**这类"时间错乱"bug 极难排查**（因为时区设置是"环境状态"，代码里看不见）。

## 五、清理策略 ⭐⭐

### 方案 A：归还前"重置会话"（推荐）⭐⭐

**通用做法：`mysql_reset_connection()`**（C API 5.7.3+）⭐：

```cpp
// 归还连接前
mysql_reset_connection(conn);
// 等价于：
//   · 回滚活动事务
//   · 释放表锁、命名锁（GET_LOCK）
//   · 关闭/清空临时表
//   · 重置会话变量为全局值 ⭐
//   · 重置用户变量
//   · 释放 prepared statements（⚠️ 会清掉语句缓存，需权衡）
//   · 清空结果集
// 但**保留连接本身**（不断开 TCP + 不重新认证）⭐
```

**这是最干净的做法** ⭐。代价：**会清掉 prepared statement 缓存**（如果用了语句缓存，需要重建）。

**如果 `mysql_reset_connection` 不适用**，可以手工执行：

```sql
-- 归还前的清理脚本
ROLLBACK;                       -- ⭐ 结束未提交事务
SET SESSION sql_mode = DEFAULT; -- ⭐ 恢复默认
SET SESSION autocommit = 1;
SET SESSION sql_log_bin = 1;    -- ⭐⭐ 特别重要
SET SESSION foreign_key_checks = 1;
SET SESSION unique_checks = 1;
SET SESSION sql_safe_updates = 0;
SET SESSION time_zone = DEFAULT;   -- ⚠️ DEFAULT 表示用全局值
SET SESSION TRANSACTION ISOLATION LEVEL <默认>;
SELECT RELEASE_ALL_LOCKS();        -- ⭐ 释放所有命名锁（5.7.5+）
-- 释放所有临时表：MySQL 没有 "DROP ALL TEMPORARY TABLES"
--   → 需要自己记录创建过的临时表名（或干脆不用临时表）⚠️
-- 释放 prepared statements：
DEALLOCATE PREPARE ...;             -- 需要逐个释放（难以枚举）⚠️
-- 重置用户变量：没有 "reset all" → 只能一个个 SET @x = NULL ⚠️
```

**⚠️ `mysql_reset_connection` 的优势就是它有"重置一切"的语义**（包括那些没法用 SQL 枚举的东西）⭐

### 方案 B：借出时"重新初始化"（更保守）⭐

```cpp
// 借出连接时，先执行一遍初始化（幂等）
MYSQL* c = pool->acquire();
mysql_query(c, "SET NAMES utf8mb4");
mysql_query(c, "SET SESSION sql_mode = '...'");   // 项目的标准 sql_mode
mysql_query(c, "SET SESSION time_zone = '+08:00'");
mysql_query(c, "SET SESSION autocommit = 1");
mysql_select_db(c, "blogdb");
// 这样即使归还时没清理干净，借出时也会被纠正 ⭐
```

**优点**：**不依赖"归还时清理是否成功"**（更健壮）⭐
**缺点**：**借出时多几次往返**（每次约 0.1~0.5ms，可接受）

### 方案 C：归还前先"验活 + 清理"，借出时"验活 + 重置"（最稳）⭐⭐

```
池归还流程：
  ① mysql_reset_connection(conn)     ← 重置会话
  ② 检查连接是否有效（可选 mysql_ping）
  ③ 放回空闲队列

池借出流程：
  ① 从队列取一个
  ② 若 max_lifetime 到期 → 丢弃重建
  ③ mysql_ping 探活（或直接借出去，让第一次查询暴露问题）
  ④ 执行会话初始化（SET NAMES / sql_mode / time_zone）
  ⑤ 交给使用者
```

## 六、项目约定：哪些东西"不要"放进连接池 ⭐

| 约定 | 理由 |
|---|---|
| **不要用临时表** | 无法可靠清理 ⚠️ 用普通表 + 唯一标识隔离 |
| **不要用用户变量** | 无"全部重置"的手段 ⚠️ |
| **不要用 `GET_LOCK`** | 依赖池清理（虽然 `RELEASE_ALL_LOCKS` 可用）|
| **不要改 `sql_log_bin`** | 一旦残留 → 主从不一致 ❗ |
| **不要靠 `USE db`** | 一律用 `库名.表名` 或每次 `mysql_select_db` ⭐ |
| **不要长期 `SET GLOBAL`** | 影响所有连接（这是"全局污染"，更危险）⚠️ |
| **尽量不用 prepared statement 缓存** | 或明确接受 `reset_connection` 会清掉它 |
| **事务必须显式提交/回滚** | 用 RAII 保证 ⭐ |

## 七、C++ 侧的完整实现模板 ⭐⭐

```cpp
class MySqlPool {
public:
    class Guard {                      // ⭐ RAII：借出即守卫
        MySqlPool* pool_;
        MYSQL* conn_;
    public:
        Guard(MySqlPool* p, MYSQL* c) : pool_(p), conn_(c) {}
        ~Guard() {
            if (conn_) pool_->release(conn_);      // 异常也归还 ⭐
        }
        Guard(const Guard&) = delete;
        Guard& operator=(const Guard&) = delete;
        MYSQL* get() const { return conn_; }
        // 显式提前归还（避免长时间占用）
        void giveBack() { if (conn_) { pool_->release(conn_); conn_ = nullptr; } }
    };

    Guard acquire() {
        std::unique_lock<std::mutex> lk(mu_);
        cv_.wait(lk, [this]{ return !idle_.empty() || idle_.size() + busy_ < max_; });
        MYSQL* c = nullptr;
        if (!idle_.empty()) {
            c = idle_.back(); idle_.pop_back();
        } else {
            c = createConn();              // 新建（已做过一次初始化）
        }
        ++busy_;
        lk.unlock();

        // ⭐ 借出时再确保会话状态正确（双保险）
        initSession(c);
        return Guard(this, c);
    }

private:
    void initSession(MYSQL* c) {
        mysql_query(c, "SET NAMES utf8mb4");
        mysql_query(c, "SET SESSION sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,"
                       "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,"
                       "NO_ENGINE_SUBSTITUTION'");
        mysql_query(c, "SET SESSION time_zone = '+08:00'");
        mysql_query(c, "SET SESSION autocommit = 1");
        mysql_query(c, "SET SESSION sql_log_bin = 1");     // ⭐⭐ 防主从不一致
        mysql_query(c, "SET SESSION foreign_key_checks = 1");
        mysql_query(c, "SET SESSION unique_checks = 1");
        mysql_select_db(c, "blogdb");                       // ⭐ 固定库
    }

    void release(MYSQL* c) {
        // ① 收尾：确保没有未读完的结果集
        while (mysql_next_result(c) == 0) {
            if (MYSQL_RES* r = mysql_store_result(c)) mysql_free_result(r);
        }
        // ② ⭐ 重置会话（最干净）
        if (mysql_reset_connection(c) != 0) {
            // 重置失败 → 丢弃这个连接
            mysql_close(c);
            std::lock_guard<std::mutex> lk(mu_);
            --busy_; cv_.notify_one();
            return;
        }
        // ③ 探活（可选）
        if (mysql_ping(c) != 0) {
            mysql_close(c);
            std::lock_guard<std::mutex> lk(mu_);
            --busy_; cv_.notify_one();
            return;
        }
        // ④ 放回池
        std::lock_guard<std::mutex> lk(mu_);
        idle_.push_back(c);
        --busy_;
        cv_.notify_one();
    }
};
```

**注意 `mysql_reset_connection` 的行为** ⭐：它会重置会话变量、回滚事务、释放锁、清空临时表与用户变量、**并释放 prepared statements**。**如果应用依赖语句缓存，重置后它们会失效，需要重新 prepare**。

## 八、如何排查"会话污染"类 bug ⭐

**特征**：**偶发、不可复现、换个环境就好、重启就好** ⚠️

```sql
-- ① 在连接上打印当前会话状态（排查期加日志）
SELECT @@session.sql_mode, @@session.autocommit, @@session.time_zone,
       @@session.sql_log_bin, @@session.foreign_key_checks,
       DATABASE() AS cur_db,
       @@character_set_client, @@character_set_connection, @@character_set_results;

-- ② 检查有没有未提交事务
SELECT * FROM information_schema.innodb_trx
WHERE trx_mysql_thread_id = CONNECTION_ID();

-- ③ 检查有没有残留的用户变量（无法枚举，但可以针对性检查）
SELECT @x, @y;   -- 若从未设置过应返回 NULL
```

**排查思路** ⭐：

```
① "重启应用就好" → 池被重建 → 强烈暗示会话状态污染 ⭐
② "并发高时才出现" → 连接复用频繁 ⭐
③ 在连接借出/归还处加日志（打印 CONNECTION_ID + 关键会话状态）
④ 对比"出问题的连接"与"正常连接"的会话状态差异
```

## 九、一句话总结

**连接池复用会带来"会话状态污染"** —— 最危险的三类是 **`sql_mode=''`（静默改数据）、`sql_log_bin=0`（主从不一致 ❗）、`autocommit=0` + 未提交事务**；此外还有 **`USE db` 查错库、`SET time_zone` 时间错乱、临时表/用户变量/`GET_LOCK` 残留、未读完的结果集导致 `Commands out of sync`**；**最干净的解法是归还时 `mysql_reset_connection()`（重置一切且不断连接）**，**最健壮的做法是"归还重置 + 借出时再显式初始化关键会话变量"双保险** ⭐⭐；**项目约定上应避免使用临时表、用户变量、`USE db`、`SET sql_log_bin` 这类无法可靠清理的状态**。""",
    ),
    (
        "MySQL",
        "变更管理,DDL,上线流程",
        2,
        r"""数据库变更（加字段、改索引、数据订正）应该怎么管理？如何做到可回滚、可审计？""",
        r"""## 一、数据库变更的六类 ⭐

| 类型 | 例子 | 风险 |
|---|---|---|
| **DDL - 加列** | `ADD COLUMN`（8.0 可 INSTANT）| 低 ⭐ |
| **DDL - 加索引** | `ADD INDEX`（可 INPLACE）| 低~中 ⭐ |
| **DDL - 改列类型/字符集** | `MODIFY COLUMN`、`CONVERT TO` | **高（COPY，重建表）** ⚠️ |
| **DDL - 删列/删索引** | `DROP COLUMN`、`DROP INDEX` | **高（不可逆）** ⚠️ |
| **DML - 数据订正** | `UPDATE ... WHERE ...` | 中（可能改错数据）⚠️ |
| **DML - 数据迁移/归档** | 批量搬运 | 中~高 |

**核心原则** ⭐：

```
① 一切变更走流程（不允许"手工上生产"）
② 变更必须可审计（谁、何时、改了什么）
③ 危险变更必须有回滚方案 + 备份 ⭐
④ 大表 DDL 必须用在线工具，且限速 ⭐
⑤ 变更前后必须验证（不只是"没报错"）
```

## 二、DDL 的算法与锁（决定风险评估）⭐

```sql
ALTER TABLE posts ADD COLUMN x INT,
  ALGORITHM=INPLACE, LOCK=NONE;
-- ↑ 指定算法和锁级别（不满足会报错而不是静默降级）⭐
```

| 操作 | ALGORITHM | LOCK | 能否在线 |
|---|---|---|---|
| **加/删二级索引** | INPLACE | NONE | ✅ 不阻塞 ⭐ |
| **加列（末尾，8.0）** | INSTANT | NONE | ✅ 秒级 ⭐ |
| **改列默认值**（8.0）| INSTANT | NONE | ✅ |
| **重命名列**（8.0）| INPLACE | NONE | ✅ |
| **加/删主键** | COPY | SHARED | ❌ 重建表 ⚠️ |
| **改列类型** | COPY | SHARED | ❌ 重建表 ⚠️ |
| **改字符集/collation** | COPY | SHARED | ❌ 重建表 ⚠️ |
| **加全文索引** | INPLACE | SHARED | ⚠️ 阻塞写 |
| **`OPTIMIZE TABLE`** | INPLACE | NONE | ✅ 但耗 IO |

**关键** ⭐：**显式指定 `ALGORITHM` 和 `LOCK`** —— 这样如果实际操作会锁表，**MySQL 会直接报错**，而不是静默地把生产锁住 ⚠️

```sql
-- 如果 INPLACE + LOCK=NONE 不支持 → 报错
-- ERROR 1846 (0A000): ALGORITHM=INPLACE is not supported. Reason: ...
-- → 这时才改用 pt-osc / gh-ost ⭐
```

## 三、大表 DDL 的三种做法 ⭐⭐

### ① 原生 INSTANT（8.0，最快）⭐

```sql
-- 加列（末尾）：秒级完成，即使 1 亿行
ALTER TABLE orders ADD COLUMN channel VARCHAR(20) NULL DEFAULT NULL,
  ALGORITHM=INSTANT;
-- 限制：新列必须在末尾（8.0.29+ 支持任意位置）；
--       不支持 AUTO_INCREMENT；不支持同时加索引 ⭐
```

**不能 INSTANT 时** → 用 pt-osc / gh-ost。

### ② `pt-online-schema-change`（影子表 + 触发器）⭐

```bash
pt-online-schema-change \
  --alter "ADD COLUMN channel VARCHAR(20) NULL DEFAULT NULL" \
  --host=127.0.0.1 --user=root \
  --max-load      Threads_running=50 \
  --critical-load Threads_running=100 \
  --chunk-time    0.5 \
  --chunk-size    1000 \
  --print \
  --dry-run \
  D=blogdb,t=orders
# 去掉 --dry-run 才真正执行
```

**原理**：

```
① CREATE TABLE _orders_new LIKE orders;  （新结构）
② ALTER _orders_new ...（改结构）
③ 在主表上建 3 个触发器（INSERT/UPDATE/DELETE → 同步到新表）⚠️
④ 分批把老数据拷到新表（chunk）
⑤ RENAME TABLE orders TO _orders_old, _orders_new TO orders;  ← 原子替换
⑥ 删触发器和 _orders_old
```

**要点**：

| 要点 | 说明 |
|---|---|
| **要求表有主键/唯一索引** ⚠️ | 没有就没法分 chunk |
| **`--max-load` / `--critical-load`** ⭐ | 超过负载自动暂停/中止，保护线上 |
| **`--chunk-time`** | 控制每批耗时（避免长事务）|
| **需要额外磁盘** | 新表 + 老表并存 ⚠️ 约 1 倍表大小 |
| **触发器有写放大** ⚠️ | 每次写要同步到新表 |
| **与原表已有触发器冲突** ⚠️ | 不支持（或需 `--preserve-triggers`）|
| **外键** | 需 `--alter-foreign-keys-method` 谨慎处理 ⚠️ |

### ③ `gh-ost`（无触发器，从 binlog 同步）⭐⭐

```bash
gh-ost \
  --host=127.0.0.1 --user=root \
  --database=blogdb --table=orders \
  --alter="ADD COLUMN channel VARCHAR(20) NULL DEFAULT NULL" \
  --max-load="Threads_running=50" \
  --critical-load="Threads_running=100" \
  --chunk-size=1000 \
  --max-lag-millis=1500 \
  --initially-drop-ghost-table \
  --allow-on-master \
  --execute
```

**优势** ⭐：

| 优势 | 说明 |
|---|---|
| **无触发器** | 从 binlog 读变更，不影响主库写性能 ⭐ |
| **可随时暂停** | `--throttle` / 交互式暂停，出问题能立刻停 ⭐ |
| **限速精细** | `--max-lag-millis` 保证从库延迟可控 ⭐ |
| **可切换** | 支持 `--cut-over` 的多种策略 |
| **可测试** | `--test-on-replica` 在从库先演练 ⭐ |

**要求**：**binlog_format = ROW**，且 gh-ost 需要能连到一个从库（或用 `--allow-on-master`）。

**推荐**：**gh-ost 优于 pt-osc**（无触发器、可暂停）⭐

## 四、数据订正（DML）的规范 ⭐⭐

```sql
-- ❌ 危险操作（无 WHERE、无 LIMIT、无备份）
UPDATE users SET status = 0;                    -- 全表！❗
DELETE FROM logs WHERE created_at < '2023-01-01';  -- 可能几千万行

-- ✅ 规范做法
-- ① 先 SELECT 确认影响行数与内容 ⭐
SELECT COUNT(*) FROM users WHERE id BETWEEN 1 AND 1000 AND status <> 0;

-- ② 备份要改的数据（改错能恢复）⭐
CREATE TABLE users_bak_20240501 AS
SELECT * FROM users WHERE id BETWEEN 1 AND 1000;

-- ③ 分批执行 + 限速
UPDATE users SET status = 0 WHERE id BETWEEN 1 AND 1000 AND status <> 0 LIMIT 1000;
-- 循环到 affected_rows = 0，批间 sleep
```

**必做清单** ⭐：

```
□ 先在从库或测试环境验证 SQL 的影响行数 ⭐
□ 备份将被修改的数据（CREATE TABLE AS SELECT）⭐
□ 分批执行（LIMIT + 循环 + sleep）
□ 记录执行前后的行数与关键字段校验和 ⭐
□ 有明确的回滚 SQL（基于备份表）⭐
□ 变更时间在低峰期
□ 有人二次复核 SQL（`sql_safe_updates=ON` 防无 WHERE）⭐
```

**`sql_safe_updates`** ⭐：

```sql
SET SESSION sql_safe_updates = 1;
UPDATE users SET status = 0;
-- ERROR 1175: You are using safe update mode and you tried to update a table
--             without a WHERE that uses a KEY column
-- → 强制要求"WHERE 必须用索引列" ⭐ 这是很实用的护栏
```

**⚠️ 但注意**：`sql_safe_updates=1` 时会话级残留 → 连接池污染问题（见"会话变量"那题）。

## 五、变更管理流程 ⭐⭐

### 变更单模板

```
【变更标题】posts 表增加 channel 列
【变更类型】DDL - 加列
【影响范围】posts 表（约 500 万行）；只影响写入性能（短时）
【执行时间】2024-05-02 03:00（低峰）
【预估时长】INSTANT 模式，秒级
【变更 SQL】
  ALTER TABLE posts ADD COLUMN channel VARCHAR(20) NULL DEFAULT NULL,
    ALGORITHM=INSTANT;
【前置检查】
  □ 已确认 8.0 支持 INSTANT
  □ 磁盘剩余 > 1GB
  □ 无长事务（History list length < 1000）
  □ 主从延迟 < 1s
【回滚方案】
  ALTER TABLE posts DROP COLUMN channel;   -- ⚠️ 若已有数据写入会丢失
  → 前置备份：XtraBackup 全量 + binlog 保留
【验证方案】
  □ SHOW CREATE TABLE posts 确认列存在
  □ 应用写入/读取测试
  □ 监控 error log、慢查询、复制延迟 15 分钟
【审批】DBA / 技术负责人
```

### 执行流程 ⭐

```
① 变更申请（写 SQL + 影响评估 + 回滚方案）
② 二次复核（另一人 review SQL）⭐
③ 备份（大变更前必须）
   · 单表：CREATE TABLE bak AS SELECT / XtraBackup
   · 全库：XtraBackup
④ 在从库/测试环境先跑一遍（验证时长与影响）⭐
⑤ 生产执行（记录开始/结束时间、执行人）
⑥ 验证（不只是"没报错"，要验证业务功能）⭐
⑦ 观察（15~30 分钟，看监控）
⑧ 记录（变更单归档）
```

## 六、可审计性 ⭐

| 手段 | 说明 |
|---|---|
| **变更单系统** | 所有变更必须有单据（Yearning、Archery、Bytebase 等开源工具）⭐ |
| **SQL 审核工具** ⭐ | 自动检测"无 WHERE 的 UPDATE/DELETE"、"大表 COPY DDL"、"索引重复"等 |
| **`general_log` / `audit_log`** | 记录所有执行的 SQL（⚠️ general_log 开销大，审计用 audit_log 插件）|
| **binlog 作为"最终记录"** ⭐ | binlog 天然记录了所有数据变更（ROW 格式含前后镜像）→ 可追溯 |
| **`binlog2sql`** ⭐ | 从 binlog 生成"回滚 SQL"（把 UPDATE 反转）—— **数据订正的救星** |
| **操作留痕** | 谁的账号、什么时间、执行的 SQL（用独立账号，不用 root）⭐ |
| **配置文件版本化** | `my.cnf` 用 git 管理 ⭐ |

**`binlog2sql` 的用法** ⭐：

```bash
# 从 binlog 解析出"回滚 SQL"
python binlog2sql.py -h127.0.0.1 -uroot -p \
  -d blogdb -t users \
  --start-file='mysql-bin.000012' \
  --start-datetime='2024-05-01 10:00:00' \
  --stop-datetime='2024-05-01 10:05:00' \
  -B > rollback.sql          # -B 表示生成回滚语句 ⭐

# 确认无误后执行
mysql -uroot -p blogdb < rollback.sql
```

**这是误操作后的最实用工具**（比全库 PITR 更精确）⭐

## 七、开源变更管理工具 ⭐

| 工具 | 特点 |
|---|---|
| **Yearning** ⭐ | 国内流行；SQL 审核 + 工单 + 执行 + 回滚 |
| **Archery** | SQL 审计 + 查询 + 工单 + 慢日志分析 |
| **Bytebase** | 现代化、支持多数据库、GitOps 风格 ⭐ |
| **Goose / Flyway / Liquibase** | 代码化的 Migration（versioned SQL）⭐ |
| **gh-ost / pt-osc** | 大表在线 DDL |
| **binlog2sql** | 回滚 SQL 生成 |

**Migration 工具（Flyway/Liquibase/Goose）的价值** ⭐：

```
✔ 变更即代码（版本化、可 review、可 CI）
✔ 自动记录已应用的版本（schema_version 表）
✔ 支持重复执行（幂等）
✔ 环境一致（dev/test/prod 用同一套）
⚠️ 生成的 DDL 需要人工审查（避免 COPY 算法）⭐
```

## 八、本项目的实践建议 ⭐

```
情况：小站、运维简单、无专职 DBA

建议（低成本可落地）：
① 变更前必备份：
   mysqldump -u root -p --single-transaction --default-character-set=utf8mb4 \
     --routines --triggers --events blogdb > ~/bak/blogdb_$(date +%F_%H%M).sql
   ⚠️ 加 --default-character-set=utf8mb4（本项目踩过乱码坑）⭐

② 变更 SQL 先写成文件并纳入 git（tools/migrations/ 目录）⭐
   例：tools/migrations/20240502_add_channel.sql
   这样"变更即代码"，可 review、可追溯

③ 变更脚本要求：
   · 幂等（重复执行不报错）—— 用 information_schema 判断列/索引是否存在 ⭐
   · 带注释说明目的
   · 危险操作用 sql_safe_updates

④ 验证用 curl 而非截图（本项目铁律）⭐
   变更后：curl -s http://127.0.0.1:8080/api/... | 检查中文/字段
   需要时用 HEX() 验证字节 ⭐

⑤ 记录到 .workbuddy/memory/ 日志（本项目已有此习惯）⭐

⑥ 种子/初始化 SQL 保持幂等（tools/seed_questions.sql 已做到）⭐
```

**幂等 DDL 的写法** ⭐：

```sql
-- 加列（存在则跳过）
SET @exists := (SELECT COUNT(*) FROM information_schema.columns
                WHERE table_schema='blogdb' AND table_name='posts' AND column_name='channel');
SET @sql := IF(@exists = 0,
  'ALTER TABLE posts ADD COLUMN channel VARCHAR(20) NULL DEFAULT NULL',
  'SELECT ''column channel already exists'' AS msg');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 加索引（存在则跳过）
SET @exists := (SELECT COUNT(*) FROM information_schema.statistics
                WHERE table_schema='blogdb' AND table_name='posts' AND index_name='idx_channel');
-- 同上模式
```

## 九、一句话总结

**数据库变更管理 = "流程 + 工具 + 验证 + 回滚"**；**DDL 必须显式指定 `ALGORITHM`/`LOCK` 让不支持的场景直接报错**，大表用 **8.0 的 INSTANT → gh-ost → pt-osc** 这条优先级链 ⭐⭐；**DML 订正必须"先 SELECT 确认 → 备份被改数据 → 分批执行 → 记录前后校验和 → 准备回滚"**，并用 **`sql_safe_updates=1`** 做护栏；**可审计靠"变更单 + 独立账号 + binlog（必要时 `binlog2sql` 生成回滚 SQL）"**；**本项目的低成本落地方式是"变更 SQL 纳入 git + 幂等 + 备份 + 用 curl/HEX 验证"**。""",
    ),
    (
        "MySQL",
        "数据安全,RPO,高可靠",
        3,
        r"""如何做到"已提交的数据绝不丢失"（RPO = 0）？完整方案是什么？""",
        r"""## 一、先明确 RPO 与 RTO ⭐

| 术语 | 含义 | 决定因素 |
|---|---|---|
| **RPO**（Recovery Point Objective） | **能容忍丢多少数据**（时间维度）| 复制方式 + 刷盘策略 + 备份频率 |
| **RTO**（Recovery Time Objective） | **能容忍停多久** | 恢复方式 + 自动化程度 |

**"RPO = 0"的意思是：任何已向客户端确认成功的提交，都不能丢。** ⭐

## 二、丢数据的五个环节 ⭐⭐

```
客户端 ──① 网络──► MySQL Server ──② 事务提交──► 存储 ──③ 复制──► 从库
                                              ↓
                                          ④ 备份
                                              ↓
                                          ⑤ 人为误操作
```

| 环节 | 丢数据的场景 | 对策 |
|---|---|---|
| **① 网络** | 服务端已提交但应答丢失 → 客户端重试可能重复写（是"多"不是"丢"）| 幂等设计 ⭐ |
| **② 提交刷盘** ⭐ | `innodb_flush_log_at_trx_commit ≠ 1` 时，提交后断电丢 1s | **双 1** ⭐⭐ |
| **③ 复制** | 异步复制时，主库提交后立即故障 → 从库还没收到 | **半同步 / MGR** ⭐⭐ |
| **④ 备份** | 备份不完整 / 从未验证 / 与数据同机 | **物理备份 + 异地 + 定期演练** ⭐ |
| **⑤ 人为误操作** ⭐ | 误 `DELETE` / 误 `DROP` / 错误的数据订正 | binlog PITR + `binlog2sql` + 权限最小化 ⭐ |

**⚠️ 重要认知**：**"RPO = 0"最难的不是"防硬件故障"，而是"防人为误删"** ⭐ —— 硬件故障有复制和备份兜底，但**误删会立刻同步到从库**（复制是"忠实"的）⚠️

## 三、第一层：单机不丢（双 1）⭐⭐

```ini
[mysqld]
innodb_flush_log_at_trx_commit = 1   # redo 每次提交 fsync ⭐
sync_binlog = 1                      # binlog 每次提交 fsync ⭐
innodb_doublewrite = ON              # 防页撕裂（默认 ON）
```

**保证**：**服务进程崩溃、操作系统崩溃、断电，都不会丢已提交事务**（前提是磁盘本身不作假）。

**⚠️ 磁盘的"作假"** ⚠️：某些廉价 SSD / 云盘**不支持真正的写缓存刷盘**（`fsync` 只是假的）→ 断电仍可能丢。**企业级 SSD / 云盘要确认有掉电保护（PLP）**，否则双 1 也不保证 ⭐

**验证方法**：

```bash
# 用 fio 测试 fsync 是否真的落盘（需要掉电测试仪，一般靠厂商承诺）
# 至少确认:
SHOW VARIABLES LIKE 'innodb_flush_log_at_trx_commit';   -- 应为 1
SHOW VARIABLES LIKE 'sync_binlog';                       -- 应为 1
```

**代价** ⭐：**每次提交 2 次 fsync**（redo + binlog）→ 写入性能下降。用**组提交（group commit）** 缓解：并发越高，摊薄到每个事务的 fsync 成本越低。

## 四、第二层：复制不丢（半同步 / MGR）⭐⭐

### 异步复制的问题 ⭐

```
主库：提交 → 返回客户端 ✅
      binlog 异步发给从库
      若此时主库宕机 → 从库还没收到 → 【已确认的事务丢了】❌
```

**异步复制的 RPO ≠ 0**，取决于主库宕机时机，可能丢几毫秒到几秒的数据。

### 半同步复制（Semi-Sync）⭐

```sql
-- 主库
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';
SET GLOBAL rpl_semi_sync_master_enabled = 1;
SET GLOBAL rpl_semi_sync_master_timeout = 100000;   -- 100s 超时（微秒）
SET GLOBAL rpl_semi_sync_master_wait_for_slave_count = 1;  -- 至少 1 个从库确认

-- 从库
INSTALL PLUGIN rpl_semi_sync_slave SONAME 'semisync_slave.so';
SET GLOBAL rpl_semi_sync_slave_enabled = 1;
STOP SLAVE IO_THREAD; START SLAVE IO_THREAD;   -- 重载插件
```

**语义**：主库**至少等 N 个从库确认"已收到 binlog"** 后才向客户端返回成功。

**⚠️ 半同步的局限** ⭐：

| 局限 | 说明 |
|---|---|
| **"收到"≠"重放完"** | 从库收到 binlog 但还没执行 → 主库故障时新主可能还没这些数据 ⚠️（需要等从库追上才能切）|
| **超时降级** ⚠️ | 超时后**自动退化为异步**（否则主库被阻塞）→ 此时 RPO 又变成"可能丢" |
| **`AFTER_SYNC` vs `AFTER_COMMIT`** ⭐ | `AFTER_SYNC`（默认，5.7+）更安全：等 ack 后才向客户端确认提交 |
| **需要插件** | 云 RDS 通常已内置 |

**`AFTER_SYNC` 的语义** ⭐：

```
AFTER_COMMIT：先提交（客户端可见）→ 再等 ack → 若等不到，事务已提交但可能没传到从库 ⚠️
AFTER_SYNC ：先等 ack → 再提交 → 若等不到，就不提交（或超时降级）✅ 更安全
```

### MGR（组复制）⭐⭐

**Paxos 多数派确认** → **真正的 "RPO = 0"**（已确认提交的事务在多数派上都有）。

```sql
-- 关键配置（MGR 要求）
gtid_mode = ON
enforce_gtid_consistency = ON
binlog_checksum = NONE          # ⚠️ 必须，否则启动失败
log_slave_updates = ON
binlog_format = ROW
group_replication_group_name = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
group_replication_single_primary_mode = ON
group_replication_start_on_boot = OFF
group_replication_local_address = "10.0.0.1:33061"
group_replication_group_seeds = "10.0.0.1:33061,10.0.0.2:33061,10.0.0.3:33061"
```

**优势** ⭐：

| 优势 | 说明 |
|---|---|
| **强一致** | 多数派确认，**已提交的事务在多数派上都有** ✅ |
| **自动选主** | 不需要外部工具 ⭐ |
| **防脑裂** | 多数派机制天然防脑裂 ✅ |
| **RPO = 0** | 只要多数派存活，已确认的事务就不会丢 ✅ |

**限制** ⚠️：

```
· 表必须有主键
· 不支持外键（不可靠）
· 大事务被拒绝（group_replication_transaction_size_limit，默认 150MB）⚠️
· 跨机房延迟显著（多数派确认要跨网络往返）⚠️
· 写延迟比异步复制高
```

**三节点部署建议** ⭐：**同城三可用区（3 副本，可容忍 1 个故障）**；跨城部署要谨慎评估延迟。

### 云 RDS 高可用（最省事）⭐⭐

```
主实例 + 备实例（同/跨可用区）
· 同步/半同步复制（厂商实现）
· 故障自动切换（RTO 秒~分钟）
· 自动备份 + 时间点恢复
→ 通常已满足 RPO ≈ 0（厂商承诺的 SLA 里会写明）⭐
```

**⚠️ 要看清 SLA 条款**：有些云 RDS 的"高可用"是**异步复制**（仍可能丢数据）⚠️ 必须确认是同步或半同步。

## 五、第三层：备份（防灾难与误操作）⭐⭐

### 备份策略 ⭐

```
① 全量备份：每天 / 每周（XtraBackup 物理备份 ⭐）
② 增量备份：每小时（XtraBackup --incremental）⭐
③ binlog 连续备份：实时（用于 PITR）⭐
④ 异地备份：至少一份在不同地域 ⭐
⑤ 3-2-1 原则：3 份副本 / 2 种介质 / 1 份异地 ⭐
⑥ 保留策略：日备 7 天 / 周备 4 周 / 月备 12 月
⑦ 加密：备份含敏感数据
⑧ 不与数据库同机（否则一起坏）
```

### 关键：备份必须"验证可恢复"⭐⭐

```
❌ "备份任务成功执行了" ≠ "备份可用"
✅ 必须定期真实恢复一次并校验数据 ⭐

验证清单：
  □ 恢复到独立实例（不同端口/容器）
  □ 对比行数（关键表）
  □ 对比校验和（pt-table-checksum 或自研）
  □ 抽查最新数据是否存在（如最新一条订单）
  □ 启动应用连接测试库，跑冒烟测试 ⭐
  □ 记录恢复耗时（这就是你的 RTO）⭐
```

**推荐频率**：**每月至少一次完整恢复演练**；自动化（脚本 + 定时任务 + 结果通知）⭐

### binlog 保留 ⭐

```ini
[mysqld]
binlog_expire_logs_seconds = 604800      # 7 天（或更长，取决于"能回溯多久"）
max_binlog_size = 1G
```

**⚠️ 保留多久取决于"能容忍多晚发现误操作"**：如果误删是 3 天后才发现的，binlog 只留 7 天刚好够（但风险大）→ **关键业务建议留 14~30 天** ⭐

**同时要把 binlog 备份到异地** ⭐（本机的 binlog 会随实例一起故障）。

## 六、第四层：防误操作（最容易被忽略）⭐⭐

**为什么这一层最重要**：因为**误删会立刻同步到从库**（复制是忠实的），**RPO = 0 的复制也救不了你** ⚠️

| 手段 | 说明 |
|---|---|
| **权限最小化** ⭐⭐ | 应用账号**不给 `DROP`/`DELETE` 权限**（或只给特定表）；运维操作走独立账号 |
| **`sql_safe_updates = 1`** ⭐ | 禁止"无索引 WHERE 的 UPDATE/DELETE" |
| **禁止 `DELETE` 全表** | 用软删除 `deleted_at` ；或先 `SELECT` 确认 |
| **`super_read_only`** | 从库开启，任何账号（除复制线程）都不能写 ⭐ |
| **延迟从库** ⭐⭐ | **见下文（最有效的防线）** |
| **DDL 审核** | 禁止无备份的 `DROP TABLE` / `TRUNCATE` |
| **操作二次确认** | 生产执行前另一人复核 SQL |
| **备份"先备份再改"** | 数据订正前 `CREATE TABLE bak AS SELECT` ⭐ |
| **审计日志** | `audit_log` 插件记录所有操作 ⭐ |
| **`binlog2sql`** | 误操作后立刻生成回滚 SQL ⭐ |

### 延迟从库（Delayed Replica）⭐⭐⭐

**思路**：**让一个从库"故意慢 N 小时"** —— 主库误删后，这个从库还没重放到误操作，可以挽救 ⭐

```sql
-- 在专用从库上
CHANGE MASTER TO MASTER_DELAY = 10800;   -- 延迟 3 小时（单位秒）
-- 8.0.23+ 语法
CHANGE REPLICATION SOURCE TO SOURCE_DELAY = 10800;
START SLAVE;
```

**效果**：

```
T0: 主库误 DELETE 全表 ⚠️
T0: 立即同步到普通从库（也丢了）❌
T0: 延迟从库还有 3 小时的缓冲 —— 误操作还没重放到它 ✅

救火流程：
  ① 立刻 STOP SLAVE ON 延迟从库  ← ⭐ 关键！阻止它继续重放
  ② 从延迟从库导出误删前的数据
  ③ 恢复到主库（或直接把延迟从库提升为主库）⭐
  ④ 用 binlog2sql 精确回滚
```

**⚠️ 延迟从库必须能"及时刹住"** ⭐：误操作后要**第一时间停止它的复制**，否则等它重放到误操作就晚了一步。所以**必须有"误操作告警 → 立即停止延迟从库复制"的应急脚本** ⭐⭐

**这是"防人为误操作"最有效的技术手段**（成本低、效果显著）。

## 七、完整的 RPO = 0 方案 ⭐⭐

```
【单机层】
  ✔ innodb_flush_log_at_trx_commit = 1
  ✔ sync_binlog = 1
  ✔ 企业级 SSD / 有掉电保护的云盘 ⭐

【复制层】
  ✔ 半同步复制（master_wait_for_slave_count = 1）
     或 MGR（3 节点，多数派）⭐
  ✔ 云 RDS：确认是"同步/半同步高可用版" ⭐

【备份层】
  ✔ 每日 XtraBackup 全量 + 每小时增量
  ✔ binlog 实时备份（保留 14~30 天）
  ✔ 3-2-1 原则（异地）
  ✔ 每月恢复演练 ⭐

【防误操作层】
  ✔ 延迟从库（延迟 3~24h）⭐⭐
  ✔ 应用账号权限最小化
  ✔ sql_safe_updates / 软删除
  ✔ DDL 与 DML 变更流程（复核 + 备份）
  ✔ binlog2sql 应急回滚工具
  ✔ 误操作告警 + 自动停延迟从库的应急脚本 ⭐

【应用层】
  ✔ 幂等设计（防重试造成重复写）
  ✔ 关键操作留审计日志
  ✔ "数据可重建"的思路（写操作先进持久化日志/MQ）⭐
```

**"数据可重建"是终极方案** ⭐：

```
核心业务写操作：
  ① 先写持久化日志（Kafka / 高可靠 MQ）—— 这是"唯一真相"⭐
  ② 异步消费落库（DB 只是"物化视图"）
  ③ DB 挂了 → 用日志重放重建 ✅ RPO = 0

代价：架构复杂度高；适用于"数据价值极高"的场景（金融、计费）
```

## 八、RPO 与 RTO 的平衡 ⭐

| 方案 | RPO | RTO | 成本 |
|---|---|---|---|
| 单机 + 定时备份 | 分钟~小时 | 小时 | 低 ⭐ |
| 异步主从 | 秒~分钟 | 分钟 | 低 |
| 半同步主从 | ~秒 | 秒~分钟 | 中 |
| MGR 三节点 | **0** | 秒 | 中高 ⭐ |
| 云 RDS 高可用版 | 接近 0 | 秒~分钟 | 中 |
| 同城双活 | 0 | 秒 | 高 |
| 异地多活 | 0 | 秒 | 很高 |
| "数据可重建"架构 | **0** | 分钟 | 高 ⭐ |

**结论** ⭐：**对绝大多数业务，"半同步/MGR + 延迟从库 + 验证过的备份"就已经达到 RPO ≈ 0 且成本可控**；"异地多活"和"数据可重建"只在数据价值极高时才值得。

## 九、验证"真的 RPO = 0"的方法 ⭐

```
① 模拟故障演练（必须做）⭐
   · 主库 kill -9 → 观察数据是否丢
   · 主库断网 → 观察半同步超时降级行为
   · 断电测试（有条件时）
② 模拟误操作演练
   · 在测试库执行"误 DELETE" → 用延迟从库 + binlog2sql 恢复 ⭐
   · 记录恢复耗时（RTO）
③ 定期恢复演练
   · 恢复备份到独立实例并校验数据 ⭐
④ 监控与告警
   · Slave_IO/SQL_Running
   · 半同步状态（Rpl_semi_sync_master_status）
   · 延迟从库的 MASTER_DELAY 是否生效
   · 备份任务是否成功（且校验可恢复）⭐
```

**"没演练过的 RPO = 0 只是理论值"** ⭐

## 十、一句话总结

**RPO = 0 需要四层共同保证：单机"双 1"（+ 有掉电保护的磁盘）、复制"半同步或 MGR"、备份"物理全量 + binlog + 异地 + 每月恢复演练"、以及防误操作的"延迟从库 + 权限最小化 + 变更流程 + `binlog2sql`"** ⭐⭐；**最容易忽略也最重要的是"防人为误删"**（因为误删会立刻同步到从库，复制救不了你），**延迟从库（配合"误操作告警即停复制"的应急脚本）是最有效且成本最低的手段** ⭐；**最终必须以"演练"验证方案真实有效，而不是停留在纸面**。""",
    ),
    (
        "MySQL",
        "并行查询,派生表,8.0优化",
        3,
        r"""MySQL 8.0 有哪些查询优化上的重大改进？派生表、子查询、并行扫描分别有什么变化？""",
        r"""## 一、派生表合并（Derived Merge）⭐

**问题**：5.7 之前，**派生表（`FROM` 子句里的子查询）一律被物化成临时表** ⚠️

```sql
SELECT * FROM (SELECT id, title FROM posts WHERE status=1) AS t
WHERE t.id > 100;
-- 5.7 及之前：先建临时表存子查询结果（可能落磁盘 ⚠️），再查临时表
--             → 无法把外层条件 t.id > 100 下推到内层
```

**8.0 的改进** ⭐：

```
优化器会尝试把派生表"合并"（merge）到外层查询：
  SELECT * FROM posts WHERE status=1 AND id > 100;
  → 完全等价，且两个条件下推，索引可用 ✅
```

**控制**：

```sql
-- 阻止合并（强制物化，有时反而更快：子查询要被多次引用时）
SELECT /*+ NO_MERGE(t) */ * FROM (SELECT ...) t;
-- 强制合并
SELECT /*+ MERGE(t) */ * FROM (SELECT ...) t;
```

**什么时候物化反而更好** ⭐：

```
· 子查询被外层多次引用（如 JOIN 两次）
· 子查询里有聚合/GROUP BY（无法简单下推）
· 子查询结果集很小而外层很大
· 优化器估算合并后需要扫描很多行（合并反而更慢）
```

## 二、子查询优化：半连接（Semi-Join）⭐⭐

**问题**：5.5 之前，`IN` 子查询是"对外层每一行执行一次子查询" → O(n × m) ⚠️

```sql
SELECT * FROM posts p
WHERE p.author_id IN (SELECT id FROM users WHERE vip=1);
-- 老实现：对每篇 posts 执行一次子查询 → 灾难 ⚠️
```

**5.6+ 引入的半连接优化** ⭐：把 `IN`/`EXISTS` 子查询**改写为 JOIN**，然后从 5 种策略里选：

| 策略 | 说明 |
|---|---|
| **Table Pull-out** | 把子查询的表"拉出来"参与 JOIN（最优，能多用索引）⭐ |
| **Duplicate Weedout** | 用临时表去重 |
| **First Match** | 先找第一条匹配就返回（适合 `EXISTS`）⭐ |
| **Loose Scan** | 松散索引扫描（子查询表索引前导列有重复值时高效）⭐ |
| **Materialization** | 物化子查询结果 + 哈希查找 |
| **8.0 新增：Hash Join** | 无索引时用哈希表代替 BNL ⭐ |

**查看优化器选了哪种** ⭐：

```sql
EXPLAIN FORMAT=TREE SELECT ...;
-- 输出里会有：
--   -> Nested loop inner join
--   -> Filter: (p.author_id is not null)
--   -> FirstMatch ... (或 LooseScan / Materialize / DuplicateWeedout)
SHOW WARNINGS;      -- ⭐ 旧式 EXPLAIN 后跟 SHOW WARNINGS 能看到改写后的 SQL
```

**开关**：

```sql
SET optimizer_switch = 'semijoin=on,materialization=on,firstmatch=on,loosescan=on,duplicateweedout=on';
```

**⚠️ 什么时候半连接帮不上** ⚠️：

```
· NOT IN（反连接）的优化较弱（NOT EXISTS 通常更好）
· 子查询涉及聚合/窗口函数
· 子查询与外层有复杂关联
```

**所以实操建议** ⭐：**`IN` 和 `EXISTS` 在 5.6+ 里性能差异通常不大，先用 `EXPLAIN` 看优化器怎么做，不要盲目改写**。真正关键的是**索引**。

## 三、Hash Join（8.0.18+）⭐⭐

**背景**：**没有索引的等值 JOIN** 在 5.7 里只能用 **BNL（Block Nested Loop）**：

```
BNL 代价：把驱动表分批读入 join buffer，然后对每个被驱动表的行做内存比对
        ≈ (rows_driver / batch) × rows_driven  ⚠️ O(n×m)
```

**8.0 的 Hash Join** ⭐：

```
① 选较小的表作为"构建表"（build table）→ 在内存里建哈希表
② 扫描另一个表（probe table），用哈希查找匹配
③ 代价 ≈ O(rows_build) + O(rows_probe)  ← 线性！⭐
```

**效果对比**（无索引 JOIN）⭐：

| 数据量 | BNL | Hash Join |
|---|---|---|
| 1万 × 1万 | 很慢 | 秒级 ⭐ |
| 100万 × 100万 | 不可用 ❌ | 可接受 ✅ |

**控制 hint**：

```sql
SELECT /*+ HASH_JOIN(t1, t2) */ ...;       -- 强制 hash join
SELECT /*+ NO_HASH_JOIN(t1, t2) */ ...;    -- 禁止
SELECT /*+ NO_BNL(t1) */ ...;              -- 禁止 BNL
SET optimizer_switch = 'hash_join=off';
```

**⚠️ 但 Hash Join 不是万能** ⚠️：

```
· 只支持【等值】连接（不支持 <、> 等）
· 构建表太大放不下内存 → 会溢出到磁盘（性能下降）⚠️
· 对"有索引的等值 JOIN"，NLJ 通常仍更快 ✅
· 所以：Hash Join 是"无索引时的救命方案"，不是"有了它就不用建索引"❗
```

**一句话** ⭐：**Hash Join 解决的是"偶发的大表无索引 JOIN"和"临时分析查询"，生产 OLTP 路径上仍应以"连接列建索引 + NLJ"为主**。

## 四、平行查询（Parallel Query，8.0.14+）⭐

**背景**：MySQL 一直是"**单查询单线程**"（`SELECT` 不能并行扫描）→ 大表分析型查询很慢 ⚠️

**8.0 引入并行扫描** ⭐：

```sql
-- 查看
SHOW VARIABLES LIKE 'innodb_parallel_read_threads';    -- 默认 4
SHOW VARIABLES LIKE 'innodb_dedicated_server';

-- 会话级调整（可调大以加速大查询）
SET SESSION innodb_parallel_read_threads = 8;
```

**⚠️ 关键限制** ⭐⭐：

```
并行扫描只对【无索引的全表扫描 COUNT(*) / 全表扫描】生效
  · SELECT COUNT(*) FROM big_table;          ✅ 可并行
  · SELECT COUNT(*) FROM t WHERE ...;        ⚠️ 仅在能并行扫描时
  · 走索引的查询                              ❌ 不并行
  · JOIN、ORDER BY、GROUP BY                  ❌ 不并行（这些阶段仍是单线程）

→ 也就是说：**并行查询的能力非常有限**，别指望它替代"列存/MPP 分析库" ⭐
```

**判断是否用了并行** ⭐：

```sql
EXPLAIN FORMAT=TREE SELECT COUNT(*) FROM big_table;
-- 输出可能出现：
--   -> Parallel scan on big_table
--       -> Count rows
```

**适用场景** ⭐：**大表的 `COUNT(*)`、大表的全表扫描导入/校验**（如 `SELECT ... INTO OUTFILE`）。

**不适用**：复杂分析的 `GROUP BY` / `JOIN` / 排序（这些应该用 ClickHouse/Doris 或走从库/离线库）⭐

## 五、其他 8.0 的查询优化改进 ⭐

| 改进 | 说明 |
|---|---|
| **Index Skip Scan**（跳跃扫描）⭐ | 联合索引 `(a,b)` 下，`WHERE b=1`（缺 a）也能用索引：跳过 a 的不同值分别扫描 → 让"违反最左前缀"的查询也能用上索引 ✅ |
| **降序索引** | `CREATE INDEX idx (a ASC, b DESC)` 真正生效（5.7 语法接受但忽略）→ `ORDER BY a ASC, b DESC` 可用索引 ⭐ |
| **函数索引** | `CREATE INDEX idx ON t ((SUBSTRING(name,1,10)))` → 表达式查询可用索引 ⭐ |
| **不可见索引** | `ALTER TABLE t ALTER INDEX idx INVISIBLE` → 安全试错删索引 ⭐ |
| **`EXPLAIN ANALYZE`** ⭐ | 真实执行并给出"估算 vs 实际"，是排查优化器选错计划的利器 |
| **`EXPLAIN FORMAT=TREE`** | 树形展示，直观看到执行顺序与并行 |
| **直方图（Histogram）** ⭐ | `ANALYZE TABLE t UPDATE HISTOGRAM ON col` → 给无索引列提供分布信息，改善倾斜数据的估算 |
| **`optimizer_cost_model`** | 8.0 可切换代价模型（考虑 SSD/内存），比 5.7 更贴合现代硬件 ⭐ |
| **临时表引擎改为 InnoDB** | 8.0 默认 `internal_tmp_mem_storage_engine=TempTable`，比老 Memory 引擎更好（支持变长、更少落盘）⭐ |
| **CTE（含递归）** | 可读性 + 优化器对 CTE 有专门的处理 ⭐ |
| **窗口函数** | 那些"自连接 / 用户变量"的解法可以退休了 ⭐ |
| **`NOWAIT` / `SKIP LOCKED`** ⭐ | `FOR UPDATE SKIP LOCKED` 实现高并发任务队列 |
| **资源组** | CPU 亲和 + 优先级隔离 |
| **`SELECT ... FOR UPDATE OF tbl`** | 只锁指定表 |
| **优化器提示（Hint）体系** ⭐ | `/*+ ... */` 统一语法，支持 JOIN 顺序、算法、`SET_VAR` 等 |
| **`information_schema` 性能** | 改查数据字典，比 5.7 快很多 |

**Index Skip Scan 值得单独说** ⭐：

```sql
CREATE INDEX idx_ab ON t (a, b);
-- 5.7: WHERE b = 1  → 用不了索引（违反最左前缀）❌
-- 8.0: WHERE b = 1  → 可以"跳跃"扫描：跳过不同 a 值分别定位 b=1 ✅
--     条件是 a 的【不同值个数（基数）很少】（如 a 只有几个取值时才有收益）
EXPLAIN SELECT * FROM t WHERE b = 1;   -- 可能出现 "Using index for skip scan"
```

## 六、8.0 优化后的实践建议 ⭐

```
① 优先"建好索引"，而不是指望优化器变强 ⭐
   优化器的改进（Hash Join / Skip Scan / 派生表合并）是"兜底"
   但都不能替代正确的索引设计

② 善用新工具排查
   · EXPLAIN ANALYZE（看估算 vs 实际）⭐
   · EXPLAIN FORMAT=TREE（看执行结构）
   · 直方图（改善倾斜数据的估算）⭐

③ 用新特性简化 SQL
   · 窗口函数替代自连接/用户变量 ⭐
   · CTE 替代嵌套子查询
   · FOR UPDATE SKIP LOCKED 实现任务队列 ⭐

④ 谨慎使用优化器 hint
   · 优先"改 SQL / 加索引 / ANALYZE TABLE"
   · hint 是最后手段（把假设硬编码进 SQL）⭐

⑤ 大分析查询不要指望 MySQL 并行
   · 并行查询能力有限（只对全表扫描）
   · 报表/统计应该走"汇总表"或"列存分析库"（ClickHouse/Doris）⭐
```

## 七、一句话总结

**8.0 在查询优化上的三大质变是：① 派生表可合并（条件可下推）、② 无索引等值 JOIN 用 Hash Join（替代灾难性的 BNL）、③ 新增 Index Skip Scan（让违反最左前缀的查询也能用索引）** ⭐；但**"并行查询"的能力非常有限（只对全表扫描的 COUNT/读，不覆盖 JOIN/GROUP BY/ORDER BY）**，别指望它替代分析型数据库 ⚠️；**最实用的新工具是 `EXPLAIN ANALYZE` + 直方图 + `INVISIBLE` 索引** ⭐；**任何优化器改进都不能替代"正确的索引设计"**。""",
    ),
]
