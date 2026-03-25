/** Format API/DB timestamps in UTC (not the browser's local zone). */

export function formatDateUTC(value) {
  if (value == null || value === '') return '—';
  return new Date(value).toLocaleDateString('en-GB', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTimeUTC(value) {
  return new Date(value).toLocaleString('en-GB', {
    timeZone: 'UTC',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  });
}

export function formatShortDateTimeUTC(value) {
  return new Date(value).toLocaleString('en-GB', {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTimeUTC(value) {
  return new Date(value).toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
  });
}
