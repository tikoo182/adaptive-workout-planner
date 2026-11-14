import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { PlanService } from './plan.service';
import type { CompletedWorkout, PlannedWorkout, LogCompletedWorkoutRequest } from './plan.service';

import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

// Main component for the planner screen.
@Component({
  imports: [DatePipe, FormsModule, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})

export class App implements OnInit {
  protected readonly workouts = signal<PlannedWorkout[]>([]);
  protected readonly completedWorkouts = signal<CompletedWorkout[]>([]);
  protected readonly historyError = signal('');
  protected readonly errorMessage = signal('');
  private readonly planService = inject(PlanService);
  protected readonly workoutTypes = [
    'hiit_legs',
    'push',
    'run',
    'legs',
    'hiit_abs',
    'pull',
  ];

  protected readonly variantsByWorkout: Record<string, string[]> = {
    push: [
      'push_dips',
      'push_pike_russian',
      'push_pike_weighted',
      'push_pike_archer',
    ],
    pull: ['pull_chinups_and_pullups', 'pull_dead_hangs_and_abs'],
    legs: ['legs_lunges', 'legs_weighted_situps'],
  };

  protected workoutType = '';
  protected rotationType = '';
  protected variant = '';
  protected completedAt = this.toLocalDateTime(new Date());
  protected readonly firstCandidateStart = this.tomorrowAtSeven();

  protected isSubmitting = false;
  protected formMessage = '';
  protected formError = '';

  // Load the plan when the app starts.
  ngOnInit(): void {
    this.planService.getPlan().subscribe({
      next: (workouts) => this.workouts.set(workouts),
      error: () =>
        this.errorMessage.set(
          'Could not load the plan. Check that the API is running.',
        ),
    });

    this.planService.getCompletedWorkouts().subscribe({
      next: (workouts) => this.completedWorkouts.set(workouts),
      error: () =>
        this.historyError.set('Could not load completed workout history.'),
    });
  }

    // Turns API values like "hiit_legs" into readable labels.
    protected formatLabel(value: string): string {
      return value
        .split('_')
        .map((word) =>
          word === 'hiit' ? 'HIIT' : word.charAt(0).toUpperCase() + word.slice(1),
        )
        .join(' ');
    }

      // Return variants for the selected workout type.
  protected get availableVariants(): string[] {
    return this.variantsByWorkout[this.workoutType] ?? [];
  }

   // Update the related form choices when the workout type changes.
   protected onWorkoutTypeChange(workoutType: string): void {
    this.workoutType = workoutType;
    this.variant = '';
    this.rotationType = workoutType;
  }

  // Format a local date and time for a datetime-local input.
  private toLocalDateTime(date: Date): string {
    const localDate = new Date(
      date.getTime() - date.getTimezoneOffset() * 60_000,
    );
    return localDate.toISOString().slice(0, 16);
  }

  // Set the next plan's default start to tomorrow at 7:00 AM.
  private tomorrowAtSeven(): string {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(7, 0, 0, 0);
    return this.toLocalDateTime(tomorrow);
  }



    // Save the workout, rebuild the plan, and refresh history.
    protected logWorkout(): void {
      if (!this.workoutType || !this.completedAt) {
        return;
      }
  
      const request: LogCompletedWorkoutRequest = {
        workout_type: this.workoutType,
        completed_at: this.completedAt,
        variant: this.variant || null,
        rotation_type: this.rotationType || null,
        first_candidate_start: this.firstCandidateStart,
        calendar_events: [],
        push_uses_rings: false,
      };
  
      this.isSubmitting = true;
      this.formMessage = '';
      this.formError = '';
  
      this.planService.logCompletedWorkout(request).subscribe({
        next: (plan) => {
          this.workouts.set(plan);
          this.isSubmitting = false;
          this.formMessage = 'Workout logged and plan rebuilt.';
  
          this.planService.getCompletedWorkouts().subscribe({
            next: (history) => {
              this.completedWorkouts.set(history);
              this.historyError.set('');
            },
            error: () => {
              this.historyError.set('Could not refresh workout history.');
            },
          });
        },
        error: () => {
          this.isSubmitting = false;
          this.formError = 'Could not log the workout. Check the API and try again.';
        },
      });
    }
}