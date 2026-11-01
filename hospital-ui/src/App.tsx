import React from "react";
import { AuthProvider, useAuth } from "./core/context/AuthContext";
import { ActivePatientProvider } from "./core/context/ActivePatientContext";
import { AppShell } from "./components/layout/AppShell";
import { LoginView } from "./components/auth/LoginView";

const RootApp: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="h-screen w-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400">
        <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-xs font-mono">Initializing Avinya Clinical Node...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginView />;
  }

  return (
    <ActivePatientProvider>
      <AppShell />
    </ActivePatientProvider>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <RootApp />
    </AuthProvider>
  );
};

export default App;

