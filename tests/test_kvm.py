"""
Tests for UmerOS KVM Python Implementation
==========================================
"""

import unittest
import sys
import os

# Add the virt/kvm module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from virt.kvm import (
    KVM, KVMVCPU, KVMMemorySlot, KVMRun,
    KVMAsyncPF, KVMAsyncPFWork, ASYNC_PF_PER_VCPU,
    KVMCoalescedMMIOZone, KVMCoalescedMMIORing, KVM_COALESCED_MMIO_MAX,
    kvm_coalesced_mmio_init, kvm_coalesced_mmio_free,
    kvm_vm_ioctl_register_coalesced_mmio, kvm_vm_ioctl_unregister_coalesced_mmio,
    KVMStatsHeader, KVMStatsDesc, KVM_STATS_NAME_SIZE, kvm_stats_read,
    KVMDirtyRing, KVMDirtyGFN, KVM_DIRTY_GFN_F_DIRTY, KVM_DIRTY_GFN_F_RESET,
    KVMKernelIrqRoutingEntry, KVM_Irq_Routing_Table,
    KVMEventFD, KVMIOEventFD, KVMVirqFD,
    KVMGuestMemfd, KVMCreateGuestMemfd,
    GFNToPFNCache, KVM_PFN_ERR_FAULT, INVALID_GPA, KVM_HVA_ERR_BAD,
    KVMVFIO, KVMVFIOFile,
    KVMFollowPFN, KVM_MMU_LOCK, KVM_MMU_UNLOCK, KVM_MMU_LOCK_INIT,
    KVM_EXIT_REASONS, KVM_MAX_VCPUS, KVM_MAX_MEM_SLOTS, KVM_PAGE_SIZE,
    kvm_async_pf_init, kvm_async_pf_deinit, kvm_async_pf_vcpu_init,
    kvm_gmem_init, kvm_gmem_exit,
    kvm_gpc_init, kvm_gpc_activate, kvm_gpc_deactivate,
    KVM_STATS_TYPE_CUMULATIVE, KVM_STATS_UNIT_BYTES,
)


class TestKVMMemorySlot(unittest.TestCase):
    """Test KVMMemorySlot"""
    
    def test_create_memory_slot(self):
        slot = KVMMemorySlot(
            id=0,
            base_gfn=0x1000,
            npages=1024,
            userspace_addr=0x7f0000000000,
            flags=0
        )
        self.assertEqual(slot.id, 0)
        self.assertEqual(slot.base_gfn, 0x1000)
        self.assertEqual(slot.npages, 1024)
        self.assertEqual(slot.userspace_addr, 0x7f0000000000)


class TestKVMVCPU(unittest.TestCase):
    """Test KVMVCPU"""
    
    def test_create_vcpu(self):
        kvm = KVM()
        vcpu = kvm.create_vcpu(0)
        self.assertEqual(vcpu.vcpu_id, 0)
        self.assertEqual(vcpu.kvm, kvm)
        self.assertIsNotNone(vcpu.run)
    
    def test_multiple_vcpus(self):
        kvm = KVM()
        for i in range(4):
            vcpu = kvm.create_vcpu(i)
            self.assertEqual(vcpu.vcpu_id, i)
        
        self.assertEqual(kvm.online_vcpus, 4)
    
    def test_get_vcpu(self):
        kvm = KVM()
        kvm.create_vcpu(0)
        kvm.create_vcpu(1)
        
        vcpu0 = kvm.get_vcpu(0)
        vcpu1 = kvm.get_vcpu(1)
        vcpu2 = kvm.get_vcpu(2)
        
        self.assertIsNotNone(vcpu0)
        self.assertIsNotNone(vcpu1)
        self.assertIsNone(vcpu2)


