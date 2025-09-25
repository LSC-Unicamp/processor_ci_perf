import argparse

from core.asic import run_asic_flow
from core.fpga import run_fpga_flow

DEFAULT_PROJECT_PATH = '/eda/processor_ci_perf'
DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'


def main() -> None:
    parser = argparse.ArgumentParser(description='Run FPGA or ASIC flow')
    parser.add_argument('--project', default=DEFAULT_PROJECT_PATH, help='Path to the project directory')
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH, help='Path to the config directory')
    parser.add_argument('--flow', choices=['fpga', 'asic'], required=True, help='Flow type to run')
    args = parser.parse_args()

    if args.flow == 'fpga':
        run_fpga_flow(
            'opensdrlab_kintex7',
            ['main.sv'],
            top_module='top',
            get_reports=True
        )
    else:
        run_asic_flow(
            'asap7',
            ['main.sv'],
            top_module='top',
            get_reports=True
        )


if __name__ == '__main__':
    main()
