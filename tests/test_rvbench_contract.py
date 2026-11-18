"""The process and template contract used by RV-Bench synthesis adapters."""

import subprocess
import shutil
import sys
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from core import TEMPLATES_DIR, run_cmd
from core.asic import OpenRoadFlow
from core.fpga import VivadoFlow, YosysFlow, _parse_synth_ecp5_utilization


def _environment():
    return Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def test_failing_subprocess_aborts_flow():
    with pytest.raises(subprocess.CalledProcessError):
        run_cmd([sys.executable, "-c", "raise SystemExit(7)"])


@pytest.mark.parametrize("kind", ["fpga", "asic"])
def test_cli_routes_declared_defines(kind, monkeypatch):
    import main as perf_main

    captured = []
    monkeypatch.setattr(perf_main, "run_fpga_flow", lambda *a, **kw: captured.append(kw))
    monkeypatch.setattr(perf_main, "run_asic_flow", lambda *a, **kw: captured.append(kw))
    monkeypatch.setattr(sys, "argv", ["main.py", "--flow", kind, "--technology",
                                  "colorlight_i9" if kind == "fpga" else "asap7",
                                  "--files", "/src/top.v", "--defines", "FEATURE", "DEPTH=64"])
    perf_main.main()
    assert len(captured) == 1
    if kind == "fpga":
        assert captured[0]["defines"] == ["FEATURE", "DEPTH=64"]
    else:
        assert captured[0]["slang_args"] == ["-DFEATURE", "-DDEPTH=64"]


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
    assert "CORE_MARGIN        = 2" in makefile


def test_ihp_pdn_ring_receives_sufficient_die_margin(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    flow = OpenRoadFlow(
        technology="ihp-sg13g2", project_files=[], constraint_file="default",
        top_module="core", include_dirs=[], env=_environment(),
    )
    flow.generate_project()
    assert "CORE_MARGIN        = 20" in (tmp_path / "openroad.mk").read_text()


def test_asic_requests_reports_without_gds(tmp_path, monkeypatch):
    from core import asic

    flow_root = tmp_path / "orfs"
    (flow_root / "flow").mkdir(parents=True)
    (flow_root / "flow/Makefile").write_text("finish:\n\t@true\n")
    monkeypatch.setitem(asic.TOOLCHAINS_INSTALL_PATH, "openroad", str(flow_root))
    commands = []
    monkeypatch.setattr(asic, "run_cmd", lambda command: commands.append(command))
    flow = OpenRoadFlow(
        technology="asap7", project_files=[], constraint_file="default",
        top_module="core", include_dirs=[], env=_environment(),
    )
    flow.run_tool()
    assert commands == [[
        "make", f"--file={flow_root / 'flow/Makefile'}",
        "DESIGN_CONFIG=openroad.mk", "check-yosys", "check-openroad",
        "synth", "floorplan", "place", "cts", "route", "do-finish",
    ]]


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
    flow.top_params = ["DEPTH=16", "ENABLE=1"]
    flow.generate_project()
    script = (tmp_path / "yosys_project.tcl").read_text()
    lines = [line for line in script.splitlines()
             if "read_systemverilog" in line and not line.lstrip().startswith("#")]
    assert len([line for line in lines if "-defer" in line]) == 1
    assert f'set rvbench_includes [list "-I{include}"]' in script
    assert f"-I{tmp_path}/{include}" not in script
    assert 'set rvbench_synlig_args [list "-noassert"]' in script
    assert 'set rvbench_files [list "/src/a.sv" "/src/b.sv"]' in script
    assert '{*}$rvbench_files' in lines[0]
    assert "yosys chparam -set DEPTH 16 -set ENABLE 1 core" in script


def test_fpga_defines_reach_every_yosys_read_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    flow = YosysFlow(
        technology="colorlight_i9", project_files=["/src/top.v"],
        constraint_file="default", top_module="top", include_dirs=[], env=_environment(),
    )
    flow.defines = ["FEATURE", "DEPTH=64"]
    flow.generate_project()
    for name in ("yosys_project.tcl", "yosys_verilog.tcl", "yosys_slang.tcl",
                 "yosys_verilog2005.tcl", "yosys_project_noabc9.tcl",
                 "yosys_verilog_noabc9.tcl", "yosys_slang_noabc9.tcl",
                 "yosys_verilog2005_noabc9.tcl"):
        script = (tmp_path / name).read_text()
        assert 'set rvbench_defines [list "-DFEATURE" "-DDEPTH=64"]' in script
        assert '\nyosys ' in script
        assert not any('set rvbench_defines ' in line and 'yosys ' in line
                       for line in script.splitlines())
        reads = [line for line in script.splitlines()
                 if line.lstrip().startswith(("yosys read_verilog", "yosys read_slang",
                                            "yosys read_systemverilog"))]
        assert reads and all("{*}$rvbench_defines" in line for line in reads
                             if "-link" not in line)


@pytest.mark.parametrize("bitstream", [False, True])
def test_vivado_synthesis_receives_defines(tmp_path, monkeypatch, bitstream):
    monkeypatch.chdir(tmp_path)
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=["/src/top.v"],
        constraint_file="default", top_module="top", include_dirs=[], env=_environment(),
    )
    flow.defines = ["FEATURE", "DEPTH=64"]
    flow.bitstream = bitstream
    flow.generate_project()
    script = (tmp_path / "vivado_project.tcl").read_text()
    synthesis = next(line for line in script.splitlines() if line.startswith("synth_design "))
    assert '-verilog_define "FEATURE"' in synthesis
    assert '-verilog_define "DEPTH=64"' in synthesis


