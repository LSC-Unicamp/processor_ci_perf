import os
import re
import csv
import json
from core import ImplementationFlow
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from jinja2 import Environment, FileSystemLoader
from core import run_cmd, write_template_to_file
from core.log import print_blue, print_red, print_green, print_yellow
from core import TEMPLATES_DIR, CONSTRAINTS_DIR
from core.board_defines import (
    DEFINES_BY_BOARD,
    SUPPORTED_BOARDS,
    VIVADO_BOARDS,
    YOSYS_BOARDS,
    GOWIN_BOARDS,
)

TOOLCHAINS_INSTALL_PATH = {
    'vivado': os.getenv('VIVADO_INSTALL_PATH', ''),
    'yosys': os.getenv('YOSYS_INSTALL_PATH', ''),
    'gowin': os.getenv('GOWIN_INSTALL_PATH', ''),
}


# -------------------------
# Helpers
# -------------------------
def write_defines(
    board_name: str, filename: str = 'processor_ci_defines.vh'
) -> None:
    if board_name not in DEFINES_BY_BOARD:
        raise ValueError(f"Board '{board_name}' not found.")

    with open(filename, 'w') as f:
        f.write(DEFINES_BY_BOARD[board_name])

    print_green(f"File '{filename}' generated for board: '{board_name}'.")


# -------------------------
# Vivado Flow
# -------------------------
class VivadoFlow(ImplementationFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Vivado flow for board: '{self.technology}'")

        constraints: str = (
            f'{CONSTRAINTS_DIR}/{self.technology}.xdc'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file)
        )

        context: Dict[str, Any] = {
            'files': self.project_files,
            'constraints': constraints,
            'top_module': self.top_module,
            'fpga_part': VIVADO_BOARDS[self.technology]['part'],
            'prefix': VIVADO_BOARDS[self.technology]['prefix'],
        }

        write_template_to_file(
            self.env, 'vivado.j2', context, 'vivado_project.tcl'
        )
        os.makedirs('reports', exist_ok=True)
        print_green(f"Vivado project files generated for '{self.technology}'")

    def run_tool(self) -> None:
        vivado_path = TOOLCHAINS_INSTALL_PATH.get('vivado', '')
        vivado_bin = os.path.join(vivado_path, 'vivado') or 'vivado'

        run_cmd(
            [
                vivado_bin,
                '-mode',
                'batch',
                '-nolog',
                '-nojournal',
                '-source',
                'vivado_project.tcl',
            ]
        )

    def clean(self) -> None:
        run_cmd(
            [
                'rm',
                '-rf',
                'build',
                'reports',
                '*.jou',
                '*.log',
                '.Xil',
                '*.bit',
            ]
        )

    def report(self, report_path: str = 'reports') -> None:
        timing_file = os.path.join(
            report_path, f'{self.technology}_timing.rpt'
        )
        util_file_xml = os.path.join(
            report_path, f'{self.technology}_utilization.xml'
        )
        csv_file = os.path.join(report_path, f'{self.technology}_report.csv')

        # --- PARSE DESIGN TIMING SUMMARY for WNS ---
        wns_ns = 0.0
        if os.path.exists(timing_file):
            with open(timing_file, 'r') as f:
                content = f.read()
                # WNS é o primeiro número da tabela de Design Timing Summary
                wns_match = re.search(
                    r'^\s*([-+]?[0-9]*\.?[0-9]+)\s+[-+]?[0-9]*\.?[0-9]+',
                    content,
                    re.MULTILINE,
                )
                if wns_match:
                    try:
                        wns_ns = float(wns_match.group(1))
                    except ValueError:
                        wns_ns = 0.0

        # --- PARSE CLOCK SUMMARY and calculate FMAX using WNS ---
        fmax: Dict[str, float] = {}
        if os.path.exists(timing_file):
            with open(timing_file, 'r') as f:
                content = f.read()
                # Regex para pegar Clock e Period(ns)
                clock_matches = re.findall(
                    r'^\s*(\S+)\s+\{[^\}]*\}\s+([0-9]*\.?[0-9]+)\s+[0-9]*\.?[0-9]+\s*$',
                    content,
                    re.MULTILINE,
                )
                for clk, period_str in clock_matches:
                    try:
                        period_ns = float(period_str)
                        effective_period = period_ns - wns_ns
                        if effective_period > 0:
                            fmax[clk] = 1000.0 / effective_period  # MHz
                    except ValueError:
                        continue

        # --- PARSE RESOURCE UTILIZATION XML ---
        resources: Dict[str, int] = {}
        if os.path.exists(util_file_xml):
            tree = ET.parse(util_file_xml)
            root = tree.getroot()

            for section in root.findall('.//section'):
                for table in section.findall('.//table'):
                    for row in table.findall('tablerow'):
                        cells = row.findall('tablecell')
                        if not cells:
                            continue
                        instance_name = cells[0].attrib.get('contents', '')
                        if instance_name != 'top':
                            continue  # pegar apenas o total do design
                        # mapeia colunas para recursos
                        res_map = {
                            'Total LUTs': int(
                                cells[2].attrib.get('contents', '0')
                            ),
                            'Logic LUTs': int(
                                cells[3].attrib.get('contents', '0')
                            ),
                            'LUTRAMs': int(
                                cells[4].attrib.get('contents', '0')
                            ),
                            'SRLs': int(cells[5].attrib.get('contents', '0')),
                            'FFs': int(cells[6].attrib.get('contents', '0')),
                            'RAMB36': int(
                                cells[7].attrib.get('contents', '0')
                            ),
                            'RAMB18': int(
                                cells[8].attrib.get('contents', '0')
                            ),
                            'DSP Blocks': int(
                                cells[9].attrib.get('contents', '0')
                            ),
                        }
                        resources.update(res_map)
                        break  # achou "top", não precisa mais

        # --- PRINT FLOW SUMMARY ---
        print_blue('=' * 60)
        print_blue(f' Vivado Flow Summary for board: {self.technology}')
        print_blue('=' * 60)

        # FMAX
        print_green('\nClock Frequency (Fmax):')
        if fmax:
            for clk, freq in fmax.items():
                print(f'  {clk:<20} {freq:8.2f} MHz')
        else:
            print_yellow('  No clock info found.')

        # RESOURCE USAGE
        print_green('\nResource Utilization (top-level):')
        print(f"{'Resource':<15} {'Used':>8}")
        print('-' * 30)
        for res, used in resources.items():
            print(f'{res:<15} {used:8}')

        print_blue('=' * 60)
        print_green('Flow summary generated successfully')

        # --- WRITE CSV ---
        with open(csv_file, 'w', newline='') as csvf:
            writer = csv.writer(csvf)
            writer.writerow(['Type', 'Name', 'Value'])
            # FMAX
            for clk, freq in fmax.items():
                writer.writerow(['FMAX (MHz)', clk, f'{freq:.2f}'])
            # Resources
            for res, used in resources.items():
                writer.writerow(['Resource', res, str(used)])

        print_green(f'CSV summary saved to: {csv_file}')


