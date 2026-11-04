/**
 * Currency formatting utilities operating strictly on integer cents.
 * Avoids all floating-point arithmetic errors for financial accuracy.
 */

export function formatCents(cents: number, currency = 'USD'): string {
  const isNegative = cents < 0;
  const absCents = Math.abs(Math.round(cents));
  const dollars = Math.floor(absCents / 100);
  const remainderCents = absCents % 100;
  const formattedDollars = new Intl.NumberFormat('en-US').format(dollars);
  const formattedCents = remainderCents.toString().padStart(2, '0');
  const sign = isNegative ? '-' : '';
  const symbol = currency === 'USD' ? '$' : `${currency} `;
  return `${sign}${symbol}${formattedDollars}.${formattedCents}`;
}

export function formatCentsCompact(cents: number, currency = 'USD'): string {
  const isNegative = cents < 0;
  const absCents = Math.abs(Math.round(cents));
  const dollars = Math.round(absCents / 100);
  const formattedDollars = new Intl.NumberFormat('en-US').format(dollars);
  const sign = isNegative ? '-' : '';
  const symbol = currency === 'USD' ? '$' : `${currency} `;
  return `${sign}${symbol}${formattedDollars}`;
}
