
cmake_minimum_required(VERSION 3.14)

project(TestManager)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找线程库
find_package(Threads REQUIRED)

# 查找 Mysql 数据库
find_path(MYSQL_INCLUDE_DIR 
    NAMES 
        mysql.h
        mysql/mysql.h 
    PATHS 
        /usr/include
        /usr/local/include
        /usr/include/mysql
        /usr/local/include/mysql
        /usr/include/mariadb
        /usr/local/include/mariadb
        /opt/mysql/include
        /opt/mysql/include/mysql
        )

find_library(MYSQL_LIBRARY
    NAMES 
        mysqlclient      # MySQL 标准库
        mysqlclient_r    # MySQL 线程安全版
        libmysql         # MySQL 替代名
        mariadb          # MariaDB
        libmariadb       # MariaDB 替代名
        libmysqlclient   # 某些发行版
    PATHS 
        /usr/lib
        /usr/lib64
        /usr/lib64/mysql
        /usr/local/lib
        /usr/local/lib64
        /usr/lib/x86_64-linux-gnu
        /usr/lib/aarch64-linux-gnu
        /usr/lib/arm-linux-gnueabihf
        /opt/mysql/lib
        /opt/mysql/lib64
        )

if (NOT MYSQL_INCLUDE_DIR OR NOT MYSQL_LIBRARY)
    message(FATAL_ERROR "找不到 mysql 数据库，请安装: sudo yum install mysql-devel")
endif()

# 指定输出目录
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)

# 编译
add_executable(task_server src/main.cpp)



# 添加 CROW 的子目录
add_subdirectory(${CMAKE_SOURCE_DIR}/Crow)

# 链接库
target_include_directories(task_server PRIVATE ${MYSQL_INCLUDE_DIR})
target_link_libraries(task_server
    Crow::Crow
    ${MYSQL_LIBRARY}
    ${CMAKE_THREAD_LIBS_INIT}
    )

# 把静态文件复制到构建目录，这样运行时能够找到
file(COPY static DESTINATION ${CMAKE_BINARY_DIR})


