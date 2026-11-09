import { apiClient } from "./client";

export const registersApi = {
  getMidnightCensus: async (dateStr?: string) => {
    return apiClient("/api/registers/midnight-census", {
      params: { census_date: dateStr },
    });
  },

  getCashierReconciliation: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/registers/cashier-shift-reconciliation", {
      params: { start_date: startDate, end_date: endDate },
    });
  },

  getNdpsLedger: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/registers/ndps-ledger", {
      params: { start_date: startDate, end_date: endDate },
    });
  },

  getArAging: async (asOfDate?: string) => {
    return apiClient("/api/registers/ar-aging", {
      params: { as_of_date: asOfDate },
    });
  },

  getBiomedicalWaste: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/registers/biomedical-waste", {
      params: { start_date: startDate, end_date: endDate },
    });
  },

  getDataInventory: async () => {
    return apiClient<{
      tenant_id: number;
      total_hospital_records: number;
      timestamp_utc: string;
      tables: Record<string, number>;
    }>("/api/analytics/data-inventory");
  },
};

