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
}

// Describes one completed workout returned by the API.
export interface CompletedWorkout {
    workout_type: string;
    rotation_type: string | null;
    variant: string | null;
    completed_at: string;
  }

// Data sent when logging a workout and rebuilding the plan.
export interface LogCompletedWorkoutRequest {
    workout_type: string;
    completed_at: string;
    variant: string | null;
    rotation_type: string | null;
    first_candidate_start: string;
    calendar_events: { starts_at: string; ends_at: string }[];
    push_uses_rings: boolean;
  }


// Gets the planned workouts from the backend.
@Injectable({ providedIn: 'root' })
export class PlanService {
  private readonly http = inject(HttpClient);

  getPlan(): Observable<PlannedWorkout[]> {
    return this.http.get<PlannedWorkout[]>('/plan');
  }

  // Gets completed workouts from the backend.
  getCompletedWorkouts(): Observable<CompletedWorkout[]> {
    return this.http.get<CompletedWorkout[]>('/completed-workouts');
  }
  
  // Logs a workout and receives the rebuilt plan.
  logCompletedWorkout(
    request: LogCompletedWorkoutRequest,
  ): Observable<PlannedWorkout[]> {
    return this.http.post<PlannedWorkout[]>('/completed-workouts', request);
  }
  
}