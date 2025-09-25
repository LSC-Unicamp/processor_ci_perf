SUPPORTED_PDKS = [
    'gf180',  # GlobalFoundries 180nm
    'ihp-sg13g2',  # IHP 130nm
    'sky130hs',  # SkyWater 130nm High Speed
    'sky130hd',  # SkyWater 130nm High Density
    'nangate45',  # Nangate 45nm
    'asap7',  # ASAP7 7nm
]


DEFINES_BY_PDK = {
    'gf180': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/gf180/lef/gf180mcuC.lef',
            '/path/to/gf180/lef/gf180mcuD.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/gf180/lib/gf180mcuC_typ.lib',
            '/path/to/gf180/lib/gf180mcuD_typ.lib',
        ],
    },
    'ihp-sg13g2': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/ihp-sg13g2/lef/ihp_sg13g2.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/ihp-sg13g2/lib/ihp_sg13g2_typ.lib',
        ],
    },
    'sky130hs': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/sky130hs/lef/sky130_fd_sc_hd.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/sky130hs/lib/sky130_fd_sc_hd_typ.lib',
        ],
    },
    'sky130hd': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/sky130hd/lef/sky130_fd_sc_hd.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/sky130hd/lib/sky130_fd_sc_hd_typ.lib',
        ],
    },
    'nangate45': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/nangate45/lef/nangate45.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/nangate45/lib/nangate45_typ.lib',
        ],
    },
    'asap7': {
        'additional_lefs': True,
        'additional_lef_files': [
            '/path/to/asap7/lef/asap7.lef',
        ],
        'additional_libs': True,
        'additional_lib_files': [
            '/path/to/asap7/lib/asap7_typ.lib',
        ],
    },
}
