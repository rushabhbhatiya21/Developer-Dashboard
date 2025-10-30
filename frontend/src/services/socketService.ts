/**
 * WebSocket Service for Dashboard Real-time Communication
 *
 * Provides bidirectional communication with backend WebSocket endpoints.
 * Replaces previous EventSource (SSE) implementation with native WebSocket.
 *
 * Features:
 * - Automatic connection on import
 * - Exponential backoff reconnection (max 10 attempts)
 * - Event subscription pattern for message handling
 * - Message sending capability for commands
 * - Backend-to-frontend event type mapping
 */

// TypeScript interfaces
export interface SocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

export type EventCallback = (message: SocketMessage) => void;

type ConnectionState = 'connected' | 'connecting' | 'disconnected';

interface EventSubscribers {
  [eventType: string]: Set<EventCallback>;
}

/**
 * WebSocket Service Class
 * Manages WebSocket connection lifecycle and message routing
 */
class SocketService {
  private websocket: WebSocket | null = null;
  private subscribers: EventSubscribers = {};
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private isManuallyDisconnected = false;
  private url: string;
  private connectionState: ConnectionState = 'disconnected';

  constructor(url: string) {
    this.url = url;
  }

  /**
   * Establish WebSocket connection to backend
   * Automatically called on module initialization
   */
  connect(): void {
    if (this.connectionState === 'connecting' || this.connectionState === 'connected') {
      return;
    }

    this.connectionState = 'connecting';
    this.isManuallyDisconnected = false;
    console.log(`[SocketService] Connecting to ${this.url}`);

    try {
      this.websocket = new WebSocket(this.url);

      // Connection opened successfully
      this.websocket.onopen = () => {
        console.log('[SocketService] WebSocket connection established');
        this.reconnectAttempts = 0;
        this.connectionState = 'connected';

        // Notify all subscribers about successful connection
        this.notifySubscribers('connection_open', {
          type: 'connection_open',
          payload: { connected: true },
          timestamp: new Date().toISOString()
        });
      };

      // Connection closed
      this.websocket.onclose = (event) => {
        console.log('[SocketService] WebSocket connection closed', event);
        this.connectionState = 'disconnected';

        // Notify subscribers
        this.notifySubscribers('connection_closed', {
          type: 'connection_closed',
          payload: { code: event.code, reason: event.reason },
          timestamp: new Date().toISOString()
        });

        // Attempt reconnection if not manually disconnected
        if (!this.isManuallyDisconnected) {
          this.handleReconnect();
        }
      };

      // Connection error occurred
      this.websocket.onerror = (error) => {
        console.error('[SocketService] WebSocket error:', error);
        this.connectionState = 'disconnected';

        // Notify subscribers about error
        this.notifySubscribers('connection_error', {
          type: 'connection_error',
          payload: { error },
          timestamp: new Date().toISOString()
        });
      };

      // Message received from backend
      this.websocket.onmessage = (event) => {
        this.handleMessage(event.data);
      };

    } catch (error) {
      console.error('[SocketService] Failed to create WebSocket:', error);
      this.connectionState = 'disconnected';
      this.handleReconnect();
    }
  }

  /**
   * Handle incoming WebSocket messages
   * Parses JSON and routes to appropriate event listeners
   */
  private handleMessage(rawMessage: string): void {
    try {
      const message: SocketMessage = JSON.parse(rawMessage);

      // Validate message structure
      if (!message.type) {
        console.warn('[SocketService] Message missing required "type" field:', message);
        return;
      }

      // Map backend message types to frontend event names
      const frontendEventType = this.mapBackendEventType(message.type);

      console.log(`[SocketService] Received ${message.type} -> ${frontendEventType}:`, message.payload);

      // Route message to subscribers
      this.notifySubscribers(frontendEventType, message);

    } catch (error) {
      console.error('[SocketService] Failed to parse WebSocket message:', rawMessage, error);
      // Don't crash - continue processing other messages
    }
  }

  /**
   * Map backend message types to frontend event names
   * Maintains backward compatibility with existing components
   */
  private mapBackendEventType(backendType: string): string {
    const mapping: { [key: string]: string } = {
      'initial_state': 'initial_data',
      'worker:registered': 'worker_registered',
      'worker:deregistered': 'worker_deregistered',
      'worker:disconnected': 'worker_status_change',
      'health:update': 'worker_status_update',
      'metrics:update': 'metrics_update',
      'resources:update': 'resources_update',
      'command:response': 'command_response'
    };

    return mapping[backendType] || backendType;
  }

