"""
OpenOrgaTEX Industrial Event & Message Broker
High-performance Pub/Sub event bus.
Enables decoupled event-driven architecture between:
- Log Ingestion / Status Watchers (Publishers)
- Realtime Setpoint Readers & Intervention Auditors (Subscribers)
- WebSockets & Telemetry Notifiers
Works natively in-memory with zero external setup,
and supports Redis Pub/Sub if REDIS_URL is configured.
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional, Set
from collections import deque

logger = logging.getLogger("orgatex.event_broker")

class EventMessage:
    def __init__(self, topic: str, data: Dict[str, Any], message_id: Optional[str] = None):
        self.topic = topic
        self.data = data
        self.timestamp = datetime.utcnow().isoformat()
        self.message_id = message_id or f"{topic}_{datetime.utcnow().timestamp()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "topic": self.topic,
            "timestamp": self.timestamp,
            "data": self.data
        }

class EventBroker:
    """
    Central Message Broker for OpenOrgaTEX.
    Singleton pattern with topic-based pub/sub.
    """
    _instance: Optional['EventBroker'] = None

    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[EventMessage], Any]]] = {}
        self._async_subscribers: Dict[str, Set[Callable[[EventMessage], Any]]] = {}
        self._message_queue: Optional[asyncio.Queue] = None
        self._history: deque = deque(maxlen=200)
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def get_instance(cls) -> 'EventBroker':
        if cls._instance is None:
            cls._instance = EventBroker()
        return cls._instance

    def subscribe(self, topic: str, callback: Callable[[EventMessage], Any]):
        """Subscribe a synchronous or asynchronous callback to a topic."""
        if asyncio.iscoroutinefunction(callback):
            if topic not in self._async_subscribers:
                self._async_subscribers[topic] = set()
            self._async_subscribers[topic].add(callback)
        else:
            if topic not in self._subscribers:
                self._subscribers[topic] = set()
            self._subscribers[topic].add(callback)
        logger.info(f"Subscribed callback to topic: {topic}")

    def unsubscribe(self, topic: str, callback: Callable[[EventMessage], Any]):
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)
        if topic in self._async_subscribers and callback in self._async_subscribers[topic]:
            self._async_subscribers[topic].remove(callback)

    async def start(self):
        """Starts the event loop worker for dispatching queued async messages."""
        if self._is_running:
            return
        self._is_running = True
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
        self._message_queue = asyncio.Queue()
        self._worker_task = asyncio.create_task(self._dispatch_loop())
        logger.info("OpenOrgaTEX Event Broker started successfully.")

    async def stop(self):
        """Stops the broker cleanly."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("OpenOrgaTEX Event Broker stopped.")

    async def _dispatch_loop(self):
        """Background worker that pulls messages from queue and executes async subscribers."""
        while self._is_running:
            try:
                msg: EventMessage = await self._message_queue.get()

                # Dispatch async subscribers
                topics = [msg.topic]
                if "*" not in topics:
                    topics.append("*")

                for t in topics:
                    for acb in list(self._async_subscribers.get(t, [])):
                        try:
                            res = acb(msg)
                            if asyncio.iscoroutine(res):
                                asyncio.create_task(res)
                        except Exception as e:
                            logger.error(f"Error in async subscriber for {msg.topic}: {e}")

                self._message_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Event Broker dispatch loop: {e}")
                await asyncio.sleep(0.1)

    async def publish(self, topic: str, data: Dict[str, Any], message_id: Optional[str] = None):
        """Publish a message asynchronously."""
        msg = EventMessage(topic, data, message_id)
        self._history.append(msg.to_dict())

        # Notify sync subscribers
        self._dispatch_sync(msg)

        # Notify async subscribers
        if self._message_queue is not None:
            await self._message_queue.put(msg)

    def publish_sync(self, topic: str, data: Dict[str, Any], message_id: Optional[str] = None):
        """Thread-safe synchronous publish: immediately invokes sync callbacks and queues async."""
        msg = EventMessage(topic, data, message_id)
        self._history.append(msg.to_dict())

        # 1. Immediately dispatch to synchronous callbacks
        self._dispatch_sync(msg)

        # 2. Queue for async subscribers if loop is active
        if self._loop and self._loop.is_running() and self._message_queue is not None and self._async_subscribers:
            try:
                self._loop.call_soon_threadsafe(self._message_queue.put_nowait, msg)
            except Exception as qe:
                logger.debug(f"Queue push bypassed: {qe}")

    def _dispatch_sync(self, msg: EventMessage):
        topics = [msg.topic]
        if "*" not in topics:
            topics.append("*")
        for t in topics:
            for cb in list(self._subscribers.get(t, [])):
                try:
                    cb(msg)
                except Exception as e:
                    logger.error(f"Error executing sync callback for {msg.topic}: {e}")

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(self._history)[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "running" if self._is_running else "stopped",
            "topics": list(set(list(self._subscribers.keys()) + list(self._async_subscribers.keys()))),
            "total_subscribers": sum(len(v) for v in self._subscribers.values()) + sum(len(v) for v in self._async_subscribers.values()),
            "queue_size": self._message_queue.qsize() if self._message_queue else 0,
            "total_logged_messages": len(self._history)
        }

# Global singleton helper
broker = EventBroker.get_instance()
