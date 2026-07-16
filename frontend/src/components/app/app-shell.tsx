import * as Dialog from "@radix-ui/react-dialog";
import { Bell, FolderKanban, Home, LayoutDashboard, LogOut, Menu, Settings, User2, X } from "lucide-react";
import type { PropsWithChildren } from "react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/app/logo";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";
import { useSession } from "@/features/session/session-provider";
import { useProfileQuery } from "@/features/profile/api";
import { cn } from "@/lib/utils";

const links = [
  { to: "/", label: "home", icon: Home },
  { to: "/links", label: "yourLinks", icon: LayoutDashboard },
  { to: "/analytics", label: "analytics", icon: Bell },
  { to: "/folders", label: "folders", icon: FolderKanban },
  { to: "/settings", label: "settings", icon: Settings },
  { to: "/profile", label: "profile", icon: User2 },
  { to: "/notifications", label: "notifications", icon: Bell },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { logout } = useSession();
  const { t } = useTranslation();
  return (
    <div className="flex h-full flex-col gap-6">
      <Logo />
      <nav className="flex flex-1 flex-col gap-1">
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-panel px-3 py-2 text-sm text-subtle transition hover:bg-muted hover:text-text",
                isActive && "bg-accent/10 text-accent",
              )
            }
          >
            <Icon className="h-4 w-4" />
            <span>{t(label)}</span>
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
  const { user, logout } = useSession();
  const profile = useProfileQuery({ enabled: Boolean(user) });
  const location = useLocation();
  const { t } = useTranslation();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);

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
              <Dialog.Root open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen}>
                <Dialog.Trigger asChild>
                  <button type="button" className="pill" aria-label="Открыть навигацию" title="Открыть навигацию">
                    <Menu className="h-4 w-4" />
                  </button>
                </Dialog.Trigger>
                <Dialog.Portal>
                  <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 data-[state=closed]:opacity-0 data-[state=open]:opacity-100" />
                  <Dialog.Content className="fixed left-0 top-0 z-50 h-full w-[min(84vw,320px)] border-r border-border bg-panel p-4 shadow-panel outline-none transition-transform duration-200 data-[state=closed]:-translate-x-full data-[state=open]:translate-x-0">
                    <Dialog.Title className="sr-only">Навигация LinkCutter</Dialog.Title>
                    <Dialog.Description className="sr-only">Переход между разделами аккаунта</Dialog.Description>
                    <div className="mb-4 flex items-center justify-between">
                      <Logo />
                      <Dialog.Close asChild>
                        <button type="button" className="pill" aria-label="Закрыть навигацию" title="Закрыть навигацию">
                          <X className="h-4 w-4" />
                        </button>
                      </Dialog.Close>
                    </div>
                    <SidebarContent onNavigate={() => setMobileNavigationOpen(false)} />
                  </Dialog.Content>
                </Dialog.Portal>
              </Dialog.Root>
              <Logo />
            </div>
            <div className="hidden lg:block">
              <p className="m-0 text-xs uppercase tracking-[0.2em] text-subtle">LinkCutter</p>
              <p className="m-0 mt-1 text-sm text-subtle">{t("shellHint")}</p>
            </div>
            <div className="flex items-center gap-2">
              <ThemeLanguageControls />
              <NavLink
                to="/profile"
                className="hidden items-center gap-2 rounded-full border border-border bg-panel py-1 pl-1 pr-3 transition hover:border-accent/50 hover:bg-muted lg:flex"
                aria-label="Открыть профиль"
                title="Открыть профиль"
              >
                <Avatar user={profile.data?.user ?? user} />
                <span className="max-w-[150px] truncate text-xs font-medium text-text">
                  {profile.data?.user.display_name || user.email}
                </span>
              </NavLink>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="hidden !h-9 !w-9 !p-0 lg:inline-flex"
                aria-label="Выйти"
                title="Выйти"
                onClick={() => void logout()}
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </header>
          <main className="min-w-0 flex-1">{children ?? <Outlet />}</main>
        </div>
      </div>
    </div>
  );
}

function Avatar({ user }: { user: NonNullable<ReturnType<typeof useSession>["user"]> }) {
  const initials = (user.display_name || user.email)
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent text-[10px] font-semibold text-white">
      {user.avatar_url ? <img src={user.avatar_url} alt="" className="h-full w-full object-cover" /> : initials}
    </span>
  );
}
