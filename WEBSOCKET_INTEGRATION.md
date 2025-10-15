# WebSocket Integration Documentation

## Overview
The frontend now communicates with the backend exclusively through Server-Sent Events (SSE), which provides real-time updates from the backend to the frontend.

## Architecture

### Backend
- **Endpoint**: `/events` (exposed on port 8090)
- **Protocol**: Server-Sent Events (SSE)
- **Events Emitted**:
  - `initial_data` - Sent when a client first connects
  - `dashboard_update` - Periodic updates of all dashboard data
  - `worker_registered` - When a new worker registers
  - `worker_deregistered` - When a worker deregisters
  - `worker_status_change` - When a worker's status changes
  - `worker_status_update` - Worker status updates
  - `metrics_update` - Real-time metrics from workers
  - `resources_update` - Resource health updates

### Frontend Service Layer

**File**: `frontend/src/services/socketService.ts`

The `SocketService` class manages the SSE connection:

- **Connection Management**: Automatic connection and reconnection logic
- **Event Subscription**: Allows components to subscribe to specific events
- **Error Handling**: Graceful handling of connection errors with exponential backoff
- **Max Reconnection Attempts**: 10 attempts with increasing delays

**Usage Example**:
```typescript
import { socketService } from '../services/socketService';

// Connect to backend
socketService.connect();

// Subscribe to events
const unsubscribe = socketService.subscribe('dashboard_update', (data) => {
  console.log('Dashboard updated:', data);
  // Update component state
});

// Clean up subscription
unsubscribe();
```

## Component Integration

### 1. Dashboard (`Dashboard.tsx`)
- Connects to SSE on mount
- Listens for `initial_data` and `dashboard_update` events
- Displays connection status indicator
- Passes data to child components

### 2. ServiceHealthCards (`ServiceHealthCards.tsx`)
- Receives worker data from Dashboard
- Maps workers to service health cards
- Shows real-time status, uptime, and response time

### 3. SystemMetrics (`SystemMetrics.tsx`)
- Displays CPU, memory, and request metrics
- Calculates averages from worker data
- Updates in real-time as data flows in

### 4. DLQMonitoring (`DLQMonitoring.tsx`)
- Monitors queue metrics
- Shows worker error counts
- Status indicators (ok/warning/critical)

### 5. QueuesView (`QueuesView.tsx`)
- Full queue management view
- Shows all workers as queues
- Real-time message counts and processing stats
- Connection status indicator

### 6. LogsView (`LogsView.tsx`)
- Real-time log streaming
- Subscribes to worker status events
- Adds log entries dynamically
- Connection status indicator

## Environment Configuration

**File**: `frontend/.env`

```
VITE_BACKEND_URL=http://localhost:8090
```

The socket service automatically constructs the SSE endpoint:
```typescript
const backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8090';
export const socketService = new SocketService(`${backendUrl}/events`);
```

## Data Flow

```
Backend (Port 8090)
      ↓
  /events (SSE)
      ↓
socketService.ts
      ↓
Event Subscriptions
      ↓
React Components
      ↓
UI Updates
```

## Key Features

### 1. Automatic Reconnection
- Exponential backoff strategy
- Max 10 reconnection attempts
- Delays: 3s, 6s, 9s, 12s, 15s (capped at 15s)

### 2. Event-Driven Updates
- Components subscribe only to events they need
- Clean subscription management with unsubscribe functions
- No polling or manual refresh required

### 3. Connection Status
- Visual indicators in Dashboard, QueuesView, and LogsView
- Green dot = Connected
- Red dot = Disconnected

### 4. Error Handling
- Connection errors logged to console
- Subscribers notified of connection issues
- Failed messages handled gracefully

## Testing the Integration

1. Start the backend:
   ```bash
   docker-compose up backend
   ```

2. Start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open browser to `http://localhost:5173`

4. Verify:
   - Connection status shows "Connected"
   - Dashboard displays real-time data
   - Worker cards update automatically
   - Logs stream in real-time

## Troubleshooting

### Connection Issues
- Check backend is running on port 8090
- Verify `VITE_BACKEND_URL` in `.env`
- Check browser console for SSE errors

### No Data Updates
- Ensure workers are registered with backend
- Check backend logs for SSE broadcast messages
- Verify event subscriptions in component code

### Build Errors
- Run `npm install` to ensure all dependencies
- Check TypeScript errors with `npm run build`

## Migration Notes

### What Was Removed
- All hardcoded mock data replaced with real-time data
- No SSH or REST API calls in frontend
- No manual polling or setTimeout intervals

### What Was Added
- `socketService.ts` - Central SSE connection manager
- Environment variable `VITE_BACKEND_URL`
- Connection status indicators
- Event subscription patterns in all components
- Automatic reconnection logic

## Future Enhancements

1. **Authentication**: Add token-based auth for SSE connection
2. **Compression**: Enable gzip compression for SSE data
3. **Filtering**: Add client-side filtering for specific events
4. **Buffering**: Implement message buffering during disconnections
5. **Health Checks**: Ping/pong mechanism for connection health
