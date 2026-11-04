import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ModeProvider } from './ModeProvider';
import { DashboardLayout } from './DashboardLayout';
import { ProtectedRoute } from './ProtectedRoute';
import { WorkspacePlaceholder } from './WorkspacePlaceholder';
import { LoginPage } from '../features/auth/LoginPage';
import { OverviewPage } from '../features/overview/OverviewPage';
import { MetadataSettingsPage } from '../features/metadata/MetadataSettingsPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route
          path="codebase"
          element={
            <WorkspacePlaceholder
              title="پایگاه کد"
              description="نمایش آزمایشی آماده‌سازی و پردازش پایگاه کد."
            />
          }
        />
        <Route
          path="documents"
          element={
            <WorkspacePlaceholder
              title="ورود اسناد"
              description="نمایش آزمایشی آماده‌سازی و ورود اسناد."
            />
          }
        />
        <Route
          path="qa"
          element={
            <WorkspacePlaceholder
              title="پرسش‌وپاسخ"
              description="نمایش آزمایشی پرسش و پاسخ از محتوای نمونه."
            />
          }
        />
        <Route
          path="settings/metadata"
          element={<MetadataSettingsPage />}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <ModeProvider>
        <AppRoutes />
      </ModeProvider>
    </BrowserRouter>
  );
}
