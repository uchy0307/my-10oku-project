import { format, isAfter } from "date-fns";
import { toZonedTime, formatInTimeZone } from "date-fns-tz";
import { CONFIG } from "./config";

export function jstStartOfToday(): Date {
  const nowUtc = new Date();
  const nowJst = toZonedTime(nowUtc, CONFIG.TIMEZONE);
  const y = nowJst.getFullYear();
  const m = nowJst.getMonth();
  const d = nowJst.getDate();
  const jstMidnightUtcMs = Date.UTC(y, m, d, 0, 0, 0) - 9 * 60 * 60 * 1000;
  return new Date(jstMidnightUtcMs);
}

export function countToday(itemsIso: string[]): number {
  const cutoff = jstStartOfToday();
  return itemsIso.filter((iso) => {
    if (!iso) return false;
    const d = new Date(iso);
    return isAfter(d, cutoff);
  }).length;
}

export function fmtJst(iso: string): string {
  if (!iso) return "—";
  try {
    return formatInTimeZone(new Date(iso), CONFIG.TIMEZONE, "MM/dd HH:mm");
  } catch {
    return iso;
  }
}

export function fmtNow(): string {
  return format(new Date(), "HH:mm:ss");
}
