import { api } from '../api/client';

// ── Offers ────────────────────────────────────────────────────

/** Fetch the requesting buyer's own offer on a listing (null if none). */
export const fetchMyOffer = (listingId) =>
  api.get(`/listings/${listingId}/my-offer`).then(d => d ?? null).catch(() => null);

/** Update the buyer's offered price on an existing offer. */
export const updateOfferPrice = (offerId, price) =>
  api.put(`/offers/${offerId}/price`, { offered_price: price });

/** Buyer accepts the seller's current asking price. */
export const buyerAcceptOffer = (offerId) =>
  api.put(`/offers/${offerId}/buyer-accept`, {});

/** Buyer withdraws their submitted offer (reason required). */
export const withdrawOffer = (offerId, reason) =>
  api.put(`/offers/${offerId}/withdraw`, { reason });

/** Seller accepts a buyer's offered price. */
export const acceptOffer = (offerId) =>
  api.put(`/offers/${offerId}/accept`, {});

/** Seller declines a buyer's offer (reason required). */
export const declineOffer = (offerId, reason) =>
  api.put(`/offers/${offerId}/decline`, { reason });

// ── Threads & Messages ────────────────────────────────────────

/** Fetch the requesting buyer's thread for a listing (null if none). */
export const fetchMyThread = (listingId) =>
  api.get(`/listings/${listingId}/my-thread`).then(d => d ?? null).catch(() => null);

/** Fetch all buyer interactions for a listing (seller view). */
export const fetchInteractions = (listingId) =>
  api.get(`/listings/${listingId}/interactions`);

/** Buyer opens a chat-only thread (no offer). */
export const createThread = (listingId) =>
  api.post(`/listings/${listingId}/threads`, {});

/** Fetch paginated messages for a thread. */
export const fetchMessages = (threadId, page = 1, pageSize = 200) =>
  api.get(`/threads/${threadId}/messages`, { page, page_size: pageSize });

/** Send a message to a thread. */
export const sendMessage = (threadId, messageText) =>
  api.post(`/threads/${threadId}/messages`, { message_text: messageText });

// ── Listing helpers ───────────────────────────────────────────

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
    images: Array.isArray(l.images) ? l.images : [],
    watcher_count: typeof l.watcher_count === 'number' ? l.watcher_count : 0,
    my_watchlist_id: l.my_watchlist_id != null ? Number(l.my_watchlist_id) : null,
  };
}
