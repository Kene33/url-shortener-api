import * as Dialog from "@radix-ui/react-dialog";
import { Bell, FolderKanban, Home, LayoutDashboard, Menu, Settings, User2, X } from "lucide-react";
import type { PropsWithChildren } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/app/logo";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";
import { useSession } from "@/features/session/session-provider";
import { cn } from "@/lib/utils";

const links = [
  { to: "/", label: "Главная", icon: Home },
  { to: "/links", label: "Мои ссылки", icon: LayoutDashboard },
  { to: "/analytics", label: "Аналитика", icon: Bell },
  { to: "/folders", label: "Папки", icon: FolderKanban },
  { to: "/settings", label: "Настройки", icon: Settings },
  { to: "/profile", label: "Профиль", icon: User2 },
  { to: "/notifications", label: "Уведомления", icon: Bell },
];

function SidebarContent() {
  const { logout } = useSession();
  return (
    <div className="flex h-full flex-col gap-6">
      <Logo />
      <nav className="flex flex-1 flex-col gap-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-panel px-3 py-2 text-sm text-subtle transition hover:bg-muted hover:text-text",
                isActive && "bg-accent/10 text-accent",
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <Button variant="ghost" className="justify-start" onClick={() => void logout()}>
        Выйти
      </Button>
    </div>
  );
}

export function AppShell({ children }: PropsWithChildren) {
  const { user } = useSession();
  const location = useLocation();

  if (!user || location.pathname === "/") {
    return <>{children}</>;
  }

  return (
    <div className="page-shell">
      <div className="mx-auto flex min-h-screen max-w-[1600px] gap-4 p-4 md:p-5">
        <aside className="panel hidden w-[248px] p-4 lg:block">
          <SidebarContent />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <header className="panel flex items-center justify-between gap-3 p-4">
            <div className="flex items-center gap-3 lg:hidden">
              <Dialog.Root>
                <Dialog.Trigger asChild>
                  <button type="button" className="pill" aria-label="Open navigation">
                    <Menu className="h-4 w-4" />
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 bg-black/50" />
                  <Dialog.Content className="fixed left-0 top-0 h-full w-[280px] bg-panel p-4">
                    <div className="mb-4 flex items-center justify-between">
                      <Logo />
                      <Dialog.Close asChild>
                        <button type="button" className="pill">
                          <X className="h-4 w-4" />
                        </button>
                      </Dialog.Close>
                    </div>
                    <SidebarContent />
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <Logo />
            </div>
            <div className="hidden lg:block">
              <p className="m-0 text-xs uppercase tracking-[0.2em] text-subtle">LinkCutter</p>
              <p className="m-0 mt-1 text-sm text-subtle">Compact control over links, analytics and account state.</p>
            </div>
            <ThemeLanguageControls />
          </header>
          <main className="min-w-0 flex-1">{children ?? <Outlet />}</main>
        </div>
      </div>
    </div>
  );
}
