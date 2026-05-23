import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import AuthPage from "@/pages/AuthPage";
import Lobby from "@/pages/Lobby";
import TablePage from "@/pages/TablePage";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === undefined) {
    return (
      <div className="min-h-screen bg-[#0A0A0C] text-zinc-500 flex items-center justify-center text-sm uppercase tracking-[0.4em]">
        Loading…
      </div>
    );
  }
  if (user === null) return <Navigate to="/auth" replace />;
  return children;
}

function PublicOnly({ children }) {
  const { user } = useAuth();
  if (user === undefined) return null;
  if (user) return <Navigate to="/lobby" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/lobby" replace />} />
          <Route path="/auth" element={<PublicOnly><AuthPage /></PublicOnly>} />
          <Route path="/lobby" element={<Protected><Lobby /></Protected>} />
          <Route path="/table/:tableId" element={<Protected><TablePage /></Protected>} />
          <Route path="*" element={<Navigate to="/lobby" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
