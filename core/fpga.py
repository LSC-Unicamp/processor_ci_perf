import os
import subprocess
from core.board_defines import (
    DEFINES_BY_BOARD,
    SUPPORTED_BOARDS,
    VIVADO_BOARDS,
    YOSYS_BOARDS,
    GOWIN_BOARDS,
)


def write_defines(board_name, filename='processor_ci_defines.vh'):
    if board_name not in DEFINES_BY_BOARD:
        raise ValueError(f"Board '{board_name}' not found.")

    with open(filename, 'w') as f:
        f.write(DEFINES_BY_BOARD[board_name])
    print(f"File '{filename}' generated for board: '{board_name}'.")
