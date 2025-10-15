import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";
import { SidebarTrigger } from "./ui/sidebar";
import { Separator } from "./ui/separator";

export function SettingsView() {
  return (
    <div className="size-full">
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="flex items-center gap-3">
          <SidebarTrigger />
          <div>
            <h1>Settings</h1>
            <p className="text-sm text-muted-foreground">Configure monitoring preferences</p>
          </div>
        </div>
      </div>

      <div className="p-6 max-w-4xl">
        <div className="space-y-6">
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Notifications</CardTitle>
              <CardDescription>Manage alert and notification settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Email Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Receive email notifications for critical issues
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>DLQ Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Alert when dead letter queue exceeds threshold
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Service Degradation Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Notify when services show degraded performance
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Thresholds</CardTitle>
              <CardDescription>Configure alert thresholds for monitoring</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="cpu-threshold">CPU Usage Threshold (%)</Label>
                <Input id="cpu-threshold" type="number" defaultValue="85" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="memory-threshold">Memory Usage Threshold (%)</Label>
                <Input id="memory-threshold" type="number" defaultValue="90" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="dlq-threshold">DLQ Message Count Threshold</Label>
                <Input id="dlq-threshold" type="number" defaultValue="10" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="response-threshold">Response Time Threshold (ms)</Label>
                <Input id="response-threshold" type="number" defaultValue="500" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Refresh Interval</CardTitle>
              <CardDescription>Set automatic refresh rate for metrics</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="refresh-interval">Refresh Interval (seconds)</Label>
                <Input id="refresh-interval" type="number" defaultValue="30" />
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-2">
            <Button variant="outline">Cancel</Button>
            <Button>Save Changes</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
