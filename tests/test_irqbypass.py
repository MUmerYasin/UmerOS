"""
Tests for UmerOS Virt Lib - IRQ Bypass Manager
==============================================
"""

import unittest
import sys
import os

# Add the virt/lib module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from virt.lib import (
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
)


class TestEventFDContext(unittest.TestCase):
    """Test EventFDContext"""
    
    def test_eventfd_creation(self):
        efd = EventFDContext(fd=10)
        self.assertEqual(efd.fd, 10)
    
    def test_eventfd_equality(self):
        efd1 = EventFDContext(fd=10)
        efd2 = EventFDContext(fd=10)
        efd3 = efd1
        
        self.assertNotEqual(efd1, efd2)  # Different objects
        self.assertEqual(efd1, efd3)     # Same object


class TestIRQBypassProducer(unittest.TestCase):
    """Test IRQBypassProducer"""
    
    def test_producer_creation(self):
        producer = IRQBypassProducer()
        self.assertIsNone(producer.eventfd)
        self.assertEqual(producer.irq, 0)
        self.assertIsNone(producer.consumer)
        self.assertIsNone(producer.add_consumer)
        self.assertIsNone(producer.del_consumer)
        self.assertIsNone(producer.start)
        self.assertIsNone(producer.stop)
    
    def test_producer_with_callbacks(self):
        def add_consumer(prod, cons):
            return 0
        
        def del_consumer(prod, cons):
            pass
        
        producer = IRQBypassProducer()
        producer.add_consumer = add_consumer
        producer.del_consumer = del_consumer
        
        self.assertEqual(producer.add_consumer, add_consumer)
        self.assertEqual(producer.del_consumer, del_consumer)


class TestIRQBypassConsumer(unittest.TestCase):
    """Test IRQBypassConsumer"""
    
    def test_consumer_creation(self):
        consumer = IRQBypassConsumer()
        self.assertIsNone(consumer.eventfd)
        self.assertIsNone(consumer.producer)
        self.assertIsNone(consumer.add_producer)
        self.assertIsNone(consumer.del_producer)
        self.assertIsNone(consumer.start)
        self.assertIsNone(consumer.stop)
    
    def test_consumer_required_callbacks(self):
        def add_producer(cons, prod):
            return 0
        
        def del_producer(cons, prod):
            pass
        
        consumer = IRQBypassConsumer()
        consumer.add_producer = add_producer
        consumer.del_producer = del_producer
        
        self.assertEqual(consumer.add_producer, add_producer)
        self.assertEqual(consumer.del_producer, del_producer)


