import React, { createContext, useContext, useEffect, useState } from "react";
import { PatientSummaryCard } from "../../types";
import { uiApi } from "../../api/uiApi";

interface ActivePatientContextType {
  activePatientId: number | null;
  patientSummary: PatientSummaryCard | null;
  isLoading: boolean;
  selectPatient: (patientId: number) => Promise<void>;
  clearPatient: () => void;
}

const ActivePatientContext = createContext<ActivePatientContextType | undefined>(undefined);

export const ActivePatientProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activePatientId, setActivePatientId] = useState<number | null>(null);
  const [patientSummary, setPatientSummary] = useState<PatientSummaryCard | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Sync active patient across browser tabs via BroadcastChannel (CCOW context alignment)
  useEffect(() => {
    let channel: BroadcastChannel | null = null;
    try {
      channel = new BroadcastChannel("avinya_patient_context");
      channel.onmessage = (event) => {
        if (event.data?.type === "PATIENT_SELECTED" && event.data.patientId) {
          loadPatient(event.data.patientId, false);
        } else if (event.data?.type === "PATIENT_CLEARED") {
          setActivePatientId(null);
          setPatientSummary(null);
        }
      };
    } catch {
      // BroadcastChannel not supported in some sandboxes
    }
    return () => {
      channel?.close();
    };
  }, []);

  const loadPatient = async (patientId: number, broadcast = true) => {
    setIsLoading(true);
    setActivePatientId(patientId);
    try {
      const summary = await uiApi.getPatientSummary(patientId);
      setPatientSummary(summary);
      if (broadcast) {
        try {
          const channel = new BroadcastChannel("avinya_patient_context");
          channel.postMessage({ type: "PATIENT_SELECTED", patientId });
          channel.close();
        } catch {
          // ignore
        }
      }
    } catch (err) {
      console.error("Failed to load patient summary card:", err);
      setPatientSummary(null);
    } finally {
      setIsLoading(false);
    }
  };

  const clearPatient = () => {
    setActivePatientId(null);
    setPatientSummary(null);
    try {
      const channel = new BroadcastChannel("avinya_patient_context");
      channel.postMessage({ type: "PATIENT_CLEARED" });
      channel.close();
    } catch {
      // ignore
    }
  };

  return (
    <ActivePatientContext.Provider
      value={{
        activePatientId,
        patientSummary,
        isLoading,
        selectPatient: (id) => loadPatient(id, true),
        clearPatient,
      }}
    >
      {children}
    </ActivePatientContext.Provider>
  );
};

export const useActivePatient = (): ActivePatientContextType => {
  const context = useContext(ActivePatientContext);
  if (!context) {
    throw new Error("useActivePatient must be used within an ActivePatientProvider");
  }
  return context;
};

