import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

// Describes one workout returned by the API.
export interface PlannedWorkout {
  workout_type: string;
  rotation_type: string;
  variant: string | null;
  starts_at: string;
  uses_rings: boolean;
  duration_minutes: number;
}

// Describes one completed workout returned by the API.
export interface CompletedWorkout {
  workout_type: string;
  rotation_type: string | null;
  variant: string | null;
  completed_at: string;
  started_at?: string | null;
  id?: number;
  healthkit_id?: string | null;
  source_activity?: string | null;
  muscles_trained: string[];
  custom_name?: string | null;
}

export interface WorkoutDefinition {
  id: string;
  name: string;
  category: 'cardio' | 'strength' | 'other';
  variants: string[];
  variant_muscles: Record<string, string[]>;
  variant_uses_rings: Record<string, boolean>;
  muscles: string[];
  uses_rings: boolean;
  is_hiit: boolean;
  enabled: boolean;
}

export interface PlannerSettings {
  workouts: WorkoutDefinition[];
  rotation: string[];
  timing: {
    earliest_start: string;
    latest_start: string;
    evening_start: string;
    latest_ring_morning_start: string;
    latest_non_ring_morning_start: string;
    latest_hiit_start: string;
    workout_duration_minutes: number;
    calendar_buffer_minutes: number;
    max_consecutive_workout_days: number;
    muscle_recovery_days: number;
    prefer_sunday_runs: boolean;
  };
  muscle_groups: string[];
}

// Data sent when logging a workout and rebuilding the plan.
export interface LogCompletedWorkoutRequest {
  workout_type: string;
  started_at: string;
  completed_at: string;
  variant: string | null;
  rotation_type: string | null;
  first_candidate_start: string;
  calendar_events: { starts_at: string; ends_at: string }[];
  push_uses_rings: boolean;
  muscles_trained?: string[];
  custom_name?: string | null;
}

export interface CorrectCompletedWorkoutRequest {
  workout_type: string;
  variant: string | null;
  rotation_type: string | null;
  muscles_trained: string[];
  custom_name: string | null;
}

// Provides API calls for plans and workout history.
@Injectable({ providedIn: 'root' })
export class PlanService {
  private readonly http = inject(HttpClient);

  // Gets the planned workouts from the backend.
  getPlan(): Observable<PlannedWorkout[]> {
    return this.http.get<PlannedWorkout[]>('/plan');
  }

  // Gets completed workouts from the backend.
  getCompletedWorkouts(): Observable<CompletedWorkout[]> {
    return this.http.get<CompletedWorkout[]>('/completed-workouts');
  }

  // Gets the shared workout catalogue and schedule preferences.
  getSettings(): Observable<PlannerSettings> {
    return this.http.get<PlannerSettings>('/settings');
  }

  // Saves the shared workout catalogue and schedule preferences.
  saveSettings(settings: PlannerSettings): Observable<PlannerSettings> {
    return this.http.put<PlannerSettings>('/settings', settings);
  }

  // Corrects a completed session, including muscles trained.
  correctCompletedWorkout(
    id: number,
    correction: CorrectCompletedWorkoutRequest,
  ): Observable<CompletedWorkout> {
    return this.http.patch<CompletedWorkout>(`/completed-workouts/${id}`, correction);
  }

  // Logs a workout and receives the rebuilt plan.
  logCompletedWorkout(
    request: LogCompletedWorkoutRequest,
  ): Observable<PlannedWorkout[]> {
    return this.http.post<PlannedWorkout[]>('/completed-workouts', request);
  }

  // Rebuilds the pending plan from a new starting time.
  rebuildPlan(firstCandidateStart: string): Observable<PlannedWorkout[]> {
    return this.http.post<PlannedWorkout[]>('/plan/rebuild', {
      first_candidate_start: firstCandidateStart,
      calendar_events: [],
      push_uses_rings: false,
    });
  }
}