@pytest.mark.parametrize("systemverilog", [False, True])
def test_vivado_reads_v_files_in_declared_language(tmp_path, monkeypatch, systemverilog):
    monkeypatch.chdir(tmp_path)
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr",
        project_files=["/src/cpu_cfig.h", "/src/common_defines.vh",
                       "/src/top.v", "/src/package.sv"],
        constraint_file="default", top_module="top",
        include_dirs=[], env=_environment(),
    )
    flow.vivado_systemverilog = systemverilog
    flow.generate_project()
    script = (tmp_path / "vivado_project.tcl").read_text()
    expected = 'read_verilog -sv "/src/top.v"' if systemverilog else 'read_verilog "/src/top.v"'
    assert expected in script
    assert 'read_verilog -sv "/src/package.sv"' in script
    assert 'read_verilog -sv "/src/cpu_cfig.h"' in script
    assert 'read_verilog -sv "/src/common_defines.vh"' in script
    assert script.index("/src/cpu_cfig.h") < script.index("/src/top.v")


def test_vivado_tcl_preserves_paths_and_applies_named_parameters(tmp_path, monkeypatch):
    if shutil.which("tclsh") is None:
        pytest.skip("Tcl interpreter unavailable")
    monkeypatch.chdir(tmp_path)
    source = "/src/Other Units/Clk[3]$core.v"
    include = "/src/Other Units/[headers]$core"
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=[source],
        constraint_file="default", top_module="ClkDiv", include_dirs=[include],
        env=_environment(),
    )
    flow.bitstream = False
    flow.top_params = ["DEPTH=16", "FEATURE=1"]
    flow.defines = ["CLK_FEATURE"]
    flow.generate_project()

    # Execute the generated Tcl with command stubs. This checks actual Tcl
    # argument boundaries and the synthesis-only branch without Vivado.
    stub = r'''
proc get_filesets {args} {return sources_1}
proc set_property {args} {puts "PROPERTY:[lindex $args 1]"}
proc read_verilog {args} {puts "SOURCE:[llength $args]:[lindex $args end]"}
proc synth_design {args} {
    puts "GENERIC:[lindex $args [expr {[lsearch $args -generic] + 1}]]"
    puts "INCLUDE:[lindex $args [expr {[lsearch $args -include_dirs] + 1}]]"
}
proc report_utilization {args} {
    set index [lsearch $args -file]
    set handle [open [lindex $args [expr {$index + 1}]] w]
    puts $handle "report"
    close $handle
}
proc get_ports {args} {return {}}
proc opt_design {} {}
proc place_design {} {error "pin pressure"}
source vivado_project.tcl
'''
    completed = subprocess.run(["tclsh"], input=stub, text=True,
                               capture_output=True, cwd=tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert f"SOURCE:1:{source}" in completed.stdout
    assert f"PROPERTY:{{{include}}}" in completed.stdout
    assert f"INCLUDE:{{{include}}}" in completed.stdout
    assert "GENERIC:DEPTH=16" in completed.stdout
    assert '-generic "FEATURE=1"' in (tmp_path / "vivado_project.tcl").read_text()
    assert (tmp_path / "reports/digilent_nexys4_ddr_metrics_stage.txt").read_text().startswith(
        "synthesis_only\npin pressure")
    assert not (tmp_path / "reports/digilent_nexys4_ddr_timing.rpt").exists()


def test_vivado_hardware_quotes_constraint_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    constraint = tmp_path / "constraints/Board [1] $pins.xdc"
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=["/src/Other Units/top.sv"],
        constraint_file=str(constraint), top_module="fpga_top", include_dirs=[],
        env=_environment(),
    )
    flow.generate_project()
    script = (tmp_path / "vivado_project.tcl").read_text()
    assert 'read_verilog -sv "/src/Other Units/top.sv"' in script
    assert r'read_xdc "' + str(constraint).replace('$', r'\$').replace('[', r'\[') + '"' in script
    assert r'get_files "' + str(constraint).replace('$', r'\$').replace('[', r'\[') + '"' in script
    if shutil.which("tclsh") is not None:
        stub = r'''
proc read_verilog {args} {}
proc read_xdc {path} {puts "XDC:$path"}
proc get_files {path} {puts "GET:$path"; return $path}
proc set_property {args} {}
proc synth_design {args} {exit 0}
source vivado_project.tcl
'''
        completed = subprocess.run(["tclsh"], input=stub, text=True,
                                   capture_output=True, cwd=tmp_path)
        assert completed.returncode == 0, completed.stderr
        assert f"XDC:{constraint}" in completed.stdout
        assert f"GET:{constraint}" in completed.stdout
    assert "synthesis_utilization.xml" not in script


