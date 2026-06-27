cmake_minimum_required(VERSION 3.24)

project(project_at2_multi_initiator_arbitration LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../../cmake/SCTLBuildOptions.cmake)
find_package(SystemC REQUIRED)

set(EXAMPLE_NAME project_at2_multi_initiator_arbitration)

add_executable(${EXAMPLE_NAME}
  main.cpp
)

target_link_libraries(${EXAMPLE_NAME} PRIVATE SystemC::systemc)

include(../../../cmake/msvc.cmake)

sctl_enable_warnings(${EXAMPLE_NAME})
