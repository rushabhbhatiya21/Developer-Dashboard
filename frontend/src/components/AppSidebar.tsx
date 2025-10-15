import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
} from "./ui/sidebar";
import { LayoutDashboard, List, FileText, Settings, Activity } from "lucide-react";

interface AppSidebarProps {
  activeView: "dashboard" | "queues" | "logs" | "settings";
  setActiveView: (view: "dashboard" | "queues" | "logs" | "settings") => void;
}

export function AppSidebar({ activeView, setActiveView }: AppSidebarProps) {
  const menuItems = [
    { id: "dashboard" as const, label: "Overview", icon: LayoutDashboard },
    { id: "queues" as const, label: "Queues", icon: List },
    { id: "logs" as const, label: "Logs", icon: FileText },
    { id: "settings" as const, label: "Settings", icon: Settings },
  ];

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary">
            <Activity className="size-5 text-sidebar-primary-foreground" />
          </div>
          <div>
            <h2>HealthMonitor</h2>
            <p className="text-xs text-muted-foreground">System Dashboard</p>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {menuItems.map((item) => (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    onClick={() => setActiveView(item.id)}
                    isActive={activeView === item.id}
                  >
                    <item.icon className="size-4" />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
