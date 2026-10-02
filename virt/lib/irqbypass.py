"""
IRQ Bypass Manager
==================

Python implementation of Linux kernel's IRQ bypass manager.
Allows interrupt producers and consumers to find each other for interrupt offload/bypass.

Based on linux/virt/lib/irqbypass.c
"""

import threading
import warnings
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, Dict
from abc import ABC, abstractmethod


# Error codes (Linux errno)
EINVAL = 22
ENOMEM = 12


@dataclass
class EventFDContext:
    """EventFD context - used as key for producer/consumer matching"""
    fd: int
    _id: int = field(default=0, init=False)
    
    def __post_init__(self):
        self._id = id(self)
    
    def __hash__(self):
        return self._id
    
    def __eq__(self, other):
        return isinstance(other, EventFDContext) and self._id == other._id


class IRQBypassProducer:
    """
    IRQ Bypass Producer - represents an interrupt source that can be bypassed.
    
    Producers are typically hardware devices (e.g., Intel VT-d Posted Interrupts,
    ARM IRQ Forwarding) that can deliver interrupts directly to guests.
    """
    
    def __init__(self):
        self.eventfd: Optional[EventFDContext] = None
        self.irq: int = 0
        self.consumer: Optional['IRQBypassConsumer'] = None
        
        # Optional callbacks (set by driver)
        self.add_consumer: Optional[Callable[['IRQBypassProducer', 'IRQBypassConsumer'], int]] = None
        self.del_consumer: Optional[Callable[['IRQBypassProducer', 'IRQBypassConsumer'], None]] = None
        self.start: Optional[Callable[['IRQBypassProducer'], None]] = None
        self.stop: Optional[Callable[['IRQBypassProducer'], None]] = None


class IRQBypassConsumer:
    """
    IRQ Bypass Consumer - represents an interrupt sink that can receive bypassed interrupts.
    
    Consumers are typically virtual machines or virtual devices that want to receive
    interrupts directly without host kernel involvement.
    """
    
    def __init__(self):
        self.eventfd: Optional[EventFDContext] = None
        self.producer: Optional[IRQBypassProducer] = None
        
        # Required callbacks
        self.add_producer: Optional[Callable[['IRQBypassConsumer', 'IRQBypassProducer'], int]] = None
        self.del_producer: Optional[Callable[['IRQBypassConsumer', 'IRQBypassProducer'], None]] = None
        
        # Optional callbacks
        self.start: Optional[Callable[['IRQBypassConsumer'], None]] = None
        self.stop: Optional[Callable[['IRQBypassConsumer'], None]] = None


