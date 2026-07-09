# ProcessorCI Perf Documentation

## Flow Boundaries

ProcessorCI Perf coordinates implementation flows; it should not own processor
discovery, test execution, or trace comparison.

## Directory Semantics

- `processor_ci_perf/core/fpga.py`: FPGA flow behavior.
- `processor_ci_perf/core/asic.py`: ASIC flow behavior.
- `processor_ci_perf/core/board_defines.py`: board metadata.
- `processor_ci_perf/core/pdk_defines.py`: PDK metadata.
- `constraints/`: board and flow constraints.
- `templates/`: command/project templates rendered by the flows.
- `scripts/`: setup and backend helper shell scripts.

Root `main.py`, `install.sh`, `openlane.sh`, and `openroad.sh` are
compatibility wrappers.

## Adding A Target

When adding a new FPGA board or ASIC target:

1. Add target metadata to the relevant definition module.
2. Add constraint files under `constraints/`.
3. Add or update templates if the tool command structure changes.
4. Document required external tools and environment variables.
5. Run `python main.py --help` and the smallest possible dry run.

## Generated Output

Tool project files, reports, logs, bitstreams, and run directories should be
treated as generated artifacts. Prefer writing them to explicit build/output
directories rather than beside source files.
