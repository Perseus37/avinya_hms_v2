import { analyticsApi, ExecutiveCommandCenterData } from "./analyticsApi";
import { uiApi } from "./uiApi";

export interface HospitalAdminDashboardSnapshot {
  executive: ExecutiveCommandCenterData | null;
  careTimings: Record<string, unknown> | null;
  opdQueue: Record<string, unknown> | null;
  dischargePipeline: Array<Record<string, unknown>> | null;
  errors: string[];
  generatedAt: string;
}

export interface DashboardDateRange {
  startDate: string;
  endDate: string;
}

/**
 * Loads the Hospital Admin overview from existing, permission-gated domain APIs.
 * Each section is isolated so a missing optional module does not blank the entire page.
 * Tenant and authentication headers are supplied by the shared apiClient.
 */
export async function getHospitalAdminDashboard(
  range: DashboardDateRange
): Promise<HospitalAdminDashboardSnapshot> {
  const requests = await Promise.allSettled([
    analyticsApi.getExecutiveCommandCenter(range.startDate, range.endDate),
    analyticsApi.getCareTimings(range.startDate, range.endDate),
    uiApi.getOpdQueueSummary(range.endDate),
    uiApi.getDischargePipeline(),
  ] as const);

  const errors: string[] = [];
  const valueAt = <T,>(index: number): T | null => {
    const result = requests[index];
    if (result.status === "fulfilled") return result.value as T;
    errors.push(result.reason instanceof Error ? result.reason.message : "A dashboard section could not be loaded.");
    return null;
  };

  return {
    executive: valueAt<ExecutiveCommandCenterData>(0),
    careTimings: valueAt<Record<string, unknown>>(1),
    opdQueue: valueAt<Record<string, unknown>>(2),
    dischargePipeline: valueAt<Array<Record<string, unknown>>>(3),
    errors,
    generatedAt: new Date().toISOString(),
  };
}
