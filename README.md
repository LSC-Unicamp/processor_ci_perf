# ProcessorCI Perf

[![Pylint](https://github.com/LSC-Unicamp/processor_ci_perf/actions/workflows/pylint.yml/badge.svg)](https://github.com/LSC-Unicamp/processor_ci_perf/actions/workflows/pylint.yml)
[![Python Code Format Check](https://github.com/LSC-Unicamp/processor_ci_perf/actions/workflows/blue.yml/badge.svg)](https://github.com/LSC-Unicamp/processor_ci_perf/actions/workflows/blue.yml)

ProcessorCI Perf drives synthesis and implementation-oriented performance flows
for ProcessorCI processor cores. It prepares FPGA and ASIC tool invocations,
selects board or PDK constraints, renders tool templates, and collects output
data needed to compare cores.

## Repository Layout

```text
processor_ci_perf/  Python package and CLI implementation
processor_ci_perf/core/ FPGA/ASIC flow implementation and shared definitions
constraints/      Board and OpenROAD constraint files
templates/        Tool command templates for Vivado, Gowin, Yosys, OpenROAD
main.py           Compatibility wrapper for the package CLI
scripts/          Local setup, OpenLane, and OpenROAD helper implementations
install.sh        Compatibility wrapper for scripts/install.sh
openlane.sh       Compatibility wrapper for scripts/openlane.sh
openroad.sh       Compatibility wrapper for scripts/openroad.sh
docs/             Flow and maintenance notes
requirements.txt  Python dependencies
```

## Installation

```bash
git clone https://github.com/LSC-Unicamp/processor_ci_perf.git
cd processor_ci_perf
python3 -m venv env
. env/bin/activate
pip install -r requirements.txt
```

Some flows require external EDA tools such as Vivado, Gowin, Yosys, OpenROAD,
OpenLane, or PDK-specific files. Install and license those tools separately.

## Quick Start

Show available options:

```bash
python main.py --help
```

Run a performance flow by selecting the flow type, technology or board, and
either explicit HDL files or a ProcessorCI config entry:

```bash
python main.py \
  -F fpga \
  -t <board_or_platform> \
  -c /path/to/config \
  -u \
  -I <processor_name>
```

Run with explicit source files instead of a config entry:

```bash
python main.py \
  -F asic \
  -t <pdk_or_technology> \
  -T <top_module> \
  -f rtl/core.sv rtl/memory.sv \
  -i rtl/include
```

Use the helper scripts only for the matching toolchain:

```bash
./openroad.sh
./openlane.sh
```

The canonical helper implementations live in `scripts/`; root shell scripts are
kept for existing workflows.

## Inputs

ProcessorCI Perf commonly uses:

- ProcessorCI JSON configuration files.
- `-F/--flow`, either `fpga` or `asic`.
- `-t/--technology`, the FPGA platform or ASIC technology/PDK name.
- HDL file lists and include directories from the selected processor config.
- Constraint files from `constraints/`.
- Tool templates from `templates/`.

## Outputs

Outputs depend on the selected backend. Expected artifacts include generated tool
project files, synthesis logs, timing/resource reports, and implementation
outputs from the selected FPGA or ASIC flow.

Keep generated tool output out of source directories when possible.

## Development

Keep CLI behavior reachable through `main.py`. Flow-specific implementation
belongs in `processor_ci_perf/core/fpga.py` or
`processor_ci_perf/core/asic.py`, while board/PDK constants should stay in the
corresponding definition modules.

See [docs/README.md](docs/README.md) for maintenance notes.

## Contributing

Issues and pull requests are welcome. When adding a board or backend, include
the constraint/template files and document the required external tools.

## License

See repository license and contribution files.
