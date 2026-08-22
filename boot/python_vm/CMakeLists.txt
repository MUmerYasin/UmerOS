# CMakeLists.txt - UmerOS Python VM Build System
#
# Usage:
#   mkdir build && cd build
#   cmake .. -G "Unix Makefiles"
#   make
#
# Or with MinGW:
#   cmake .. -G "MinGW Makefiles"
#   mingw32-make

cmake_minimum_required(VERSION 3.10)
project(umeros_python C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Version
set(UMEROS_PYTHON_VERSION_MAJOR 3)
set(UMEROS_PYTHON_VERSION_MINOR 14)
set(UMEROS_PYTHON_VERSION_PATCH 0)
set(UMEROS_PYTHON_BUILD "UmerOS")

# Compiler flags
if(MSVC)
    add_compile_definitions(_CRT_SECURE_NO_WARNINGS)
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        add_compile_options(/W4 /Od /Zi /MDd /DDEBUG)
    else()
        add_compile_options(/W4 /O2 /DNDEBUG)
    endif()
else()
    if(CMAKE_BUILD_TYPE STREQUAL "Debug")
        add_compile_options(-Wall -Wextra -Wpedantic -g -O0 -DDEBUG)
    else()
        add_compile_options(-Wall -Wextra -Wpedantic -O2 -DNDEBUG)
    endif()
endif()

# Source files
set(VM_SOURCES
    Objects/object.c
    Objects/long.c
    Objects/float.c
    Objects/unicode.c
    Objects/bool.c
    Objects/none.c
    Objects/errors.c
    Builtins/builtins.c
    Compiler/compiler.c
    VM/vm.c
    Programs/main.c
)

# Create executable
add_executable(umeros_python ${VM_SOURCES})

target_include_directories(umeros_python PRIVATE Include)

# Platform-specific settings
if(UNIX)
    target_link_libraries(umeros_python m)
    install(TARGETS umeros_python DESTINATION bin)
endif()

if(WIN32)
    target_link_libraries(umeros_python)
    install(TARGETS umeros_python DESTINATION bin)
endif()

# Generate compile_commands.json for IDE
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