def test_vivado_synthesis_only_report_uses_actual_top(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    cells = ["Core", "(top)", "123", "120", "0", "0", "45", "2", "1", "0"]
    xml_cells = "".join(f'<tablecell contents="{value}"/>' for value in cells)
    (reports / "digilent_nexys4_ddr_synthesis_utilization.xml").write_text(
        f'<report designname="Core"><section><table><tablerow>{xml_cells}'
        '</tablerow></table></section></report>')
    (reports / "digilent_nexys4_ddr_metrics_stage.txt").write_text(
        "synthesis_only\npin pressure\n")
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=[],
        constraint_file="default", top_module="Core", include_dirs=[],
        env=_environment(),
    )
    output = tmp_path / "evidence"
    flow.report(report_path=str(output))
    csv = (output / "digilent_nexys4_ddr_report.csv").read_text()
    assert "Resource,Total LUTs,123" in csv
    assert "Resource,FFs,45" in csv
    assert "FMAX" not in csv
    assert (output / "digilent_nexys4_ddr_metrics_stage.txt").read_text().startswith(
        "synthesis_only")
    assert (output / "digilent_nexys4_ddr_synthesis_utilization.xml").is_file()


@pytest.mark.parametrize("bitstream", [False, True])
def test_vivado_synthesis_failure_never_becomes_utilization_only(
        tmp_path, monkeypatch, bitstream):
    if shutil.which("tclsh") is None:
        pytest.skip("Tcl interpreter unavailable")
    monkeypatch.chdir(tmp_path)
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=["/src/top.v"],
        constraint_file="default", top_module="top", include_dirs=[],
        env=_environment(),
    )
    flow.bitstream = bitstream
    flow.generate_project()
    stub = r'''
proc read_verilog {args} {}
proc read_xdc {args} {}
proc get_files {args} {return source}
proc set_property {args} {}
proc synth_design {args} {error "elaboration failed"}
if {[catch {source vivado_project.tcl} reason]} {
    puts stderr $reason
    exit 7
}
'''
    completed = subprocess.run(["tclsh"], input=stub, text=True,
                               capture_output=True, cwd=tmp_path)
    assert completed.returncode == 7
    assert "elaboration failed" in completed.stderr
    assert not (tmp_path / "reports/digilent_nexys4_ddr_metrics_stage.txt").exists()


def test_vivado_hardware_placement_failure_remains_fatal(tmp_path, monkeypatch):
    if shutil.which("tclsh") is None:
        pytest.skip("Tcl interpreter unavailable")
    monkeypatch.chdir(tmp_path)
    flow = VivadoFlow(
        technology="digilent_nexys4_ddr", project_files=["/src/top.v"],
        constraint_file="default", top_module="top", include_dirs=[],
        env=_environment(),
    )
    flow.generate_project()
    stub = r'''
proc read_verilog {args} {}
proc read_xdc {args} {}
proc get_files {args} {return source}
proc set_property {args} {}
proc synth_design {args} {}
proc opt_design {} {}
proc place_design {} {error "pin pressure"}
if {[catch {source vivado_project.tcl} reason]} {
    puts stderr $reason
    exit 8
}
'''
    completed = subprocess.run(["tclsh"], input=stub, text=True,
                               capture_output=True, cwd=tmp_path)
    assert completed.returncode == 8
    assert "pin pressure" in completed.stderr


