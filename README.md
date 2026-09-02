# 环境准备

redhat 环境

```shell
# 1. 基础编译环境
sudo yum install build-essential cmake git

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
