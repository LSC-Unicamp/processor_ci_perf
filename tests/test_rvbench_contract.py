"""The process and template contract used by RV-Bench synthesis adapters."""

import subprocess
import sys
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from core import TEMPLATES_DIR, run_cmd
from core.asic import OpenRoadFlow
from core.fpga import YosysFlow


def _environment():
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def test_failing_subprocess_aborts_flow():
    with pytest.raises(subprocess.CalledProcessError):
        run_cmd([sys.executable, "-c", "raise SystemExit(7)"])


def test_asic_filelist_and_slang_flags_reach_makefile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RVB_SLANG_DIAG_JSON", str(tmp_path / "slang.json"))
    filelist = tmp_path / "source.f"
    filelist.write_text("/src/core.sv\n")
    flow = OpenRoadFlow(
        technology="asap7", project_files=[], constraint_file="default",
        top_module="core", include_dirs=[], env=_environment(),
    )
    flow.filelist = str(filelist)
    flow.slang_args = ["--ignore-initial"]
    flow.top_params = ["DEPTH=16"]
    flow.generate_project()
    makefile = (tmp_path / "openroad.mk").read_text()
    assert f"VERILOG_FILES_FILE = {filelist}" in makefile
    assert "--ignore-initial --diag-json " in makefile
    assert "--error-limit 0 -F $(VERILOG_FILES_FILE)" in makefile
    assert "VERILOG_TOP_PARAMS = DEPTH 16" in makefile


def test_fpga_includes_and_flags_reach_one_compilation_unit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    include = tmp_path / "rtl"
    include.mkdir()
    flow = YosysFlow(
        technology="colorlight_i9",
        project_files=["/src/a.sv", "/src/b.sv"],
        constraint_file="default", top_module="core",
        include_dirs=[str(include)], env=_environment(),
    )
    flow.synlig_args = ["-noassert"]
    flow.generate_project()
    script = (tmp_path / "yosys_project.tcl").read_text()
    lines = [line for line in script.splitlines() if "read_systemverilog" in line]
    assert len([line for line in lines if "-defer" in line]) == 1
    assert f"-I{include}" in lines[0]
    assert f"-I{tmp_path}/{include}" not in lines[0]
    assert "-noassert" in lines[0]
    assert "/src/a.sv /src/b.sv" in lines[0]


def test_fpga_uses_explicit_locked_executables(monkeypatch):
    calls = []
    monkeypatch.setattr('core.fpga.run_cmd', lambda command: calls.append(command))
    monkeypatch.setenv('SYNLIG_EXE', '/locked/synlig')
    monkeypatch.setenv('NEXTPNR_ECP5_EXE', '/locked/nextpnr-ecp5')
    monkeypatch.setenv('ECPPACK_EXE', '/locked/ecppack')
    flow = YosysFlow(
        technology='colorlight_i9', project_files=['/src/core.sv'],
        constraint_file='default', top_module='core',
        include_dirs=[], env=_environment(),
    )
    flow.run_tool()
    assert [command[0] for command in calls] == [
        '/locked/synlig', '/locked/nextpnr-ecp5', '/locked/ecppack']
