import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { PlanService } from './plan.service';
import type {
  CompletedWorkout,
  LogCompletedWorkoutRequest,
  WorkoutDefinition,
  PlannerSettings,
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
  protected readonly plannerSettings = signal<PlannerSettings | null>(null);
  protected readonly settingsOpen = signal(false);
  protected readonly settingsMessage = signal('');
  protected readonly settingsError = signal('');
  protected readonly settingsLoading = signal(false);
  protected readonly isSavingSettings = signal(false);
  protected readonly editingWorkout = signal<CompletedWorkout | null>(null);
  protected readonly editingMuscles = signal<string[]>([]);
  protected readonly editingCustomName = signal('');
  protected readonly historySaveError = signal('');
  protected selectedMuscles: string[] = [];
  protected customWorkoutName = '';
  private readonly planService = inject(PlanService);
  private rescheduleTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly rescheduleIntervalMs = 60 * 60 * 1000;

  protected workoutType = '';
  protected rotationType = '';
  protected variant = '';
  protected startedAt = this.toLocalDateTime(
    new Date(Date.now() - 30 * 60 * 1000),
  );
  protected completedAt = this.toLocalDateTime(new Date());
  protected hasCustomEndTime = false;
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
    this.loadSettings();
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
    const configuredName = this.plannerSettings()?.workouts.find((item) => item.id === value)?.name;
    if (configuredName) return configuredName;
    return value
      .split('_')
      .map((word) =>
        word === 'hiit' ? 'HIIT' : word.charAt(0).toUpperCase() + word.slice(1),
      )
      .join(' ');
  }

  // Return variants for the selected workout type.
  protected get availableVariants(): string[] {
    return [...new Set(this.plannerSettings()?.workouts.find((item) => item.id === this.workoutType)?.variants ?? [])];
  }

  protected get workoutTypes(): string[] {
    return this.plannerSettings()?.workouts.filter((item) => item.enabled).map((item) => item.id) ?? [];
  }

  protected get rotationTypes(): string[] {
    return this.plannerSettings()?.rotation ?? [];
  }

  protected get muscleGroups(): string[] {
    return this.plannerSettings()?.muscle_groups ?? [];
  }

  protected get selectedWorkoutDefinition() {
    return this.plannerSettings()?.workouts.find((item) => item.id === this.workoutType);
  }

  // Update the related form choices when the workout type changes.
  protected onWorkoutTypeChange(workoutType: string): void {
    this.workoutType = workoutType;
    this.variant = '';
    this.rotationType = this.rotationTypes.includes(workoutType) ? workoutType : '';
    this.customWorkoutName = '';
    this.selectedMuscles = [...(this.plannerSettings()?.workouts.find((item) => item.id === workoutType)?.muscles ?? [])];
    if (workoutType === 'custom') this.rotationType = '';
  }

  // Load shared workout and timing settings from the backend.
  private loadSettings(): void {
    this.settingsLoading.set(true);
    this.settingsError.set('');
    this.planService.getSettings().subscribe({
      next: (settings) => {
        this.plannerSettings.set(settings);
        this.settingsLoading.set(false);
      },
      error: () => {
        this.settingsLoading.set(false);
        this.settingsError.set('Could not load workout settings. Check the API and try again.');
      },
    });
  }

  protected retrySettingsLoad(): void {
    this.loadSettings();
  }

  // Add a user-defined workout to the shared catalogue.
  protected addWorkoutDefinition(): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const id = `custom_${Date.now()}`;
    this.plannerSettings.set({
      ...settings,
      workouts: [...settings.workouts, { id, name: 'New workout', category: 'other', variants: [], variant_muscles: {}, variant_uses_rings: {}, muscles: [], uses_rings: false, is_hiit: false, enabled: true }],
      rotation: [...settings.rotation, id],
    });
  }

  protected updateVariants(workoutId: string, value: string): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const variants = value.split(',').map((item) => item.trim()).filter(Boolean);
    this.plannerSettings.set({
      ...settings,
      workouts: settings.workouts.map((item) => item.id === workoutId ? {
        ...item,
        variants,
        variant_muscles: Object.fromEntries(Object.entries(item.variant_muscles).filter(([id]) => variants.includes(id))),
        variant_uses_rings: Object.fromEntries(Object.entries(item.variant_uses_rings).filter(([id]) => variants.includes(id))),
      } : item),
    });
  }

  protected toggleVariantMuscle(workoutId: string, variant: string, muscle: string, checked: boolean): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const workouts = settings.workouts.map((item) => {
      if (item.id !== workoutId) return item;
      const selected = item.variant_muscles[variant] ?? item.muscles;
      return {
        ...item,
        variant_muscles: {
          ...item.variant_muscles,
          [variant]: checked ? [...new Set([...selected, muscle])] : selected.filter((value) => value !== muscle),
        },
      };
    });
    this.plannerSettings.set({ ...settings, workouts });
  }

  protected uniqueVariants(definition: WorkoutDefinition): string[] {
    return [...new Set(definition.variants)];
  }

  protected toggleVariantRings(workoutId: string, variant: string, checked: boolean): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const workouts = settings.workouts.map((item) => item.id !== workoutId ? item : {
      ...item,
      variant_uses_rings: { ...item.variant_uses_rings, [variant]: checked },
    });
    this.plannerSettings.set({ ...settings, workouts });
  }

  protected hideSettingsKeyboard(): void {
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement) activeElement.blur();
  }

  protected onVariantChange(variant: string): void {
    this.variant = variant;
    const definition = this.selectedWorkoutDefinition;
    this.selectedMuscles = [...(definition?.variant_muscles[variant] ?? definition?.muscles ?? [])];
  }

  protected removeWorkoutDefinition(workoutId: string): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    this.plannerSettings.set({
      ...settings,
      workouts: settings.workouts.filter((item) => item.id !== workoutId),
      rotation: settings.rotation.filter((item) => item !== workoutId),
    });
  }

  protected moveRotationItem(index: number, offset: number): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const target = index + offset;
    if (target < 0 || target >= settings.rotation.length) return;
    const rotation = [...settings.rotation];
    [rotation[index], rotation[target]] = [rotation[target], rotation[index]];
    this.plannerSettings.set({ ...settings, rotation });
  }

  // Keep a workout's selected muscle groups in its editable definition.
  protected toggleDefinitionMuscle(workoutId: string, muscle: string, checked: boolean): void {
    const settings = this.plannerSettings();
    if (!settings) return;
    const workouts = settings.workouts.map((item) => item.id !== workoutId ? item : {
      ...item,
      muscles: checked ? [...new Set([...item.muscles, muscle])] : item.muscles.filter((value) => value !== muscle),
    });
    this.plannerSettings.set({ ...settings, workouts });
  }

  protected toggleSelectedMuscle(muscle: string, checked: boolean): void {
    this.selectedMuscles = checked
      ? [...new Set([...this.selectedMuscles, muscle])]
      : this.selectedMuscles.filter((item) => item !== muscle);
  }

  protected musclesLabel(muscles: string[]): string {
    return muscles.map((muscle) => this.formatLabel(muscle)).join(', ');
  }

  protected toggleSettings(): void {
    this.settingsOpen.set(!this.settingsOpen());
  }

  protected updateCustomName(value: string): void {
    this.editingCustomName.set(value);
  }

  // Save workout definitions and schedule preferences for both apps.
  protected saveSettings(): void {
    const settings = this.plannerSettings();
    if (!settings || this.isSavingSettings()) return;
    this.isSavingSettings.set(true);
    this.settingsError.set('');
    this.settingsMessage.set('');
    this.planService.saveSettings(settings).subscribe({
      next: (saved) => {
        this.plannerSettings.set(saved);
        this.isSavingSettings.set(false);
        this.settingsMessage.set('Settings saved for this planner.');
        this.refreshPlan();
      },
      error: () => {
        this.isSavingSettings.set(false);
        this.settingsError.set('Could not save settings. Check the API.');
      },
    });
  }

  // Open the history editor with the saved muscle snapshot.
  protected editWorkout(workout: CompletedWorkout): void {
    this.editingWorkout.set(workout);
    this.editingMuscles.set([...workout.muscles_trained]);
    this.editingCustomName.set(workout.custom_name ?? '');
    this.historySaveError.set('');
  }

  // Toggle one muscle in the session being corrected.
  protected toggleEditingMuscle(muscle: string, checked: boolean): void {
    const current = this.editingMuscles();
    this.editingMuscles.set(checked ? [...new Set([...current, muscle])] : current.filter((item) => item !== muscle));
  }

  // Save corrected muscles so extra sessions contribute to recovery planning.
  protected saveWorkoutCorrection(): void {
    const workout = this.editingWorkout();
    if (!workout?.id) return;
    this.historySaveError.set('');
    this.planService.correctCompletedWorkout(workout.id, {
      workout_type: workout.workout_type,
      variant: workout.variant ?? null,
      rotation_type: workout.rotation_type ?? null,
      muscles_trained: this.editingMuscles(),
      custom_name: this.editingCustomName().trim() || null,
    }).subscribe({
      next: () => {
        this.editingWorkout.set(null);
        this.loadCompletedWorkouts();
      },
      error: () => this.historySaveError.set('Could not save this workout correction.'),
    });
  }

  // Keep the end time 30 minutes after the selected start by default.
  protected onStartedAtChange(startedAt: string): void {
    this.startedAt = startedAt;
    if (!this.hasCustomEndTime) {
      this.completedAt = this.addMinutesToLocalDateTime(startedAt, 30);
    }
  }

  // Restore the default duration when custom end-time selection is turned off.
  protected onCustomEndTimeChange(isCustom: boolean): void {
    this.hasCustomEndTime = isCustom;
    if (!isCustom) {
      this.completedAt = this.addMinutesToLocalDateTime(this.startedAt, 30);
    }
  }

  // Add minutes while keeping the value suitable for a local date-time input.
  private addMinutesToLocalDateTime(value: string, minutes: number): string {
    const date = new Date(value);
    date.setMinutes(date.getMinutes() + minutes);
    return this.toLocalDateTime(date);
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
    if (!this.workoutType || !this.startedAt || !this.completedAt) {
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
      started_at: this.startedAt,
      variant: this.variant || null,
      rotation_type: this.rotationType || null,
      first_candidate_start: this.firstCandidateStart,
      calendar_events: [],
      push_uses_rings: false,
      muscles_trained: this.selectedMuscles,
      custom_name: this.workoutType === 'custom'
        ? this.customWorkoutName.trim() || null
        : this.selectedWorkoutDefinition?.name ?? null,
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
