"""Locate native Python method table entries for Lirin's metin queue."""

import struct
from pathlib import Path


data = Path(__file__).parents[1].joinpath("input", "LirinGame.exe").read_bytes()
pe = struct.unpack_from("<I", data, 0x3C)[0]
number_sections = struct.unpack_from("<H", data, pe + 6)[0]
optional_size = struct.unpack_from("<H", data, pe + 20)[0]
image_base = struct.unpack_from("<Q", data, pe + 24 + 24)[0]
section_start = pe + 24 + optional_size
sections = []
for index in range(number_sections):
    start = section_start + index * 40
    name, virtual_size, rva, raw_size, raw_start = struct.unpack_from("<8sIIII", data, start)
    sections.append((name.rstrip(b"\0").decode("ascii"), virtual_size, rva, raw_size, raw_start))


def va_for_offset(offset):
    for name, virtual_size, rva, raw_size, raw_start in sections:
        if raw_start <= offset < raw_start + raw_size:
            return image_base + rva + offset - raw_start
    return None


for method in ("MetinQueueAdd", "MetinQueueGetSize", "MetinQueueGetMaxSize",
               "MetinQueueIsEnabled", "MetinQueueSetEnabled",
               "AddMetinQueueAllowedRace"):
    needle = method.encode("ascii") + b"\0"
    offset = data.find(needle)
    if offset < 0:
        print(method, "string not found")
        continue
    va = va_for_offset(offset)
    print(method, "string VA", hex(va))
    pointer = struct.pack("<Q", va)
    search = 0
    while True:
        reference = data.find(pointer, search)
        if reference < 0:
            break
        search = reference + 1
        if reference + 32 <= len(data):
            function, flags, doc = struct.unpack_from("<QI4xQ", data, reference + 8)
            if image_base <= function < image_base + 0x10000000:
                print("  table", hex(va_for_offset(reference)), "function", hex(function),
                      "flags", hex(flags), "doc", hex(doc))
