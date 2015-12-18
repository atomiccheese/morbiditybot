cmake_minimum_required(VERSION 2.8)
project(libmorbidcv)

find_package(OpenCV REQUIRED)

set(CMAKE_CXX_FLAGS "-std=c++11 -O3")
include_directories(${OpenCV_INCLUDE_DIR})
add_executable(morbidcv
    src/main.cpp)

target_link_libraries(morbidcv ${OpenCV_LIBS})
