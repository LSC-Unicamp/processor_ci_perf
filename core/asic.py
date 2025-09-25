import os
from core.pdk_defines import DEFINES_BY_PDK, SUPPORTED_PDKS
from core.log import print_blue, print_red, print_yellow, print_green
from core import run_cmd, write_template_to_file
from jinja2 import Environment, FileSystemLoader
from core import ImplementationFlow
from typing import Any, Dict
from core import TEMPLATES_DIR, CONSTRAINTS_DIR


TOOLCHAINS_INSTALL_PATH = {
    'openroad': os.getenv('OPENROAD_INSTALL_PATH', '/eda/asic/OpenROAD-flow-scripts/'),
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
            'synth_hierarchical': False,
            'synth_min_keep_size': 0,
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
        pass


def run_asic_flow(
    pdk_name: str,
    project_files: list[str],
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
    )

    flow.run()

    if get_reports:
        flow.report(report_path=report_path)

    if clean:
        flow.clean()