class TestIRQBypassManager(unittest.TestCase):
    """Test IRQBypassManager"""
    
    def setUp(self):
        self.manager = IRQBypassManager()
    
    def test_manager_creation(self):
        self.assertEqual(len(self.manager._producers), 0)
        self.assertEqual(len(self.manager._consumers), 0)
    
    def test_register_producer(self):
        producer = IRQBypassProducer()
        eventfd = EventFDContext(fd=10)
        
        ret = self.manager.register_producer(producer, eventfd, 42)
        self.assertEqual(ret, 0)
        self.assertEqual(producer.irq, 42)
        self.assertIs(producer.eventfd, eventfd)
        self.assertEqual(len(self.manager._producers), 1)
    
    def test_register_producer_duplicate(self):
        producer1 = IRQBypassProducer()
        producer2 = IRQBypassProducer()
        eventfd = EventFDContext(fd=10)
        
        ret1 = self.manager.register_producer(producer1, eventfd, 10)
        self.assertEqual(ret1, 0)
        
        # Same eventfd - should fail
        ret2 = self.manager.register_producer(producer2, eventfd, 20)
        self.assertEqual(ret2, -22)  # EINVAL
    
    def test_unregister_producer(self):
        producer = IRQBypassProducer()
        eventfd = EventFDContext(fd=10)
        
        self.manager.register_producer(producer, eventfd, 10)
        self.assertEqual(len(self.manager._producers), 1)
        
        self.manager.unregister_producer(producer)
        self.assertEqual(len(self.manager._producers), 0)
        self.assertIsNone(producer.eventfd)
    
    def test_unregister_unregistered_producer(self):
        producer = IRQBypassProducer()
        # Should not raise
        self.manager.unregister_producer(producer)
    
    def test_register_consumer(self):
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        eventfd = EventFDContext(fd=20)
        
        ret = self.manager.register_consumer(consumer, eventfd)
        self.assertEqual(ret, 0)
        self.assertIs(consumer.eventfd, eventfd)
        self.assertEqual(len(self.manager._consumers), 1)
    
    def test_register_consumer_missing_callbacks(self):
        consumer = IRQBypassConsumer()
        eventfd = EventFDContext(fd=20)
        
        ret = self.manager.register_consumer(consumer, eventfd)
        self.assertEqual(ret, -22)  # EINVAL
    
    def test_unregister_consumer(self):
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        eventfd = EventFDContext(fd=20)
        
        self.manager.register_consumer(consumer, eventfd)
        self.assertEqual(len(self.manager._consumers), 1)
        
        self.manager.unregister_consumer(consumer)
        self.assertEqual(len(self.manager._consumers), 0)
        self.assertIsNone(consumer.eventfd)
    
    def test_producer_consumer_connection(self):
        """Test automatic connection when both register with same eventfd"""
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd = EventFDContext(fd=30)
        
        # Register producer first
        ret1 = self.manager.register_producer(producer, eventfd, 10)
        self.assertEqual(ret1, 0)
        self.assertIsNone(producer.consumer)
        
        # Register consumer - should auto-connect
        ret2 = self.manager.register_consumer(consumer, eventfd)
        self.assertEqual(ret2, 0)
        self.assertIs(producer.consumer, consumer)
        self.assertIs(consumer.producer, producer)
    
    def test_consumer_then_producer_connection(self):
        """Test connection when consumer registers first"""
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd = EventFDContext(fd=40)
        
        # Register consumer first
        ret1 = self.manager.register_consumer(consumer, eventfd)
        self.assertEqual(ret1, 0)
        self.assertIsNone(consumer.producer)
        
        # Register producer - should auto-connect
        ret2 = self.manager.register_producer(producer, eventfd, 10)
        self.assertEqual(ret2, 0)
        self.assertIs(producer.consumer, consumer)
        self.assertIs(consumer.producer, producer)
    
    def test_disconnect_on_unregister(self):
        """Test disconnect when unregistering"""
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd = EventFDContext(fd=50)
        
        self.manager.register_producer(producer, eventfd, 10)
        self.manager.register_consumer(consumer, eventfd)
        
        self.assertIsNotNone(producer.consumer)
        self.assertIsNotNone(consumer.producer)
        
        # Unregister producer - should disconnect
        self.manager.unregister_producer(producer)
        
        self.assertIsNone(producer.consumer)
        self.assertIsNone(consumer.producer)
    
    def test_get_producer_consumer(self):
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd = EventFDContext(fd=60)
        
        self.assertIsNone(self.manager.get_producer(eventfd))
        self.assertIsNone(self.manager.get_consumer(eventfd))
        
        self.manager.register_producer(producer, eventfd, 10)
        self.assertIs(self.manager.get_producer(eventfd), producer)
        
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        self.manager.register_consumer(consumer, eventfd)
        self.assertIs(self.manager.get_consumer(eventfd), consumer)
    
    def test_get_stats(self):
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd1 = EventFDContext(fd=10)
        eventfd2 = EventFDContext(fd=20)
        
        stats = self.manager.get_stats()
        self.assertEqual(stats["producers"], 0)
        self.assertEqual(stats["consumers"], 0)
        self.assertEqual(stats["connected_pairs"], 0)
        
        self.manager.register_producer(producer, eventfd1, 10)
        stats = self.manager.get_stats()
        self.assertEqual(stats["producers"], 1)
        
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        self.manager.register_consumer(consumer, eventfd2)
        stats = self.manager.get_stats()
        self.assertEqual(stats["producers"], 1)
        self.assertEqual(stats["consumers"], 1)
        
        # Now connect them
        eventfd3 = EventFDContext(fd=30)
        producer2 = IRQBypassProducer()
        consumer2 = IRQBypassConsumer()
        consumer2.add_producer = lambda c, p: 0
        consumer2.del_producer = lambda c, p: None
        
        self.manager.register_producer(producer2, eventfd3, 20)
        self.manager.register_consumer(consumer2, eventfd3)
        
        stats = self.manager.get_stats()
        self.assertEqual(stats["connected_pairs"], 1)


