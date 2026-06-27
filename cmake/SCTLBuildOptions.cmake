include_guard(GLOBAL)

list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}")

# Keep independently configured labs on the same language baseline as the
# repository root.  The cache value intentionally accepts newer standards for
# compatibility smoke builds without making them the default requirement.
set(SCTL_CXX_STANDARD "17" CACHE STRING "C++ standard used to build the labs")
set_property(CACHE SCTL_CXX_STANDARD PROPERTY STRINGS 17 20 23)
set(CMAKE_CXX_STANDARD "${SCTL_CXX_STANDARD}")
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT DEFINED SCTL_ENABLE_WARNINGS)
  option(SCTL_ENABLE_WARNINGS "Enable warnings for repository-owned targets" ON)
endif()

function(sctl_enable_warnings target_name)
  if(NOT SCTL_ENABLE_WARNINGS)
    return()
  endif()

  if(MSVC)
    target_compile_options(${target_name} PRIVATE /W4)
  else()
    target_compile_options(${target_name} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
endfunction()
