export DESIGN_NICKNAME = top
export DESIGN_NAME     = top
export PLATFORM        = asap7

export SYNTH_HIERARCHICAL ?= False
export SYNTH_MINIMUM_KEEP_SIZE ?= 0

export VERILOG_FILES = main.sv
export SDC_FILE      = /eda/processor_ci_perf/constraints/openroad.sdc




export CORE_UTILIZATION       = 5
export PLACE_DENSITY          = 0.1

export SYNTH_HDL_FRONTEND = slang
export TNS_END_PERCENT    = 100