class TestKVMMemoryManagement(unittest.TestCase):
    """Test KVM Memory Management"""
    
    def test_set_memory_region(self):
        kvm = KVM()
        ret = kvm.set_memory_region(
            slot=0,
            flags=0,
            guest_phys_addr=0x100000,
            memory_size=0x1000000,  # 16MB
            userspace_addr=0x7f0000000000
        )
        self.assertEqual(ret, 0)
        
        slot = kvm.get_memory_region(0)
        self.assertIsNotNone(slot)
        self.assertEqual(slot.npages, 0x1000000 // KVM_PAGE_SIZE)
        self.assertIsNotNone(slot.dirty_bitmap)
    
    def test_clear_memory_region(self):
        kvm = KVM()
        kvm.set_memory_region(0, 0, 0x100000, 0x1000000, 0x7f0000000000)
        
        # Clear by setting size to 0
        ret = kvm.set_memory_region(0, 0, 0, 0, 0)
        self.assertEqual(ret, 0)
        
        slot = kvm.get_memory_region(0)
        self.assertIsNone(slot)
    
    def test_gfn_to_hva(self):
        kvm = KVM()
        kvm.set_memory_region(0, 0, 0x100000, 0x10000, 0x7f0000000000)
        
        # GFN within slot (slot starts at 0x100000/4096 = 0x100, has 0x10000/4096 = 0x10 pages)
        hva = kvm.gfn_to_hva(0x100)  # First page of slot
        expected = 0x7f0000000000
        self.assertEqual(hva, expected)
        
        hva = kvm.gfn_to_hva(0x101)  # Second page
        expected = 0x7f0000000000 + KVM_PAGE_SIZE
        self.assertEqual(hva, expected)
        
        # GFN outside slot
        hva = kvm.gfn_to_hva(0x110)
        self.assertEqual(hva, -1)


class TestKVMAsyncPF(unittest.TestCase):
    """Test Async Page Fault"""
    
    def test_async_pf_init(self):
        ret = kvm_async_pf_init()
        self.assertEqual(ret, 0)
        
        kvm_async_pf_deinit()
    
    def test_async_pf_vcpu_init(self):
        kvm = KVM()
        vcpu = kvm.create_vcpu(0)
        
        kvm_async_pf_vcpu_init(vcpu)
        
        self.assertIsNotNone(vcpu.async_pf)
        self.assertEqual(vcpu.async_pf.queued, 0)
    
    def test_async_pf_setup(self):
        kvm = KVM()
        vcpu = kvm.create_vcpu(0)
        kvm_async_pf_vcpu_init(vcpu)
        
        # Try to setup async PF
        result = kvm._async_pf_manager.alloc_work() is not None
        self.assertTrue(result)


class TestKVMCoalescedMMIO(unittest.TestCase):
    """Test Coalesced MMIO"""
    
    def test_coalesced_mmio_init(self):
        kvm = KVM()
        ret = kvm_coalesced_mmio_init(kvm)
        self.assertEqual(ret, 0)
        
        self.assertIsNotNone(kvm.coalesced_mmio_ring)
        self.assertEqual(kvm.coalesced_mmio_ring.first, 0)
        self.assertEqual(kvm.coalesced_mmio_ring.last, 0)
    
    def test_register_coalesced_mmio(self):
        kvm = KVM()
        kvm_coalesced_mmio_init(kvm)
        
        zone = KVMCoalescedMMIOZone(
            addr=0x3f8,  # COM1
            size=8,
            pio=1
        )
        
        ret = kvm_vm_ioctl_register_coalesced_mmio(kvm, zone)
        self.assertEqual(ret, 0)
        self.assertEqual(len(kvm.coalesced_zones), 1)
    
    def test_unregister_coalesced_mmio(self):
        kvm = KVM()
        kvm_coalesced_mmio_init(kvm)
        
        zone = KVMCoalescedMMIOZone(addr=0x3f8, size=8, pio=1)
        kvm_vm_ioctl_register_coalesced_mmio(kvm, zone)
        
        ret = kvm_vm_ioctl_unregister_coalesced_mmio(kvm, zone)
        self.assertEqual(ret, 0)
        self.assertEqual(len(kvm.coalesced_zones), 0)


class TestKVMBinaryStats(unittest.TestCase):
    """Test Binary Statistics"""
    
    def test_stats_header_pack_unpack(self):
        header = KVMStatsHeader(
            name_size=KVM_STATS_NAME_SIZE,
            num_desc=2,
            id_offset=40,
            desc_offset=40 + KVM_STATS_NAME_SIZE,
            data_offset=40 + KVM_STATS_NAME_SIZE + 2 * (24 + KVM_STATS_NAME_SIZE)
        )
        
        packed = header.pack()
        unpacked = KVMStatsHeader.unpack(packed)
        
        self.assertEqual(unpacked.name_size, header.name_size)
        self.assertEqual(unpacked.num_desc, header.num_desc)
        self.assertEqual(unpacked.id_offset, header.id_offset)
    
    def test_stats_desc_pack_unpack(self):
        desc = KVMStatsDesc(
            offset=0,
            size=8,
            type=KVM_STATS_TYPE_CUMULATIVE,
            unit=KVM_STATS_UNIT_BYTES,
            scale=0,
            name="test_stat"
        )
        
        packed = desc.pack()
        unpacked = KVMStatsDesc.unpack(packed)
        
        self.assertEqual(unpacked.offset, desc.offset)
        self.assertEqual(unpacked.size, desc.size)
        self.assertEqual(unpacked.type, desc.type)
        self.assertEqual(unpacked.unit, desc.unit)
        self.assertEqual(unpacked.name, desc.name)
    
    def test_kvm_stats_read(self):
        header = KVMStatsHeader(
            name_size=KVM_STATS_NAME_SIZE,
            num_desc=1,
            id_offset=40,
            desc_offset=40 + KVM_STATS_NAME_SIZE,
            data_offset=40 + KVM_STATS_NAME_SIZE + (24 + KVM_STATS_NAME_SIZE)
        )
        
        desc = [KVMStatsDesc(
            offset=0, size=8, type=0, unit=0, scale=0, name="test"
        )]
        
        stats_data = b'\x10\x00\x00\x00\x00\x00\x00\x00'  # value 16
        
        user_buffer = bytearray(100)
        bytes_read = kvm_stats_read("test-vm", header, desc, stats_data,
                                    user_buffer, 100, 0)
        
        self.assertGreater(bytes_read, 0)


class TestKVMDirtyRing(unittest.TestCase):
    """Test Dirty Ring"""
    
    def test_dirty_ring_alloc(self):
        kvm = KVM()
        ring = KVMDirtyRing()
        
        ret = ring.__init__()
        ret = kvm._dirty_ring_alloc(kvm, ring, 0, 4096)
        self.assertEqual(ret, 0)
        
        self.assertGreater(ring.size, 0)
        self.assertEqual(ring.dirty_index, 0)
        self.assertEqual(ring.reset_index, 0)
    
    def test_dirty_ring_push(self):
        kvm = KVM()
        ring = KVMDirtyRing()
        kvm._dirty_ring_alloc(kvm, ring, 0, 4096)
        
        # Push some dirty entries
        ring.dirty_index = 0
        for i in range(10):
            ring.dirty_gfns[ring.dirty_index & (ring.size - 1)].slot = 0
            ring.dirty_gfns[ring.dirty_index & (ring.size - 1)].offset = i
            ring.dirty_gfns[ring.dirty_index & (ring.size - 1)].flags = KVM_DIRTY_GFN_F_DIRTY
            ring.dirty_index += 1
        
        self.assertEqual(kvm._dirty_ring_used(ring), 10)
        self.assertFalse(kvm._dirty_ring_soft_full(ring))
    
    def test_dirty_ring_reset(self):
        kvm = KVM()
        ring = KVMDirtyRing()
        kvm._dirty_ring_alloc(kvm, ring, 0, 4096)
        
        # Add entries and mark as harvested
        for i in range(5):
            entry = ring.dirty_gfns[i]
            entry.slot = 0
            entry.offset = i
            entry.flags = KVM_DIRTY_GFN_F_DIRTY | KVM_DIRTY_GFN_F_RESET
        
        ring.dirty_index = 5
        ring.reset_index = 0
        
        nr_reset = [0]
        ret = kvm._dirty_ring_reset(kvm, ring, nr_reset)
        
        self.assertEqual(ret, 0)
        self.assertEqual(nr_reset[0], 5)
        self.assertEqual(ring.reset_index, 5)


class TestKVMIRQChip(unittest.TestCase):
    """Test IRQ Chip / Routing"""
    
    def test_init_irq_routing(self):
        kvm = KVM()
        ret = kvm.init_irq_routing()
        self.assertEqual(ret, 0)
        
        self.assertIsNotNone(kvm.irq_routing)
        self.assertEqual(kvm.irq_routing.nr_rt_entries, 1)
    
    def test_create_irqchip_entry(self):
        entry = KVMKernelIrqRoutingEntry()
        entry.gsi = 1
        entry.type = 0  # KVM_IRQ_ROUTING_IRQCHIP
        entry.flags = 0
        entry.irqchip = {'irqchip': 0, 'pin': 1}
        
        self.assertEqual(entry.gsi, 1)
        self.assertEqual(entry.type, 0)


class TestKVMEventFD(unittest.TestCase):
    """Test EventFD"""
    
    def test_eventfd_create(self):
        from kvm.eventfd import eventfd_create, eventfd_signal, eventfd_read
        
        fd = eventfd_create()
        self.assertGreaterEqual(fd, 0)
        
        # Signal
        ret = eventfd_signal(fd, 5)
        self.assertEqual(ret, 0)
        
        # Read back
        val = eventfd_read(fd)
        self.assertEqual(val, 5)
        
        os.close(fd)
    
    def test_kvm_eventfd_init(self):
        kvm = KVM()
        eventfd = KVMEventFD()
        
        from kvm.eventfd import eventfd_create, kvm_eventfd_init
        fd = eventfd_create()
        
        ret = kvm_eventfd_init(kvm, eventfd, fd, virq=1)
        self.assertEqual(ret, 0)
        self.assertTrue(eventfd.active)
        self.assertEqual(eventfd.virq, 1)
        
        os.close(fd)


class TestKVMGuestMemfd(unittest.TestCase):
    """Test Guest Memfd"""
    
    def test_gmem_init(self):
        ret = kvm_gmem_init()
        self.assertEqual(ret, 0)
        
        kvm_gmem_exit()
    
    def test_gmem_create(self):
        kvm = KVM()
        kvm_gmem_init()
        
        args = KVMCreateGuestMemfd(size=4096 * 1024, flags=0)
        ret = kvm.kvm_gmem_create(kvm, args)
        
        if ret == 0:  # May fail on non-Linux
            self.assertGreater(args.fd, 0)
            os.close(args.fd)
        
        kvm_gmem_exit()


class TestKVMPFNCache(unittest.TestCase):
    """Test PFN Cache"""
    
    def test_gpc_init(self):
        kvm = KVM()
        gpc = GFNToPFNCache()
        
        kvm_gpc_init(gpc, kvm)
        
        self.assertEqual(gpc.kvm, kvm)
        self.assertFalse(gpc.active)
        self.assertFalse(gpc.valid)
    
    def test_gpc_activate_gpa(self):
        kvm = KVM()
        gpc = GFNToPFNCache()
        
        kvm_gpc_init(gpc, kvm)
        
        # GPA-based activation
        ret = kvm_gpc_activate(gpc, 0x100000, 4096)
        
        if ret == 0:
            self.assertTrue(gpc.active)
    
    def test_gpc_deactivate(self):
        kvm = KVM()
        gpc = GFNToPFNCache()
        
        kvm_gpc_init(gpc, kvm)
        kvm_gpc_activate(gpc, 0x100000, 4096)
        
        kvm_gpc_deactivate(gpc)
        
        self.assertFalse(gpc.active)


class TestKVMVFIO(unittest.TestCase):
    """Test VFIO"""
    
    def test_vfio_init(self):
        ret = kvm.kvm_vfio_ops_init()
        self.assertEqual(ret, 0)
        
        kvm.kvm_vfio_ops_exit()


class TestKVMMMULock(unittest.TestCase):
    """Test MMU Lock"""
    
    def test_mmu_lock_init(self):
        kvm = KVM()
        KVM_MMU_LOCK_INIT(kvm)
        
        self.assertIsNotNone(kvm.mmu_lock)
    
    def test_mmu_lock_acquire_release(self):
        kvm = KVM()
        KVM_MMU_LOCK_INIT(kvm)
        
        KVM_MMU_LOCK(kvm)
        KVM_MMU_UNLOCK(kvm)


class TestConstants(unittest.TestCase):
    """Test Constants"""
    
    def test_exit_reasons(self):
        self.assertEqual(KVM_EXIT_REASONS.UNKNOWN, 0)
        self.assertEqual(KVM_EXIT_REASONS.MMIO, 6)
        self.assertEqual(KVM_EXIT_REASONS.DIRTY_RING_FULL, 31)
    
    def test_max_values(self):
        self.assertEqual(KVM_MAX_VCPUS, 1024)
        self.assertEqual(KVM_MAX_MEM_SLOTS, 1024)
        self.assertEqual(KVM_PAGE_SIZE, 4096)
    
    def test_async_pf_constants(self):
        self.assertEqual(ASYNC_PF_PER_VCPU, 64)
    
    def test_coalesced_mmio_constants(self):
        self.assertEqual(KVM_COALESCED_MMIO_MAX, 64)
    
    def test_stats_constants(self):
        self.assertEqual(KVM_STATS_NAME_SIZE, 64)
        self.assertEqual(KVM_STATS_TYPE_CUMULATIVE, 0)
        self.assertEqual(KVM_STATS_UNIT_BYTES, 1)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_full_vm_lifecycle(self):
        """Test creating VM, vCPUs, memory, and running"""
        kvm = KVM(vm_id=1)
        
        # Create vCPUs
        vcpu0 = kvm.create_vcpu(0)
        vcpu1 = kvm.create_vcpu(1)
        
        # Set up memory
        kvm.set_memory_region(0, 0, 0, 0x10000000, 0x7f0000000000)  # 256MB
        
        # Initialize subsystems
        kvm.init_irq_routing()
        kvm_coalesced_mmio_init(kvm)
        kvm_async_pf_init()
        kvm_async_pf_vcpu_init(vcpu0)
        kvm_async_pf_vcpu_init(vcpu1)
        
        # Verify state
        self.assertEqual(kvm.online_vcpus, 2)
        self.assertEqual(kvm.used_memslots, 1)
        self.assertIsNotNone(kvm.irq_routing)
        self.assertIsNotNone(kvm.coalesced_mmio_ring)
        
        # Clean up
        kvm_async_pf_deinit()
    
    def test_stats_builder(self):
        from kvm.binary_stats import KVMStatsBuilder, create_vm_stats_builder
        
        builder = create_vm_stats_builder(1)
        builder.add_stat("vcpu_count", 4, type_=KVM_STATS_TYPE_INSTANT)
        builder.add_stat("memory_bytes", 0x10000000, unit=KVM_STATS_UNIT_BYTES)
        
        buffer = builder.get_buffer()
        self.assertGreater(len(buffer), 0)
        
        # Verify we can read it back
        header = KVMStatsHeader.unpack(buffer[:40])
        self.assertEqual(header.num_desc, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)