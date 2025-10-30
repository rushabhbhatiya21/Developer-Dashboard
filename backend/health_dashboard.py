#!/usr/bin/env python3
"""
WebSocket-based Health Dashboard Backend
Using FastAPI WebSockets + Redis for real-time monitoring
"""

import os
import json
import logging
import asyncio
import uvicorn
import redis.asyncio as aioredis

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Callable, Awaitable


from shared.config import get_settings # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AsyncRedisClient:
    """
    An asynchronous Redis client wrapper class that provides optimized methods for common Redis operations,
    including Pub/Sub functionality.

    Features:
    - Asynchronous operations for improved performance
    - Connection pooling for better resource utilization
    - Serialization/deserialization of complex data types
    - Pub/Sub support for real-time messaging
    - Batch operations for efficiency
    - Type annotations for better IDE support
    - RedisJSON support for structured data storage
    - Pub/Sub support for real-time messaging
    - Singleton pattern to ensure only one instance exists
    """
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self, host: str = get_settings().redis_host, port: int = get_settings().redis_port, **kwargs):
        """
        Initialize the Redis client with connection parameters.

        Parameters
        ----------
        host : str, optional
            Redis server hostname. Defaults to 'localhost'.
        port : int, optional
            Redis server port. Defaults to 6379.
        **kwargs : dict, optional
            - db : int, optional
                Redis database number. Defaults to 0.
            - username : str, optional
                Redis authentication username. Defaults to None.
            - password : str, optional
                Redis authentication password. Defaults to None.
            - decode_responses : bool, optional
                Whether to decode Redis responses to strings. Defaults to True.
            - max_connections : int, optional
                Size of the connection pool. Defaults to 10.
            - default_ttl : int, optional
                Default time-to-live for keys in seconds. Defaults to 86400 (24 hours).
        """

        self.host = host
        self.port = port
        self.db = kwargs.get('db', 0)
        self.username = kwargs.get('username')
        self.password = kwargs.get('password')
        self.decode_responses = kwargs.get('decode_responses', True)
        self.max_connections = kwargs.get('max_connections', 10)
        self.default_ttl = kwargs.get('default_ttl', 86400)

        self._client: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None

        self._connection_url = f"redis://{self.host}:{self.port}/{self.db}"
        if self.password:
            self._connection_url = f"redis://{self.username}:{self.password}@{self.host}:{self.port}/{self.db}"
        # if self._client:
        #     self._json_client = self._client.json()

        # Stores active subscription handlers
        self._subscription_tasks = set()
        self._channel_handlers = {}
        self._client = aioredis.Redis.from_url(
            self._connection_url,
            decode_responses=self.decode_responses,
            max_connections=self.max_connections
        )
        if self._client:
            self._pubsub = self._client.pubsub()

        self.sets = defaultdict(set)
        self.lists = defaultdict(list)

    @classmethod
    async def get_instance(cls, **kwargs) -> "AsyncRedisClient":
        """Returns the singleton instance of AsyncRedisClient."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(**kwargs)
                await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        """Initialize the Redis connection."""
        self._client = aioredis.Redis.from_url(
            self._connection_url,
            decode_responses=self.decode_responses,
            max_connections=self.max_connections
        )
        self._pubsub = self._client.pubsub()

    async def ttl(self, key: str) -> int:
        """
        Get the remaining time-to-live for a key.

        Args:
            key: The Redis key

        Returns:
            TTL in seconds, -1 if key has no TTL, -2 if key doesn't exist
        """
        return await self._client.ttl(key)

    async def _set_ttl(self, key: str, ttl: Optional[int] = None) -> None:
        """
        Set TTL for a key if a TTL value is provided.

        Args:
            key: The Redis key
            ttl: Time-to-live in seconds, if None, use default_ttl (if set)
        """
        # Use provided TTL, fall back to default TTL if available
        effective_ttl = ttl if ttl is not None else self.default_ttl

        if effective_ttl is not None:
            await self._client.expire(key, effective_ttl)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> Any:
        """
        Set a key-value pair in Redis with optional expiration.

        Args:
            key: The key to set
            value: The value to set (will be serialized if not a string)
            ex: Expiration time in seconds (None means no expiration)

        Returns:
            bool: Success status
        """
        if not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value)

        if ex is not None:
            return await self._client.setex(key, ex, value)
        else:
            result = await self._client.set(key, value)
            await self._set_ttl(key, ex)
            return result

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from Redis by key.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The value or default if key doesn't exist
        """
        value = await self._client.get(key)
        if value is None:
            return default

        # Try to deserialize JSON if it looks like JSON
        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        return value

    async def delete(self, key: str) -> None:
        """
        Delete a key from Redis.
        Args:
            key: The key to delete

        Returns:
            None
        """
        await self._client.delete(key)

    async def hset(self, key: str, field: str, value: Any, ttl: Optional[int] = None) -> Any:
        """
        Set a field-value pair in a Redis hash.

        Args:
            key: The Redis hash key
            field: The field inside the hash
            value: The value to store (will be serialized if needed)
            ttl: Time-to-live in seconds, if None, use default_ttl (if set)

        Returns:
            Number of fields that were added.
        """
        if not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value)  # Serialize complex data to JSON

        result = await self._client.hset(key, field, value)
        await self._set_ttl(key, ttl)
        return result

    async def hget(self, key: str, field: str, default: Any = None) -> Any:
        """
        Get a field value from a Redis hash.

        Args:
            key: The Redis hash key
            field: The field to retrieve
            default: Default value if field doesn't exist

        Returns:
            The value of the field or default if not found.
        """
        value = await self._client.hget(key, field)
        if value is None or value == 'null':
            return default

        if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        return value

    async def hset_multiple(self, key: str, mapping: dict, ttl: Optional[int] = None) -> Any:
        """
        Set multiple field-value pairs in a Redis hash.

        Args:
            key: The Redis hash key
            mapping: A dictionary of field-value pairs
            ttl: Time-to-live in seconds, if None, use default_ttl (if set)

        Returns:
            Number of fields that were added.
        """
        # Convert non-string values (dict, list) to JSON strings
        serialized_mapping = {
            k: json.dumps(v) if not isinstance(v, (str, int, float, bool)) else v for k, v in mapping.items()
        }

        result = await self._client.hmset(name=key, mapping=serialized_mapping)
        await self._set_ttl(key, ttl)
        return result

    async def hget_all(self, key: str) -> dict:
        """
        Retrieve all field-value pairs from a Redis hash.

        Args:
            key: The Redis hash key

        Returns:
            Dictionary of field-value pairs.
        """
        stored_data = await self._client.hgetall(key)

        # Convert JSON strings back to dictionaries or lists if necessary
        return {k: json.loads(v) if v.startswith('{') or v.startswith('[') else v for k, v in stored_data.items()}

    # --- LIST OPERATIONS ---
    async def lpush(self, key: str, value: str) -> int:
        """
        Push ``values`` onto the head of the list ``name``

        Args:
            key: The Redis hash key
            value: The value to push

        Returns:
            int: Number of fields that were added.
        """
        return await self._client.lpush(key, value)

    async def ltrim(self, key: str, start: int, end: int) -> str:
        """
        Trim the list ``name``, removing all values not within the slice between ``start`` and ``end``
        ``start`` and ``end`` can be negative numbers just like Python slicing notation

        Args:
            key: The Redis hash key
            start: The start index
            end: The end index

        Returns:
            str
        """
        return await self._client.ltrim(key, start, end)

    async def list_push(self, key: str, values: List[str], ttl: Optional[int] = None) -> int:
        """
        Append one or more string values to the end of a Redis list.

        Args:
            key (str): The Redis key where the list is stored.
            *values (List[str]): List of one or more string values to append to the redis list.
            ttl: Time-to-live in seconds, if None, use default_ttl (if set)

        Returns:
            int: The length of the list after the push operation.
        """
        length = await self._client.rpush(key, *values)
        await self._set_ttl(key, ttl)
        return length

    async def list_get(self, key: str, start: int = 0, end: int = -1) -> List[str]:
        """
        Retrieve a range of elements from a Redis list.

        Args:
            key (str): The Redis key where the list is stored.
            start (int, optional): The starting index (default 0 = first element).
            end (int, optional): The ending index (default -1 = last element).

        Returns:
            List[str]: A list of string elements retrieved from the Redis list.
        """
        return await self._client.lrange(key, start, end)

    async def list_remove(self, key: str, value: str, count: int = 0) -> int:
        """
        Remove occurrences of a specific value from a Redis list.

        Args:
            key (str): The Redis key where the list is stored.
            value (str): The value to remove from the list.
            count (int, optional):
                Number of occurrences to remove:
                  > 0 : remove from head to tail.
                  < 0 : remove from tail to head.
                  = 0 : remove all occurrences.
                Defaults to 0 (remove all).

        Returns:
            int: The number of removed elements.
        """
        return await self._client.lrem(key, count, value)


    async def list_rpop(self, key: str) -> Optional[str]:
        """
        Remove and return the last element from a Redis list.

        Args:
            key (str): The Redis key where the list is stored.

        Returns:
            Optional[str]: The value of the last element in the list, or None if the list is empty.
        """
        return await self._client.rpop(key)

    async def list_len(self, key: str) -> int:
        """
        Get the length of a Redis list.

        Args:
            key (str): The Redis key where the list is stored.

        Returns:
            int: The number of elements in the list.
                 Returns 0 if the key does not exist or the list is empty.
        """
        return await self._client.llen(key)

    # --- SET OPERATIONS ---
    async def sadd(self, key: str, value: str):
        await self._client.sadd(key, value)

    async def srem(self, key: str, value: str):
        await self._client.srem(key, value)

    async def smembers(self, key: str):
        return await self._client.smembers(key)

    async def hincr_by(self, key: str, field: str, value: int = 1):
        """
        Increment a hash field's integer value in Redis.

        Args:
            key (str): The Redis hash key where the field is stored.
            field (str): The specific field inside the hash to increment.
            value (int, optional): The amount to increment by (default is 1).

        Returns:
            int: The new value of the field after incrementing.
        """
        # Ensure the Redis field exists and increment its value
        return await self._client.hincrby(key, field, value)

    async def hdelete_fields(self, key: str, *fields: str) -> int:
        """
        Deletes specific fields from a Redis hash.

        Args:
            key (str): The Redis hash key.
            *fields (str): The fields to remove.

        Returns:
            int: The number of fields that were removed.
        """
        return await self._client.hdel(key, *fields)

    async def hdelete(self, key: str) -> bool:
        """
        Deletes an entire Redis hash.

        Args:
            key (str): The Redis hash key.

        Returns:
            bool: True if the key was deleted, False if it did not exist.
        """
        return await self._client.delete(key) > 0

    async def hexists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.

        Args:
            key: The key to check

        Returns:
            bool: True if key exists, False otherwise
        """
        return bool(await self._client.hexists(key))

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set an expiration time on a key.

        Args:
            key: The key to set expiration on
            seconds: Time in seconds until expiration

        Returns:
            bool: Success status
        """
        return await self._client.expire(key, seconds)

    async def pipeline_execute(self, commands: List[tuple]) -> List[Any]:
        """
        Execute multiple commands in a pipeline for better performance.

        Args:
            commands: List of (method_name, args, kwargs) tuples

        Returns:
            List[Any]: Results of the commands
        """
        pipeline = self._client.pipeline()

        for cmd, args, kwargs in commands:
            method = getattr(pipeline, cmd)
            method(*args, **kwargs)

        return await pipeline.execute()

    async def flush_db(self) -> bool:
        """
        Remove all keys from the current database.

        Returns:
            bool: Success status
        """
        return await self._client.flushdb()

    # PUB/SUB METHODS

    async def publish(self, channel: str, message: Dict) -> int:
        """
        Publish a message to a channel.

        Args:
            channel: The channel to publish to
            message: The message to publish (will be serialized if not a string)

        Returns:
            int: Number of clients that received the message
        """
        print(f'publishing message to channel: {channel}')
        message = json.dumps(message)
        return await self._client.publish(channel, message)

    @staticmethod
    async def _message_handler(channel_name: str, pubsub: aioredis.client.PubSub) -> None:
        """
        Internal handler for processing messages from a subscription.

        Args:
            channel_name: Redis channel name
            pubsub: Pubsub client

        Returns:
            None
        """
        # channel_name = channel.name.decode('utf-8') if isinstance(channel.name, bytes) else channel.name
        handler: Callable[[str, Any], Awaitable[None]] = pubsub.channels.get(channel_name)

        if not handler:
            print('handler not found.')
            return

        try:
            async for message in pubsub.listen():
                payload = message

                # Try to deserialize if it looks like JSON
                if isinstance(payload, str) and (payload.startswith('{') or payload.startswith('[')):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        pass

                # Call the user's handler with the message
                await handler(channel_name, payload)

        except asyncio.CancelledError:
            # Subscription was cancelled
            pass
        except Exception as e:
            print(f"Error processing message from channel {channel_name}: {str(e)}")


    async def subscribe(self, channel: str, handler: Callable[[str, Any], Awaitable[None]]) -> None:
        """
        Subscribe to a channel.

        Args:
            channel: The channel to subscribe to
            handler: Async callback function that receives (channel, message)
        """
        # Store the handler for this channel
        self._channel_handlers[channel] = handler

        # Create a Redis channel
        await self._pubsub.subscribe(channel, **{f'{channel}': handler})

        print('listening...')
        # Start a task to process messages
        task = asyncio.create_task(self._message_handler(channel_name=channel, pubsub=self._pubsub))
        self._subscription_tasks.add(task)

        # Clean up the task when it's done
        task.add_done_callback(self._subscription_tasks.discard)

    async def awaitable_subscribe(self, channel: str, handler: Callable[[str, Any], Awaitable[None]]) -> None:
        """
        Subscribe to a channel and wait.

        Args:
            channel: The channel to subscribe to
            handler: Async callback function that receives (channel, message)
        """
        # Store the handler for this channel
        self._channel_handlers[channel] = handler

        # Create a Redis channel
        await self._pubsub.subscribe(channel, **{f'{channel}': handler})

        print('listening...')
        # Start a task to process messages
        await self._message_handler(channel_name=channel, pubsub=self._pubsub)
        # self._subscription_tasks.add(task)
        #
        # # Clean up the task when it's done
        # task.add_done_callback(self._subscription_tasks.discard)

    async def unsubscribe(self, channel: str) -> None:
        """
        Unsubscribe from a channel.

        Args:
            channel: The channel to unsubscribe from
        """
        await self._pubsub.unsubscribe(channel)

        # Remove the handler
        if channel in self._channel_handlers:
            del self._channel_handlers[channel]


    async def close(self) -> None:
        """
        Close all connections and cancel subscription tasks.
        """
        # Cancel all subscription tasks
        for task in self._subscription_tasks:
            task.cancel()

        if self._subscription_tasks:
            await asyncio.gather(*self._subscription_tasks, return_exceptions=True)
            self._subscription_tasks.clear()

        # Close PubSub connection
        if self._pubsub is not None:
            await self._pubsub.aclose()
            # await self.pubsub.wait_closed()

        # Close main connections pool
        if self._client is not None:
            await self._client.aclose()
            # await self.client.wait_closed()