class TestGlobalManager(unittest.TestCase):
    """Test global manager functions"""
    
    def setUp(self):
        # Reset global manager
        set_global_manager(IRQBypassManager())
    
    def test_global_manager_functions(self):
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        
        eventfd = EventFDContext(fd=100)
        
        # Register via global functions
        ret = irq_bypass_register_producer(producer, eventfd, 10)
        self.assertEqual(ret, 0)
        
        consumer.add_producer = lambda c, p: 0
        consumer.del_producer = lambda c, p: None
        ret = irq_bypass_register_consumer(consumer, eventfd)
        self.assertEqual(ret, 0)
        
        self.assertIs(producer.consumer, consumer)
        
        # Unregister via global functions
        irq_bypass_unregister_producer(producer)
        self.assertIsNone(producer.consumer)
        self.assertIsNone(consumer.producer)
        
        irq_bypass_unregister_consumer(consumer)
    
    def test_get_global_manager(self):
        manager = get_global_manager()
        self.assertIsInstance(manager, IRQBypassManager)
    
    def test_set_global_manager(self):
        custom_manager = IRQBypassManager()
        set_global_manager(custom_manager)
        self.assertIs(get_global_manager(), custom_manager)


class TestCallbacks(unittest.TestCase):
    """Test callback execution"""
    
    def test_producer_callbacks(self):
        manager = IRQBypassManager()
        
        producer = IRQBypassProducer()
        consumer = IRQBypassConsumer()
        
        callback_log = []
        
        def add_consumer(prod, cons):
            callback_log.append(("add_consumer", prod, cons))
            return 0
        
        def del_consumer(prod, cons):
            callback_log.append(("del_consumer", prod, cons))
        
        def start_producer(prod):
            callback_log.append(("start_producer", prod))
        
        def stop_producer(prod):
            callback_log.append(("stop_producer", prod))
        
        producer.add_consumer = add_consumer
        producer.del_consumer = del_consumer
        producer.start = start_producer
        producer.stop = stop_producer
        
        # Set up consumer callbacks BEFORE registration so they're called during connection
        consumer.add_producer = lambda c, p: callback_log.append(("add_producer", c, p)) or 0
        consumer.del_producer = lambda c, p: callback_log.append(("del_producer", c, p))
        consumer.start = lambda c: callback_log.append(("start_consumer", c))
        consumer.stop = lambda c: callback_log.append(("stop_consumer", c))
        
        eventfd = EventFDContext(fd=10)
        
        manager.register_producer(producer, eventfd, 10)
        manager.register_consumer(consumer, eventfd)
        
        # Check connection callbacks
        self.assertIn(("stop_producer", producer), callback_log)
        self.assertIn(("stop_consumer", consumer), callback_log)
        self.assertIn(("add_consumer", producer, consumer), callback_log)
        self.assertIn(("add_producer", consumer, producer), callback_log)
        self.assertIn(("start_consumer", consumer), callback_log)
        self.assertIn(("start_producer", producer), callback_log)
        
        callback_log.clear()
        
        # Disconnect
        manager.unregister_producer(producer)
        
        self.assertIn(("stop_producer", producer), callback_log)
        self.assertIn(("stop_consumer", consumer), callback_log)
        self.assertIn(("del_consumer", producer, consumer), callback_log)
        self.assertIn(("del_producer", consumer, producer), callback_log)
        self.assertIn(("start_consumer", consumer), callback_log)
        self.assertIn(("start_producer", producer), callback_log)


if __name__ == '__main__':
    unittest.main(verbosity=2)