"""Message queue client abstraction."""
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Awaitable
import json
import asyncio
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError
import redis.asyncio as redis
import pika
from apps.shared.config import settings


class MQClient(ABC):
    """Abstract message queue client interface."""
    
    @abstractmethod
    async def publish(self, topic: str, message: dict) -> None:
        """Publish a message to a topic."""
        pass
    
    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[dict], Awaitable[None] | None],
        group_id: Optional[str] = None,
    ) -> None:
        """Subscribe to a topic and call callback for each message."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        pass


class KafkaMQClient(MQClient):
    """Kafka message queue client."""
    
    def __init__(self):
        """Initialize Kafka client."""
        self.bootstrap_servers = settings.kafka_bootstrap_servers.split(",")
        self.topic_prefix = settings.kafka_topic_prefix
        self.producer: Optional[KafkaProducer] = None
        self.consumers: dict[str, KafkaConsumer] = {}
    
    def _get_topic_name(self, topic: str) -> str:
        """Get full topic name with prefix."""
        return f"{self.topic_prefix}-{topic}"
    
    async def publish(self, topic: str, message: dict) -> None:
        """Publish a message to Kafka."""
        if not self.producer:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        
        topic_name = self._get_topic_name(topic)
        try:
            future = self.producer.send(topic_name, message)
            # Wait for send to complete
            record_metadata = future.get(timeout=10)
        except KafkaError as e:
            raise RuntimeError(f"Failed to publish message: {e}") from e
    
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[dict], Awaitable[None] | None],
        group_id: Optional[str] = None,
    ) -> None:
        """Subscribe to a Kafka topic."""
        topic_name = self._get_topic_name(topic)
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id or f"{self.topic_prefix}-consumer",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        
        self.consumers[topic] = consumer
        
        # Run consumer in background
        asyncio.create_task(self._consume_loop(consumer, callback))
    
    async def _consume_loop(
        self, consumer: KafkaConsumer, callback: Callable[[dict], Awaitable[None] | None]
    ):
        """Consume messages in a loop."""
        try:
            for message in consumer:
                result = callback(message.value)
                if asyncio.iscoroutine(result):
                    await result
        except Exception as e:
            raise RuntimeError(f"Error consuming messages: {e}") from e
    
    async def close(self) -> None:
        """Close Kafka connections."""
        if self.producer:
            self.producer.close()
        for consumer in self.consumers.values():
            consumer.close()


class RedisMQClient(MQClient):
    """Redis message queue client (using pub/sub)."""
    
    def __init__(self):
        """Initialize Redis client."""
        self.redis_url = settings.redis_url
        self.client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.running = False
    
    async def _get_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if not self.client:
            self.client = await redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self.client
    
    async def publish(self, topic: str, message: dict) -> None:
        """Publish a message to Redis."""
        client = await self._get_client()
        await client.publish(topic, json.dumps(message))
    
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[dict], Awaitable[None] | None],
        group_id: Optional[str] = None,
    ) -> None:
        """Subscribe to a Redis topic."""
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(topic)
        self.pubsub = pubsub
        self.running = True
        
        # Run consumer in background
        asyncio.create_task(self._consume_loop(pubsub, callback))
    
    async def _consume_loop(
        self, pubsub: redis.client.PubSub, callback: Callable[[dict], Awaitable[None] | None]
    ):
        """Consume messages in a loop."""
        try:
            while self.running:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = json.loads(message["data"])
                    result = callback(data)
                    if asyncio.iscoroutine(result):
                        await result
                await asyncio.sleep(0.1)
        except Exception as e:
            raise RuntimeError(f"Error consuming messages: {e}") from e
    
    async def close(self) -> None:
        """Close Redis connections."""
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.client:
            await self.client.close()


class RabbitMQClient(MQClient):
    """RabbitMQ message queue client."""
    
    def __init__(self):
        """Initialize RabbitMQ client."""
        self.rabbitmq_url = settings.rabbitmq_url
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
    
    def _get_connection(self) -> pika.BlockingConnection:
        """Get or create RabbitMQ connection."""
        if not self.connection or self.connection.is_closed:
            parameters = pika.URLParameters(self.rabbitmq_url)
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
        return self.connection
    
    async def publish(self, topic: str, message: dict) -> None:
        """Publish a message to RabbitMQ."""
        connection = self._get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=topic, durable=True)
        
        channel.basic_publish(
            exchange="",
            routing_key=topic,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),  # Make message persistent
        )
    
    async def subscribe(
        self,
        topic: str,
        callback: Callable[[dict], Awaitable[None] | None],
        group_id: Optional[str] = None,
    ) -> None:
        """Subscribe to a RabbitMQ topic."""
        connection = self._get_connection()
        channel = connection.channel()
        channel.queue_declare(queue=topic, durable=True)
        
        def on_message(ch, method, properties, body):
            message = json.loads(body)
            result = callback(message)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        channel.basic_consume(queue=topic, on_message_callback=on_message)
        
        # Run consumer in background
        asyncio.create_task(self._consume_loop(channel))
    
    async def _consume_loop(self, channel: pika.channel.Channel):
        """Consume messages in a loop."""
        try:
            channel.start_consuming()
        except Exception as e:
            raise RuntimeError(f"Error consuming messages: {e}") from e
    
    async def close(self) -> None:
        """Close RabbitMQ connections."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()


def get_mq_client() -> MQClient:
    """Get message queue client based on configuration."""
    mq_type = settings.mq_type.lower()
    
    if mq_type == "kafka":
        return KafkaMQClient()
    elif mq_type == "redis":
        return RedisMQClient()
    elif mq_type == "rabbitmq":
        return RabbitMQClient()
    else:
        raise ValueError(f"Unknown MQ type: {mq_type}")

