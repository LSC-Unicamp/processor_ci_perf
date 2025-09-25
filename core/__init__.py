import os
import re
import csv
import json
import subprocess
from core.log import print_blue, print_red, print_yellow, print_green
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, Template
from abc import ABC, abstractmethod


# Diretórios principais
CORE_DIR: str = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'templates')
)
CONSTRAINTS_DIR: str = os.path.normpath(
    os.path.join(CORE_DIR, '..', 'constraints')
)


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
class ImplementationFlow(ABC):
    def __init__(
        self,
        technology: str,
        project_files: List[str],
        constraint_file: str,
        top_module: str,
        env: Environment,
    ) -> None:
        self.technology: str = technology
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

    @abstractmethod
    def report(self, report_path: str = 'reports') -> None:
        pass

    def run(self) -> None:
        self.generate_project()
        self.run_tool()