# -------------------------
# Yosys Flow
# -------------------------
class YosysFlow(ImplementationFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Yosys flow for board: '{self.technology}'")

        output_json: str = (
            f"build/{YOSYS_BOARDS[self.technology]['prefix']}.synth.json"
        )
        context: Dict[str, Any] = {
            'files': self.project_files,
            'top_module': self.top_module,
            'output_json': output_json,
        }

        write_template_to_file(
            self.env, 'yosys.j2', context, 'yosys_project.tcl'
        )
        os.makedirs('build', exist_ok=True)
        print_green(f"Yosys project files generated for '{self.technology}'")

    def run_tool(self) -> None:
        prefix: str = YOSYS_BOARDS[self.technology]['prefix']
        lpf_file: str = (
            f'{CONSTRAINTS_DIR}/{self.technology}.lpf'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file)
        )

        yosys_path = TOOLCHAINS_INSTALL_PATH.get('yosys', '')

        yosys_bin = os.path.join(yosys_path, 'synlig') or 'synlig'
        nextpnr_bin = (
            os.path.join(yosys_path, 'nextpnr-ecp5') or 'nextpnr-ecp5'
        )
        ecppack_bin = os.path.join(yosys_path, 'ecppack') or 'ecppack'

        run_cmd(
            [
                yosys_bin,
                '-c',
                'yosys_project.tcl',
            ]
        )

        run_cmd(
            [
                nextpnr_bin,
                '--json',
                f'build/{prefix}.synth.json',
                '--lpf',
                lpf_file,
                YOSYS_BOARDS[self.technology]['option'],
                '--textcfg',
                f'build/{prefix}.config',
                '--package',
                YOSYS_BOARDS[self.technology]['package'],
                '--speed',
                YOSYS_BOARDS[self.technology]['speed'],
                '--lpf-allow-unconstrained',
                '--report',
                f'reports/{prefix}_place_route.json',
            ]
        )

        run_cmd(
            [
                ecppack_bin,
                '--compress',
                '--input',
                f'build/{prefix}.config',
                '--bit',
                f'{prefix}.bit',
            ]
        )

    def clean(self) -> None:
        run_cmd(['rm', '-rf', 'build', '*.bit', '*.json', '*.rpt', 'slpp_all'])

    def report(self, report_path: str = 'reports') -> None:
        prefix: str = YOSYS_BOARDS[self.technology]['prefix']
        report_path: str = f'reports/{prefix}_place_route.json'
        csv_path: str = f'{report_path}/{prefix}_report.csv'

        # --- Lê o JSON ---
        with open(report_path, 'r') as f:
            data: Dict[str, Any] = json.load(f)

        fmax_info: Dict[str, Any] = data.get('fmax', {})
        util_info: Dict[str, Any] = data.get('utilization', {})

        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            writer.writerow(['Resource', 'Used', 'Available', 'Utilization %'])

            # --- FMAX ---
            for clk, values in fmax_info.items():
                achieved: float = values.get('achieved', 0.0)
                constraint: float = values.get('constraint', 0.0)
                writer.writerow(
                    [
                        'FMAX',
                        f'{constraint:.2f}',
                        f'{achieved:.2f}',
                        f'{constraint / achieved * 100:.2f}%',
                    ]
                )

            # --- UTILIZATION ---

            for res, values in util_info.items():
                used: int = values.get('used', 0)
                available: int = values.get('available', 0)
                percent: int = (
                    int(round((used / available) * 100))
                    if available > 0
                    else 0
                )
                writer.writerow([res, used, available, f'{percent}%'])

        print_green(f'Report CSV generated at: {csv_path}')

        print_blue('=' * 60)
        print_blue(f' FPGA Flow Summary for board: {self.technology}')
        print_blue('=' * 60)

        # --- FMAX ---
        print_green('Clock Frequency (Fmax):')
        for clk, values in fmax_info.items():
            achieved: float = values.get('achieved', 0.0)
            constraint: float = values.get('constraint', 0.0)
            status: str = 'OK' if achieved >= constraint else 'VIOLATED'
            print(
                f'  {clk:<35} {achieved:8.2f} MHz '
                f'(constraint {constraint:.2f} MHz) -> {status}'
            )
        print('')

        # --- UTILIZATION ---
        print_green('Resource Utilization:')
        header = f"{'Resource':<20} {'Used':>8} {'Avail':>8} {'Util %':>8}"
        print(header)
        print('-' * len(header))

        for res, values in util_info.items():
            used: int = values.get('used', 0)
            available: int = values.get('available', 0)
            percent: int = (
                int(round((used / available) * 100)) if available > 0 else 0
            )
            print(f'{res:<20} {used:8} {available:8} {percent:7}%')

        print_blue('=' * 60)
        print_green('Flow summary generated successfully ')


