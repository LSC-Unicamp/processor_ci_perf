# main.py
import argparse
import json
import os
import sys

from core.asic import run_asic_flow
from core.fpga import run_fpga_flow
from core.log import print_blue, print_green, print_red, print_yellow
from core.processor_ci_internals import CONTROLLER_FILES, PROCESSOR_INTERNAL_FILES

INSTALL_DIR: str = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROJECT_PATH = '/eda/processor_ci_perf'
DEFAULT_CONFIG_PATH = '/eda/processor_ci/config'
PROCESSOR_CI_PATH = os.getenv('PROCESSOR_CI_PATH', '/eda/processor_ci')


def main() -> None:
    parser = argparse.ArgumentParser(description='Run FPGA or ASIC flow')
    parser.add_argument(
        '-F',
        '--flow',
        choices=['fpga', 'asic'],
        required=True,
        help='Flow type to run',
    )
    parser.add_argument(
        '-T', '--top', default='processorci_top', help='Top module name'
    )
    parser.add_argument(
        '-t',
        '--technology',
        required=True,
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

    if not args.technology:
        print_red('Error: Technology/PDK name is required.')
        sys.exit(1)

    if args.files and args.use_config:
        print_yellow(
            'Warning: Both project files and use-config flag are provided. Ignoring provided files and using config files.'
        )

    files = args.files if args.files else []
    top_module = args.top if args.top else 'processorci_top'
    include_dirs = args.include_dirs if args.include_dirs else []

    if args.use_config:
        config_data = {}
        with open(args.config, 'r', encoding='utf-8') as file:
            config_data = json.load(file)

            files = config_data.get('files', [])
            include_dirs = config_data.get('include_dirs', [])
            top_module = config_data.get('top_module', top_module)

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
