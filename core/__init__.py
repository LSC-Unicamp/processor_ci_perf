# core/__init__.py
import os
import re
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from jinja2 import Environment, Template

from core.log import print_blue, print_green, print_red, print_yellow

# Diretórios principais
CORE_DIR: str = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'templates')
)
CONSTRAINTS_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'constraints')
)

def ensure_env(var_name: str, default_value: str) -> str:
    """
    Garante que uma variável de ambiente esteja definida.
    Se não existir, define com o valor padrão.
    
    Retorna o valor final da variável.
    """
    if var_name not in os.environ:
        os.environ[var_name] = default_value
        print(f"[INFO] Variável de ambiente '{var_name}' não existia. Setada para: {default_value}")
    else:
        print(f"[INFO] Variável de ambiente '{var_name}' já existe: {os.environ[var_name]}")
    return os.environ[var_name]


def find_clock_signal(verilog_file: str) -> Optional[str]:
    """
    Procura no arquivo Verilog por um sinal de clock.
    
    Critérios:
    - Deve ser input
    - Deve ter 1 bit (não vetor, ou [0:0])
    - Nome contém 'clk' ou 'clock' (case-insensitive)
    - Tipo pode ser 'wire' ou 'logic' (opcional)
    
    Retorna:
        Nome do sinal de clock ou None se não encontrado
    """
    clk_signal = None
    input_regex = re.compile(
        r'^\s*input\s+(?:wire|logic)?\s*(?:\[0:0\]\s*)?(\w+)\s*[,;]',
        re.IGNORECASE
    )
    
    with open(verilog_file, 'r') as f:
        for line in f:
            line = line.strip()
            if 'clk' in line.lower() or 'clock' in line.lower():
                match = input_regex.match(line)
                if match:
                    clk_signal = match.group(1)
                    break  # retorna o primeiro encontrado
    return clk_signal


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
    subprocess.run(command, cwd=cwd, check=False)


# -------------------------
# Classe base para flows
# -------------------------
class ImplementationFlow(ABC):
    def __init__(
        self,
        technology: str,
        project_files: List[str],
        constraint_file: str,
        top_module: str,
        include_dirs: List[str],
        env: Environment,
    ) -> None:
        self.technology: str = technology
        self.project_files: List[str] = project_files
        self.constraint_file: str = constraint_file
        self.top_module: str = top_module
        self.env: Environment = env
        self.include_dirs: List[str] = include_dirs

    @abstractmethod
    def generate_project(self) -> None:
        pass

    @abstractmethod
    def run_tool(self) -> None:
        pass

    @abstractmethod
    def clean(self) -> None:
        pass

    @abstractmethod
    def report(self, report_path: str = 'reports') -> None:
        pass

    def run(self) -> None:
        self.generate_project()
        self.run_tool()
