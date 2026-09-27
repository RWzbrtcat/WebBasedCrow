# 1. 环境准备

> redhat/centos 环境


## 1.1 基础编译环境

```bash
sudo yum install build-essential cmake git
yum install epel-release
yum install libasio-dev
```

## 1.2 装crow

```bash
git clone https://github.com/CrowCpp/Crow.git
```

## 1.3 编译安装 crow

```bash
cd Crow
mkdir build
cd build
cmake .. -DCROW_BUILD_EXAMPLES=OFF
sudo make install
```

# 2. WebBasedCrow

- 主分支 - 任务管理器

- 子分支(dev-blog) - 博客网站（文章列表 / 详情 / 新建编辑 / 删除）

## 2.1 数据库准备

dev-blog 分支使用 `blogdb` 数据库，表名为 `posts`（启动时会自动建表）：

```sql
CREATE DATABASE IF NOT EXISTS blogdb DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 2.2 编译安装

```bash
cd build
cmake ..
make
```

编译后的可执行程序在task_server在项目根目录的`bin`子目录下:

```bash
# 进入子目录中
cd bin
# 通过环境变量指定数据库连接（不传则用默认值）
MYSQL_HOST=localhost MYSQL_USER=root MYSQL_PASSWORD=你的数据库密码 ./task_server
```

运行成功后通过 http://localhost:8080 访问网站。

首次启动（`admins` 表为空）时，会自动创建主管理员账号 `admin@localhost`，并**随机生成密码打印到控制台一次**，请立即登录并妥善保存。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_HOST` | `localhost` | 数据库地址 |
| `MYSQL_PORT` | `3306` | 数据库端口 |
| `MYSQL_USER` | `root` | 数据库账号 |
| `MYSQL_PASSWORD` | （空） | 数据库密码 |
| `MYSQL_DB` | `blogdb` | 数据库名 |

> 管理员账号与密码全部保存在数据库 `admins` 表中，密码使用「随机盐 + SHA2 哈希」存储，不存明文。




## 补充

### 1. 将 Crow 的源码合并到该仓库中


```bash
# 删除父仓库的指针记录（若还未git add，则不需要）
git rm --cached Crow

# 删除 Crow 内部的 .git 隐藏文件夹
rm -rf Crow/.git

# 重新将 Crow 文件夹添加为普通文件
git add Crow
```

