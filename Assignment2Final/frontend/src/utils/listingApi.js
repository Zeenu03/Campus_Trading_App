/** True when object looks like GET /listings/:id JSON (not e.g. `{ message }`). */
export function isListingDetailShape(obj) {
  return (
    obj != null &&
    typeof obj === 'object' &&
    obj.listing_id != null &&
    typeof obj.title === 'string'
  );
}

/**
 * Normalize listing JSON for React state (numbers, arrays, missing joined fields).
 */
export function normalizeListingPayload(l) {
  if (!l || typeof l !== 'object') return null;

  const rawPrice = l.asking_price;
  let askingNum = null;
  if (rawPrice != null && rawPrice !== '') {
    askingNum = typeof rawPrice === 'number' ? rawPrice : parseFloat(String(rawPrice).replace(/,/g, ''));
    if (Number.isNaN(askingNum)) askingNum = null;
  }

  return {
    ...l,
    listing_id: l.listing_id != null ? Number(l.listing_id) : l.listing_id,
    seller_id: l.seller_id != null ? Number(l.seller_id) : l.seller_id,
    category_id: l.category_id != null ? Number(l.category_id) : l.category_id,
    asking_price: askingNum != null ? askingNum : 0,
    seller_name: l.seller_name ?? '',
    category_name: l.category_name ?? '',
    is_negotiable: Boolean(l.is_negotiable),
    is_donation: Boolean(l.is_donation),
    images: Array.isArray(l.images) ? l.images : [],
  };
}
