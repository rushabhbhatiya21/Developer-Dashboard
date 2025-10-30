import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";
import { SidebarTrigger } from "./ui/sidebar";
import { Separator } from "./ui/separator";
import { useEffect, useState } from "react";
import { socketService, sendMessage } from "../services/socketService";

export function SettingsView() {
  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Notification settings
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [dlqAlerts, setDlqAlerts] = useState(true);
  const [degradationAlerts, setDegradationAlerts] = useState(true);

  // Threshold settings
  const [cpuThreshold, setCpuThreshold] = useState(85);
  const [memoryThreshold, setMemoryThreshold] = useState(90);
  const [dlqThreshold, setDlqThreshold] = useState(10);
  const [responseThreshold, setResponseThreshold] = useState(500);

  // Refresh interval
  const [refreshInterval, setRefreshInterval] = useState(30);

  // Validation errors
  const [validationErrors, setValidationErrors] = useState<{ [key: string]: string }>({});

  // Initial settings for reset
  const [initialSettings, setInitialSettings] = useState<any>(null);

  useEffect(() => {
    socketService.connect();

    const unsubscribeOpen = socketService.subscribe('connection_open', () => {
      setIsConnected(true);
      // Load settings from backend when connected
      loadSettings();
    });

    const unsubscribeError = socketService.subscribe('connection_error', () => {
      setIsConnected(false);
    });

    const unsubscribeClosed = socketService.subscribe('connection_closed', () => {
      setIsConnected(false);
    });

    // Subscribe to command responses
    const unsubscribeResponse = socketService.subscribe('command_response', (message) => {
      const { payload } = message;

      if (payload.command === 'settings:save') {
        setIsSaving(false);

        if (payload.success) {
          console.log('Settings saved successfully');
          alert('Settings saved successfully!');
          setIsDirty(false);
          // Reload settings to get confirmation
          loadSettings();
        } else {
          console.error('Failed to save settings:', payload.error);
          alert(`Error saving settings: ${payload.error}`);
        }
      }

      if (payload.command === 'settings:get') {
        if (payload.success && payload.settings) {
          console.log('Loaded settings from backend:', payload.settings);
          applySettings(payload.settings);
        } else {
          console.warn('Failed to load settings, using defaults:', payload.error);
          // Keep current default values
        }
      }
    });

    return () => {
      unsubscribeOpen();
      unsubscribeError();
      unsubscribeClosed();
      unsubscribeResponse();
    };
  }, []);

  /**
   * Load settings from backend
   */
  const loadSettings = async () => {
    if (!isConnected) return;

    try {
      await sendMessage('settings:get', {});
      console.log('Sent settings:get command');
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  /**
   * Apply loaded settings to form state
   */
  const applySettings = (settings: any) => {
    if (settings.notifications) {
      setEmailAlerts(settings.notifications.email_alerts ?? true);
      setDlqAlerts(settings.notifications.dlq_alerts ?? true);
      setDegradationAlerts(settings.notifications.degradation_alerts ?? true);
    }

    if (settings.thresholds) {
      setCpuThreshold(settings.thresholds.cpu_percent ?? 85);
      setMemoryThreshold(settings.thresholds.memory_percent ?? 90);
      setDlqThreshold(settings.thresholds.dlq_count ?? 10);
      setResponseThreshold(settings.thresholds.response_time_ms ?? 500);
    }

    if (settings.refresh_interval_seconds !== undefined) {
      setRefreshInterval(settings.refresh_interval_seconds);
    }

    // Store as initial settings for cancel/reset
    setInitialSettings(settings);
    setIsDirty(false);
  };

  /**
   * Validate threshold values
   */
  const validateSettings = (): boolean => {
    const errors: { [key: string]: string } = {};

    if (cpuThreshold < 1 || cpuThreshold > 100) {
      errors.cpuThreshold = 'CPU threshold must be between 1-100';
    }

    if (memoryThreshold < 1 || memoryThreshold > 100) {
      errors.memoryThreshold = 'Memory threshold must be between 1-100';
    }

    if (dlqThreshold < 0) {
      errors.dlqThreshold = 'DLQ threshold must be >= 0';
    }

    if (responseThreshold < 0) {
      errors.responseThreshold = 'Response threshold must be >= 0';
    }

    if (refreshInterval < 5) {
      errors.refreshInterval = 'Refresh interval must be >= 5 seconds';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  /**
   * Handle save settings action
   */
  const handleSave = async () => {
    if (!isConnected) {
      alert('Cannot save: Not connected to server');
      return;
    }

    if (!validateSettings()) {
      alert('Please fix validation errors before saving');
      return;
    }

    setIsSaving(true);

    const settings = {
      notifications: {
        email_alerts: emailAlerts,
        dlq_alerts: dlqAlerts,
        degradation_alerts: degradationAlerts
      },
      thresholds: {
        cpu_percent: cpuThreshold,
        memory_percent: memoryThreshold,
        dlq_count: dlqThreshold,
        response_time_ms: responseThreshold
      },
      refresh_interval_seconds: refreshInterval
    };

    try {
      await sendMessage('settings:save', settings);
      console.log('Sent settings:save command', settings);
    } catch (error) {
      console.error('Failed to send save command:', error);
      alert(`Failed to save settings: ${error}`);
      setIsSaving(false);
    }
  };

  /**
   * Handle cancel action - reset to initial settings
   */
  const handleCancel = () => {
    if (initialSettings) {
      applySettings(initialSettings);
    } else {
      // If no initial settings loaded, request them again
      loadSettings();
    }
    setIsDirty(false);
  };

  /**
   * Mark form as dirty when any setting changes
   */
  const markDirty = () => {
    if (!isDirty) {
      setIsDirty(true);
    }
  };

  // Handler wrappers that mark form as dirty
  const handleEmailAlertsChange = (checked: boolean) => {
    setEmailAlerts(checked);
    markDirty();
  };

  const handleDlqAlertsChange = (checked: boolean) => {
    setDlqAlerts(checked);
    markDirty();
  };

  const handleDegradationAlertsChange = (checked: boolean) => {
    setDegradationAlerts(checked);
    markDirty();
  };

  const handleCpuThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCpuThreshold(Number(e.target.value));
    markDirty();
  };

  const handleMemoryThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMemoryThreshold(Number(e.target.value));
    markDirty();
  };

  const handleDlqThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setDlqThreshold(Number(e.target.value));
    markDirty();
  };

  const handleResponseThresholdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setResponseThreshold(Number(e.target.value));
    markDirty();
  };

  const handleRefreshIntervalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRefreshInterval(Number(e.target.value));
    markDirty();
  };

  return (
    <div className="size-full">
      <div className="border-b border-border bg-card px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SidebarTrigger />
            <div>
              <h1>Settings</h1>
              <p className="text-sm text-muted-foreground">Configure monitoring preferences</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className={`size-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-500'} animate-pulse`} />
            <span className="text-xs text-muted-foreground">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
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
                <Switch checked={emailAlerts} onCheckedChange={handleEmailAlertsChange} />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>DLQ Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Alert when dead letter queue exceeds threshold
                  </p>
                </div>
                <Switch checked={dlqAlerts} onCheckedChange={handleDlqAlertsChange} />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Service Degradation Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Notify when services show degraded performance
                  </p>
                </div>
                <Switch checked={degradationAlerts} onCheckedChange={handleDegradationAlertsChange} />
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
                <Input
                  id="cpu-threshold"
                  type="number"
                  value={cpuThreshold}
                  onChange={handleCpuThresholdChange}
                  min={1}
                  max={100}
                />
                {validationErrors.cpuThreshold && (
                  <p className="text-sm text-red-500">{validationErrors.cpuThreshold}</p>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="memory-threshold">Memory Usage Threshold (%)</Label>
                <Input
                  id="memory-threshold"
                  type="number"
                  value={memoryThreshold}
                  onChange={handleMemoryThresholdChange}
                  min={1}
                  max={100}
                />
                {validationErrors.memoryThreshold && (
                  <p className="text-sm text-red-500">{validationErrors.memoryThreshold}</p>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="dlq-threshold">DLQ Message Count Threshold</Label>
                <Input
                  id="dlq-threshold"
                  type="number"
                  value={dlqThreshold}
                  onChange={handleDlqThresholdChange}
                  min={0}
                />
                {validationErrors.dlqThreshold && (
                  <p className="text-sm text-red-500">{validationErrors.dlqThreshold}</p>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="response-threshold">Response Time Threshold (ms)</Label>
                <Input
                  id="response-threshold"
                  type="number"
                  value={responseThreshold}
                  onChange={handleResponseThresholdChange}
                  min={0}
                />
                {validationErrors.responseThreshold && (
                  <p className="text-sm text-red-500">{validationErrors.responseThreshold}</p>
                )}
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
                <Input
                  id="refresh-interval"
                  type="number"
                  value={refreshInterval}
                  onChange={handleRefreshIntervalChange}
                  min={5}
                />
                {validationErrors.refreshInterval && (
                  <p className="text-sm text-red-500">{validationErrors.refreshInterval}</p>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={!isDirty}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!isConnected || isSaving || !isDirty || Object.keys(validationErrors).length > 0}
              title={!isConnected ? 'Connect to server to save' : 'Save settings to backend'}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
