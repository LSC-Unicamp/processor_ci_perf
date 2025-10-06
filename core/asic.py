# core/asic.py
import os
import re
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader

from core import (
    CONSTRAINTS_DIR,
    TEMPLATES_DIR,
    ImplementationFlow,
    run_cmd,
    write_template_to_file,
)
from core.log import print_blue, print_green, print_red, print_yellow
from core.pdk_defines import DEFINES_BY_PDK, SUPPORTED_PDKS

TOOLCHAINS_INSTALL_PATH = {
    'openroad': os.getenv(
        'OPENROAD_INSTALL_PATH', '/eda/asic/OpenROAD-flow-scripts/'
    ),
}


# -------------------------
# OpenRoad Flow
# -------------------------
class OpenRoadFlow(ImplementationFlow):
    def generate_project(self) -> None:
        print_blue(f"Running OpenRoad flow for PDK: '{self.technology}'")

        constraints: str = (
            f'{CONSTRAINTS_DIR}/openroad.sdc'
            if self.constraint_file == 'default'
            else self.constraint_file
        )

        context: Dict[str, Any] = {
            'design_name': self.top_module,
            'verilog_files': self.project_files,
            'sdc_file': constraints,
            'design_nickname': self.top_module,
            'platform': self.technology,
            'core_utilization': 5,
            'place_density': 0.10,
            'synth_hdl_frontend': 'slang',
            'synth_hierarchical': True,
            'synth_min_keep_size': 10,
            'additional_lefs': False,
            'additional_lef_files': DEFINES_BY_PDK[self.technology].get(
                'additional_lef_files', []
            ),
            'additional_libs': False,
            'additional_lib_files': DEFINES_BY_PDK[self.technology].get(
                'additional_lib_files', []
            ),
        }

        write_template_to_file(self.env, 'openroad.j2', context, 'openroad.mk')
        print_green(
            f"OpenRoad project files generated for '{self.technology}' PDK."
        )

    def run_tool(self) -> None:
        openroad_path = TOOLCHAINS_INSTALL_PATH.get('openroad', '')
        if not openroad_path or not os.path.exists(openroad_path):
            raise EnvironmentError(
                'OpenRoad toolchain path is not set or does not exist.'
            )

        openroad_makefile_path = os.path.join(openroad_path, 'flow/Makefile')

        run_cmd(
            [
                'make',
                f'--file={openroad_makefile_path}',
                'DESIGN_CONFIG=openroad.mk',
            ]
        )

    def clean(self) -> None:
        run_cmd(['rm', '-rf', 'build', 'reports', '*.jou', '*.log', '*.bit'])


    def report(self, report_path: str = 'reports') -> None:
        print_blue(f"Generating report for PDK: '{self.technology}'")

        os.makedirs(report_path, exist_ok=True)

        csv_path = os.path.join(report_path, f'{self.technology}_report.csv')
        synth_stats_path: str = f'reports/{self.technology}/{self.top_module}/base/synth_stat.txt'
        finish_timing: str = f'reports/{self.technology}/{self.top_module}/base/6_finish.rpt'

        clock_info: Dict[str, float] = {}
        if os.path.exists(finish_timing):
            with open(finish_timing, 'r') as f:
                content = f.read()

                # Regex para pegar period_min e fmax
                clock_matches = re.findall(
                    r'^\s*(\S+)\s+period_min\s*=\s*([0-9]*\.?[0-9]+)\s+fmax\s*=\s*([0-9]*\.?[0-9]+)',
                    content,
                    re.MULTILINE
                )

                for clk_name, period_str, fmax_str in clock_matches:
                    try:
                        period_min = float(period_str)
                        fmax = float(fmax_str)
                        clock_info[clk_name] = {'period_min': period_min, 'fmax': fmax}
                    except ValueError:
                        continue

        # --- PARSE SYNTHESIS STATISTICS ---
        cell_usage: Dict[str, Dict[str, float]] = {}
        chip_area = 0.0
        seq_area = 0.0

        if os.path.exists(synth_stats_path):
            with open(synth_stats_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    # Captura linhas de células: quantidade, área, nome
                    cell_match = re.match(r'^\s*(\d+)\s+([0-9]*\.?[0-9]+)\s+(\S+)', line)
                    if cell_match:
                        count = int(cell_match.group(1))
                        area = float(cell_match.group(2))
                        cell_name = cell_match.group(3)
                        cell_usage[cell_name] = {'count': count, 'area': area}

                    # Captura Chip area
                    chip_match = re.match(r'^\s*Chip area for module.*:\s*([0-9]*\.?[0-9]+)', line)
                    if chip_match:
                        chip_area = float(chip_match.group(1))

                    # Captura sequential elements area
                    seq_match = re.match(r'^\s*of which used for sequential elements:\s*([0-9]*\.?[0-9]+)', line)
                    if seq_match:
                        seq_area = float(seq_match.group(1))

        # --- PRINT RESULTS ---
        print_green("\nClock Information:")
        for clk, info in clock_info.items():
            print(f"{clk}: period_min = {info['period_min']} ns, fmax = {info['fmax']} MHz")

        print_green("\nCell Usage:")
        for cell, stats in cell_usage.items():
            print(f"{cell:<20} count={stats['count']:<5} area={stats['area']}")

        print_green(f"\nChip Area: {chip_area} (sequential: {seq_area})")

        # --- WRITE CSV ---
        import csv
        with open(csv_path, 'w', newline='') as csvf:
            writer = csv.writer(csvf)
            writer.writerow(['Type', 'Name', 'Count', 'Area'])
            for cell, stats in cell_usage.items():
                writer.writerow(['Cell', cell, stats['count'], stats['area']])
            writer.writerow(['Chip', 'Total', '', chip_area])
            writer.writerow(['Chip', 'Sequential', '', seq_area])
            for clk, info in clock_info.items():
                writer.writerow(['Clock', clk, info['period_min'], info['fmax']])
        
        print_green(f"\nCSV summary saved to: {csv_path}")



def run_asic_flow(
    pdk_name: str,
    project_files: list[str],
    include_dirs: list[str],
    constraint_file: str = 'default',
    top_module: str = 'processorci_top',
    get_reports: bool = False,
    clean: bool = False,
    report_path: str = 'reports',
) -> None:
    pdk_name = pdk_name.lower()
    if pdk_name not in SUPPORTED_PDKS:
        raise ValueError(
            f"PDK '{pdk_name}' is not supported. Supported PDKs: {SUPPORTED_PDKS}"
        )

    env: Environment = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    flow = OpenRoadFlow(
        technology=pdk_name,
        project_files=project_files,
        constraint_file=constraint_file,
        top_module=top_module,
        env=env,
        include_dirs=include_dirs,
    )

    flow.run()

    if get_reports:
        flow.report(report_path=report_path)

    if clean:
        flow.clean()
