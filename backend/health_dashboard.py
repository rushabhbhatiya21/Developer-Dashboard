#!/usr/bin/env python3
"""
Health Dashboard Application with Live Updates
A web-based dashboard for monitoring worker health status with real-time updates
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
from pydantic import BaseModel
from aiohttp import web, ClientSession, ClientTimeout, TCPConnector
from jinja2 import FileSystemLoader
import aiohttp_jinja2
import weakref

from collections import defaultdict, deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Summary(BaseModel):
    total_workers: int
    healthy_workers: int
    unhealthy_workers: int
    total_processed: int
    total_errors: int
    overall_error_rate: float

    def to_dict(self):
        return {
            'total_workers': self.total_workers,
            'healthy_workers': self.healthy_workers,
            'unhealthy_workers': self.unhealthy_workers,
            'total_processed': self.total_processed,
            'total_errors': self.total_errors,
            'overall_error_rate': self.overall_error_rate,
        }


class WorkersData(BaseModel):
    workers: List
    summary: Summary
    last_update: str
    timestamp: str

    def to_dict(self):
        return {
            'workers': self.workers,
            'summary': self.summary.to_dict(),
            'last_update': self.last_update,
            'timestamp': self.timestamp,
        }


class SSEManager:
    """Manage Server-Sent Events connections"""

    def __init__(self):
        self.connections: Set[web.StreamResponse] = weakref.WeakSet() # type: ignore

    def add_connection(self, response: web.StreamResponse):
        """Add a new SSE connection"""
        self.connections.add(response)
        logger.info(f"SSE connection added. Total: {len(self.connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all connected clients"""
        if not self.connections:
            return

        message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        # Create a copy of connections to avoid modification during iteration
        connections_copy = list(self.connections)

        for response in connections_copy:
            try:
                if not response.task.done():
                    await response.write(message.encode())
            except Exception as e:
                logger.warning(f"Failed to send SSE message: {e}")
                # Connection will be automatically removed by WeakSet

        logger.info(f"Broadcast {event_type} event to {len(connections_copy)} clients")


