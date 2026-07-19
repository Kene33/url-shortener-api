import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppProviders } from "@/app/providers";
import { AppShell } from "@/components/app/app-shell";
import { useSession } from "@/features/session/session-provider";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AdminDashboardPage } from "@/pages/AdminDashboardPage";
import { AdminLinksPage } from "@/pages/AdminLinksPage";
import { AdminSettingsPage } from "@/pages/AdminSettingsPage";
import { AdminUsersPage } from "@/pages/AdminUsersPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { FoldersPage } from "@/pages/FoldersPage";
import { HomePage } from "@/pages/HomePage";
import { LinksPage } from "@/pages/LinksPage";
import { LoginPage } from "@/pages/LoginPage";
import { AdminAccessDeniedPage } from "@/pages/AdminAccessDeniedPage";
import { NotificationsPage } from "@/pages/NotificationsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";

function ProtectedRoute() {
  const { user, isBootstrapping } = useSession();
  if (isBootstrapping) {
    return <div className="page-shell flex min-h-screen items-center justify-center text-subtle">Loading session…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function AdminRoute() {
  const { user } = useSession();
  if (!user?.is_admin) {
    return <AdminAccessDeniedPage />;
  }
  return <Outlet />;
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
        <Route element={<ProtectedRoute />}>
          <Route path="/links" element={<LinksPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/folders" element={<FoldersPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route element={<AdminRoute />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/links" element={<AdminLinksPage />} />
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
