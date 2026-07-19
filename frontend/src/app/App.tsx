import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppShell } from "@/components/app/app-shell";
import type { StaffRole } from "@/api/types";
import { useSession } from "@/features/session/session-provider";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AdminAccessDeniedPage } from "@/pages/AdminAccessDeniedPage";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { AdminLinksPage } from "@/pages/AdminLinksPage";
import { AdminSettingsPage } from "@/pages/AdminSettingsPage";
import { AdminUsersPage } from "@/pages/AdminUsersPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { FoldersPage } from "@/pages/FoldersPage";
import { HomePage } from "@/pages/HomePage";
import { LinksPage } from "@/pages/LinksPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";

const adminRouteRoles = {
  dashboard: ["moderator", "admin"] as StaffRole[],
  users: ["support", "admin"] as StaffRole[],
  links: ["moderator", "admin"] as StaffRole[],
  settings: ["admin"] as StaffRole[],
};

function isAllowedRole(role: string | undefined, allowed: readonly StaffRole[]) {
  return Boolean(role && allowed.includes(role as StaffRole));
}

function getDefaultStaffPath(role: string | undefined) {
  if (isAllowedRole(role, adminRouteRoles.dashboard)) return "/admin";
  if (isAllowedRole(role, adminRouteRoles.users)) return "/admin/users";
  return "/admin/access-denied";
}

function ProtectedRoute() {
  const { user, isBootstrapping } = useSession();
  if (isBootstrapping) {
    return <div className="page-shell flex min-h-screen items-center justify-center text-subtle">Loading session...</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function StaffRoute({ allowed }: { allowed: readonly StaffRole[] }) {
  const { user } = useSession();
  if (!isAllowedRole(user?.role, allowed)) {
    return <AdminAccessDeniedPage />;
  }
  return <Outlet />;
}

function AdminIndexRoute() {
  const { user } = useSession();
  return <Navigate to={getDefaultStaffPath(user?.role)} replace />;
}

function AppRoutes() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/admin/access-denied" element={<AdminAccessDeniedPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/links" element={<LinksPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/folders" element={<FoldersPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/admin" element={<AdminIndexRoute />} />
          <Route element={<StaffRoute allowed={adminRouteRoles.dashboard} />}>
            <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
          </Route>
          <Route element={<StaffRoute allowed={adminRouteRoles.users} />}>
            <Route path="/admin/users" element={<AdminUsersPage />} />
          </Route>
          <Route element={<StaffRoute allowed={adminRouteRoles.links} />}>
            <Route path="/admin/links" element={<AdminLinksPage />} />
          </Route>
          <Route element={<StaffRoute allowed={adminRouteRoles.settings} />}>
            <Route path="/admin/settings" element={<AdminSettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppShell>
  );
}

export function App() {
  return (
    <AppProviders>
      <AppRoutes />
    </AppProviders>
  );
}
