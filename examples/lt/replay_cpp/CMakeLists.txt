cmake_minimum_required(VERSION 3.24)

project(lt_replay_cpp LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../../cmake/SCTLBuildOptions.cmake)

add_executable(replay_cpp
  src/main.cpp
  src/cli.cpp
  src/csv_reader.cpp
  src/trace_validator.cpp
  src/replay_model.cpp
  src/metrics.cpp
  src/csv_writer.cpp
)

target_include_directories(replay_cpp PRIVATE include)
sctl_enable_warnings(replay_cpp)
