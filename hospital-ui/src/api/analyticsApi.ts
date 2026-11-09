import { apiClient } from "./client";

export interface ExecutiveCommandCenterData {
  window: {
    start_date: string;
    end_date: string;
    is_single_day: boolean;
  };
  bed_census: {
    total_beds: number;
    status_breakdown: Record<string, number>;
    overall_occupancy_rate_pct: number;
    daily_occupied_bed_rate_accrual_paise: number;
    daily_potential_rack_capacity_paise: number;
    bed_turnover_events_count: number;
    by_ward_type: Record<
      string,
      {
        total_beds: number;
        occupied_beds: number;
        available_beds: number;
        occupancy_rate_pct: number;
      }
    >;
  };
  encounters_and_ipd_alos: {
    total_encounters: number;
    active_encounters_by_type: Record<string, number>;
    total_ipd_admissions: number;
    discharged_ipd_admissions: number;
    average_length_of_stay_hours: number;
    average_length_of_stay_days: number;
    readmission_rate_pct: number;
    inpatient_mortality_rate_pct: number;
  };
  opd_funnel: {
    total_appointments: number;
    status_breakdown: Record<string, number>;
    completion_rate_pct: number;
    no_show_rate_pct: number;
  };
  unit_economics: {
    total_net_billed_paise: number;
    arpob_paise: number;
    arpu_per_encounter_paise: number;
  };
}

export const analyticsApi = {
  getExecutiveCommandCenter: async (
    startDate?: string,
    endDate?: string
  ): Promise<ExecutiveCommandCenterData> => {
    return apiClient<ExecutiveCommandCenterData>("/api/analytics/executive-command-center", {
      params: {
        start_date: startDate,
        end_date: endDate,
      },
    });
  },

  getFinancialRevenueCycle: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/analytics/financial-revenue-cycle", {
      params: {
        start_date: startDate,
        end_date: endDate,
      },
    });
  },

  getCareTimings: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/analytics/care-timings", {
      params: {
        start_date: startDate,
        end_date: endDate,
      },
    });
  },

  getClinicalQualityAndSafety: async (startDate?: string, endDate?: string) => {
    return apiClient("/api/analytics/clinical-quality-and-safety", {
      params: {
        start_date: startDate,
        end_date: endDate,
      },
    });
  },
};

