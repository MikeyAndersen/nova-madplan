import { describe, it, expect } from 'vitest';
import { parseWeekPlan } from '../src/lib/weekplan';

describe('parseWeekPlan', () => {
  it('parses the usual "Dag: mad" format (incl. ø/parenteser/trailing space)', () => {
    const raw = `Mandag: hel kylling
Tirsdag: Sandwich (bagels)
Onsdag: Salsicca pasta
Torsdag: rugbrød (Sia fest)
Fredag: Lasagne (Mikey T fest)
Lørdag: karry
Søndag: Ramen eller karry`;
    expect(parseWeekPlan(raw)).toEqual([
      { weekday: 1, title: 'hel kylling' },
      { weekday: 2, title: 'Sandwich (bagels)' },
      { weekday: 3, title: 'Salsicca pasta' },
      { weekday: 4, title: 'rugbrød (Sia fest)' },
      { weekday: 5, title: 'Lasagne (Mikey T fest)' },
      { weekday: 6, title: 'karry' },
      { weekday: 7, title: 'Ramen eller karry' },
    ]);
  });

  it('accepts abbreviations and is case-insensitive', () => {
    const raw = `man: A\nTIR: B\nons: C\ntor: D\nfre: E\nlør: F\nsøn: G`;
    expect(parseWeekPlan(raw).map((e) => e.weekday)).toEqual([1, 2, 3, 4, 5, 6, 7]);
  });

  it('ignores blank lines and lines without a recognised day', () => {
    const raw = `Mandag: Tacos\n\nHandleliste:\nFredag: Pizza`;
    expect(parseWeekPlan(raw)).toEqual([
      { weekday: 1, title: 'Tacos' },
      { weekday: 5, title: 'Pizza' },
    ]);
  });

  it('does not mistake a meal name for a day (only real day tokens before colon)', () => {
    const raw = `Mandel: kage`; // "Mandel" is not "Mandag"
    expect(parseWeekPlan(raw)).toEqual([]);
  });

  it('falls back to sequential days when no day prefixes are present', () => {
    const raw = `Tacos\nPizza\nPasta`;
    expect(parseWeekPlan(raw)).toEqual([
      { weekday: 1, title: 'Tacos' },
      { weekday: 2, title: 'Pizza' },
      { weekday: 3, title: 'Pasta' },
    ]);
  });

  it('last line wins if a day appears twice', () => {
    expect(parseWeekPlan(`Mandag: A\nMandag: B`)).toEqual([{ weekday: 1, title: 'B' }]);
  });
});
