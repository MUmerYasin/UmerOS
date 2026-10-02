from compatibility import memory_map as mm

h = mm.CreateFileMappingA(mm.INVALID_HANDLE_VALUE, None, mm.PAGE_READWRITE, 0, 4096, "Local\\UmerOS_test")
print("h=", h, flush=True)
addr = mm.MapViewOfFile(h, mm.FILE_MAP_ALL_ACCESS, 0, 0, 4096)
print("addr=", addr, flush=True)

print("calling UnmapViewOfFile...", flush=True)
ok = mm.UnmapViewOfFile(addr)
print("ok=", ok, flush=True)

print("calling CloseMappingHandle...", flush=True)
ok = mm.CloseMappingHandle(h)
print("ok=", ok, flush=True)
print("DONE", flush=True)
