import { useState } from "react";
import { SidebarProvider } from "./components/ui/sidebar";
import { AppSidebar } from "./components/AppSidebar";
import { Dashboard } from "./components/Dashboard";
import { QueuesView } from "./components/QueuesView";
import { LogsView } from "./components/LogsView";
import { SettingsView } from "./components/SettingsView";

export default function App() {
  const [activeView, setActiveView] = useState<"dashboard" | "queues" | "logs" | "settings">("dashboard");

  return (
    <div className="size-full dark">
      <SidebarProvider>
        <div className="flex size-full">
          <AppSidebar activeView={activeView} setActiveView={setActiveView} />
          <main className="flex-1 overflow-auto bg-background">
            {activeView === "dashboard" && <Dashboard />}
            {activeView === "queues" && <QueuesView />}
            {activeView === "logs" && <LogsView />}
            {activeView === "settings" && <SettingsView />}
          </main>
        </div>
      </SidebarProvider>
    </div>
  );
}
