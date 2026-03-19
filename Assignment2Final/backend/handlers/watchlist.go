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

	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT w.WatchlistID, w.MemberID, w.ListingID, l.Title, w.AddedDate,
             w.NotifyOnPriceChange, w.NotifyOnStatusChange
          FROM Watchlist w JOIN Listing l ON l.ListingID = w.ListingID
          WHERE w.MemberID = ? ORDER BY w.AddedDate DESC`, memberID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var items []models.Watchlist
	for rows.Next() {
		var item models.Watchlist
		_ = rows.Scan(&item.WatchlistID, &item.MemberID, &item.ListingID, &item.ListingTitle,
			&item.AddedDate, &item.NotifyOnPriceChange, &item.NotifyOnStatusChange)
		items = append(items, item)
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
	err := appdb.DB.QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, body.ListingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if sellerID == memberID {
		respondError(w, http.StatusForbidden, "cannot watch your own listing")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Watchlist (MemberID, ListingID, NotifyOnPriceChange, NotifyOnStatusChange)
         VALUES (?, ?, ?, ?)`,
		memberID, body.ListingID, body.NotifyOnPriceChange, body.NotifyOnStatusChange)
	if err != nil {
		if sqlContains(err.Error(), "Duplicate") {
			respondError(w, http.StatusConflict, "listing already in watchlist")
		} else {
			respondError(w, http.StatusInternalServerError, "add failed")
		}
		return
	}
	wid, _ := res.LastInsertId()
	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"watchlist_id": wid, "message": "added to watchlist"})
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
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT w.MemberID, m.user_id FROM Watchlist w JOIN Member m ON m.MemberID = w.MemberID WHERE w.WatchlistID = ?`,
		watchlistID).Scan(&memberID, &ownerUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "watchlist entry not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, ownerUserID) {
		mw.RespondForbidden(w)
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
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
