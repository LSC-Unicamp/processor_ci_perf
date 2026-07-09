CONTROLLER_FILES = [
    'modules/uart.sv',
    'modules/UART/rtl/uart_rx.v',
    'modules/UART/rtl/uart_tx.v',
    'rtl/fifo.sv',
    'rtl/reset.sv',
    'rtl/clk_divider.sv',
    'rtl/memory.sv',
    'rtl/interpreter.sv',
    'rtl/controller.sv',
    'timer.sv',
]

PROCESSOR_INTERNAL_FILES = [
    'internal/fpga_top.sv',
    'internal/axi4lite_to_wishbone.sv',
    'internal/axi4_to_wishbone.sv',
    'internal/ahblite_to_wishbone.sv',
]
