import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { PlanService } from './plan.service';
import type {
  CompletedWorkout,
  LogCompletedWorkoutRequest,
  PlannedWorkout,
} from './plan.service';

// Main component for the planner screen.
@Component({
  imports: [DatePipe, FormsModule, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit, OnDestroy {
  protected readonly workouts = signal<PlannedWorkout[]>([]);
  protected readonly completedWorkouts = signal<CompletedWorkout[]>([]);
  protected readonly historyError = signal('');
  protected readonly errorMessage = signal('');
  protected readonly darkMode = signal(false);
  protected readonly isRebuilding = signal(false);
  private readonly planService = inject(PlanService);
  private rescheduleTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly rescheduleIntervalMs = 60 * 60 * 1000;

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

  // Load the plan and history when the app starts.
  ngOnInit(): void {
    this.loadThemePreference();

    this.planService.getPlan().subscribe({
      next: (workouts) => {
        this.workouts.set(workouts);
        this.scheduleRescheduleCheck(workouts);
      },
      error: () =>
        this.errorMessage.set(
          'Could not load the plan. Check that the API is running.',
        ),
    });

    this.loadCompletedWorkouts();
  }

  // Restore the saved theme choice when the app opens.
  private loadThemePreference(): void {
    const useDarkMode =
      typeof localStorage !== 'undefined' &&
      localStorage.getItem('adaptive-workout-theme') === 'dark';
    this.darkMode.set(useDarkMode);

    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark-mode', useDarkMode);
    }
  }

  // Switch themes and remember the choice on this device.
  protected toggleDarkMode(): void {
    const useDarkMode = !this.darkMode();
    this.darkMode.set(useDarkMode);
    localStorage.setItem(
      'adaptive-workout-theme',
      useDarkMode ? 'dark' : 'light',
    );
    document.documentElement.classList.toggle('dark-mode', useDarkMode);
  }

  // Rebuild the plan now so new calendar Busy events take effect.
  protected refreshPlan(): void {
    if (this.isRebuilding()) {
      return;
    }

    if (this.rescheduleTimer !== undefined) {
      clearTimeout(this.rescheduleTimer);
      this.rescheduleTimer = undefined;
    }

    this.isRebuilding.set(true);
    this.errorMessage.set('');
    this.planService.rebuildPlan(this.tomorrowAtSeven()).subscribe({
      next: (plan) => {
        this.workouts.set(plan);
        this.isRebuilding.set(false);
        this.scheduleRescheduleCheck(plan);
      },
      error: () => {
        this.isRebuilding.set(false);
        this.errorMessage.set('Could not rebuild the plan. Check the API.');
      },
    });
  }

  // Clear the pending timer when Angular removes this screen.
  ngOnDestroy(): void {
    if (this.rescheduleTimer !== undefined) {
      clearTimeout(this.rescheduleTimer);
    }
  }

  // Set a timer for the first pending workout.
  private scheduleRescheduleCheck(workouts: PlannedWorkout[]): void {
    if (this.rescheduleTimer !== undefined) {
      clearTimeout(this.rescheduleTimer);
      this.rescheduleTimer = undefined;
    }

    const nextWorkout = workouts[0];
    if (!nextWorkout) {
      return;
    }

    const scheduledStart = new Date(nextWorkout.starts_at);
    const firstRetryTime = new Date(
      scheduledStart.getTime() + this.rescheduleIntervalMs,
    );
    const delay = firstRetryTime.getTime() - Date.now();

    if (delay <= 0) {
      this.rebuildAfterMissedWorkout(
        this.getNextCandidateStart(firstRetryTime),
      );
      return;
    }

    this.rescheduleTimer = setTimeout(() => {
      this.rebuildAfterMissedWorkout(
        this.getNextCandidateStart(firstRetryTime),
      );
    }, delay);
  }

  // Skip hourly slots that passed while the app was closed or asleep.
  private getNextCandidateStart(firstRetryTime: Date): string {
    const candidate = new Date(firstRetryTime);
    const lateBy = Date.now() - candidate.getTime();

    if (lateBy > 60_000) {
      const missedIntervals = Math.ceil(
        lateBy / this.rescheduleIntervalMs,
      );
      candidate.setTime(
        candidate.getTime() + missedIntervals * this.rescheduleIntervalMs,
      );
    }

    return this.toLocalDateTime(candidate);
  }

  // Rebuild the plan while keeping the pending rotation item due.
  private rebuildAfterMissedWorkout(firstCandidateStart: string): void {
    this.rescheduleTimer = undefined;

    this.planService.rebuildPlan(firstCandidateStart).subscribe({
      next: (plan) => {
        this.workouts.set(plan);
        this.errorMessage.set('');
        this.scheduleRescheduleCheck(plan);
      },
      error: () =>
        this.errorMessage.set(
          'Could not reschedule the workout. Check the API.',
        ),
    });
  }

  // Load completed workouts from the backend.
  private loadCompletedWorkouts(): void {
    this.planService.getCompletedWorkouts().subscribe({
      next: (workouts) => {
        this.completedWorkouts.set(workouts);
        this.historyError.set('');
      },
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

    const previousPlan = this.workouts();
    if (this.rescheduleTimer !== undefined) {
      clearTimeout(this.rescheduleTimer);
      this.rescheduleTimer = undefined;
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
        this.scheduleRescheduleCheck(plan);
        this.isSubmitting = false;
        this.formMessage = 'Workout logged and plan rebuilt.';
        this.loadCompletedWorkouts();
      },
      error: () => {
        this.isSubmitting = false;
        this.formError =
          'Could not log the workout. Check the API and try again.';
        this.scheduleRescheduleCheck(previousPlan);
      },
    });
  }
}