# ============================================================================
# Data Models
# ============================================================================

class WorkerStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class WorkerState(BaseModel):
    worker_id: str
    name: str
    endpoint: str
    port: int
    capabilities: List[str] = Field(default_factory=list)
    version: str = "1.0.0"
    connected: bool = False
    connected_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    sid: Optional[str] = None  # WebSocket connection ID
    status: WorkerStatus = WorkerStatus.UNKNOWN


class MetricsSnapshot(BaseModel):
    worker_id: str
    timestamp: str
    cpu: float = 0.0
    memory: int = 0
    memory_percent: float = 0.0
    total_processed: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    throughput_per_sec: float = 0.0
    avg_response_time_ms: float = 0.0
    queue_depth: int = 0


class HealthCheckRequest(BaseModel):
    check_id: str


class HealthCheckResponse(BaseModel):
    check_id: str
    status: str
    worker_status: str
    last_heartbeat: str
    container_id: str = "unknown"
    uptime_seconds: int = 0
    check_response_time_ms: float = 0.0


class ResourceHealth(BaseModel):
    resource_type: str
    resources: Dict[str, Any]
    timestamp: str


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionType(str, Enum):
    WORKER = "worker"
    DASHBOARD = "dashboard"
    ADMIN = "admin"


class ConnectionManager:
    """Manage WebSocket connections by type"""

    def __init__(self):
        # Store connections by type and ID
        self.workers: Dict[str, WebSocket] = {}  # worker_id -> websocket
        self.dashboards: Dict[str, WebSocket] = {}  # connection_id -> websocket
        self.admins: Dict[str, WebSocket] = {}  # connection_id -> websocket

        # Track connection metadata
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}

    async def connect_worker(self, worker_id: str, websocket: WebSocket):
        """Register a worker connection"""
        await websocket.accept()
        self.workers[worker_id] = websocket
        self.connection_metadata[worker_id] = {
            "type": ConnectionType.WORKER,
            "connected_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        logger.info(f"Worker {worker_id} connected. Total workers: {len(self.workers)}")

    async def connect_dashboard(self, connection_id: str, websocket: WebSocket):
        """Register a dashboard client connection"""
        await websocket.accept()
        self.dashboards[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "type": ConnectionType.DASHBOARD,
            "connected_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        logger.info(f"Dashboard {connection_id} connected. Total dashboards: {len(self.dashboards)}")

    def disconnect_worker(self, worker_id: str):
        """Remove a worker connection"""
        if worker_id in self.workers:
            del self.workers[worker_id]
            del self.connection_metadata[worker_id]
            logger.info(f"Worker {worker_id} disconnected. Total workers: {len(self.workers)}")

    def disconnect_dashboard(self, connection_id: str):
        """Remove a dashboard connection"""
        if connection_id in self.dashboards:
            del self.dashboards[connection_id]
            del self.connection_metadata[connection_id]
            logger.info(f"Dashboard {connection_id} disconnected. Total dashboards: {len(self.dashboards)}")

    async def send_to_worker(self, worker_id: str, message: Dict[str, Any]):
        """Send message to specific worker"""
        if worker_id in self.workers:
            try:
                await self.workers[worker_id].send_json(message)
                self.connection_metadata[worker_id]["last_activity"] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"Failed to send to worker {worker_id}: {e}")
                self.disconnect_worker(worker_id)

    async def broadcast_to_dashboards(self, message: Dict[str, Any]):
        """Broadcast message to all dashboard clients"""
        disconnected = []
        for conn_id, websocket in self.dashboards.items():
            try:
                await websocket.send_json(message)
                self.connection_metadata[conn_id]["last_activity"] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"Failed to send to dashboard {conn_id}: {e}")
                disconnected.append(conn_id)

        # Clean up disconnected clients
        for conn_id in disconnected:
            self.disconnect_dashboard(conn_id)

    async def broadcast_to_workers(self, message: Dict[str, Any]):
        """Broadcast message to all workers"""
        disconnected = []
        for worker_id, websocket in self.workers.items():
            try:
                await websocket.send_json(message)
                self.connection_metadata[worker_id]["last_activity"] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"Failed to send to worker {worker_id}: {e}")
                disconnected.append(worker_id)

        # Clean up disconnected workers
        for worker_id in disconnected:
            self.disconnect_worker(worker_id)

    async def broadcast_to_all(self, message: Dict[str, Any]):
        """Broadcast to all connections"""
        await self.broadcast_to_dashboards(message)
        await self.broadcast_to_workers(message)


