import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { AlertCircle, AlertTriangle, CheckCircle } from "lucide-react";
import { useEffect, useState } from "react";

interface QueueMetric {
  name: string;
  count: number;
  status: "ok" | "warning" | "critical";
}

const defaultQueueMetrics: QueueMetric[] = [
  { name: "Email Queue", count: 0, status: "ok" },
  { name: "Processing Queue", count: 12, status: "ok" },
  { name: "Notification Queue", count: 3, status: "ok" },
  { name: "DLQ - Email", count: 2, status: "warning" },
  { name: "DLQ - Processing", count: 8, status: "critical" },
  { name: "DLQ - Notification", count: 0, status: "ok" },
];

function getStatusIcon(status: string) {
  switch (status) {
    case "critical":
      return <AlertCircle className="size-4 text-red-500" />;
    case "warning":
      return <AlertTriangle className="size-4 text-yellow-500" />;
    default:
      return <CheckCircle className="size-4 text-emerald-500" />;
  }
}

interface DLQMonitoringProps {
  data?: any;
}

export function DLQMonitoring({ data }: DLQMonitoringProps) {
  const [queueMetrics, setQueueMetrics] = useState<QueueMetric[]>(defaultQueueMetrics);

  useEffect(() => {
    if (!data || !data.workers) return;

    const updatedMetrics = data.workers.map((worker: any) => {
      const errorCount = worker.error_count || 0;
      let status: "ok" | "warning" | "critical" = "ok";

      if (errorCount > 10) status = "critical";
      else if (errorCount > 5) status = "warning";

      return {
        name: worker.name,
        count: worker.total_processed || 0,
        status,
      };
    });

    setQueueMetrics(updatedMetrics);
  }, [data]);

  const totalDLQ = queueMetrics
    .filter((q) => q.name.startsWith("DLQ"))
    .reduce((sum, q) => sum + q.count, 0);

  return (
    <Card className="bg-card border-border h-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Queue Monitoring</CardTitle>
          {totalDLQ > 0 && (
            <Badge variant={totalDLQ > 5 ? "destructive" : "secondary"}>
              {totalDLQ} in DLQ
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {queueMetrics.map((queue) => (
          <div
            key={queue.name}
            className="flex items-center justify-between p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
          >
            <div className="flex items-center gap-2">
              {getStatusIcon(queue.status)}
              <span className="text-sm">{queue.name}</span>
            </div>
            <span className={`text-sm ${queue.count > 0 && queue.name.startsWith("DLQ") ? "text-destructive" : "text-muted-foreground"}`}>
              {queue.count}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
