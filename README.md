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
# 运行即可
./task_server
```

运行成功后通过https://localhost::8080访问网站




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