# ============================================================================
# Worker Manager
# ============================================================================

class WorkerManager:
    """Manage worker registration and state"""

    def __init__(self, redis_service: AsyncRedisClient):
        self.redis = redis_service
        self.workers_key = "workers:list"

    async def register_worker(self, worker_state: WorkerState) -> bool:
        """Register a new worker"""
        worker_key = f"worker:{worker_state.worker_id}:data"

        # Store worker data in Redis
        await self.redis.set(worker_key, worker_state.model_dump_json())

        # Add to workers list
        await self.redis.sadd(self.workers_key, worker_state.worker_id)

        logger.info(f"Registered worker {worker_state.worker_id}: {worker_state.name}")
        return True

    async def deregister_worker(self, worker_id: str) -> bool:
        """Deregister a worker"""
        worker_key = f"worker:{worker_id}:data"

        # Remove from workers list
        await self.redis.srem(self.workers_key, worker_id)

        # Delete worker data
        await self.redis.delete(worker_key)

        # Clean up metrics
        metrics_key = f"worker:{worker_id}:metrics:current"
        await self.redis.delete(metrics_key)

        logger.info(f"Deregistered worker {worker_id}")
        return True

    async def get_worker(self, worker_id: str) -> Optional[WorkerState]:
        """Get worker state"""
        worker_key = f"worker:{worker_id}:data"
        data = await self.redis.get(worker_key)

        if data:
            return WorkerState.model_validate_json(data)
        return None

    async def get_all_workers(self) -> List[WorkerState]:
        """Get all registered workers"""
        worker_ids = await self.redis.smembers(self.workers_key)
        workers = []

        for worker_id in worker_ids:
            worker = await self.get_worker(worker_id)
            if worker:
                workers.append(worker)

        return workers

    async def update_worker_status(self, worker_id: str, status: WorkerStatus, last_heartbeat: str = None):
        """Update worker status"""
        worker = await self.get_worker(worker_id)
        if worker:
            worker.status = status
            if last_heartbeat:
                worker.last_heartbeat = last_heartbeat

            worker_key = f"worker:{worker_id}:data"
            await self.redis.set(worker_key, worker.model_dump_json())


