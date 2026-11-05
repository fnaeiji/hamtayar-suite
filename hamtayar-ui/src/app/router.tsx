import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ModeProvider } from './ModeProvider';
import { DashboardLayout } from './DashboardLayout';
import { ProtectedRoute } from './ProtectedRoute';
import { DocumentIngestionPage } from '../features/documents/DocumentIngestionPage';
import { QAPage } from '../features/qa/QAPage';
import { CodebasePage } from '../features/codebase/CodebasePage';
import { PhraseSearchPage } from '../features/search/PhraseSearchPage';
import { LoginPage } from '../features/auth/LoginPage';
import { OverviewPage } from '../features/overview/OverviewPage';

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
        <Route path="codebase" element={<Navigate to="/codebase/dashboard" replace />} />
        <Route path="codebase/:view" element={<CodebasePage />} />
        <Route path="search" element={<PhraseSearchPage />} />
        <Route path="documents" element={<DocumentIngestionPage />} />
        <Route path="qa" element={<QAPage />} />
        <Route path="settings/metadata" element={<Navigate to="/" replace />} />
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
