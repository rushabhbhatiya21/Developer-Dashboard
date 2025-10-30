import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { SidebarTrigger } from "./ui/sidebar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { AlertCircle, AlertTriangle, CheckCircle, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { socketService, sendMessage, getConnectionState } from "../services/socketService";

interface QueueDetail {
  id: string;
  name: string;
  messages: number;
  consumers: number;
  rate: string;
  status: "ok" | "warning" | "critical";
  lastProcessed: string;
}

const defaultQueues: QueueDetail[] = [
  {
    id: "1",
    name: "email.send",
    messages: 0,
    consumers: 3,
    rate: "245/min",
    status: "ok",
    lastProcessed: "2s ago",
  },
  {
    id: "2",
    name: "processing.images",
    messages: 12,
    consumers: 5,
    rate: "120/min",
    status: "ok",
    lastProcessed: "5s ago",
  },
  {
    id: "3",
    name: "notifications.push",
    messages: 3,
    consumers: 2,
    rate: "80/min",
    status: "ok",
    lastProcessed: "1s ago",
  },
  {
    id: "4",
    name: "dlq.email.send",
    messages: 2,
    consumers: 0,
    rate: "0/min",
    status: "warning",
    lastProcessed: "2h ago",
  },
  {
    id: "5",
    name: "dlq.processing.images",
    messages: 8,
    consumers: 0,
    rate: "0/min",
    status: "critical",
    lastProcessed: "5h ago",
  },
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

export function QueuesView() {
  const [queues, setQueues] = useState<QueueDetail[]>(defaultQueues);
  const [isConnected, setIsConnected] = useState(false);
  const [deletingQueues, setDeletingQueues] = useState<Set<string>>(new Set());

  useEffect(() => {
    socketService.connect();

    const unsubscribeOpen = socketService.subscribe('connection_open', () => {
      setIsConnected(true);
    });

    const unsubscribeError = socketService.subscribe('connection_error', () => {
      setIsConnected(false);
    });

    const unsubscribeClosed = socketService.subscribe('connection_closed', () => {
      setIsConnected(false);
    });

    const unsubscribeInitial = socketService.subscribe('initial_data', (data) => {
      updateQueuesFromData(data);
    });

    const unsubscribeUpdate = socketService.subscribe('dashboard_update', (data) => {
      updateQueuesFromData(data);
    });

    // Subscribe to command responses for delete operations
    const unsubscribeResponse = socketService.subscribe('command_response', (message) => {
      const { payload } = message;

      if (payload.command === 'dlq:clear') {
        const queueName = payload.queue_name;

        // Remove queue from deleting state
        setDeletingQueues(prev => {
          const next = new Set(prev);
          next.delete(queueName);
          return next;
        });

        if (payload.success) {
          console.log(`DLQ ${queueName} cleared successfully:`, payload);
          alert(`Successfully deleted ${payload.messages_deleted || 0} messages from ${queueName}`);
          // Refresh data after successful delete
          handleRefresh();
        } else {
          console.error(`Failed to clear DLQ ${queueName}:`, payload.error);
          alert(`Error deleting DLQ: ${payload.error}`);
        }
      }
    });

    return () => {
      unsubscribeOpen();
      unsubscribeError();
      unsubscribeClosed();
      unsubscribeInitial();
      unsubscribeUpdate();
      unsubscribeResponse();
    };
  }, []);

  const updateQueuesFromData = (data: any) => {
    if (!data || !data.workers) return;

    const updatedQueues: QueueDetail[] = data.workers.map((worker: any, index: number) => {
      const errorCount = worker.error_count || 0;
      let status: "ok" | "warning" | "critical" = "ok";

      if (errorCount > 10) status = "critical";
      else if (errorCount > 5) status = "warning";

      return {
        id: String(index + 1),
        name: worker.name.toLowerCase().replace(/\s+/g, '.'),
        messages: worker.total_processed || 0,
        consumers: worker.healthy ? 1 : 0,
        rate: `${worker.total_processed || 0}/total`,
        status,
        lastProcessed: worker.last_checked ? new Date(worker.last_checked).toLocaleString() : 'N/A',
      };
    });

    setQueues(updatedQueues);
  };

  /**
   * Handle DLQ delete operation with user confirmation
   * @param queueId Queue ID
   * @param queueName Queue name to delete
   */
  const handleDeleteDLQ = async (queueId: string, queueName: string) => {
    if (!isConnected) {
      alert('Cannot delete: Not connected to server');
      return;
    }

    // Show confirmation dialog with action selection
    const confirmMessage = `Delete DLQ '${queueName}'?\n\nClick OK to delete ALL messages\nClick Cancel to delete only failed messages\n\nPress Escape to abort`;
    const userChoice = window.confirm(confirmMessage);

    if (userChoice === undefined || userChoice === null) {
      // User pressed Escape or closed dialog
      return;
    }

    const action = userChoice ? 'clear_all' : 'clear_failed';

    // Mark queue as being deleted
    setDeletingQueues(prev => new Set(prev).add(queueName));

    try {
      await sendMessage('dlq:clear', {
        queue_name: queueName,
        action: action
      });
      console.log(`Sent dlq:clear command for ${queueName} with action ${action}`);
    } catch (error) {
      console.error('Failed to send delete command:', error);
      alert(`Failed to delete DLQ: ${error}`);

      // Remove from deleting state on error
      setDeletingQueues(prev => {
        const next = new Set(prev);
        next.delete(queueName);
        return next;
      });
    }
  };

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
              <h1>Queue Management</h1>
              <p className="text-sm text-muted-foreground">Monitor and manage message queues</p>
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
          </div>
        </div>
      </div>

      <div className="p-6">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Active Queues</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Queue Name</TableHead>
                  <TableHead>Messages</TableHead>
                  <TableHead>Consumers</TableHead>
                  <TableHead>Rate</TableHead>
                  <TableHead>Last Processed</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queues.map((queue) => (
                  <TableRow key={queue.id}>
                    <TableCell>{getStatusIcon(queue.status)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span>{queue.name}</span>
                        {queue.name.startsWith("dlq") && (
                          <Badge variant="destructive" className="text-xs">DLQ</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={queue.messages > 0 && queue.name.startsWith("dlq") ? "text-destructive" : ""}>
                        {queue.messages}
                      </span>
                    </TableCell>
                    <TableCell>{queue.consumers}</TableCell>
                    <TableCell className="text-muted-foreground">{queue.rate}</TableCell>
                    <TableCell className="text-muted-foreground">{queue.lastProcessed}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {queue.name.startsWith("dlq") && queue.messages > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteDLQ(queue.id, queue.name)}
                            disabled={!isConnected || deletingQueues.has(queue.name)}
                            title={!isConnected ? 'Connect to server to delete' : 'Delete DLQ messages'}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
