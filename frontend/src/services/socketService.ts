type EventCallback = (data: any) => void;

interface EventSubscribers {
  [eventType: string]: EventCallback[];
}

export class SocketService {
  private eventSource: EventSource | null = null;
  private subscribers: EventSubscribers = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 3000;
  private isConnecting = false;
  private url: string;

  constructor(url: string) {
    this.url = url;
  }

  connect(): void {
    if (this.isConnecting || this.eventSource?.readyState === EventSource.OPEN) {
      return;
    }

    this.isConnecting = true;
    console.log(`[SocketService] Connecting to ${this.url}`);

    try {
      this.eventSource = new EventSource(this.url);

      this.eventSource.onopen = () => {
        console.log('[SocketService] Connection established');
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        this.notifySubscribers('connection_open', { connected: true });
      };

      this.eventSource.onerror = (error) => {
        console.error('[SocketService] Connection error:', error);
        this.isConnecting = false;
        this.notifySubscribers('connection_error', { error });
        this.handleReconnect();
      };

      this.eventSource.addEventListener('initial_data', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Received initial_data:', data);
        this.notifySubscribers('initial_data', data);
      });

      this.eventSource.addEventListener('dashboard_update', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Received dashboard_update:', data);
        this.notifySubscribers('dashboard_update', data);
      });

      this.eventSource.addEventListener('worker_registered', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Worker registered:', data);
        this.notifySubscribers('worker_registered', data);
      });

      this.eventSource.addEventListener('worker_deregistered', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Worker deregistered:', data);
        this.notifySubscribers('worker_deregistered', data);
      });

      this.eventSource.addEventListener('worker_status_change', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Worker status changed:', data);
        this.notifySubscribers('worker_status_change', data);
      });

      this.eventSource.addEventListener('worker_status_update', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Worker status update:', data);
        this.notifySubscribers('worker_status_update', data);
      });

      this.eventSource.addEventListener('metrics_update', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Metrics update:', data);
        this.notifySubscribers('metrics_update', data);
      });

      this.eventSource.addEventListener('resources_update', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('[SocketService] Resources update:', data);
        this.notifySubscribers('resources_update', data);
      });
    } catch (error) {
      console.error('[SocketService] Failed to create EventSource:', error);
      this.isConnecting = false;
      this.handleReconnect();
    }
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SocketService] Max reconnection attempts reached');
      this.notifySubscribers('connection_failed', {
        message: 'Failed to connect after multiple attempts'
      });
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5);
    console.log(`[SocketService] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.disconnect();
      this.connect();
    }, delay);
  }

  subscribe(eventType: string, callback: EventCallback): () => void {
    if (!this.subscribers[eventType]) {
      this.subscribers[eventType] = [];
    }
    this.subscribers[eventType].push(callback);

    return () => {
      this.unsubscribe(eventType, callback);
    };
  }

  unsubscribe(eventType: string, callback: EventCallback): void {
    if (!this.subscribers[eventType]) return;

    this.subscribers[eventType] = this.subscribers[eventType].filter(
      (cb) => cb !== callback
    );
  }

  private notifySubscribers(eventType: string, data: any): void {
    if (!this.subscribers[eventType]) return;

    this.subscribers[eventType].forEach((callback) => {
      try {
        callback(data);
      } catch (error) {
        console.error(`[SocketService] Error in subscriber callback for ${eventType}:`, error);
      }
    });
  }

  disconnect(): void {
    if (this.eventSource) {
      console.log('[SocketService] Disconnecting');
      this.eventSource.close();
      this.eventSource = null;
    }
    this.isConnecting = false;
  }

  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN;
  }
}

const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8090';
export const socketService = new SocketService(`${backendUrl}/events`);
