cmake_minimum_required(VERSION 3.24)

project(systemc_tlm_architecture_performance_labs LANGUAGES CXX)

set(SCTL_CXX_STANDARD "17" CACHE STRING "C++ standard used to build the labs")
set_property(CACHE SCTL_CXX_STANDARD PROPERTY STRINGS 17 20 23)
set(CMAKE_CXX_STANDARD ${SCTL_CXX_STANDARD})
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(BUILD_LT_LABS "Build standalone LT labs" ON)
option(BUILD_AT_LABS "Build the AT-1 through AT-8 architecture performance labs" ON)
option(BUILD_RTL_REFERENCE "Build optional RTL/Verilator reference path" OFF)
option(SCTL_ENABLE_WARNINGS "Enable warnings for repository-owned targets" ON)

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(SCTLBuildOptions)

message(STATUS "SCTL_CXX_STANDARD: ${SCTL_CXX_STANDARD}")
message(STATUS "BUILD_LT_LABS: ${BUILD_LT_LABS}")
message(STATUS "BUILD_AT_LABS: ${BUILD_AT_LABS}")
message(STATUS "BUILD_RTL_REFERENCE: ${BUILD_RTL_REFERENCE}")

if(BUILD_AT_LABS)
    find_package(SystemC REQUIRED)
    add_subdirectory(examples/at)
else()
    message(STATUS "SystemC include dir: not requested (BUILD_AT_LABS=OFF)")
    message(STATUS "SystemC library: not requested (BUILD_AT_LABS=OFF)")
    message(STATUS "SystemC root / source: not requested (BUILD_AT_LABS=OFF)")
endif()

if(BUILD_LT_LABS)
    add_subdirectory(examples/lt/replay_cpp)
    add_subdirectory(examples/lt/banked_memory_controller_cpp)
endif()

if(BUILD_RTL_REFERENCE)
    add_subdirectory(examples/lt/rtl_banked_memory_controller)
endif()
