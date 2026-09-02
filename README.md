# 环境准备

redhat 环境

```bash
# 1. 基础编译环境
sudo yum install build-essential cmake git
yum install epel-release
yum install libasio-dev

# 2. 装crow

git clone https://github.com/CrowCpp/Crow.git

# 3. 编译安装 crow

cd Crow
mkdir build
cd build
cmake .. -DCROW_BUILD_EXAMPLES=OFF
sudo make install

```

# WebBasedCrow

通过开源Crow做的网页



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

