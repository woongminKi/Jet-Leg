const RELATIVE_THRESHOLDS: Array<{ unit: Intl.RelativeTimeFormatUnit; ms: number }> = [
  { unit: 'year', ms: 365 * 24 * 60 * 60 * 1000 },
  { unit: 'month', ms: 30 * 24 * 60 * 60 * 1000 },
  { unit: 'day', ms: 24 * 60 * 60 * 1000 },
  { unit: 'hour', ms: 60 * 60 * 1000 },
  { unit: 'minute', ms: 60 * 1000 },
  { unit: 'second', ms: 1000 },
];

const KO_RELATIVE = new Intl.RelativeTimeFormat('ko', { numeric: 'auto' });

export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const target = new Date(iso);
  if (Number.isNaN(target.getTime())) return '';
  const diffMs = target.getTime() - now.getTime();
  const absMs = Math.abs(diffMs);
  if (absMs < 1000) return '방금';
  for (const { unit, ms } of RELATIVE_THRESHOLDS) {
    if (absMs >= ms || unit === 'second') {
      const value = Math.round(diffMs / ms);
      return KO_RELATIVE.format(value, unit);
    }
  }
  return '';
}

const SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return '0 B';
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), SIZE_UNITS.length - 1);
  const value = n / Math.pow(1024, i);
  const formatted = value >= 10 || i === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${formatted} ${SIZE_UNITS[i]}`;
}
