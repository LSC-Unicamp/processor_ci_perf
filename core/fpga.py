# core/fpga.py
import csv
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

CURRENT_DIR: str = os.getcwd()

from core import (
    CONSTRAINTS_DIR,
    TEMPLATES_DIR,
    ImplementationFlow,
    run_cmd,
    write_template_to_file,
)
from core.board_defines import (
    DEFINES_BY_BOARD,
    GOWIN_BOARDS,
    SUPPORTED_BOARDS,
    VIVADO_BOARDS,
    YOSYS_BOARDS,
)
from core.log import print_blue, print_green, print_red, print_yellow

TOOLCHAINS_INSTALL_PATH = {
    'vivado': os.getenv('VIVADO_INSTALL_PATH', ''),
    'yosys': os.getenv('YOSYS_INSTALL_PATH', ''),
    'gowin': os.getenv('GOWIN_INSTALL_PATH', ''),
}


def _slang_yosys_bin() -> str | None:
    """The `yosys` that ships the `slang` frontend plugin, or None.

    The `slang` plugin lives in the RV-Bench toolchain's `oss-cad-suite`
    (`share/yosys/plugins/slang.so`), which is also the `yosys` that pairs
    with the GHDL plugin.  The system `yosys` is a different build and cannot
    load that plugin.  Look for the same layouts `_yosys_for_ghdl` uses
    (core/vhdl.py), so the fallback works whether or not the shell sourced
    `env.sh`.
    """
    candidates = [
        os.environ.get('RVBENCH_TOOLCHAIN_DIR'),
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'toolchain'),
        os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'oss-cad-suite'),
        '/eda/oss-cad-suite',
    ]
    for root in candidates:
        if not root:
            continue
        candidate = os.path.join(root, 'oss-cad-suite', 'bin', 'yosys')
        if not os.path.isfile(candidate):
            candidate = os.path.join(root, 'bin', 'yosys')
        if os.path.isfile(candidate):
            plugin = os.path.join(
                os.path.dirname(candidate), '..', 'share', 'yosys', 'plugins',
                'slang.so',
            )
            if os.path.isfile(plugin):
                return candidate
    return None


# -------------------------
# Helpers
# -------------------------
# RV-Bench local addition (not upstream): `synth_ecp5` prints the cell
# counts in its "Number of cells" block, keyed by the ECP5 cell name
# (`LUT4`, `TRELLIS_FF`, ...).  The board's resource budget is keyed by
# nextpnr's resource name (`TRELLIS_COMB`, ...), so the two have to be
# mapped.  A `LUT4` cell is one `TRELLIS_COMB`; the `CCU2C`/`PFUMX`/
# `L6MUX21` cells are not counted as a separate resource, they are packed
# into the same `TRELLIS_COMB` fabric, so they are not mapped here.
_SYNTH_ECP5_CELL_MAP = {
    'LUT4': 'TRELLIS_COMB',
    'TRELLIS_FF': 'TRELLIS_FF',
    'DP16KD': 'DP16KD',
    'TRELLIS_IO': 'TRELLIS_IO',
    'MULT18X18D': 'MULT18X18D',
    'ALU54B': 'ALU54B',
    'TRELLIS_RAMW': 'TRELLIS_RAMW',
}


