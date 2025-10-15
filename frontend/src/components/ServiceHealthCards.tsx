import { Card, CardContent } from "./ui/card";
import { Badge } from "./ui/badge";
import { Database, Cpu, HardDrive, Box, GitBranch, Server, Activity } from "lucide-react";
import { useEffect, useState } from "react";

type ServiceStatus = "healthy" | "degraded" | "down";

interface Service {
  id: string;
  name: string;
  status: ServiceStatus;
  uptime: string;
  responseTime: string;
  icon: any;
}

const defaultServices: Service[] = [
  {
    id: "postgres",
    name: "PostgreSQL",
    status: "healthy",
    uptime: "99.98%",
    responseTime: "12ms",
    icon: Database,
  },
  {
    id: "redis",
    name: "Redis Cache",
    status: "healthy",
    uptime: "99.99%",
    responseTime: "3ms",
    icon: HardDrive,
  },
  {
    id: "rabbitmq",
    name: "RabbitMQ",
    status: "healthy",
    uptime: "99.95%",
    responseTime: "8ms",
    icon: GitBranch,
  },
  {
    id: "api",
    name: "API Server",
    status: "healthy",
    uptime: "99.97%",
    responseTime: "45ms",
    icon: Server,
  },
  {
    id: "worker",
    name: "Worker Process",
    status: "degraded",
    uptime: "98.50%",
    responseTime: "120ms",
    icon: Cpu,
  },
  {
    id: "storage",
    name: "Object Storage",
    status: "healthy",
    uptime: "100%",
    responseTime: "25ms",
    icon: Box,
  },
];

function getStatusColor(status: ServiceStatus): string {
  switch (status) {
    case "healthy":
      return "bg-emerald-500";
    case "degraded":
      return "bg-yellow-500";
    case "down":
      return "bg-red-500";
  }
}

function getStatusBadgeVariant(status: ServiceStatus): "default" | "secondary" | "destructive" {
  switch (status) {
    case "healthy":
      return "default";
    case "degraded":
      return "secondary";
    case "down":
      return "destructive";
  }
}

interface ServiceHealthCardsProps {
  data?: any;
}

export function ServiceHealthCards({ data }: ServiceHealthCardsProps) {
  const [services, setServices] = useState<Service[]>(defaultServices);

  useEffect(() => {
    if (!data || !data.workers) return;

    const updatedServices = data.workers.map((worker: any) => {
      const iconMap: { [key: string]: any } = {
        'Server': Server,
        'OCR Worker': Activity,
        'LLM Worker': Cpu,
        'O1 LLM Worker': Cpu,
        'Summary Worker': Box,
        'Strikethrough Worker': Box,
      };

      return {
        id: worker.name.toLowerCase().replace(/\s+/g, '_'),
        name: worker.name,
        status: worker.healthy ? 'healthy' : 'down',
        uptime: worker.worker_status === 'running' ? '100%' : '0%',
        responseTime: worker.response_time || 'N/A',
        icon: iconMap[worker.name] || Activity,
      };
    });

    setServices(updatedServices);
  }, [data]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {services.map((service) => {
        const Icon = service.icon;
        return (
          <Card key={service.id} className="bg-card border-border hover:border-primary/50 transition-colors">
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted">
                    <Icon className="size-5 text-foreground" />
                  </div>
                  <div>
                    <h3 className="text-sm">{service.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <div className={`size-2 rounded-full ${getStatusColor(service.status)} animate-pulse`} />
                      <span className="text-xs text-muted-foreground capitalize">{service.status}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-border">
                <div>
                  <p className="text-xs text-muted-foreground">Uptime</p>
                  <p className="text-sm mt-1">{service.uptime}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Response</p>
                  <p className="text-sm mt-1">{service.responseTime}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
