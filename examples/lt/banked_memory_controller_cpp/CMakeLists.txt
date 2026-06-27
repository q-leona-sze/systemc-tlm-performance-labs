cmake_minimum_required(VERSION 3.24)

project(project_e_banked_memory_controller LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../../cmake/SCTLBuildOptions.cmake)

add_executable(banked_memory_controller
  src/main.cpp
  src/banked_memory_model.cpp
  src/cli.cpp
  src/csv.cpp
)

target_include_directories(banked_memory_controller PRIVATE include)
sctl_enable_warnings(banked_memory_controller)
