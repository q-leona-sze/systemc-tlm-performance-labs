include_guard(GLOBAL)

# Repository-owned SystemC resolver.  It accepts a CMake package configuration
# when present, then falls back to a header/library pair from documented
# prefixes.  Every repository target links the resulting SystemC::systemc
# target rather than resolving a library independently.

set(_SystemC_PREFIX_HINTS)

foreach(_SystemC_ROOT_VAR SYSTEMC_ROOT SYSTEMC_HOME USER_SYSTEMC_ROOT)
  if(DEFINED ${_SystemC_ROOT_VAR} AND NOT "${${_SystemC_ROOT_VAR}}" STREQUAL "")
    list(APPEND _SystemC_PREFIX_HINTS "${${_SystemC_ROOT_VAR}}")
  endif()
  if(DEFINED ENV{${_SystemC_ROOT_VAR}} AND NOT "$ENV{${_SystemC_ROOT_VAR}}" STREQUAL "")
    list(APPEND _SystemC_PREFIX_HINTS "$ENV{${_SystemC_ROOT_VAR}}")
  endif()
endforeach()

if(SystemC_DIR)
  get_filename_component(_SystemC_DIR_PREFIX "${SystemC_DIR}/../../.." ABSOLUTE)
  list(APPEND _SystemC_PREFIX_HINTS "${_SystemC_DIR_PREFIX}")
endif()

if(DEFINED ENV{HOME} AND NOT "$ENV{HOME}" STREQUAL "")
  list(APPEND _SystemC_PREFIX_HINTS
    "$ENV{HOME}/local/systemc"
    "$ENV{HOME}/local/systemc-3.0.2"
  )
endif()

list(APPEND _SystemC_PREFIX_HINTS /usr/local /opt/systemc)
list(REMOVE_DUPLICATES _SystemC_PREFIX_HINTS)

# Prefer an upstream package configuration when it already exports the target
# name used by this repository. NO_MODULE prevents this module from recursing.
if(NOT TARGET SystemC::systemc)
  find_package(SystemC CONFIG QUIET NO_MODULE)
endif()

set(_SystemC_CONFIG_TARGET "")
foreach(_SystemC_TARGET_CANDIDATE SystemC::systemc SystemC systemc)
  if(TARGET ${_SystemC_TARGET_CANDIDATE})
    set(_SystemC_CONFIG_TARGET "${_SystemC_TARGET_CANDIDATE}")
    break()
  endif()
endforeach()

if(_SystemC_CONFIG_TARGET)
  if(NOT TARGET SystemC::systemc)
    add_library(SystemC::systemc ALIAS ${_SystemC_CONFIG_TARGET})
  endif()

  get_target_property(SystemC_INCLUDE_DIR SystemC::systemc INTERFACE_INCLUDE_DIRECTORIES)
  get_target_property(SystemC_LIBRARY SystemC::systemc IMPORTED_LOCATION)
  if(SystemC_LIBRARY STREQUAL "SystemC_LIBRARY-NOTFOUND")
    set(SystemC_LIBRARY "provided by SystemC CMake package")
  endif()
  set(SystemC_DISCOVERY_SOURCE "SystemC CMake package: ${SystemC_DIR}")
  set(SystemC_FOUND TRUE)
else()
  set(_SystemC_INCLUDE_HINTS)
  set(_SystemC_LIBRARY_HINTS)

  if(DEFINED USER_SYSTEMC_INCLUDE_DIR AND NOT "${USER_SYSTEMC_INCLUDE_DIR}" STREQUAL "")
    list(APPEND _SystemC_INCLUDE_HINTS "${USER_SYSTEMC_INCLUDE_DIR}")
  endif()
  if(DEFINED USER_SYSTEMC_LIB_DIR AND NOT "${USER_SYSTEMC_LIB_DIR}" STREQUAL "")
    list(APPEND _SystemC_LIBRARY_HINTS "${USER_SYSTEMC_LIB_DIR}")
  endif()

  foreach(_SystemC_PREFIX IN LISTS _SystemC_PREFIX_HINTS)
    list(APPEND _SystemC_INCLUDE_HINTS "${_SystemC_PREFIX}" "${_SystemC_PREFIX}/include")
    list(APPEND _SystemC_LIBRARY_HINTS
      "${_SystemC_PREFIX}"
      "${_SystemC_PREFIX}/lib"
      "${_SystemC_PREFIX}/lib64"
      "${_SystemC_PREFIX}/lib-linux64"
    )
  endforeach()

  # The three names cover the canonical SystemC header, the legacy .h header,
  # and the TLM header installed beside them.
  find_path(SystemC_INCLUDE_DIR
    NAMES systemc systemc.h tlm
    HINTS ${_SystemC_INCLUDE_HINTS}
    PATH_SUFFIXES include
  )
  find_library(SystemC_LIBRARY
    NAMES systemc libsystemc libsystemc.a libsystemc.so libsystemc.dylib
    HINTS ${_SystemC_LIBRARY_HINTS}
    PATH_SUFFIXES lib lib64 lib-linux64
  )

  include(FindPackageHandleStandardArgs)
  set(SystemC_NOT_FOUND_MESSAGE
    "SystemC not found. The primary target is SystemC 3.0.2. Set SYSTEMC_ROOT or SYSTEMC_HOME to its install prefix, or provide USER_SYSTEMC_INCLUDE_DIR and USER_SYSTEMC_LIB_DIR. See README.md for a no-sudo installation example."
  )
  find_package_handle_standard_args(SystemC
    REQUIRED_VARS SystemC_INCLUDE_DIR SystemC_LIBRARY
    REASON_FAILURE_MESSAGE "${SystemC_NOT_FOUND_MESSAGE}"
  )

  if(SystemC_FOUND)
    find_package(Threads QUIET)
    add_library(SystemC::systemc UNKNOWN IMPORTED GLOBAL)
    set_target_properties(SystemC::systemc PROPERTIES
      IMPORTED_LOCATION "${SystemC_LIBRARY}"
      INTERFACE_INCLUDE_DIRECTORIES "${SystemC_INCLUDE_DIR}"
    )
    if(TARGET Threads::Threads)
      set_property(TARGET SystemC::systemc APPEND PROPERTY
        INTERFACE_LINK_LIBRARIES Threads::Threads
      )
    endif()
    set(SystemC_DISCOVERY_SOURCE "manual header/library discovery")
  endif()
endif()

if(SystemC_FOUND)
  if(NOT TARGET systemc)
    add_library(systemc ALIAS SystemC::systemc)
  endif()
  message(STATUS "SystemC include dir: ${SystemC_INCLUDE_DIR}")
  message(STATUS "SystemC library: ${SystemC_LIBRARY}")
  message(STATUS "SystemC root / source: ${SystemC_DISCOVERY_SOURCE}")
endif()
