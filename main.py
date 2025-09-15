import argparse
from core.fpga import run_fpga_flow
from core.asic import run_asic_flow

DEFAULT_PROJECT_PATH = '/eda/processor_ci_perf'
DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'


def main() -> None:
    run_fpga_flow('colorlight_i9', ['main.sv'], top_module='top')
    print('Hello, World!')


if __name__ == '__main__':
    main()