def _parse_synth_ecp5_utilization(
    log_path: str, technology: str
) -> Dict[str, Dict[str, int]]:
    """Read the utilisation from a `synth_ecp5` "Number of cells" block.

    Used when the nextpnr place-and-route report is missing: a design that
    does not fit or misses timing still leaves a complete synthesis
    utilisation, which is enough to say how much of the board it would
    occupy.  The board's `resources` budget supplies the "available" side.
    """
    budget: Dict[str, int] = YOSYS_BOARDS.get(technology, {}).get(
        'resources', {}
    )
    utilization: Dict[str, Dict[str, int]] = {}
    in_stats = False
    try:
        with open(log_path, 'r', errors='replace') as log:
            for line in log:
                if 'Number of cells:' in line:
                    in_stats = True
                    continue
                if not in_stats:
                    continue
                match = re.match(r'^\s+([A-Za-z0-9_]+)\s+(\d+)\s*$', line)
                if match is None:
                    # A blank line or a non-cell line ends the block.
                    if line.strip() and not line.startswith(' '):
                        in_stats = False
                    continue
                cell, count = match.group(1), int(match.group(2))
                resource = _SYNTH_ECP5_CELL_MAP.get(cell)
                if resource is not None:
                    utilization[resource] = {
                        'used': count,
                        'available': budget.get(resource, 0),
                    }
    except OSError:
        return {}
    return utilization


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
            'include_dirs': self.include_dirs,
            # RV-Bench local patch: metrics-only runs skip the bitstream step.
            'bitstream': self.bitstream,
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
            "reports", f'{self.technology}_timing.rpt'
        )
        power_file = os.path.join(
            "reports", f'{self.technology}_power.rpt'
        )
        util_file_xml = os.path.join(
            "reports", f'{self.technology}_utilization.xml'
        )
        csv_file = os.path.join(report_path, f'{self.technology}_report.csv')

        # RV-Bench local patch (not upstream): YosysFlow.report() already
        # creates this directory; VivadoFlow's did not, so a hardware run
        # that completed synthesis and bitstream still died at report() with
        # FileNotFoundError because --report-path pointed at a directory
        # nothing had created. The Tcl's own reports/ lives in the cwd, but
        # --report-path is a separate, caller-supplied directory.
        os.makedirs(report_path, exist_ok=True)

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

        # --- PARSE POWER SUMMARY for Dynamic and Device Static ---
        dynamic_w = 0.0
        device_static_w = 0.0
        if os.path.exists(power_file):
            with open(power_file, 'r') as f:
                content = f.read()
                dynamic_match = re.search(r'Dynamic \(W\)\s*\|\s*([0-9]*\.?[0-9]+)', content)
                if dynamic_match:
                    dynamic_w = float(dynamic_match.group(1))
                device_static_match = re.search(r'Device Static \(W\)\s*\|\s*([0-9]*\.?[0-9]+)', content)
                if device_static_match:
                    device_static_w = float(device_static_match.group(1))

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

        # --- PRINT POWER SUMMARY ---
        print('-' * 30)
        print_green('Power Summary:')
        print(f'Dynamic Power (W)      : {dynamic_w}')
        print(f'Device Static Power (W): {device_static_w}')

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

        # --- WRITE CSV --- (adicionar ao final da escrita)
        with open(csv_file, 'a', newline='') as csvf:  # 'a' para adicionar
            writer = csv.writer(csvf)
            writer.writerow(['Power', 'Dynamic (W)', f'{dynamic_w:.3f}'])
            writer.writerow(['Power', 'Device Static (W)', f'{device_static_w:.3f}'])

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

        # An already-absolute d (e.g. RV-Bench's synth-fpga always resolves
        # against the materialised source root) must not be prefixed with
        # CURRENT_DIR too -- that produced a double-concatenated, unresolvable
        # path (CURRENT_DIR + '/' + an absolute path) for every caller that
        # passes absolute include dirs, silently breaking --include-dirs
        # whenever a core's top-level file `include`s a sibling header.
        include_dirs_str = ' '.join(
            f'-I{d}' if os.path.isabs(d) else f'-I{CURRENT_DIR}/{d}'
            for d in self.include_dirs
        )

        context: Dict[str, Any] = {
            'files': self.project_files,
            'top_module': self.top_module,
            'output_json': output_json,
            # Was 'include_dirs' -- templates/yosys.j2 reads
            # {{ include_dirs_str }}, so the mismatched key rendered as
            # empty for every job regardless of what --include-dirs passed.
            # Patched locally, not upstream, per RV-Bench's convention for
            # this submodule (see run_cmd() in core/__init__.py).
            'include_dirs_str': include_dirs_str,
            # Same shape as OpenRoadFlow's synth_slang_args (core/asic.py) --
            # extra flags for this flow's own SystemVerilog frontend
            # (synlig/Surelog's read_systemverilog, not SLANG -- different
            # tool, different flag surface, hence the separate name).
            'synth_synlig_args': ' '.join(getattr(self, 'synlig_args', [])),
            # Named core presets: NAME=VALUE tokens applied with `chparam`
            # after the read step (see templates/yosys.j2).
            'frontend': getattr(self, 'frontend', 'synlig'),
            'top_params': [
                token.split('=', 1)
                for token in getattr(self, 'top_params', [])
            ],
            # RV-Bench local addition (not upstream): the `abc9` mapper
            # asserts (`no_loops' in abc9_ops.cc) on a combinational loop and
            # aborts the whole run, even though the classic `abc` handles the
            # same design.  Each read frontend is rendered twice -- once with
            # `-abc9` (better timing) and once with `-noabc9` -- and run_tool()
            # retries the `-noabc9` copy when the `-abc9` synth step fails.
            'synth_ecp5_flags': '-abc9',
        }

        write_template_to_file(
            self.env, 'yosys.j2', context, 'yosys_project.tcl'
        )
        # RV-Bench local addition (not upstream): a second project that reads
        # the same sources with Yosys's own Verilog frontend. run_tool() falls
        # back to it when the Surelog frontend aborts the process; see
        # templates/yosys_verilog.j2 for why that cannot be handled in TCL.
        write_template_to_file(
            self.env, 'yosys_verilog.j2', context, 'yosys_verilog.tcl'
        )
        # RV-Bench local addition (not upstream): a third project that reads
        # the same sources with Slang's full SystemVerilog frontend.  It is
        # only reached when both the Surelog and the plain `read_verilog`
        # projects fail; it covers cores whose SystemVerilog is too modern
        # for Yosys's parser but whose `read_systemverilog -link` crashes
        # (see templates/yosys_slang.j2).
        write_template_to_file(
            self.env, 'yosys_slang.j2', context, 'yosys_slang.tcl'
        )
        # RV-Bench local addition (not upstream): a fourth project that reads
        # the sources in Verilog-2005 mode (no `-sv`), for cores whose RTL
        # uses a SystemVerilog keyword as an identifier (`input int,`) and
        # therefore cannot go through any of the three SystemVerilog
        # frontends.  See templates/yosys_verilog2005.j2.
        write_template_to_file(
            self.env, 'yosys_verilog2005.j2', context, 'yosys_verilog2005.tcl'
        )

        # RV-Bench local addition (not upstream): the same four frontends with
        # the classic `abc` instead of `abc9` (see synth_ecp5_flags above).
        # run_tool() falls back to these when the `-abc9` synth step aborts on
        # a combinational loop.
        noabc9_context = dict(context, synth_ecp5_flags='-noabc9')
        write_template_to_file(
            self.env, 'yosys.j2', noabc9_context, 'yosys_project_noabc9.tcl'
        )
        write_template_to_file(
            self.env, 'yosys_verilog.j2', noabc9_context,
            'yosys_verilog_noabc9.tcl',
        )
        write_template_to_file(
            self.env, 'yosys_slang.j2', noabc9_context,
            'yosys_slang_noabc9.tcl',
        )
        write_template_to_file(
            self.env, 'yosys_verilog2005.j2', noabc9_context,
            'yosys_verilog2005_noabc9.tcl',
        )
        os.makedirs('build', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        print_green(f"Yosys project files generated for '{self.technology}'")

    def run_tool(self) -> None:
        prefix: str = YOSYS_BOARDS[self.technology]['prefix']
        lpf_file: str = (
            f'{CONSTRAINTS_DIR}/{self.technology}.lpf'
            if self.constraint_file == 'default'
            else os.path.abspath(self.constraint_file)
        )

        yosys_path = TOOLCHAINS_INSTALL_PATH.get('yosys', '')

        frontend = getattr(self, 'frontend', 'synlig')
        if frontend == 'yosys':
            yosys_bin = os.getenv('YOSYS_EXE') or os.path.join(yosys_path, 'yosys')
        else:
            yosys_bin = os.getenv('SYNLIG_EXE') or os.path.join(yosys_path, 'synlig')
        nextpnr_bin = (os.getenv('NEXTPNR_ECP5_EXE') or
                       os.path.join(yosys_path, 'nextpnr-ecp5') or 'nextpnr-ecp5')
        ecppack_bin = (os.getenv('ECPPACK_EXE') or
                       os.path.join(yosys_path, 'ecppack') or 'ecppack')

        # RV-Bench local addition (not upstream): a previous run of this same
        # job shares the scratch directory and may have left a place-and-route
        # report behind.  nextpnr only overwrites it on success, so a run that
        # fails at placement would otherwise read the stale report and record
        # the previous run's numbers.  Drop it first so `report()` can tell
        # "nextpnr wrote nothing" from "nextpnr wrote this run's numbers".
        try:
            os.remove(f'reports/{prefix}_place_route.json')
        except OSError:
            pass

        # RV-Bench local addition (not upstream): each read frontend is tried
        # with `-abc9` first and, if that synth step aborts (the `no_loops'
        # assert in abc9_ops.cc), with its `-noabc9` copy.  The `-noabc9`
        # retry is taken only when the read step itself succeeded -- the
        # templates touch `build/rvbench_read_ok` right after the read, so a
        # frontend that fails while parsing is not re-run.  See
        # `synth_ecp5_flags` in generate_project.
        slang_yosys = _slang_yosys_bin()
        frontends: list[tuple[str, list[str]]] = [
            ('SystemVerilog', [yosys_bin, '-c', 'yosys_project.tcl']),
            ('Yosys read_verilog', [yosys_bin, '-c', 'yosys_verilog.tcl']),
        ]
        if slang_yosys:
            frontends.append(
                ('Slang', [slang_yosys, '-m', 'slang', '-c', 'yosys_slang.tcl'])
            )
        frontends.append(
            ('Verilog-2005', [yosys_bin, '-c', 'yosys_verilog2005.tcl'])
        )

        read_ok_marker = 'build/rvbench_read_ok'
        synthesised = False
        last_error: subprocess.CalledProcessError | None = None
        for index, (label, command) in enumerate(frontends):
            if index:
                print_yellow(f'retrying with the {label} frontend')
            try:
                os.remove(read_ok_marker)
            except OSError:
                pass
            try:
                run_cmd(command)
                synthesised = True
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
            # The read succeeded (the marker exists) but the `-abc9` synth
            # step aborted: retry the same frontend with the classic `abc`.
            noabc9 = [*command[:-1], command[-1].replace('.tcl', '_noabc9.tcl')]
            if not os.path.exists(read_ok_marker) or not os.path.exists(noabc9[-1]):
                continue
            print_yellow(
                f'{label} frontend read the design but the -abc9 synth step '
                f'failed; retrying with -noabc9'
            )
            try:
                run_cmd(noabc9)
                synthesised = True
                break
            except subprocess.CalledProcessError as exc:
                last_error = exc
        if not synthesised and last_error is not None:
            raise last_error

        # RV-Bench local addition (not upstream): the metrics variant builds
        # the core's own top, which is not a board-level design and has no
        # board pin constraints.  A core with more than 381 user ports (the
        # ECP5 45K's IO budget) therefore cannot be placed: nextpnr tries to
        # insert an IO buffer for every port and runs out of TRELLIS_IO BELs.
        # nextpnr's `--out-of-context` mode skips IO buffer insertion and
        # global promotion entirely, which is exactly what a utilisation and
        # timing estimate needs; the board variant still places IO.
        # In that mode nextpnr cannot emit a Trellis textcfg, so it writes the
        # post-PnR JSON instead (--write), and the bitstream pack is skipped.
        nextpnr_args = [
            nextpnr_bin,
            '--json',
            f'build/{prefix}.synth.json',
            '--lpf',
            lpf_file,
            YOSYS_BOARDS[self.technology]['option'],
            '--package',
            YOSYS_BOARDS[self.technology]['package'],
            '--speed',
            YOSYS_BOARDS[self.technology]['speed'],
            '--lpf-allow-unconstrained',
            '--report',
            f'reports/{prefix}_place_route.json',
            *getattr(self, 'nextpnr_args', []),
        ]
        if not self.bitstream:
            nextpnr_args += [
                '--out-of-context',
                '--ignore-loops',
                '--timing-allow-fail',
                '--write',
                f'build/{prefix}.pnr.json',
            ]
        else:
            nextpnr_args += ['--textcfg', f'build/{prefix}.config']

        # RV-Bench local addition (not upstream): for a metrics-only run a
        # design that does not fit or misses timing is a *result*, not a
        # failure -- "the core would need 131% of the LUTs" is exactly the
        # number the metrics variant is meant to report.  nextpnr exits
        # non-zero and writes no report in that case, so let the run
        # continue and fall back to the synthesis utilisation in report().
        if not self.bitstream:
            try:
                run_cmd(nextpnr_args)
            except subprocess.CalledProcessError:
                print_yellow(
                    'nextpnr did not complete (design does not fit or '
                    'misses timing); reporting synthesis utilisation only'
                )
        else:
            run_cmd(nextpnr_args)

        # RV-Bench local patch: metrics-only runs skip the bitstream pack.
        # The nextpnr report already carries utilisation and timing, so the
        # .bit is dead weight for a metrics variant.
        if self.bitstream:
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
        run_cmd(['rm', '-rf', 'build', '*.bit', '*.json', '*.rpt', 'slpp_all'], check=False)

    def _find_synth_log(self, report_path: str) -> str | None:
        """Locate the log that holds `synth_ecp5`'s "Number of cells" block.

        RV-Bench local addition (not upstream): `synth_ecp5` prints its
        utilisation to stdout and the flow captures no copy of its own, so
        the caller's redirection is the only one there is.  Two are checked,
        in this order:

        - `subprocess.stdout.log` in the cwd.  RV-Bench's runner streams the
          flow's stdout straight to that file (see `ToolContext.run_subprocess`)
          and runs the flow from its scratch directory, so it is present --
          and, by the time `report()` runs, complete for the synthesis step,
          which finished before this Python process reached `report()`.
        - `stdout.log` in the cwd, for a standalone run redirected to a file.

        The wrapper's copy wins because it is the one the run record itself
        is built from.
        """
        for candidate in ('subprocess.stdout.log', 'stdout.log'):
            if os.path.isfile(candidate):
                return candidate
        return None

    def report(self, report_path: str = 'reports') -> None:

        print_blue(f"Generating report for board: '{self.technology}'")
        
        prefix: str = YOSYS_BOARDS[self.technology]['prefix']
        json_report_path: str = f'reports/{prefix}_place_route.json'
        csv_path: str = f'{report_path}/{prefix}_report.csv'

        # --- Lê o JSON ---
        # RV-Bench local addition (not upstream): when the metrics-only
        # run did not fit (or missed timing), nextpnr writes no report, so
        # fall back to the `synth_ecp5` utilisation from the job log.  That
        # still answers "how much of the board would it occupy"; the timing
        # side is unavailable, so only the utilisation is reported.
        if os.path.exists(json_report_path):
            with open(json_report_path, 'r') as f:
                data: Dict[str, Any] = json.load(f)
            fmax_info: Dict[str, Any] = data.get('fmax', {})
            util_info: Dict[str, Any] = data.get('utilization', {})
        else:
            print_yellow(
                'nextpnr report missing; falling back to synth_ecp5 '
                'utilisation (timing unavailable)'
            )
            fmax_info = {}
            log_path = self._find_synth_log(report_path)
            util_info = (
                _parse_synth_ecp5_utilization(log_path, self.technology)
                if log_path
                else {}
            )

        os.makedirs(report_path, exist_ok=True)

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
        run_cmd(['rm', '-rf', 'build', 'reports', '*.jou', '*.log', '*.bit'], check=False)

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
    include_dirs: List[str],
    env: Environment,
) -> ImplementationFlow:
    if board_name in VIVADO_BOARDS:
        return VivadoFlow(
            technology=board_name, project_files=project_files, constraint_file=constraint_file, top_module=top_module, env=env, include_dirs=include_dirs
        )
    elif board_name in YOSYS_BOARDS:
        return YosysFlow(
            technology=board_name, project_files=project_files, constraint_file=constraint_file, top_module=top_module, env=env, include_dirs=include_dirs
        )
    elif board_name in GOWIN_BOARDS:
        return GowinFlow(
            technology=board_name, project_files=project_files, constraint_file=constraint_file, top_module=top_module, env=env, include_dirs=include_dirs
        )
    else:
        raise ValueError(f"Board '{board_name}' not supported.")


# -------------------------
# Função principal
# -------------------------
def run_fpga_flow(
    board_name: str,
    project_files: List[str],
    include_dirs: List[str],
    constraint_file: str = 'default',
    top_module: str = 'processorci_top',
    get_reports: bool = False,
    clean: bool = False,
    report_path: str = 'reports',
    synlig_args: list[str] | None = None,
    nextpnr_args: list[str] | None = None,
    frontend: str = 'synlig',
    top_params: list[str] | None = None,
    bitstream: bool = True,
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
        board_name=board_name,
        project_files=project_files,
        constraint_file=constraint_file,
        top_module=top_module,
        include_dirs=include_dirs,
        env=env,
    )
    flow.synlig_args = synlig_args or []
    flow.nextpnr_args = nextpnr_args or []
    flow.frontend = frontend
    flow.top_params = top_params or []
    # RV-Bench local patch: metrics-only runs skip the bitstream step.
    flow.bitstream = bitstream
    flow.run()

    if get_reports:
        flow.report(report_path=report_path)

    if clean:
        flow.clean()
