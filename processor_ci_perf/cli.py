# main.py
import argparse
import json
import os
import sys

from processor_ci_perf.core.asic import run_asic_flow
from processor_ci_perf.core.fpga import run_fpga_flow
from processor_ci_perf.core.log import print_blue, print_green, print_red, print_yellow
from processor_ci_perf.core.processor_ci_internals import CONTROLLER_FILES, PROCESSOR_INTERNAL_FILES

INSTALL_DIR: str = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT_PATH = '/eda/processor_ci_perf'
DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'
PROCESSOR_CI_PATH = os.getenv('PROCESSOR_CI_PATH', '/eda/processor_ci')

RVB_CORE_NAME = os.environ.get('RVB_CORE_NAME', None)
RVB_CORE_FOLDER = os.environ.get('RVB_CORE_FOLDER', None)
RVB_CORE_REPO = os.environ.get('RVB_CORE_REPO', None)
RVB_CORE_CONFIG = os.environ.get('RVB_CORE_CONFIG', None)
RVB_BENCH_ROOT = os.environ.get('RVB_BENCH_ROOT', None)
RVB_FLOW = os.environ.get('RVB_FLOW', None)
RVB_TECHNOLOGY = os.environ.get('RVB_TECHNOLOGY', None)



def main() -> None:
    running_from_rvbench = RVB_CORE_NAME is not None

    parser = argparse.ArgumentParser(description='Run FPGA or ASIC flow')
    parser.add_argument(
        '-F',
        '--flow',
        choices=['fpga', 'asic'],
        required=not running_from_rvbench,
        default=os.getenv("RVB_FLOW"),
        help='Flow type to run',
    )
    parser.add_argument(
        '-T', '--top', default='processorci_top', help='Top module name'
    )
    parser.add_argument(
        '-t',
        '--technology',
        required=not running_from_rvbench,
        default=os.getenv("RVB_TECHNOLOGY"),
        help='Technology/PDK name for ASIC flow or FPGA platform',
    )
    parser.add_argument(
        '-f', '--files', nargs='+', default=[], help='List of project files'
    )
    parser.add_argument(
        '-p',
        '--constraint',
        default='default',
        help='Constraint file name (default uses built-in constraints)',
    )
    parser.add_argument(
        '-c',
        '--config',
        default=DEFAULT_CONFIG_PATH,
        help='Path to the config directory',
    )
    parser.add_argument(
        '-u',
        '--use-config',
        action='store_true',
        help='Use default config files from config directory or use provided files',
    )
    parser.add_argument(
        '-r',
        '--reports',
        action='store_true',
        help='Generate reports after flow completion',
    )
    parser.add_argument(
        '-C',
        '--clean',
        action='store_true',
        help='Clean intermediate files after flow completion',
    )
    parser.add_argument(
        '-R', '--report-path', default='reports', help='Path to save reports'
    )
    parser.add_argument(
        '-P',
        '--processor-ci-path',
        default=PROCESSOR_CI_PATH,
        help='Path to the Processor CI directory',
    )
    parser.add_argument(
        '-U',
        '--use-pci-wrapper',
        action='store_true',
        help='Use Processor CI wrapper RTL files with available for this flow',
    )
    parser.add_argument(
        '-I',  # identifier of core
        '--core-id',
        type=str,
        required=False,
        help='Identifier of the core to use configuration from config directory',
    )
    parser.add_argument(
        '-i',  # include dirs
        '--include-dirs',
        nargs='+',
        default=[],
        help='List of directories to include in the flow',
    )

    args = parser.parse_args()
    
    if not args.flow:
        print_red("Error: flow not provided (use -F or RVB_FLOW).")
        sys.exit(1)

    if not args.technology:
        print_red('Error: Technology/PDK name is required.')
        print_red("Error: technology not provided (use -t or RVB_TECHNOLOGY).")
        sys.exit(1)

    if args.files and args.use_config:
        print_yellow(
            'Warning: Both project files and use-config flag are provided. Ignoring provided files and using config files.'
        )

    files = args.files if args.files else []
    top_module = args.top if args.top else 'processorci_top'
    include_dirs = args.include_dirs if args.include_dirs else []

    config_data = {}

    # Caso esteja rodando pelo RVBench
    if running_from_rvbench:
        if not RVB_CORE_CONFIG:
            print_red("Error: RVB_CORE_CONFIG not defined.")
            sys.exit(1)

        print_blue(f"[RVBench] Using core config: {RVB_CORE_CONFIG}")

        with open(RVB_CORE_CONFIG, "r", encoding="utf-8") as file:
            config_data = json.load(file)

        files = config_data.get("files", [])
        include_dirs = config_data.get("include_dirs", [])
        top_module = config_data.get("top_module", top_module)

    # modo manual antigo
    elif args.use_config:
        with open(args.config, "r", encoding="utf-8") as file:
            config_data = json.load(file)

        files = config_data.get("files", [])
        include_dirs = config_data.get("include_dirs", [])
        top_module = config_data.get("top_module", top_module)

    if args.use_pci_wrapper:
        top_module = 'fpga_top'

        controller_path = args.processor_ci_path.replace(
            'processor_ci', 'processor-ci-controller/'
        )

        for i in CONTROLLER_FILES:
            files.append(os.path.join(controller_path, i))

        for i in PROCESSOR_INTERNAL_FILES:
            files.append(os.path.join(args.processor_ci_path, i))

        if not args.core_id:
            print_red(
                'Error: Core ID is required when using Processor CI wrapper.'
            )
            sys.exit(1)

        files.append(
            os.path.join(args.processor_ci_path, f'rtl/{args.core_id}.sv')
        )

    if args.flow == 'fpga':
        run_fpga_flow(
            args.technology,
            files,
            top_module=top_module,
            get_reports=args.reports,
            clean=args.clean,
            report_path=args.report_path,
            include_dirs=include_dirs,
        )
    else:
        run_asic_flow(
            args.technology,
            files,
            top_module=top_module,
            get_reports=args.reports,
            clean=args.clean,
            report_path=args.report_path,
            include_dirs=include_dirs,
        )


if __name__ == '__main__':
    main()
