// SPDX-License-Identifier: Apache-2.0

#include "at_lab.h"

int sc_main(int, char **)
{
    at_lab::PhaseTrace trace("phase_trace.csv");
    at_lab::Top top("top", trace);

    sc_core::sc_start();

    return 0;
}
