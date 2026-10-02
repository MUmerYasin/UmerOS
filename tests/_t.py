from compatibility.win32_runner import build_gettickcount_pe
blob = build_gettickcount_pe()
print("blob[0x15c:0x164]:", blob[0x15c:0x164].hex())
