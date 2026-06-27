cmake_minimum_required(VERSION 3.24)

project(project_at3_qos_sensitivity_sla LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../../cmake/SCTLBuildOptions.cmake)
find_package(SystemC REQUIRED)

set(EXAMPLE_NAME project_at3_qos_sensitivity_sla)

add_executable(${EXAMPLE_NAME}
  main.cpp
)

target_link_libraries(${EXAMPLE_NAME} PRIVATE SystemC::systemc)

include(../../../cmake/msvc.cmake)

sctl_enable_warnings(${EXAMPLE_NAME})
