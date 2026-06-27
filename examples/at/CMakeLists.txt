cmake_minimum_required(VERSION 3.24)

project(systemc_tlm_at_architecture_labs LANGUAGES CXX)

include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/SCTLBuildOptions.cmake)
find_package(SystemC REQUIRED)

set(EXAMPLE_NAME at)

file(GLOB_RECURSE systemc_sources systemc/src/*.cpp)

add_executable(${EXAMPLE_NAME} ${systemc_sources})

target_include_directories(${EXAMPLE_NAME} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/systemc/include
)
target_link_libraries(${EXAMPLE_NAME} PRIVATE SystemC::systemc)
sctl_enable_warnings(${EXAMPLE_NAME})

include(../../cmake/msvc.cmake)

function(sctl_add_at_target target_name source_file)
    add_executable(${target_name} ${source_file})
    target_link_libraries(${target_name} PRIVATE SystemC::systemc)
    sctl_enable_warnings(${target_name})
endfunction()

sctl_add_at_target(project_at4_cache_mshr_pressure project_at4_cache_mshr_pressure.cpp)
sctl_add_at_target(project_at5_backpressure_qos_collapse project_at5_backpressure_qos_collapse.cpp)
sctl_add_at_target(project_at6_heterogeneous_soc_fabric project_at6_heterogeneous_soc_fabric.cpp)
sctl_add_at_target(project_at7_gpu_like_throughput_saturation project_at7_gpu_like_throughput_saturation.cpp)
sctl_add_at_target(project_at8_amba_noc_qos_coherency_boundary project_at8_amba_noc_qos_coherency_boundary.cpp)

add_subdirectory(four_phase_memory_timing)
add_subdirectory(multi_initiator_arbitration)
add_subdirectory(qos_sensitivity_sla)
