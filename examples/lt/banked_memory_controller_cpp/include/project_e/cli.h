#pragma once

#include "project_e/banked_memory_model.h"

namespace project_e {

ModelConfig parse_cli(int argc, char** argv);
void print_usage(const char* program);

}  // namespace project_e
