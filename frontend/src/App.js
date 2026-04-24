import React from "react";
import { BrowserRouter, Routes, Route, useLocation, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Protected from "./components/Protected";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/Upload";
import DocumentList from "./pages/DocumentList";
import CreateDocument from "./pages/CreateDocument";
import Templates from "./pages/Templates";
import Review from "./pages/Review";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AdminUsers from "./pages/AdminUsers";
import AuditLog from "./pages/AuditLog";

function Shell({ children }) {
  const location = useLocation();
  const { user } = useAuth();
  const isAuthRoute = ["/login", "/register"].includes(location.pathname);
  const isReview = location.pathname.startsWith("/review/");

  if (isAuthRoute) return children;
  if (!user) return children; // Protected wrapper will redirect
  if (isReview) return <div className="h-screen flex flex-col">{children}</div>;

  return (
    <div className="min-h-screen flex">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

function AuthRedirectIfLoggedIn({ children }) {
  const { user, ready } = useAuth();
  if (!ready) return <div className="p-10 pf-pulse text-[#71717A]">Loading…</div>;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Shell>
          <Routes>
            <Route path="/login" element={<AuthRedirectIfLoggedIn><Login /></AuthRedirectIfLoggedIn>} />
            <Route path="/register" element={<AuthRedirectIfLoggedIn><Register /></AuthRedirectIfLoggedIn>} />

            <Route path="/" element={<Protected><Dashboard /></Protected>} />
            <Route path="/upload" element={<Protected minRole="user"><UploadPage /></Protected>} />
            <Route path="/documents" element={<Protected><DocumentList /></Protected>} />
            <Route path="/create" element={<Protected minRole="user"><CreateDocument /></Protected>} />
            <Route path="/templates" element={<Protected><Templates /></Protected>} />
            <Route path="/review/:id" element={<Protected><Review /></Protected>} />

            <Route path="/admin/users" element={<Protected minRole="admin"><AdminUsers /></Protected>} />
            <Route path="/admin/audit" element={<Protected minRole="admin"><AuditLog /></Protected>} />
          </Routes>
        </Shell>
      </AuthProvider>
    </BrowserRouter>
  );
}