class HealthDashboard:
    def __init__(
            self,
            port: int = 8090,
            refresh_interval: int = 30
    ):
        self.template_dir = os.path.join(BASE_DIR, "templates")
        self.port = port
        self.refresh_interval = refresh_interval
        self.app = None
        self.last_update = None
        self.cached_data = []
        self.registered_workers: Dict[str, str] = {}
        self.sse_manager = SSEManager()
        self.resource_health_history = defaultdict(lambda: deque(maxlen=100))
        self.current_resource_health = {}

        # Background task for periodic health checks
        self.background_task = None

        # Shared ClientSession for all HTTP requests
        self.client_session: Optional[ClientSession] = None

        logger.info(f"Dashboard initialized with workers: {self.registered_workers}")

    async def _create_client_session(self):
        """Create a reusable client session with proper connector settings"""
        connector = TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            force_close=True  # Ensure connections are properly closed
        )
        timeout = ClientTimeout(total=10, connect=5, sock_read=5)
        self.client_session = ClientSession(
            connector=connector,
            timeout=timeout
        )
        logger.info("HTTP client session created")

    async def start_background_monitoring(self):
        """Start background task for periodic health monitoring"""
        self.background_task = asyncio.create_task(self._periodic_health_check())

    async def stop_background_monitoring(self):
        """Stop background monitoring task"""
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass

    async def resources_health_handler(self, request):
        """Receive health updates from resource monitors"""
        try:
            health_data = await request.json()

            # Store current health for each resource type
            for resource_type, data in health_data.items():
                self.current_resource_health[resource_type] = data
                self.resource_health_history[resource_type].append({
                    **data,
                    "timestamp": datetime.now().isoformat()
                })

            # Broadcast resource health update via SSE
            await self.sse_manager.broadcast('resources_update', {
                'resources': health_data,
                'timestamp': datetime.now().isoformat()
            })

            return web.json_response({
                "status": "ok",
                "received": len(health_data)
            })
        except Exception as e:
            logger.error(f"Error in resources_health_handler: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_resources_health_handler(self, request):
        """Get current resource health status"""
        total = len(self.current_resource_health)
        healthy = sum(1 for h in self.current_resource_health.values()
                      if h.get('status') == 'healthy')

        return web.json_response({
            "resources": self.current_resource_health,
            "summary": {
                "total": total,
                "healthy": healthy,
                "unhealthy": total - healthy,
                "timestamp": datetime.now().isoformat()
            }
        })

    async def _periodic_health_check(self):
        """Periodic health check that broadcasts updates"""
        while True:
            try:
                await asyncio.sleep(self.refresh_interval)

                if self.registered_workers:
                    old_data = {w['name']: w for w in self.cached_data}
                    new_data = await self.collect_all_health_data()

                    # Check for status changes
                    for worker in new_data:
                        old_worker = old_data.get(worker['name'])
                        if old_worker and (
                                old_worker['healthy'] != worker['healthy'] or
                                old_worker['worker_status'] != worker['worker_status'] or
                                old_worker['total_processed'] != worker['total_processed']
                        ):
                            # Worker status changed
                            await self.sse_manager.broadcast('worker_status_change', {
                                'worker': worker,
                                'previous': old_worker,
                                'timestamp': datetime.now().isoformat()
                            })

                    # Broadcast full update
                    await self.broadcast_dashboard_update()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background health check error: {e}")

    async def broadcast_dashboard_update(self):
        """Broadcast full dashboard update via SSE"""
        worker_data = self.cached_data

        # Calculate summary statistics
        total_workers = len(worker_data)
        healthy_workers = sum(1 for w in worker_data if w['healthy'])
        total_processed = sum(w['total_processed'] for w in worker_data)
        total_errors = sum(w['error_count'] for w in worker_data)
        overall_error_rate = (total_errors / max(total_processed, 1)) * 100

        summary = Summary(
            total_workers=total_workers,
            healthy_workers=healthy_workers,
            unhealthy_workers=total_workers - healthy_workers,
            total_processed=total_processed,
            total_errors=total_errors,
            overall_error_rate=round(overall_error_rate, 2)
        )

        update_data = WorkersData(
            workers=worker_data,
            summary=summary,
            last_update=self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'Never',
            timestamp=datetime.now().isoformat()
        )

        # update_data = {
        #     'workers': worker_data,
        #     'summary': {
        #         'total_workers': total_workers,
        #         'healthy_workers': healthy_workers,
        #         'unhealthy_workers': total_workers - healthy_workers,
        #         'total_processed': total_processed,
        #         'total_errors': total_errors,
        #         'overall_error_rate': round(overall_error_rate, 2)
        #     },
        #     'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'Never',
        #     'timestamp': datetime.now().isoformat()
        # }

        await self.sse_manager.broadcast('dashboard_update', update_data.to_dict())

    # --- SSE endpoint ---
    async def sse_handler(self, request):
        """Server-Sent Events endpoint for live updates"""
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )

        await response.prepare(request)

        # Add connection to manager
        self.sse_manager.add_connection(response)

        try:
            # Send initial data
            initial_data = await self.get_dashboard_data()
            message = f"event: initial_data\ndata: {json.dumps(initial_data)}\n\n"
            await response.write(message.encode())

            # Keep connection alive
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
        finally:
            # Connection will be automatically removed from WeakSet
            pass

        return response

    async def get_dashboard_data(self):
        """Get current dashboard data"""
        worker_data = self.cached_data or await self.collect_all_health_data()

        # Calculate summary statistics
        total_workers = len(worker_data)
        healthy_workers = sum(1 for w in worker_data if w['healthy'])
        total_processed = sum(w['total_processed'] for w in worker_data)
        total_errors = sum(w['error_count'] for w in worker_data)
        overall_error_rate = (total_errors / max(total_processed, 1)) * 100

        summary = Summary(
            total_workers=total_workers,
            healthy_workers=healthy_workers,
            unhealthy_workers=total_workers - healthy_workers,
            total_processed=total_processed,
            total_errors=total_errors,
            overall_error_rate=round(overall_error_rate, 2)
        )

        update_data = WorkersData(
            workers=worker_data,
            summary=summary,
            last_update=self.last_update.strftime('%Y-%m-%d %H:%M:%S') if self.last_update else 'Never',
            timestamp=datetime.now().isoformat()
        )

        result = update_data.to_dict()

        # Add resources if available
        if self.current_resource_health:
            result['resources'] = self.current_resource_health

        return result

    # --- Enhanced registration methods ---
    async def register_handler(self, request):
        """Worker calls this to register itself"""
        data = await request.json()
        worker_id = data.get("id")
        endpoint = data.get("endpoint")
        if not worker_id or not endpoint:
            return web.json_response({"error": "id and endpoint required"}, status=400)

        was_new_worker = worker_id not in self.registered_workers
        self.registered_workers[worker_id] = endpoint
        logger.info(f"Registered worker {worker_id} at {endpoint}")

        # Trigger immediate refresh
        await self.collect_all_health_data()

        # Broadcast registration event
        await self.sse_manager.broadcast('worker_registered', {
            'worker_id': worker_id,
            'endpoint': endpoint,
            'is_new': was_new_worker,
            'total_workers': len(self.registered_workers),
            'timestamp': datetime.now().isoformat()
        })

        # Broadcast full dashboard update
        await self.broadcast_dashboard_update()

        return web.json_response({"status": "registered", "worker_id": worker_id})

    async def deregister_handler(self, request):
        """Worker calls this to deregister itself"""
        data = await request.json()
        worker_id = data.get("id")

        endpoint = None
        if worker_id in self.registered_workers:
            endpoint = self.registered_workers.pop(worker_id)
            logger.info(f"Deregistered worker {worker_id}")

        # Trigger immediate refresh
        await self.collect_all_health_data()

        # Broadcast deregistration event
        await self.sse_manager.broadcast('worker_deregistered', {
            'worker_id': worker_id,
            'endpoint': endpoint,
            'total_workers': len(self.registered_workers),
            'timestamp': datetime.now().isoformat()
        })

        # Broadcast full dashboard update
        await self.broadcast_dashboard_update()

        return web.json_response({"status": "deregistered", "worker_id": worker_id})

    # --- Worker status update endpoint ---
    async def status_update_handler(self, request):
        """Endpoint for workers to report status changes"""
        data = await request.json()
        worker_id = data.get("id")
        status = data.get("status")

        if not worker_id or not status:
            return web.json_response({"error": "id and status required"}, status=400)

        if worker_id not in self.registered_workers:
            return web.json_response({"error": "worker not registered"}, status=404)

        logger.info(f"Status update from worker {worker_id}: {status}")

        # Trigger immediate refresh to get latest data
        await self.collect_all_health_data()

        # Find the worker in cached data
        worker_data = None
        for worker in self.cached_data:
            if self._extract_worker_name(self.registered_workers[worker_id]) == worker['name']:
                worker_data = worker
                break

        # Broadcast status change event
        await self.sse_manager.broadcast('worker_status_update', {
            'worker_id': worker_id,
            'status': status,
            'worker_data': worker_data,
            'timestamp': datetime.now().isoformat()
        })

        # Broadcast full dashboard update
        await self.broadcast_dashboard_update()

        return web.json_response({"status": "updated", "worker_id": worker_id})

    async def fetch_worker_health(self, endpoint: str) -> Dict[str, Any]:
        """Fetch health data from a single worker endpoint"""
        worker_name = self._extract_worker_name(endpoint)

        try:
            # Fetch health data
            timeout = ClientTimeout(total=5)
            async with self.client_session.get(f"{endpoint}/health", timeout=timeout) as resp:
                if resp.status == 200:
                    health_data = await resp.json()

                    # Also fetch metrics if available
                    try:
                        async with self.client_session.get(f"{endpoint}/metrics", timeout=timeout) as metrics_resp:
                            if metrics_resp.status == 200:
                                metrics_data = await metrics_resp.json()
                                health_data.update({
                                    'total_processed': metrics_data.get('total_processed', 0),
                                    'error_count': metrics_data.get('error_count', 0),
                                    'error_rate': metrics_data.get('error_rate', 0),
                                    'cpu': metrics_data.get('cpu', 0),
                                    'memory': metrics_data.get('memory', 0)
                                })
                    except:
                        pass  # Metrics are optional

                    return {
                        'name': worker_name,
                        'endpoint': endpoint,
                        'status': 'healthy',
                        'healthy': health_data.get('status') == 'healthy',
                        'worker_status': health_data.get('worker_status', 'unknown'),
                        'last_heartbeat': health_data.get('last_heartbeat', 'N/A'),
                        'container_id': health_data.get('container_id', 'unknown'),
                        'total_processed': health_data.get('total_processed', 0),
                        'error_count': health_data.get('error_count', 0),
                        'error_rate': health_data.get('error_rate', 0),
                        'cpu': health_data.get('cpu', 0),
                        'memory': health_data.get('memory', 0),
                        'response_time': 'normal',
                        'last_checked': datetime.now().isoformat()
                    }
                else:
                    return self._create_error_response(worker_name, endpoint, f"HTTP {resp.status}")

        except asyncio.TimeoutError:
            return self._create_error_response(worker_name, endpoint, "Timeout")
        except Exception as e:
            return self._create_error_response(worker_name, endpoint, str(e))

    async def metrics_update_handler(self, request):
        """Endpoint for workers to push real-time metrics"""
        try:
            data = await request.json()
            worker_id = data.get("id")

            if not worker_id or worker_id not in self.registered_workers:
                return web.json_response({"error": "worker not registered"}, status=404)

            # Update cached data with new metrics
            endpoint = self.registered_workers[worker_id]
            worker_name = self._extract_worker_name(endpoint)

            # Find and update the worker in cached_data
            for worker in self.cached_data:
                if worker['name'] == worker_name:
                    # Update metrics
                    worker['cpu'] = data.get('cpu', worker.get('cpu', 0))
                    worker['memory'] = data.get('memory', worker.get('memory', 0))
                    worker['total_processed'] = data.get('total_processed', worker.get('total_processed', 0))
                    worker['error_count'] = data.get('error_count', worker.get('error_count', 0))
                    worker['error_rate'] = data.get('error_rate', worker.get('error_rate', 0))
                    worker['worker_status'] = data.get('worker_status', worker.get('worker_status', 'unknown'))
                    worker['last_checked'] = datetime.now().isoformat()
                    break

            # Broadcast the update to all SSE clients
            await self.sse_manager.broadcast('metrics_update', {
                'worker_id': worker_id,
                'worker_name': worker_name,
                'metrics': data,
                'timestamp': datetime.now().isoformat()
            })

            return web.json_response({"status": "updated"})

        except Exception as e:
            logger.error(f"Error in metrics_update_handler: {e}")
            return web.json_response({"error": str(e)}, status=500)

    @staticmethod
    def _extract_worker_name(endpoint: str) -> str:
        """Extract worker name from endpoint"""
        # http://ocr_worker:8080
        if '8080' in endpoint.lower():
            return 'Server'
        elif '8081' in endpoint.lower():
            return 'OCR Worker'
        elif '8082' in endpoint.lower():
            return 'LLM Worker'
        elif '8083' in endpoint.lower():
            return 'O1 LLM Worker'
        elif '8084' in endpoint.lower():
            return 'Summary Worker'
        elif '8085' in endpoint.lower():
            return 'Strikethrough Worker'
        else:
            # Extract from URL
            parts = endpoint.replace('http://', '').replace('https://', '').split(':')
            return f"Worker ({parts[0]}:{parts[1] if len(parts) > 1 else '80'})"

    @staticmethod
    def _create_error_response(worker_name: str, endpoint: str, error: str) -> Dict[str, Any]:
        """Create error response for failed health check"""
        return {
            'name': worker_name,
            'endpoint': endpoint,
            'status': 'error',
            'healthy': False,
            'worker_status': 'unknown',
            'last_heartbeat': 'N/A',
            'container_id': 'unknown',
            'total_processed': 0,
            'error_count': 0,
            'error_rate': 0,
            'response_time': 'error',
            'error_message': error,
            'last_checked': datetime.now().isoformat()
        }

    async def collect_all_health_data(self) -> List[Dict[str, Any]]:
        """Collect health data from all worker endpoints"""
        if not self.registered_workers:
            logger.warning("No workers registered yet")
            self.cached_data = []
            return []

        if not self.client_session or self.client_session.closed:
            logger.error("Client session not initialized or closed")
            return self.cached_data

        tasks = [
            self.fetch_worker_health(endpoint)
            for endpoint in self.registered_workers.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return valid results
        valid_results = []
        for result in results:
            if isinstance(result, dict):
                valid_results.append(result)
            else:
                logger.error(f"Health check failed: {result}")

        self.cached_data = valid_results
        self.last_update = datetime.now()
        return valid_results

    async def dashboard_handler(self, request):
        """Main dashboard page handler"""
        template_data = await self.get_dashboard_data()
        template_data['refresh_interval'] = self.refresh_interval
        return aiohttp_jinja2.render_template('index.html', request, template_data)

    async def api_health_handler(self, request):
        """API endpoint for health data (JSON)"""
        worker_data = await self.collect_all_health_data()

        return web.json_response({
            'workers': worker_data,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'timestamp': datetime.now().isoformat()
        })

    async def dashboard_health_handler(self, request):
        """Health check for the dashboard itself"""
        return web.json_response({
            'status': 'healthy',
            'service': 'health-dashboard',
            'workers': self.registered_workers,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'timestamp': datetime.now().isoformat()
        })

    def setup_routes(self):
        """Setup application routes"""
        self.app.router.add_get('/', self.dashboard_handler)
        self.app.router.add_get('/api/health', self.api_health_handler)
        self.app.router.add_get('/health', self.dashboard_health_handler)

        # Live updates endpoint
        self.app.router.add_get('/events', self.sse_handler)

        # Worker management endpoints
        self.app.router.add_post('/register', self.register_handler)
        self.app.router.add_post('/deregister', self.deregister_handler)
        self.app.router.add_post('/status-update', self.status_update_handler)
        self.app.router.add_post('/metrics-update', self.metrics_update_handler)

        self.app.router.add_post('/resources/health', self.resources_health_handler)
        self.app.router.add_get('/resources/health/current', self.get_resources_health_handler)


    async def start(self):
        """Start the dashboard server"""
        self.app = web.Application()

        # Setup Jinja2 templates
        aiohttp_jinja2.setup(
            self.app,
            loader=FileSystemLoader(self.template_dir)
        )

        self.setup_routes()

        # Create shared HTTP client session
        await self._create_client_session()

        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()

        # Start background monitoring
        await self.start_background_monitoring()

        logger.info(f"Health Dashboard started on http://0.0.0.0:{self.port}")
        logger.info(f"Live updates available at http://0.0.0.0:{self.port}/events")

        return runner

    async def cleanup(self):
        """Cleanup resources"""
        await self.stop_background_monitoring()

        # Close the shared client session
        if self.client_session and not self.client_session.closed:
            await self.client_session.close()
            logger.info("HTTP client session closed")


def parse_worker_endpoints(endpoints_str: str) -> List[str]:
    """Parse worker endpoints from environment variable"""
    if not endpoints_str:
        return []

    endpoints = []
    for endpoint in endpoints_str.split(','):
        endpoint = endpoint.strip()
        if endpoint:
            # Ensure endpoint has protocol
            if not endpoint.startswith(('http://', 'https://')):
                endpoint = f"http://{endpoint}"
            endpoints.append(endpoint)

    return endpoints


async def main():
    """Main application entry point"""
    # Get configuration from environment
    port = int(os.getenv('DASHBOARD_PORT', 8090))
    refresh_interval = int(os.getenv('REFRESH_INTERVAL', 30))

    # Create and start dashboard
    dashboard = HealthDashboard(
        port=port,
        refresh_interval=refresh_interval
    )

    runner = await dashboard.start()

    try:
        # Keep the server running
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down dashboard...")
    finally:
        await dashboard.cleanup()
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
