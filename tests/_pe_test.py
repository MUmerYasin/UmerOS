"""Trace pe_loader selftest step by step."""
import sys
sys.path.insert(0, '.')
from compatibility.pe_loader import _build_fake_pe, PeFile

data = _build_fake_pe()
pe = PeFile.from_bytes(data)

# Reproduce the selftest's checks
checks = [
    ('machine == 0x014C', pe.machine == 0x014C),
    ('pe_class == PeClass.PE32', pe.optional_header.pe_class == 0x14C and pe.optional_header.pe_class.value == 32),
    ('number_of_sections != 2', pe.number_of_sections != 2),
    ('entry_point_rva != 0x1000', pe.entry_point_rva != 0x1000),
    ('image_base != 0x400000', pe.image_base != 0x400000),
    ('subsystem_name != WINDOWS_CUI', pe.subsystem_name != "WINDOWS_CUI"),
    ('dll_characteristics & 0x100 == 0', (pe.optional_header.dll_characteristics & 0x100) == 0),
    ('len(dirs) != 16', len(pe.optional_header.data_directories) != 16),
    ('dir0 is_present', pe.optional_header.data_directories[0].is_present),
    ('dir1 is_present', pe.optional_header.data_directories[1].is_present),
    ('.text not in names', ".text" not in [s.name for s in pe.sections]),
    ('.data not in names', ".data" not in [s.name for s in pe.sections]),
    ('not text.is_code', not pe.sections[0].is_code),
    ('not data.is_data', not pe.sections[1].is_data),
    ('rva_to_offset off != 0x200', pe.rva_to_offset(0x1000)[0] != 0x200),
    ('get_data != 0xC3', pe.get_data(0x1000, 1) != b'\xC3'),
]
for name, val in checks:
    print(f'  {"FAIL -> " if val else "OK    "}  {name}')

if all(v for _, v in checks):
    print('  ALL PASS')
else:
    print('  at least one fails -> selftest returns False')
