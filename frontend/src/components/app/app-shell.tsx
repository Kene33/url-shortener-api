import * as Dialog from "@radix-ui/react-dialog";
import { BarChart3, Bell, FolderKanban, Home, LayoutDashboard, Link2, LogOut, Menu, PanelLeftClose, PanelLeftOpen, Settings, Shield, User2, Users, X } from "lucide-react";
import type { PropsWithChildren } from "react";
import { useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/app/logo";
import { ThemeLanguageControls } from "@/components/app/theme-language-controls";
import { useSession } from "@/features/session/session-provider";
import { useProfileQuery } from "@/features/profile/api";
import { cn } from "@/lib/utils";

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { logout, user } = useSession();
  const { t } = useTranslation();
  const primaryLinks = useMemo(() => [
    { to: "/", label: t("common.home"), icon: Home }, { to: "/links", label: t("nav.links"), icon: LayoutDashboard },
    { to: "/analytics", label: t("nav.analytics"), icon: BarChart3 }, { to: "/folders", label: t("nav.folders"), icon: FolderKanban },
    { to: "/settings", label: t("nav.settings"), icon: Settings }, { to: "/profile", label: t("nav.profile"), icon: User2 },
    { to: "/notifications", label: t("nav.notifications"), icon: Bell },
  ], [t]);
  const adminLinks = useMemo(() => {
    if (user?.role === "admin") return [
      { to: "/admin", label: t("nav.admin"), icon: Shield }, { to: "/admin/users", label: t("nav.adminUsers"), icon: Users },
      { to: "/admin/links", label: t("nav.adminLinks"), icon: Link2 }, { to: "/admin/settings", label: t("nav.adminSettings"), icon: Settings },
    ];
    if (user?.role === "moderator") return [
      { to: "/admin", label: t("nav.admin"), icon: Shield }, { to: "/admin/links", label: t("nav.adminLinks"), icon: Link2 },
    ];
    if (user?.role === "support") return [{ to: "/admin/users", label: t("nav.adminUsers"), icon: Users }];
    return [];
  }, [t, user?.role]);
  const renderLink = (to: string, label: string, Icon: typeof Home) => <NavLink key={to} to={to} end={to === "/admin"} onClick={onNavigate} className={({ isActive }) => cn("flex items-center gap-3 rounded-panel px-3 py-2 text-sm text-subtle transition hover:bg-muted hover:text-text", isActive && "bg-accent/10 text-accent")}><Icon className="h-4 w-4" /><span>{label}</span></NavLink>;
  const isStaff = adminLinks.length > 0;
  return <div className="flex h-full flex-col gap-6"><Logo /><nav className="flex flex-1 flex-col gap-5"><div className="flex flex-col gap-1">{primaryLinks.map(({ to, label, icon }) => renderLink(to, label, icon))}</div>{isStaff ? <div className="flex flex-col gap-1"><p className="px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-subtle">{t("nav.adminSection")}</p>{adminLinks.map(({ to, label, icon }) => renderLink(to, label, icon))}</div> : null}</nav><Button variant="ghost" className="justify-start" onClick={() => void logout()}>{t("shell.logout")}</Button></div>;
}

export function AppShell({ children }: PropsWithChildren) {
  const { user, logout } = useSession(); const profile = useProfileQuery({ enabled: Boolean(user) }); const { t } = useTranslation();
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false); const [sidebarOpen, setSidebarOpen] = useState(true);
  if (!user) return <>{children}</>;
  return <div className="page-shell"><div className="mx-auto flex min-h-screen max-w-[1600px] gap-4 p-4 md:p-5"><aside className={cn("panel hidden w-[248px] shrink-0 p-4 lg:block", !sidebarOpen && "lg:hidden")}><SidebarContent /></aside><div className="flex min-w-0 flex-1 flex-col gap-4"><header className="panel flex items-center justify-between gap-3 p-4"><div className="flex items-center gap-3 lg:hidden"><Dialog.Root open={mobileNavigationOpen} onOpenChange={setMobileNavigationOpen}><Dialog.Trigger asChild><button type="button" className="pill" aria-label={t("shell.openNav")}><Menu className="h-4 w-4" /></button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" /><Dialog.Content className="fixed left-0 top-0 z-50 h-full w-[min(84vw,320px)] border-r border-border bg-panel p-4 shadow-panel outline-none"><Dialog.Title className="sr-only">{t("shell.mobileTitle")}</Dialog.Title><Dialog.Description className="sr-only">{t("shell.mobileDescription")}</Dialog.Description><div className="mb-4 flex items-center justify-between"><Logo /><Dialog.Close asChild><button type="button" className="pill" aria-label={t("shell.closeNav")}><X className="h-4 w-4" /></button></Dialog.Close></div><SidebarContent onNavigate={() => setMobileNavigationOpen(false)} /></Dialog.Content></Dialog.Portal></Dialog.Root><Logo /></div><div className="hidden items-center gap-3 lg:flex"><button type="button" className="pill !h-9 !w-9 !justify-center !p-0" aria-label={sidebarOpen ? t("shell.hideSidebar") : t("shell.showSidebar")} onClick={() => setSidebarOpen((open) => !open)}>{sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}</button><div><p className="m-0 text-base font-extrabold uppercase tracking-[0.14em] text-text">{t("common.brand")}</p><p className="m-0 mt-1 text-sm text-subtle">{t("shell.hint")}</p></div></div><div className="flex items-center gap-2"><ThemeLanguageControls /><NavLink to="/profile" className="hidden items-center gap-2 rounded-full border border-border bg-panel py-1 pl-1 pr-3 transition hover:border-accent/50 hover:bg-muted lg:flex" aria-label={t("shell.openProfile")}><Avatar user={profile.data?.user ?? user} /><span className="max-w-[150px] truncate text-xs font-medium text-text">{profile.data?.user.display_name || user.email}</span></NavLink><Button type="button" variant="ghost" size="sm" className="hidden !h-9 !w-9 !p-0 lg:inline-flex" aria-label={t("shell.logout")} onClick={() => void logout()}><LogOut className="h-4 w-4" /></Button></div></header><main className="min-w-0 flex-1">{children ?? <Outlet />}</main></div></div></div>;
}

function Avatar({ user }: { user: NonNullable<ReturnType<typeof useSession>["user"]> }) { const initials = (user.display_name || user.email).split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase(); return <span className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-accent text-[10px] font-semibold text-white">{user.avatar_url ? <img src={user.avatar_url} alt="" className="h-full w-full object-cover" /> : initials}</span>; }