def test_yosys_fallbacks_keep_source_paths_with_spaces_as_one_argument(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = "/src/RTL/Other Units/ClkDiv.v"
    include = "/src/RTL/Other Units"
    flow = YosysFlow(
        technology="colorlight_i9", project_files=[source],
        constraint_file="default", top_module="ClkDiv",
        include_dirs=[include], env=_environment(),
    )
    flow.generate_project()
    for name in ("yosys_project.tcl", "yosys_verilog.tcl",
                 "yosys_slang.tcl", "yosys_verilog2005.tcl"):
        script = (tmp_path / name).read_text()
        assert f'set rvbench_files [list "{source}"]' in script
        assert f'set rvbench_includes [list "-I{include}"]' in script
        assert "{*}$rvbench_files" in script


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
    flow.nextpnr_args = ['--ignore-loops']
    flow.run_tool()
    assert [command[0] for command in calls] == [
        '/locked/synlig', '/locked/nextpnr-ecp5', '/locked/ecppack']
    assert '--ignore-loops' in calls[1]


def test_unplaced_ecp5_design_retains_synthesis_utilization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / 'reports'
    reports.mkdir()
    log = reports / 'colorlight_i9_synthesis.log'
    log.write_text(
        '=== design hierarchy ===\n'
        '    52073 submodules\n'
        '    34206 LUT4\n'
        '     2787 TRELLIS_FF\n'
        '\n2.52. Executing CHECK pass.\n'
    )
    flow = YosysFlow(
        technology='colorlight_i9', project_files=['/src/core.sv'],
        constraint_file='default', top_module='core',
        include_dirs=[], env=_environment(),
    )
    flow.report(report_path=str(tmp_path / 'evidence'))
    report = (tmp_path / 'evidence/colorlight_i9_report.csv').read_text()
    assert 'TRELLIS_COMB,34206,' in report
    assert 'TRELLIS_FF,2787,' in report
    assert 'FMAX' not in report
    assert (tmp_path / 'evidence/colorlight_i9_synthesis.log').is_file()
    assert _parse_synth_ecp5_utilization(str(log), 'colorlight_i9')['TRELLIS_COMB']['used'] == 34206


def test_legacy_ecp5_stat_format_is_still_readable(tmp_path):
    log = tmp_path / 'old-yosys.log'
    log.write_text('Number of cells:\n   LUT4 123\n   TRELLIS_FF 45\n')
    util = _parse_synth_ecp5_utilization(str(log), 'colorlight_i9')
    assert util['TRELLIS_COMB']['used'] == 123
    assert util['TRELLIS_FF']['used'] == 45


def test_metrics_placement_timeout_uses_synthesis_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if command[0] == '/locked/nextpnr-ecp5':
            raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr('core.fpga.run_cmd', fake_run)
    monkeypatch.setenv('YOSYS_EXE', '/locked/yosys')
    monkeypatch.setenv('NEXTPNR_ECP5_EXE', '/locked/nextpnr-ecp5')
    flow = YosysFlow(
        technology='colorlight_i9', project_files=['/src/core.v'],
        constraint_file='default', top_module='core',
        include_dirs=[], env=_environment(),
    )
    flow.frontend = 'yosys'
    flow.bitstream = False
    flow.nextpnr_timeout = 1
    flow.generate_project()
    flow.run_tool()
    assert commands[0][0][1:3] == ['-l', 'reports/colorlight_i9_synthesis.log']
    assert commands[1][1]['timeout_seconds'] == 1


def test_fpga_native_yosys_frontend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('YOSYS_EXE', '/locked/yosys')
    calls = []
    monkeypatch.setattr('core.fpga.run_cmd', lambda command: calls.append(command))
    flow = YosysFlow(
        technology='colorlight_i9', project_files=['/src/core.v'],
        constraint_file='default', top_module='core',
        include_dirs=['/src'], env=_environment(),
    )
    flow.frontend = 'yosys'
    flow.generate_project()
    script = (tmp_path / 'yosys_project.tcl').read_text()
    assert 'set rvbench_includes [list "-I/src"]' in script
    assert 'set rvbench_files [list "/src/core.v"]' in script
    assert 'read_verilog -sv {*}$rvbench_includes {*}$rvbench_defines {*}$rvbench_files' in script
    assert not any('read_systemverilog' in line for line in script.splitlines()
                   if not line.lstrip().startswith('#'))
    flow.run_tool()
    assert calls[0][0] == '/locked/yosys'
