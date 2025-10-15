import { ServiceHealthCards } from "./ServiceHealthCards";
import { DLQMonitoring } from "./DLQMonitoring";
import { SystemMetrics } from "./SystemMetrics";
import { Button } from "./ui/button";
import { FileText, RefreshCw } from "lucide-react";
import { SidebarTrigger } from "./ui/sidebar";

export function Dashboard() {
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
            <Button variant="outline" size="sm">
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
          <ServiceHealthCards />
        </section>

        {/* DLQ Monitoring and System Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <SystemMetrics />
          </div>
          <div>
            <DLQMonitoring />
          </div>
        </div>
      </div>
    </div>
  );
}
