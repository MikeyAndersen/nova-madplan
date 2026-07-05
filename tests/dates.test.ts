import { describe, it, expect } from 'vitest';
import { weekStatus, mondayOf, isoWeek, nextWeekStart } from '../src/lib/dates';

describe('dates', () => {
  it('derives week status from dates (start_date is a Monday)', () => {
    expect(weekStatus('2026-06-15', new Date('2026-06-18'))).toBe('nuvaerende'); // Mon 15 – Sun 21
    expect(weekStatus('2026-06-08', new Date('2026-06-18'))).toBe('historisk'); // ended Sun 14
    expect(weekStatus('2026-06-22', new Date('2026-06-18'))).toBe('kommende');
  });

  it('treats the Sunday boundary as still current', () => {
    expect(weekStatus('2026-06-15', new Date('2026-06-21'))).toBe('nuvaerende'); // Sunday
    expect(weekStatus('2026-06-15', new Date('2026-06-22'))).toBe('historisk'); // next Monday
  });

  it('mondayOf returns the ISO Monday of the week', () => {
    expect(mondayOf(new Date('2026-06-18'))).toBe('2026-06-15'); // Thursday -> Monday
    expect(mondayOf(new Date('2026-06-15'))).toBe('2026-06-15'); // Monday -> itself
    expect(mondayOf(new Date('2026-06-21'))).toBe('2026-06-15'); // Sunday -> Monday
  });

  it('isoWeek gives ISO year/week', () => {
    expect(isoWeek(new Date('2026-06-18'))).toEqual({ year: 2026, week: 25 });
    expect(isoWeek(new Date('2026-01-01'))).toEqual({ year: 2026, week: 1 });
  });

  it('nextWeekStart advances 7 days to the next Monday', () => {
    expect(nextWeekStart('2026-06-15')).toEqual({ year: 2026, week: 26, start_date: '2026-06-22' });
  });
});
