import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Tenants from "./pages/Tenants";
import Entities from "./pages/Entities";
import EntityDetail from "./pages/EntityDetail";
import Activity from "./pages/Activity";
import Portal from "./pages/Portal";
import Advisor from "./pages/Advisor";
import Invest from "./pages/Invest";
import SubmitKpis from "./pages/SubmitKpis";
import GettingStarted from "./pages/GettingStarted";
import type { ReactElement } from "react";

function Protected({ children }: { children: ReactElement }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="container">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/invest/:token" element={<Invest />} />
      <Route path="/submit-kpis/:token" element={<SubmitKpis />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Tenants />} />
        <Route path="/tenants/:tenantId/entities" element={<Entities />} />
        <Route path="/entities/:entityId" element={<EntityDetail />} />
        <Route path="/activity" element={<Activity />} />
        <Route path="/portal" element={<Portal />} />
        <Route path="/advisor" element={<Advisor />} />
        <Route path="/guide" element={<GettingStarted />} />
        <Route path="/guide/:audience" element={<GettingStarted />} />
        <Route path="/guide/:audience/:topicId" element={<GettingStarted />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
