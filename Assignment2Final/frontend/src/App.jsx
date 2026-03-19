import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute, RoleRoute } from './components/ProtectedRoute';
import Layout from './components/Layout';

import Login         from './pages/Login';
import Register      from './pages/Register';
import Dashboard     from './pages/Dashboard';
import Listings      from './pages/Listings';
import ListingDetail from './pages/ListingDetail';
import ListingNew    from './pages/ListingNew';
import Portfolio     from './pages/Portfolio';
import AdminMembers  from './pages/admin/Members';
import AdminReports  from './pages/admin/Reports';
import AdminAudit    from './pages/admin/Audit';
import AdminBenchmark from './pages/admin/Benchmark';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: { fontSize: '14px' },
            success: { iconTheme: { primary: '#2563eb', secondary: '#fff' } },
          }}
        />
        <Routes>
          {/* Public routes */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected routes wrapped in Layout */}
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"      element={<Dashboard />} />
            <Route path="listings"       element={<Listings />} />
            <Route path="listings/new"   element={<RoleRoute role="member"><ListingNew /></RoleRoute>} />
            <Route path="listings/:id"   element={<ListingDetail />} />
            <Route path="portfolio/:id"  element={<Portfolio />} />

            {/* Admin routes */}
            <Route path="admin/members"   element={<RoleRoute role="admin"><AdminMembers /></RoleRoute>} />
            <Route path="admin/reports"   element={<RoleRoute role="admin"><AdminReports /></RoleRoute>} />
            <Route path="admin/audit"     element={<RoleRoute role="admin"><AdminAudit /></RoleRoute>} />
            <Route path="admin/benchmark" element={<RoleRoute role="admin"><AdminBenchmark /></RoleRoute>} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