class IRQBypassManager:
    """
    IRQ Bypass Manager - manages producer/consumer registration and connection.
    
    Uses eventfd as the key to match producers with consumers.
    Thread-safe with internal locking.
    """
    
    def __init__(self):
        self._producers: Dict[int, IRQBypassProducer] = {}
        self._consumers: Dict[int, IRQBypassConsumer] = {}
        self._lock = threading.RLock()
    
    def _connect(self, producer: IRQBypassProducer, 
                 consumer: IRQBypassConsumer) -> int:
        """
        Connect a producer to a consumer.
        Must be called with lock held.
        """
        ret = 0
        
        if producer.stop:
            producer.stop(producer)
        if consumer.stop:
            consumer.stop(consumer)
        
        if producer.add_consumer:
            ret = producer.add_consumer(producer, consumer)
        
        if ret == 0 and consumer.add_producer:
            ret = consumer.add_producer(consumer, producer)
            if ret != 0 and producer.del_consumer:
                producer.del_consumer(producer, consumer)
        
        if consumer.start:
            consumer.start(consumer)
        if producer.start:
            producer.start(producer)
        
        if ret == 0:
            producer.consumer = consumer
            consumer.producer = producer
        
        return ret
    
    def _disconnect(self, producer: IRQBypassProducer,
                    consumer: IRQBypassConsumer):
        """
        Disconnect a producer from a consumer.
        Must be called with lock held.
        """
        if producer.stop:
            producer.stop(producer)
        if consumer.stop:
            consumer.stop(consumer)
        
        consumer.del_producer(consumer, producer)
        
        if producer.del_consumer:
            producer.del_consumer(producer, consumer)
        
        if consumer.start:
            consumer.start(consumer)
        if producer.start:
            producer.start(producer)
        
        producer.consumer = None
        consumer.producer = None
    
    def register_producer(self, producer: IRQBypassProducer,
                          eventfd: EventFDContext, irq: int) -> int:
        """
        Register an IRQ bypass producer.
        
        Args:
            producer: Producer structure to register
            eventfd: EventFD context for matching with consumer
            irq: Linux IRQ number of the underlying producer device
            
        Returns:
            0 on success, negative error code on failure
        """
        if producer.eventfd is not None:
            warnings.warn("Producer already registered")
            return -EINVAL
        
        producer.irq = irq
        
        with self._lock:
            # Use eventfd's id as index (like Linux uses pointer address)
            index = id(eventfd)
            
            if index in self._producers:
                return -EINVAL
            
            self._producers[index] = producer
            
            # Check for matching consumer
            consumer = self._consumers.get(index)
            if consumer:
                ret = self._connect(producer, consumer)
                if ret != 0:
                    del self._producers[index]
                    return ret
            
            producer.eventfd = eventfd
            return 0
    
    def unregister_producer(self, producer: IRQBypassProducer):
        """
        Unregister an IRQ bypass producer.
        Safe to call even if registration failed.
        """
        if producer.eventfd is None:
            return
        
        with self._lock:
            index = id(producer.eventfd)
            
            if producer.consumer:
                self._disconnect(producer, producer.consumer)
            
            if self._producers.get(index) is producer:
                del self._producers[index]
            
            producer.eventfd = None
    
    def register_consumer(self, consumer: IRQBypassConsumer,
                          eventfd: EventFDContext) -> int:
        """
        Register an IRQ bypass consumer.
        
        Args:
            consumer: Consumer structure to register
            eventfd: EventFD context for matching with producer
            
        Returns:
            0 on success, negative error code on failure
        """
        if consumer.eventfd is not None:
            warnings.warn("Consumer already registered")
            return -EINVAL
        
        if not consumer.add_producer or not consumer.del_producer:
            return -EINVAL
        
        with self._lock:
            index = id(eventfd)
            
            if index in self._consumers:
                return -EINVAL
            
            self._consumers[index] = consumer
            
            # Check for matching producer
            producer = self._producers.get(index)
            if producer:
                ret = self._connect(producer, consumer)
                if ret != 0:
                    del self._consumers[index]
                    return ret
            
            consumer.eventfd = eventfd
            return 0
    
    def unregister_consumer(self, consumer: IRQBypassConsumer):
        """
        Unregister an IRQ bypass consumer.
        Safe to call even if registration failed.
        """
        if consumer.eventfd is None:
            return
        
        with self._lock:
            index = id(consumer.eventfd)
            
            if consumer.producer:
                self._disconnect(consumer.producer, consumer)
            
            if self._consumers.get(index) is consumer:
                del self._consumers[index]
            
            consumer.eventfd = None
    
    def get_producer(self, eventfd: EventFDContext) -> Optional[IRQBypassProducer]:
        """Get producer by eventfd"""
        with self._lock:
            return self._producers.get(id(eventfd))
    
    def get_consumer(self, eventfd: EventFDContext) -> Optional[IRQBypassConsumer]:
        """Get consumer by eventfd"""
        with self._lock:
            return self._consumers.get(id(eventfd))
    
    def get_stats(self) -> Dict[str, int]:
        """Get manager statistics"""
        with self._lock:
            return {
                "producers": len(self._producers),
                "consumers": len(self._consumers),
                "connected_pairs": sum(1 for p in self._producers.values() if p.consumer is not None)
            }


# Global manager instance (singleton pattern like Linux kernel)
_global_manager = IRQBypassManager()


def irq_bypass_register_producer(producer: IRQBypassProducer,
                                  eventfd: EventFDContext, irq: int) -> int:
    """Register an IRQ bypass producer (global manager)"""
    return _global_manager.register_producer(producer, eventfd, irq)


def irq_bypass_unregister_producer(producer: IRQBypassProducer):
    """Unregister an IRQ bypass producer (global manager)"""
    _global_manager.unregister_producer(producer)


def irq_bypass_register_consumer(consumer: IRQBypassConsumer,
                                  eventfd: EventFDContext) -> int:
    """Register an IRQ bypass consumer (global manager)"""
    return _global_manager.register_consumer(consumer, eventfd)


def irq_bypass_unregister_consumer(consumer: IRQBypassConsumer):
    """Unregister an IRQ bypass consumer (global manager)"""
    _global_manager.unregister_consumer(consumer)


def get_global_manager() -> IRQBypassManager:
    """Get the global IRQ bypass manager instance"""
    return _global_manager


# For testing: allow replacing global manager
def set_global_manager(manager: IRQBypassManager):
    """Set a custom global manager (for testing)"""
    global _global_manager
    _global_manager = manager