# -------------------------
# Gowin Flow
# -------------------------
class GowinFlow(ImplementationFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Gowin flow for board: '{self.technology}'")

        constraints: List[str] = [
            f'{CONSTRAINTS_DIR}/{self.technology}.sdc'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file),
            f'{CONSTRAINTS_DIR}/{self.technology}.cst'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file),
        ]

        context: Dict[str, Any] = {
            'files': self.project_files,
            'constraints': constraints,
            'top_module': self.top_module,
            'device_name': GOWIN_BOARDS[self.technology]['device_name'],
            'device_package': GOWIN_BOARDS[self.technology]['device_package'],
            'prefix': GOWIN_BOARDS[self.technology]['prefix'],
            'options': {},
        }

        write_template_to_file(
            self.env, 'gowin.j2', context, 'gowin_project.tcl'
        )
        print_green(f"Gowin project files generated for '{self.technology}'")

    def run_tool(self) -> None:
        gowin_path = TOOLCHAINS_INSTALL_PATH.get('gowin', '')
        gowin_bin = os.path.join(gowin_path, 'gw_sh') or 'gw_sh'

        run_cmd([gowin_bin, 'gowin_project.tcl'])

    def clean(self) -> None:
        run_cmd(['rm', '-rf', 'build', 'reports', '*.jou', '*.log', '*.bit'])

    def report(self, report_path: str = 'reports') -> None:
        pass


# -------------------------
# Factory
# -------------------------
def get_flow(
    board_name: str,
    project_files: List[str],
    constraint_file: str,
    top_module: str,
    env: Environment,
) -> ImplementationFlow:
    if board_name in VIVADO_BOARDS:
        return VivadoFlow(
            board_name, project_files, constraint_file, top_module, env
        )
    elif board_name in YOSYS_BOARDS:
        return YosysFlow(
            board_name, project_files, constraint_file, top_module, env
        )
    elif board_name in GOWIN_BOARDS:
        return GowinFlow(
            board_name, project_files, constraint_file, top_module, env
        )
    else:
        raise ValueError(f"Board '{board_name}' not supported.")


# -------------------------
# Função principal
# -------------------------
def run_fpga_flow(
    board_name: str,
    project_files: List[str],
    constraint_file: str = 'default',
    top_module: str = 'processorci_top',
    get_reports: bool = False,
    clean: bool = False,
    report_path: str = 'reports',
) -> None:
    board_name = board_name.lower()

    if board_name not in SUPPORTED_BOARDS:
        raise ValueError(f"Board '{board_name}' is not supported.")

    write_defines(board_name)

    env: Environment = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    flow: ImplementationFlow = get_flow(
        board_name, project_files, constraint_file, top_module, env
    )
    flow.run()

    if get_reports:
        flow.report(report_path=report_path)

    if clean:
        flow.clean()