  /**
   * Handle automatic reconnection with exponential backoff
   * Delays: 1s, 2s, 4s, 8s, 16s, 32s (capped at 32s)
   */
  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[SocketService] Max reconnection attempts reached');
      this.notifySubscribers('max_retries_reached', {
        type: 'max_retries_reached',
        payload: { message: 'Failed to connect after 10 attempts' },
        timestamp: new Date().toISOString()
      });
      return;
    }

    this.reconnectAttempts++;

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 32s (cap at 32s)
    const baseDelay = 1000; // 1 second
    const delay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts - 1), 32000);

    console.log(`[SocketService] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.disconnect(false); // Close without marking as manual
      this.connect();
    }, delay);
  }

  /**
   * Subscribe to specific event types
   * Returns unsubscribe function for cleanup
   */
  subscribe(eventType: string, callback: EventCallback): () => void {
    if (!this.subscribers[eventType]) {
      this.subscribers[eventType] = new Set();
    }
    this.subscribers[eventType].add(callback);

    // Return unsubscribe function
    return () => {
      this.unsubscribe(eventType, callback);
    };
  }

  /**
   * Unsubscribe from event type
   */
  unsubscribe(eventType: string, callback: EventCallback): void {
    if (!this.subscribers[eventType]) return;
    this.subscribers[eventType].delete(callback);
  }

  /**
   * Notify all subscribers for a given event type
   */
  private notifySubscribers(eventType: string, message: SocketMessage): void {
    if (!this.subscribers[eventType]) return;

    this.subscribers[eventType].forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        console.error(`[SocketService] Error in subscriber callback for ${eventType}:`, error);
      }
    });
  }

  /**
   * Send message to backend (NEW - enables bidirectional communication)
   * @param type Message type/command
   * @param payload Message payload data
   * @returns Promise that resolves when message sent
   * @throws Error if WebSocket not connected
   */
  sendMessage(type: string, payload: any): Promise<void> {
    return new Promise((resolve, reject) => {
      // Check connection state
      if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected'));
        return;
      }

      const message: SocketMessage = {
        type,
        payload,
        timestamp: new Date().toISOString()
      };

      try {
        this.websocket.send(JSON.stringify(message));
        console.log(`[SocketService] Sent message type: ${type}`, payload);
        resolve();
      } catch (error) {
        console.error(`[SocketService] Failed to send message:`, error);
        reject(error);
      }
    });
  }

  /**
   * Get current connection state
   * @returns Connection state: 'connected', 'connecting', or 'disconnected'
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Check if currently connected
   * @returns True if WebSocket connection is open
   */
  isConnected(): boolean {
    return this.connectionState === 'connected';
  }

  /**
   * Manually disconnect from WebSocket
   * @param manual If true, prevents automatic reconnection
   */
  disconnect(manual: boolean = true): void {
    if (manual) {
      this.isManuallyDisconnected = true;
    }

    if (this.websocket) {
      console.log('[SocketService] Disconnecting WebSocket');
      this.websocket.close();
      this.websocket = null;
    }

    this.connectionState = 'disconnected';
  }
}

/**
 * Generate WebSocket URL from backend HTTP URL
 * Converts http:// to ws:// and https:// to wss://
 * Appends unique connection ID to endpoint path
 */
function generateWebSocketUrl(backendUrl: string): string {
  // Convert protocol: http -> ws, https -> wss
  let wsUrl = backendUrl.replace(/^http:\/\//, 'ws://').replace(/^https:\/\//, 'wss://');

  // Generate unique connection ID: dashboard-{timestamp}-{random}
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(7);
  const connectionId = `dashboard-${timestamp}-${random}`;

  // Append WebSocket endpoint path
  wsUrl = `${wsUrl}/ws/dashboard/${connectionId}`;

  return wsUrl;
}

// Initialize service with backend URL from environment
const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8090';
const wsUrl = generateWebSocketUrl(backendUrl);

// Create singleton instance
export const socketService = new SocketService(wsUrl);

// Auto-connect on module import
socketService.connect();

// Export helper functions for convenience
export const connect = () => socketService.connect();
export const disconnect = () => socketService.disconnect();
export const subscribe = (eventType: string, callback: EventCallback) => socketService.subscribe(eventType, callback);
export const unsubscribe = (eventType: string, callback: EventCallback) => socketService.unsubscribe(eventType, callback);
export const sendMessage = (type: string, payload: any) => socketService.sendMessage(type, payload);
export const getConnectionState = () => socketService.getConnectionState();
export const isConnected = () => socketService.isConnected();
