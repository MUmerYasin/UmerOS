"""
UmerOS Virt Lib - IRQ Bypass Manager
=====================================

Python implementation of Linux kernel's virt/lib IRQ bypass manager.
Provides producer/consumer registration for interrupt offload/bypass.

Based on linux/virt/lib/irqbypass.c
"""

from .irqbypass import (
    IRQBypassProducer,
    IRQBypassConsumer,
    IRQBypassManager,
    EventFDContext,
    irq_bypass_register_producer,
    irq_bypass_unregister_producer,
    irq_bypass_register_consumer,
    irq_bypass_unregister_consumer,
    get_global_manager,
    set_global_manager,
    EINVAL,
    ENOMEM,
)

__version__ = "1.0.0"
__author__ = "UmerOS"
__license__ = "GPL-3.0"

__all__ = [
    "IRQBypassProducer",
    "IRQBypassConsumer",
    "IRQBypassManager",
    "EventFDContext",
    "irq_bypass_register_producer",
    "irq_bypass_unregister_producer",
    "irq_bypass_register_consumer",
    "irq_bypass_unregister_consumer",
    "get_global_manager",
    "set_global_manager",
    "EINVAL",
    "ENOMEM",
]