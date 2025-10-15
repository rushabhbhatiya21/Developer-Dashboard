import { ServiceHealthCards } from "./ServiceHealthCards";
import { DLQMonitoring } from "./DLQMonitoring";
import { SystemMetrics } from "./SystemMetrics";
import { Button } from "./ui/button";
import { FileText, RefreshCw } from "lucide-react";
import { SidebarTrigger } from "./ui/sidebar";
import { useEffect, useState } from "react";
import { socketService } from "../services/socketService";

export function Dashboard() {
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    socketService.connect();

    const unsubscribeOpen = socketService.subscribe('connection_open', () => {
      setIsConnected(true);
    });

    const unsubscribeError = socketService.subscribe('connection_error', () => {
      setIsConnected(false);
    });

    const unsubscribeInitial = socketService.subscribe('initial_data', (data) => {
      setDashboardData(data);
    });

    const unsubscribeUpdate = socketService.subscribe('dashboard_update', (data) => {
      setDashboardData(data);
    });

    return () => {
      unsubscribeOpen();
      unsubscribeError();
      unsubscribeInitial();
      unsubscribeUpdate();
    };
  }, []);

  const handleRefresh = () => {
    socketService.disconnect();
    socketService.connect();
  };

  return (
    <div className="size-full">
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <div>
              <h1>System Health Overview</h1>
              <p className="text-sm text-muted-foreground">Real-time monitoring and status</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 mr-4">
              <div className={`size-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'} animate-pulse`} />
              <span className="text-xs text-muted-foreground">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={handleRefresh}>
              <RefreshCw className="size-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline" size="sm">
              <FileText className="size-4 mr-2" />
              View Logs
            </Button>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Service Health Status - Top Priority */}
        <section>
          <h2 className="mb-4">Service Health</h2>
          <ServiceHealthCards data={dashboardData} />
        </section>

        {/* DLQ Monitoring and System Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <SystemMetrics data={dashboardData} />
          </div>
          <div>
            <DLQMonitoring data={dashboardData} />
          </div>
        </div>
      </div>
    </div>
  );
}
