import React from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import UploadPage from "./pages/Upload";
import DocumentList from "./pages/DocumentList";
import CreateDocument from "./pages/CreateDocument";
import Templates from "./pages/Templates";
import Review from "./pages/Review";

function Shell({ children }) {
  const location = useLocation();
  const isReview = location.pathname.startsWith("/review/");
  if (isReview) return <div className="h-screen flex flex-col">{children}</div>;
  return (
    <div className="min-h-screen flex">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/documents" element={<DocumentList />} />
          <Route path="/create" element={<CreateDocument />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/review/:id" element={<Review />} />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
