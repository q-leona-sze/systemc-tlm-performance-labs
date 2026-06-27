cmake_minimum_required(VERSION 3.24)

project(project_at1_four_phase_memory_timing LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../../cmake/SCTLBuildOptions.cmake)
find_package(SystemC REQUIRED)

set(EXAMPLE_NAME project_at1_four_phase_memory_timing)

add_executable(${EXAMPLE_NAME}
  main.cpp
)

target_link_libraries(${EXAMPLE_NAME} PRIVATE SystemC::systemc)

include(../../../cmake/msvc.cmake)

sctl_enable_warnings(${EXAMPLE_NAME})