# ============================================================================
# Health Monitor
# ============================================================================

class HealthMonitor:
    """Monitor worker health with periodic checks"""

    def __init__(
            self,
            worker_manager: WorkerManager,
            connection_manager: ConnectionManager,
            redis_service: AsyncRedisClient,
            check_interval: int = 30
    ):
        self.worker_manager = worker_manager
        self.connection_manager = connection_manager
        self.redis = redis_service
        self.check_interval = check_interval
        self.monitoring_task = None
        self.pending_checks: Dict[str, asyncio.Future] = {}

    async def start_monitoring(self):
        """Start periodic health checks"""
        self.monitoring_task = asyncio.create_task(self._health_check_loop())
        logger.info("Health monitoring started")

    async def stop_monitoring(self):
        """Stop health monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")

    async def _health_check_loop(self):
        """Periodic health check loop"""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self.check_all_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def check_all_workers(self):
        """Check health of all registered workers"""
        workers = await self.worker_manager.get_all_workers()

        if not workers:
            return

        logger.info(f"Checking health of {len(workers)} workers")

        for worker in workers:
            await self.check_worker_health(worker.worker_id)

        # Broadcast aggregated health update
        await self.broadcast_health_update()

    async def check_worker_health(self, worker_id: str):
        """Send health check to specific worker"""
        check_id = f"check-{worker_id}-{datetime.now().timestamp()}"

        message = {
            "type": "health:check",
            "payload": {
                "check_id": check_id
            },
            "timestamp": datetime.now().isoformat()
        }

        # Create future for response
        future = asyncio.Future()
        self.pending_checks[check_id] = future

        # Send check request
        await self.connection_manager.send_to_worker(worker_id, message)

        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=5.0)

            # Update worker status based on response
            status = WorkerStatus.HEALTHY if response.get("status") == "healthy" else WorkerStatus.UNHEALTHY
            await self.worker_manager.update_worker_status(
                worker_id,
                status,
                response.get("last_heartbeat")
            )

        except asyncio.TimeoutError:
            logger.warning(f"Health check timeout for worker {worker_id}")
            await self.worker_manager.update_worker_status(worker_id, WorkerStatus.UNHEALTHY)
        finally:
            if check_id in self.pending_checks:
                del self.pending_checks[check_id]

    async def handle_health_response(self, check_id: str, response: Dict[str, Any]):
        """Handle health check response from worker"""
        if check_id in self.pending_checks:
            self.pending_checks[check_id].set_result(response)

    async def broadcast_health_update(self):
        """Broadcast health summary to all dashboards"""
        workers = await self.worker_manager.get_all_workers()

        # Prepare worker health data
        worker_health = []
        healthy_count = 0

        for worker in workers:
            is_healthy = worker.status == WorkerStatus.HEALTHY
            if is_healthy:
                healthy_count += 1

            worker_health.append({
                "worker_id": worker.worker_id,
                "name": worker.name,
                "healthy": is_healthy,
                "status": worker.status.value,
                "worker_status": "running" if is_healthy else "unknown",
                "last_heartbeat": worker.last_heartbeat or "N/A",
                "response_time_ms": 0  # Would be calculated from actual response time
            })

        message = {
            "type": "health:update",
            "payload": {
                "workers": worker_health,
                "summary": {
                    "total_workers": len(workers),
                    "healthy_workers": healthy_count,
                    "unhealthy_workers": len(workers) - healthy_count,
                    "check_timestamp": datetime.now().isoformat()
                }
            }
        }

        await self.connection_manager.broadcast_to_dashboards(message)


# ============================================================================
# Metrics Aggregator
# ============================================================================

class MetricsAggregator:
    """Aggregate and broadcast metrics"""

    def __init__(
            self,
            connection_manager: ConnectionManager,
            redis_service: AsyncRedisClient,
            broadcast_interval: int = 3
    ):
        self.connection_manager = connection_manager
        self.redis = redis_service
        self.broadcast_interval = broadcast_interval
        self.metrics_buffer: Dict[str, List[MetricsSnapshot]] = defaultdict(list)
        self.aggregation_task = None

    async def start_aggregation(self):
        """Start periodic metrics aggregation"""
        self.aggregation_task = asyncio.create_task(self._aggregation_loop())
        logger.info("Metrics aggregation started")

    async def stop_aggregation(self):
        """Stop metrics aggregation"""
        if self.aggregation_task:
            self.aggregation_task.cancel()
            try:
                await self.aggregation_task
            except asyncio.CancelledError:
                pass
        logger.info("Metrics aggregation stopped")

    async def _aggregation_loop(self):
        """Periodic aggregation and broadcast loop"""
        while True:
            try:
                await asyncio.sleep(self.broadcast_interval)
                await self.aggregate_and_broadcast()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics aggregation error: {e}")

    async def process_metrics(self, metrics: MetricsSnapshot):
        """Process incoming metrics from worker"""
        # Store current metrics in Redis
        metrics_key = f"worker:{metrics.worker_id}:metrics:current"
        await self.redis.set(metrics_key, metrics.model_dump_json())

        # Add to buffer
        self.metrics_buffer[metrics.worker_id].append(metrics)

        # Store in history (limited to last 100)
        history_key = f"worker:{metrics.worker_id}:metrics:history"
        await self.redis.lpush(history_key, metrics.model_dump_json())
        await self.redis.ltrim(history_key, 0, 99)  # Keep last 100

    async def aggregate_and_broadcast(self):
        """Aggregate metrics and broadcast to dashboards"""
        if not self.metrics_buffer:
            return

        # Get latest metrics for each worker
        worker_metrics = []
        total_processed = 0
        total_errors = 0
        cpu_sum = 0
        memory_sum = 0
        worker_count = 0

        for worker_id, metrics_list in self.metrics_buffer.items():
            if not metrics_list:
                continue

            # Get latest metrics
            latest = metrics_list[-1]

            worker_metrics.append({
                "worker_id": worker_id,
                "name": worker_id,  # Would lookup actual name
                "metrics": {
                    "cpu": latest.cpu,
                    "memory_percent": latest.memory_percent,
                    "error_rate": latest.error_rate,
                    "throughput_per_sec": latest.throughput_per_sec
                }
            })

            total_processed += latest.total_processed
            total_errors += latest.error_count
            cpu_sum += latest.cpu
            memory_sum += latest.memory_percent
            worker_count += 1

        # Calculate aggregates
        avg_cpu = cpu_sum / worker_count if worker_count > 0 else 0
        avg_memory = memory_sum / worker_count if worker_count > 0 else 0
        overall_error_rate = (total_errors / total_processed * 100) if total_processed > 0 else 0

        message = {
            "type": "metrics:update",
            "payload": {
                "workers": worker_metrics,
                "aggregated": {
                    "total_processed": total_processed,
                    "total_errors": total_errors,
                    "overall_error_rate": round(overall_error_rate, 2),
                    "avg_cpu": round(avg_cpu, 2),
                    "avg_memory_percent": round(avg_memory, 2)
                }
            },
            "timestamp": datetime.now().isoformat()
        }

        await self.connection_manager.broadcast_to_dashboards(message)

        # Clear buffer
        self.metrics_buffer.clear()


# ============================================================================
# Resource Monitor
# ============================================================================

class ResourceMonitor:
    """Monitor external resources (DB, Redis, etc.)"""

    def __init__(self, connection_manager: ConnectionManager, redis_service: AsyncRedisClient):
        self.connection_manager = connection_manager
        self.redis = redis_service

    async def process_resource_health(self, resource_health: ResourceHealth):
        """Process resource health update"""
        # Store current resource health
        for resource_name, health_data in resource_health.resources.items():
            key = f"resource:{resource_health.resource_type}:{resource_name}:current"
            await self.redis.set(key, json.dumps(health_data))

            # Store in history
            history_key = f"resource:{resource_health.resource_type}:{resource_name}:history"
            await self.redis.lpush(history_key, json.dumps({
                **health_data,
                "timestamp": resource_health.timestamp
            }))
            await self.redis.ltrim(history_key, 0, 99)

        # Broadcast update
        await self.broadcast_resource_update(resource_health)

    async def broadcast_resource_update(self, resource_health: ResourceHealth):
        """Broadcast resource health to dashboards"""
        # Count healthy resources
        total = len(resource_health.resources)
        healthy = sum(1 for r in resource_health.resources.values()
                      if r.get('status') == 'healthy')

        message = {
            "type": "resources:update",
            "payload": {
                "resources": {
                    resource_health.resource_type: resource_health.resources
                },
                "summary": {
                    "total_resources": total,
                    "healthy_resources": healthy,
                    "unhealthy_resources": total - healthy
                }
            },
            "timestamp": resource_health.timestamp
        }

        await self.connection_manager.broadcast_to_dashboards(message)


# ============================================================================
# Main WebSocket Manager
# ============================================================================

class WebSocketManager:
    """Main orchestrator for WebSocket-based health dashboard"""

    def __init__(self, redis_service: AsyncRedisClient):
        self.connection_manager = ConnectionManager()
        self.worker_manager = WorkerManager(redis_service)
        self.health_monitor = HealthMonitor(
            self.worker_manager,
            self.connection_manager,
            redis_service
        )
        self.metrics_aggregator = MetricsAggregator(
            self.connection_manager,
            redis_service
        )
        self.resource_monitor = ResourceMonitor(
            self.connection_manager,
            redis_service
        )

    async def start(self):
        """Start all background tasks"""
        await self.health_monitor.start_monitoring()
        await self.metrics_aggregator.start_aggregation()
        logger.info("WebSocket manager started")

    async def stop(self):
        """Stop all background tasks"""
        await self.health_monitor.stop_monitoring()
        await self.metrics_aggregator.stop_aggregation()
        logger.info("WebSocket manager stopped")

    async def handle_worker_message(self, worker_id: str, message: Dict[str, Any]):
        """Route incoming worker messages"""
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type == "worker:register":
            await self._handle_worker_register(payload)

        elif msg_type == "worker:deregister":
            await self._handle_worker_deregister(payload)

        elif msg_type == "health:response":
            await self._handle_health_response(payload)

        elif msg_type == "metrics:push":
            await self._handle_metrics_push(payload)

        else:
            logger.warning(f"Unknown message type from worker: {msg_type}")

    async def handle_dashboard_message(self, connection_id: str, message: Dict[str, Any]):
        """Route incoming dashboard messages"""
        msg_type = message.get("type")
        payload = message.get("payload", {})

        if msg_type == "command:restart":
            await self._handle_restart_command(payload)

        elif msg_type == "dlq:clear":
            await self._handle_dlq_clear(connection_id, payload)

        elif msg_type == "logs:export":
            await self._handle_logs_export(connection_id, payload)

        elif msg_type == "settings:save":
            await self._handle_settings_save(connection_id, payload)

        elif msg_type == "settings:get":
            await self._handle_settings_get(connection_id, payload)

        else:
            logger.warning(f"Unknown message type from dashboard: {msg_type}")

    async def _handle_worker_register(self, payload: Dict[str, Any]):
        """Handle worker registration"""
        worker_state = WorkerState(
            worker_id=payload["worker_id"],
            name=payload["worker_name"],
            endpoint=payload["endpoint"],
            port=payload["port"],
            capabilities=payload.get("capabilities", []),
            version=payload.get("version", "1.0.0"),
            connected=True,
            connected_at=datetime.now().isoformat()
        )

        await self.worker_manager.register_worker(worker_state)

        # Broadcast registration to dashboards
        workers = await self.worker_manager.get_all_workers()
        message = {
            "type": "worker:registered",
            "payload": {
                "worker_id": worker_state.worker_id,
                "worker_name": worker_state.name,
                "total_workers": len(workers),
                "timestamp": datetime.now().isoformat()
            }
        }
        await self.connection_manager.broadcast_to_dashboards(message)

    async def _handle_worker_deregister(self, payload: Dict[str, Any]):
        """Handle worker deregistration"""
        worker_id = payload["worker_id"]
        await self.worker_manager.deregister_worker(worker_id)

        # Broadcast deregistration to dashboards
        workers = await self.worker_manager.get_all_workers()
        message = {
            "type": "worker:deregistered",
            "payload": {
                "worker_id": worker_id,
                "total_workers": len(workers),
                "timestamp": datetime.now().isoformat()
            }
        }
        await self.connection_manager.broadcast_to_dashboards(message)

    async def _handle_health_response(self, payload: Dict[str, Any]):
        """Handle health check response"""
        check_id = payload["check_id"]
        await self.health_monitor.handle_health_response(check_id, payload)

    async def _handle_metrics_push(self, payload: Dict[str, Any]):
        """Handle metrics push from worker"""
        metrics = MetricsSnapshot(
            worker_id=payload["worker_id"],
            timestamp=datetime.now().isoformat(),
            **payload.get("metrics", {})
        )
        await self.metrics_aggregator.process_metrics(metrics)

    async def _handle_restart_command(self, payload: Dict[str, Any]):
        """Handle restart command from dashboard"""
        worker_id = payload["worker_id"]

        message = {
            "type": "command:restart",
            "payload": payload,
            "timestamp": datetime.now().isoformat()
        }

        await self.connection_manager.send_to_worker(worker_id, message)

    async def send_initial_state(self, connection_id: str):
        """Send initial state to newly connected dashboard"""
        workers = await self.worker_manager.get_all_workers()

        # Prepare initial worker data
        worker_data = []
        for worker in workers:
            worker_data.append({
                "worker_id": worker.worker_id,
                "name": worker.name,
                "endpoint": worker.endpoint,
                "status": worker.status.value,
                "connected": worker.connected,
                "last_heartbeat": worker.last_heartbeat
            })

        message = {
            "type": "initial_state",
            "payload": {
                "workers": worker_data,
                "timestamp": datetime.now().isoformat()
            }
        }

        # Send to specific dashboard
        if connection_id in self.connection_manager.dashboards:
            await self.connection_manager.dashboards[connection_id].send_json(message)


# ============================================================================
# FastAPI Application
# ============================================================================

# Initialize FastAPI app
app = FastAPI(title="Health Dashboard WebSocket Backend")

# Initialize services (replace MockRedisService with actual redis_service)
redis_service = AsyncRedisClient()
ws_manager = WebSocketManager(redis_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on application startup & Clean up on application shutdown"""
    await ws_manager.start()
    logger.info("Application started")

    yield

    await ws_manager.stop()
    logger.info("Application shutdown")


