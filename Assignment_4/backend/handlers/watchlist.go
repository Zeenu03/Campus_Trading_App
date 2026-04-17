package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/watchlist — member, own watchlist
func GetWatchlist(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var items []models.Watchlist
	for _, shardDB := range appdb.AllShardConnections() {
		rows, err := shardDB.QueryContext(ctx,
			`SELECT WatchlistID, MemberID, ListingID, AddedDate,
             NotifyOnPriceChange, NotifyOnStatusChange
          FROM Watchlist WHERE MemberID = ? ORDER BY AddedDate DESC`, memberID)
		if err != nil {
			respondError(w, http.StatusInternalServerError, "query failed")
			return
		}
		for rows.Next() {
			var item models.Watchlist
			_ = rows.Scan(&item.WatchlistID, &item.MemberID, &item.ListingID,
				&item.AddedDate, &item.NotifyOnPriceChange, &item.NotifyOnStatusChange)
			if listingTitle := loadListingTitleFromShard(ctx, item.ListingID); listingTitle != "" {
				item.ListingTitle = listingTitle
			}
			items = append(items, item)
		}
		rows.Close()
	}
	if items == nil {
		items = []models.Watchlist{}
	}
	respondJSON(w, http.StatusOK, items)
}

// POST /api/v1/watchlist — member
func AddToWatchlist(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var body struct {
		ListingID            int  `json:"listing_id"`
		NotifyOnPriceChange  bool `json:"notify_on_price_change"`
		NotifyOnStatusChange bool `json:"notify_on_status_change"`
	}
	body.NotifyOnPriceChange = true
	body.NotifyOnStatusChange = true

	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.ListingID == 0 {
		respondError(w, http.StatusBadRequest, "listing_id required")
		return
	}

	// Cannot watch own listing
	var sellerID int
	err := listingShardDB(body.ListingID).QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, body.ListingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if sellerID == memberID {
		respondError(w, http.StatusForbidden, "cannot watch your own listing")
		return
	}

	watchlistID, err := nextRecordID(ctx, "Watchlist", "WatchlistID")
	if err != nil {
		respondError(w, http.StatusInternalServerError, "watchlist id allocation failed")
		return
	}
	tx, err := watchlistShardDB(watchlistID).BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, err = tx.ExecContext(ctx,
		`INSERT INTO Watchlist (WatchlistID, MemberID, ListingID, NotifyOnPriceChange, NotifyOnStatusChange)
         VALUES (?, ?, ?, ?, ?)`,
		watchlistID, memberID, body.ListingID, body.NotifyOnPriceChange, body.NotifyOnStatusChange)
	if err != nil {
		if sqlContains(err.Error(), "Duplicate") {
			respondError(w, http.StatusConflict, "listing already in watchlist")
		} else {
			respondError(w, http.StatusInternalServerError, "add failed")
		}
		return
	}
	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"watchlist_id": watchlistID, "message": "added to watchlist"})
}

// DELETE /api/v1/watchlist/listing/:listingId — member, remove current user's watch by listing ID
// Blocked while the member has an active (Submitted) offer on this listing.
func RemoveFromWatchlistByListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "listingId")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	// Block removal if there is an active offer
	var activeOfferCount int
	_ = listingShardDB(listingID).QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Offer WHERE ListingID = ? AND BuyerID = ? AND OfferStatus = 'Submitted'`,
		listingID, memberID).Scan(&activeOfferCount)
	if activeOfferCount > 0 {
		respondError(w, http.StatusConflict, "cannot remove: active offer in progress")
		return
	}

	var watchlistID int
	_, err = rowFromAllShards(ctx, []any{&watchlistID},
		`SELECT WatchlistID FROM Watchlist WHERE ListingID = ? AND MemberID = ?`,
		listingID, memberID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "not watching this listing")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}

	tx, err := watchlistShardDB(watchlistID).BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))
	_, _ = tx.ExecContext(ctx, `DELETE FROM Watchlist WHERE WatchlistID = ?`, watchlistID)
	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "removed from watchlist"})
}

// DELETE /api/v1/watchlist/:id — own
func RemoveFromWatchlist(w http.ResponseWriter, r *http.Request) {
	watchlistID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid watchlist id")
		return
	}
	ctx := r.Context()

	var memberID int
	var ownerUserID int
	err = watchlistShardDB(watchlistID).QueryRowContext(ctx,
		`SELECT MemberID FROM Watchlist WHERE WatchlistID = ?`, watchlistID).Scan(&memberID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "watchlist entry not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	err = centralShardDB().QueryRowContext(ctx,
		`SELECT user_id FROM Member WHERE MemberID = ?`, memberID).Scan(&ownerUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "member not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, ownerUserID) {
		mw.RespondForbidden(w)
		return
	}

	tx, err := watchlistShardDB(watchlistID).BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx, `DELETE FROM Watchlist WHERE WatchlistID = ?`, watchlistID)
	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "removed from watchlist"})
}
