import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, Template

from core.log import print_blue, print_red, print_green, print_yellow
from core.board_defines import (
    DEFINES_BY_BOARD,
    SUPPORTED_BOARDS,
    VIVADO_BOARDS,
    YOSYS_BOARDS,
    GOWIN_BOARDS,
)

# Diretórios principais
CORE_DIR: str = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'templates')
)
CONSTRAINTS_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'constraints')
)


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


def write_template_to_file(
    env: Environment,
    template_name: str,
    context: Dict[str, Any],
    filename: str,
) -> str:
    template: Template = env.get_template(template_name)
    output: str = template.render(context)
    with open(filename, 'w') as f:
        f.write(output)
    return filename


def run_cmd(command: List[str], cwd: Optional[str] = None) -> None:
    print_yellow(f"Running command: {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


# -------------------------
# Classe base para flows
# -------------------------
class FPGAFlow(ABC):
    def __init__(
        self,
        board_name: str,
        project_files: List[str],
        constraint_file: str,
        top_module: str,
        env: Environment,
    ) -> None:
        self.board_name: str = board_name
        self.project_files: List[str] = project_files
        self.constraint_file: str = constraint_file
        self.top_module: str = top_module
        self.env: Environment = env

    @abstractmethod
    def generate_project(self) -> None:
        pass

    @abstractmethod
    def run_tool(self) -> None:
        pass

    @abstractmethod
    def clean(self) -> None:
        pass

    def run(self) -> None:
        self.generate_project()
        self.run_tool()


# -------------------------
# Vivado Flow
# -------------------------
class VivadoFlow(FPGAFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Vivado flow for board: '{self.board_name}'")

        constraints: str = (
            f'{CONSTRAINTS_DIR}/{self.board_name}.xdc'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file)
        )

        context: Dict[str, Any] = {
            'files': self.project_files,
            'constraints': constraints,
            'top_module': self.top_module,
            'fpga_part': VIVADO_BOARDS[self.board_name]['part'],
            'prefix': VIVADO_BOARDS[self.board_name]['prefix'],
        }

        write_template_to_file(
            self.env, 'vivado.j2', context, 'vivado_project.tcl'
        )
        os.makedirs('reports', exist_ok=True)
        print_green(f"Vivado project files generated for '{self.board_name}'")

    def run_tool(self) -> None:
        run_cmd(
            [
                'vivado',
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


# -------------------------
# Yosys Flow
# -------------------------
class YosysFlow(FPGAFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Yosys flow for board: '{self.board_name}'")

        output_json: str = (
            f"build/{YOSYS_BOARDS[self.board_name]['prefix']}.synth.json"
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
        print_green(f"Yosys project files generated for '{self.board_name}'")

    def run_tool(self) -> None:
        prefix: str = YOSYS_BOARDS[self.board_name]['prefix']
        lpf_file: str = (
            f'{CONSTRAINTS_DIR}/{self.board_name}.lpf'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file)
        )

        run_cmd(['synlig', '-c', 'yosys_project.tcl'])

        run_cmd(
            [
                'nextpnr-ecp5',
                '--json',
                f'build/{prefix}.synth.json',
                '--lpf',
                lpf_file,
                YOSYS_BOARDS[self.board_name]['option'],
                '--textcfg',
                f'build/{prefix}.config',
                '--package',
                YOSYS_BOARDS[self.board_name]['package'],
                '--speed',
                YOSYS_BOARDS[self.board_name]['speed'],
                '--lpf-allow-unconstrained',
            ]
        )

        run_cmd(
            [
                'ecppack',
                '--compress',
                '--input',
                f'build/{prefix}.config',
                '--bit',
                f'{prefix}.bit',
            ]
        )

    def clean(self) -> None:
        run_cmd(['rm', '-rf', 'build', '*.bit', '*.json', '*.rpt', 'slpp_all'])


# -------------------------
# Gowin Flow
# -------------------------
class GowinFlow(FPGAFlow):
    def generate_project(self) -> None:
        print_blue(f"Running Gowin flow for board: '{self.board_name}'")

        constraints: List[str] = [
            f'{CONSTRAINTS_DIR}/{self.board_name}.sdc'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file),
            f'{CONSTRAINTS_DIR}/{self.board_name}.cst'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file),
        ]

        context: Dict[str, Any] = {
            'files': self.project_files,
            'constraints': constraints,
            'top_module': self.top_module,
            'device_name': GOWIN_BOARDS[self.board_name]['device_name'],
            'device_package': GOWIN_BOARDS[self.board_name]['device_package'],
            'prefix': GOWIN_BOARDS[self.board_name]['prefix'],
            'options': {},
        }

        write_template_to_file(
            self.env, 'gowin.j2', context, 'gowin_project.tcl'
        )
        print_green(f"Gowin project files generated for '{self.board_name}'")

    def run_tool(self) -> None:
        run_cmd(['gw_sh', 'gowin_project.tcl'])

    def clean(self) -> None:
        run_cmd(['rm', '-rf', 'build', 'reports', '*.jou', '*.log', '*.bit'])


# -------------------------
# Factory
# -------------------------
def get_flow(
    board_name: str,
    project_files: List[str],
    constraint_file: str,
    top_module: str,
    env: Environment,
) -> FPGAFlow:
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

    flow: FPGAFlow = get_flow(
        board_name, project_files, constraint_file, top_module, env
    )
    flow.run()