@app.websocket("/ws/worker/{worker_id}")
async def worker_websocket(websocket: WebSocket, worker_id: str):
    """WebSocket endpoint for worker connections"""
    await ws_manager.connection_manager.connect_worker(worker_id, websocket)

    try:
        while True:
            message = await websocket.receive_json()
            await ws_manager.handle_worker_message(worker_id, message)

    except WebSocketDisconnect:
        ws_manager.connection_manager.disconnect_worker(worker_id)

        # Notify dashboards
        await ws_manager.connection_manager.broadcast_to_dashboards({
            "type": "worker:disconnected",
            "payload": {
                "worker_id": worker_id,
                "timestamp": datetime.now().isoformat()
            }
        })


@app.websocket("/ws/dashboard/{connection_id}")
async def dashboard_websocket(websocket: WebSocket, connection_id: str):
    """WebSocket endpoint for dashboard connections"""
    await ws_manager.connection_manager.connect_dashboard(connection_id, websocket)

    # Send initial state
    await ws_manager.send_initial_state(connection_id)

    try:
        while True:
            message = await websocket.receive_json()
            await ws_manager.handle_dashboard_message(connection_id, message)

    except WebSocketDisconnect:
        ws_manager.connection_manager.disconnect_dashboard(connection_id)


@app.post("/api/resources/health")
async def resource_health_endpoint(resource_health: ResourceHealth):
    """HTTP endpoint for resource health updates (from external monitors)"""
    await ws_manager.resource_monitor.process_resource_health(resource_health)
    return {"status": "ok"}


@app.get("/health")
async def health_check():
    """Health check endpoint for the dashboard itself"""
    workers = await ws_manager.worker_manager.get_all_workers()
    return {
        "status": "healthy",
        "service": "health-dashboard",
        "total_workers": len(workers),
        "connected_dashboards": len(ws_manager.connection_manager.dashboards),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 8090))
    uvicorn.run(
        "health_dashboard:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
