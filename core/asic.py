import os
import subprocess
from core.pdk_defines import DEFINES_BY_PDK, SUPPORTED_PDKS


def run_asic_flow(pdk_name: str, project_files: list[str]) -> None:
    pdk_name = pdk_name.lower()

    if pdk_name not in SUPPORTED_PDKS:
        raise ValueError(f"PDK '{pdk_name}' is not supported.")
