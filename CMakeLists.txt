# Build:   cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build
# Result:  build/heat
cmake_minimum_required(VERSION 3.16)
project(heat CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()
# -O2 and NO fused multiply-add, so every machine computes exactly the same numbers (project sheet, Part 1)
set(CMAKE_CXX_FLAGS_RELEASE "-O2")
add_compile_options(-ffp-contract=off -Wall -Wextra)

add_executable(heat src/main.cpp src/heat.cpp src/serial.cpp src/strips.cpp src/blocks.cpp)

find_package(MPI COMPONENTS CXX)
if(MPI_CXX_FOUND)
  target_compile_definitions(heat PRIVATE USE_MPI)
  target_link_libraries(heat PRIVATE MPI::MPI_CXX)
else()
  message(WARNING "MPI not found: building the serial version only")
endif()
