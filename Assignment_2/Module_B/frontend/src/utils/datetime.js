/** Format instants in UTC (matches server / MySQL session timezone). */

const utcDate = { timeZone: 'UTC', year: 'numeric', month: '2-digit', day: '2-digit' };

const utcDateTime = {
  timeZone: 'UTC',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  fractionalSecondDigits: 3,
};

export function formatUtcDate(value) {
  return new Date(value).toLocaleDateString('en-GB', utcDate);
}

export function formatUtcDateTime(value) {
  return new Date(value).toLocaleString('en-GB', utcDateTime);
}

export function formatUtcTimeShort(value) {
  return new Date(value).toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatUtcMonthDayTime(value) {
  return new Date(value).toLocaleString('en-GB', {
    timeZone: 'UTC',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
