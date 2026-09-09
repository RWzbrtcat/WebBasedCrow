
cmake_minimum_required(VERSION 3.14)

project(TestManager)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找线程库
find_package(Threads REQUIRED)

# 查找 Mysql 数据库
find_path(MYSQL_INCLUDE_DIR mysql/mysql.h 
    PATHS 
        /usr/include/mysql
        /usr/local/include/mysql
        /usr/include/mariadb
        /usr/local/include/mariadb
        )

find_library(MYSQL_LIBRARY
    NAMES mysqlclient mysqlclient_r libmysql
    PATHS 
        /usr/lib/x86_64-linux-gnu
        /usr/lib64
        /usr/lib
        /usr/local/lib
        )

if (NOT MYSQL_INCLUDE_DIR OR NOT MYSQL_LIBRARY)
    message(FATAL_ERROR "找不到 mysql 数据库，请安装: sudo yum install libmysqlclient-dev")
endif()

# 编译
add_executable(task_server src/main.cpp)

# 链接库
target_include_directories(task_server PRIVATE ${MYSQL_INCLUDE_DIR})
target_link_libraries(task_server
    Crow::Crow
    ${MYSQL_LIBRARY}
    Threads:Threads
    )

# 把静态文件复制到构建目录，这样运行时能够找到
file(COPY static DESTINATION ${CMAKE_BINARY_DIR})


