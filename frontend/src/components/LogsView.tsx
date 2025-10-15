import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { SidebarTrigger } from "./ui/sidebar";
import { ScrollArea } from "./ui/scroll-area";
import { Search, Download, RefreshCw } from "lucide-react";

interface LogEntry {
  id: string;
  timestamp: string;
  level: "info" | "warning" | "error" | "debug";
  service: string;
  message: string;
}

const logs: LogEntry[] = [
  {
    id: "1",
    timestamp: "2025-10-09 14:32:15",
    level: "info",
    service: "API Server",
    message: "Request processed successfully: POST /api/users",
  },
  {
    id: "2",
    timestamp: "2025-10-09 14:31:58",
    level: "warning",
    service: "Worker Process",
    message: "High memory usage detected: 85% of allocated memory",
  },
  {
    id: "3",
    timestamp: "2025-10-09 14:31:45",
    level: "error",
    service: "RabbitMQ",
    message: "Failed to process message in processing.images queue",
  },
  {
    id: "4",
    timestamp: "2025-10-09 14:31:30",
    level: "info",
    service: "PostgreSQL",
    message: "Connection pool resized: 10 -> 15 connections",
  },
  {
    id: "5",
    timestamp: "2025-10-09 14:31:12",
    level: "debug",
    service: "Redis Cache",
    message: "Cache hit rate: 94.5% (last 1000 requests)",
  },
  {
    id: "6",
    timestamp: "2025-10-09 14:30:55",
    level: "info",
    service: "API Server",
    message: "Health check passed for all endpoints",
  },
  {
    id: "7",
    timestamp: "2025-10-09 14:30:40",
    level: "error",
    service: "Worker Process",
    message: "Image processing failed: Invalid format for file abc123.tmp",
  },
  {
    id: "8",
    timestamp: "2025-10-09 14:30:25",
    level: "warning",
    service: "API Server",
    message: "Rate limit approaching for client IP 192.168.1.100",
  },
];

function getLevelColor(level: string): string {
  switch (level) {
    case "error":
      return "text-red-500";
    case "warning":
      return "text-yellow-500";
    case "info":
      return "text-blue-500";
    case "debug":
      return "text-gray-500";
    default:
      return "";
  }
}

export function LogsView() {
  return (
    <div className="size-full">
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <div>
              <h1>System Logs</h1>
              <p className="text-sm text-muted-foreground">View and search application logs</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <RefreshCw className="size-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline" size="sm">
              <Download className="size-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </div>

      <div className="p-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input placeholder="Search logs..." className="pl-9" />
              </div>
              <Select defaultValue="all">
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Levels</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="debug">Debug</SelectItem>
                </SelectContent>
              </Select>
              <Select defaultValue="all-services">
                <SelectTrigger className="w-[180px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all-services">All Services</SelectItem>
                  <SelectItem value="api">API Server</SelectItem>
                  <SelectItem value="worker">Worker Process</SelectItem>
                  <SelectItem value="postgres">PostgreSQL</SelectItem>
                  <SelectItem value="redis">Redis Cache</SelectItem>
                  <SelectItem value="rabbitmq">RabbitMQ</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[600px]">
              <div className="space-y-2">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors border border-border"
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-xs text-muted-foreground whitespace-nowrap font-mono">
                        {log.timestamp}
                      </span>
                      <span className={`text-xs uppercase ${getLevelColor(log.level)} min-w-[60px]`}>
                        {log.level}
                      </span>
                      <span className="text-xs text-muted-foreground min-w-[120px]">
                        {log.service}
                      </span>
                      <span className="text-sm flex-1">{log.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
