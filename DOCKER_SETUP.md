# Docker Setup Guide

## Fixed Issues

### 1. Path Mismatch
- **Problem**: Dockerfile used `/frontend` but docker-compose used `/client`
- **Fix**: Updated docker-compose.yaml to use `/frontend` consistently

### 2. Port Configuration
- **Problem**: Vite was configured to run on port 3000 instead of 5173
- **Fix**: Updated vite.config.ts to use port 5173

### 3. Browser Auto-Open Error
- **Problem**: `xdg-open ENOENT` error because Vite tried to open browser in Docker
- **Fix**: Set `open: false` in vite.config.ts

### 4. Network Binding
- **Problem**: Vite wasn't accessible from outside container
- **Fix**: Added `host: '0.0.0.0'` in vite.config.ts

## Running the Application

### Using Docker Compose (Recommended)

```bash
# Navigate to project directory
cd Developer-Dashboard

# Build and start all services
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f frontend
docker-compose logs -f backend

# Stop services
docker-compose down
```

### Access Points

- **Frontend Dashboard**: http://localhost:5173
- **Backend API**: http://localhost:8090
- **Backend WebSocket**: ws://localhost:8090/ws/dashboard/{connection_id}
- **Health Check**: http://localhost:8090/health

## Environment Variables

### Frontend (.env)
```env
VITE_BACKEND_URL=http://localhost:8090
```

### Backend (docker-compose.yaml)
```yaml
environment:
  - DASHBOARD_PORT=8090
  - REFRESH_INTERVAL=30
```

## Development Workflow

### Hot Reload
The frontend supports hot reload. Changes to files in `./frontend/` will automatically update in the browser.

### Debugging

**Check frontend logs:**
```bash
docker logs dashboard_frontend
```

**Check backend logs:**
```bash
docker logs dashboard_backend
```

**Access frontend container:**
```bash
docker exec -it dashboard_frontend sh
```

**Access backend container:**
```bash
docker exec -it dashboard_backend sh
```

## File Structure

```
Developer-Dashboard/
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── socketService.ts    # WebSocket client
│   │   └── components/
│   │       ├── QueuesView.tsx      # DLQ management
│   │       ├── LogsView.tsx        # Log export
│   │       └── SettingsView.tsx    # Settings persistence
│   ├── vite.config.ts              # Vite configuration
│   ├── Dockerfile                  # Frontend container
│   ├── .env                        # Local environment
│   ├── .env.example               # Environment template
│   └── .dockerignore              # Docker ignore rules
├── backend/
│   ├── health_dashboard.py        # WebSocket server
│   └── Dockerfile                 # Backend container
└── docker-compose.yaml            # Multi-container setup
```

## Troubleshooting

### Port Already in Use
If ports 5173 or 8090 are already in use:
```bash
# Find process using port
lsof -i :5173
lsof -i :8090

# Kill the process or change ports in docker-compose.yaml
```

### Container Won't Start
```bash
# Remove old containers and volumes
docker-compose down -v

# Rebuild from scratch
docker-compose up --build --force-recreate
```

### WebSocket Connection Failed
1. Verify backend is running: `curl http://localhost:8090/health`
2. Check browser console for WebSocket errors
3. Verify VITE_BACKEND_URL in environment

### Frontend Not Updating
```bash
# Clear Docker build cache
docker-compose build --no-cache frontend

# Or rebuild with fresh node_modules
docker-compose down
docker volume prune
docker-compose up --build
```

## Production Deployment

For production, update the Dockerfile target and environment:

```yaml
frontend:
  build:
    context: frontend
    dockerfile: Dockerfile
    target: production  # Use production stage
  environment:
    - VITE_BACKEND_URL=https://your-backend-domain.com
```

Then build the production image:
```bash
docker-compose -f docker-compose.prod.yaml up --build
```
