DEFINES_BY_BOARD = {
    'xilinx_vc709': """\
`define CLOCK_FREQ 100_000_000
`define MEMORY_SIZE 16384
`define HIGH_CLK 1
`define ID 32'h56433730 // VC709
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
`define DIFERENCIAL_CLK 1
""",
    'digilent_arty_a7_100t': """\
`define CLOCK_FREQ 50_000_000
`define MEMORY_SIZE 8192
`define HIGH_CLK 1
`define ID 32'h41525459 // ARTY
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
    'digilent_nexys4_ddr': """\
`define CLOCK_FREQ 50_000_000
`define MEMORY_SIZE 8192
`define HIGH_CLK 1
`define ID 32'h4E455859 // NEXYS
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
    'opensdrlab_kintex7': """\
`define CLOCK_FREQ 50_000_000
`define MEMORY_SIZE 8192
`define ID 32'h4B494E54 // KINTEX
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
    'zedboard': """\
`define CLOCK_FREQ 50_000_000
`define MEMORY_SIZE 8192
`define ID 32'h5A454442 // ZEDBOARD
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
    'colorlight_i9': """\
`define CLOCK_FREQ 25_000_000
`define MEMORY_SIZE 4096
`define ID 32'h434F4C4F // COLORLIGHT 
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
    'tangnano_20k': """\
`define CLOCK_FREQ 27_000_000
`define MEMORY_SIZE 4096
`define ID 32'h54414E47 // TANG
`define BIT_RATE 115200
`define PAYLOAD_BITS 8
`define BUFFER_SIZE 8
`define PULSE_CONTROL_BITS 32
`define BUS_WIDTH 32
`define WORD_SIZE_BY 4
`define RESET_CLK_CYCLES 20
`define MEMORY_FILE ""
""",
}

VIVADO_BOARDS = {
    'xilinx_vc709': {
        'part': 'xc7vx690tffg1761-2',
        'vendor': 'xilinx',
        'family': 'virtex7',
        'prefix': 'xilinx_vc709',
    },
    'digilent_arty_a7_100t': {
        'part': 'xc7a100tcsg324-1',
        'vendor': 'xilinx',
        'family': 'artix7',
        'prefix': 'digilent_arty_a7_100t',
    },
    'digilent_nexys4_ddr': {
        'part': 'xc7a100tcsg324-1',
        'vendor': 'xilinx',
        'family': 'artix7',
        'prefix': 'digilent_nexys4_ddr',
    },
    'opensdrlab_kintex7': {
        'part': 'xc7k325tffg676-2',
        'vendor': 'xilinx',
        'family': 'kintex7',
        'prefix': 'opensdrlab_kintex7',
    },
    'zedboard': {
        'part': 'xc7z020clg484-1',
        'vendor': 'xilinx',
        'family': 'zynq7',
        'prefix': 'zedboard',
    },
}

YOSYS_BOARDS = {
    'colorlight_i9': {
        'part': 'ecp5-45f',
        'vendor': 'lattice',
        'family': 'ecp5',
        'prefix': 'colorlight_i9',
        'option': '--45k',
        'package': 'CABGA381',
        'speed': '6',
    }
}

GOWIN_BOARDS = {
    'tangnano_20k': {
        'device_name': 'GW1NR-9C',
        'device_package': 'C',
        'vendor': 'gowin',
        'family': 'gowin',
        'prefix': 'tangnano_20k',
    },
    'tangnano_9k': {
        'device_name': 'GW1NR-9K',
        'device_package': 'C',
        'vendor': 'gowin',
        'family': 'gowin',
        'prefix': 'tangnano_9k',
    },
}

SUPPORTED_BOARDS = VIVADO_BOARDS | YOSYS_BOARDS | GOWIN_BOARDS
