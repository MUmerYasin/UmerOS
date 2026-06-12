import ctypes
from ctypes import c_int, c_uint32, POINTER
import os

# Locate shared lib relative to repo
LIB_PATH = os.path.join(os.path.dirname(__file__), '..', 'drivers', 'libumerhal.so')
LIB_PATH = os.path.abspath(LIB_PATH)

class HAL:
    def __init__(self, lib_path=LIB_PATH):
        self.lib = ctypes.CDLL(lib_path)
        self.lib.hw_init_device.argtypes = (c_int,)
        self.lib.hw_init_device.restype = c_int
        self.lib.hw_read_register.argtypes = (c_int, c_uint32, POINTER(c_uint32))
        self.lib.hw_read_register.restype = c_int
        self.lib.hw_write_register.argtypes = (c_int, c_uint32, c_uint32)
        self.lib.hw_write_register.restype = c_int

    def init_device(self, device_id: int) -> bool:
        rc = self.lib.hw_init_device(int(device_id))
        return rc == 0

    def read_register(self, device_id: int, reg: int) -> int:
        out = c_uint32()
        rc = self.lib.hw_read_register(int(device_id), c_uint32(reg), ctypes.byref(out))
        if rc != 0:
            raise RuntimeError("hw_read_register failed")
        return int(out.value)

    def write_register(self, device_id: int, reg: int, val: int) -> bool:
        rc = self.lib.hw_write_register(int(device_id), c_uint32(reg), c_uint32(val))
        return rc == 0