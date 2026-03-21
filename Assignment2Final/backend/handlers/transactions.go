package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/transactions — auth, own transactions
// Status and Reason are derived from Offer via OfferID FK (not stored in Transaction).
func ListTransactions(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 && !mw.HasRole(ctx, "admin") {
		respondError(w, http.StatusForbidden, "member or admin only")
		return
	}

	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)

	var total int
	var countQuery string
	var countArgs []interface{}
	if mw.HasRole(ctx, "admin") {
		countQuery = `SELECT COUNT(*) FROM Transaction`
	} else {
		countQuery = `SELECT COUNT(*) FROM Transaction WHERE SellerID = ? OR BuyerID = ?`
		countArgs = []interface{}{memberID, memberID}
	}
	_ = appdb.DB.QueryRowContext(ctx, countQuery, countArgs...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	// has_rated sub-select: whether the requesting member has already rated this transaction.
	// For admin (memberID == 0) this always returns 0.
	hasRatedExpr := `0`
	if memberID != 0 {
		hasRatedExpr = `(SELECT COUNT(*) FROM Rating r WHERE r.TransactionID = t.TransactionID AND r.RaterID = ?)`
	}

	var query string
	var args []interface{}
	if mw.HasRole(ctx, "admin") {
		query = `SELECT t.TransactionID, t.ListingID, l.Title,
                     t.SellerID, ms.Name, t.BuyerID, mb.Name,
                     t.OfferID, t.AgreedPrice,
                     o.OfferStatus, o.Reason, ` + hasRatedExpr + `, t.CreatedDate
                  FROM Transaction t
                  JOIN Listing l  ON l.ListingID  = t.ListingID
                  JOIN Member ms  ON ms.MemberID  = t.SellerID
                  JOIN Member mb  ON mb.MemberID  = t.BuyerID
                  JOIN Offer o    ON o.OfferID    = t.OfferID
                  ORDER BY t.CreatedDate DESC LIMIT ? OFFSET ?`
		args = []interface{}{pageSize, offset}
	} else {
		query = `SELECT t.TransactionID, t.ListingID, l.Title,
                     t.SellerID, ms.Name, t.BuyerID, mb.Name,
                     t.OfferID, t.AgreedPrice,
                     o.OfferStatus, o.Reason, ` + hasRatedExpr + `, t.CreatedDate
                  FROM Transaction t
                  JOIN Listing l  ON l.ListingID  = t.ListingID
                  JOIN Member ms  ON ms.MemberID  = t.SellerID
                  JOIN Member mb  ON mb.MemberID  = t.BuyerID
                  JOIN Offer o    ON o.OfferID    = t.OfferID
                  WHERE t.SellerID = ? OR t.BuyerID = ?
                  ORDER BY t.CreatedDate DESC LIMIT ? OFFSET ?`
		args = []interface{}{memberID, memberID, memberID, pageSize, offset}
	}

	rows, err := appdb.DB.QueryContext(ctx, query, args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var txs []models.Transaction
	for rows.Next() {
		var t models.Transaction
		var hasRatedInt int
		_ = rows.Scan(
			&t.TransactionID, &t.ListingID, &t.ListingTitle,
			&t.SellerID, &t.SellerName, &t.BuyerID, &t.BuyerName,
			&t.OfferID, &t.AgreedPrice,
			&t.Status, &t.Reason, &hasRatedInt, &t.CreatedDate,
		)
		t.HasRated = hasRatedInt > 0
		txs = append(txs, t)
	}
	if txs == nil {
		txs = []models.Transaction{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: txs, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// POST /api/v1/transactions/:id/rate — own party, only for Accepted transactions
func RateTransaction(w http.ResponseWriter, r *http.Request) {
	txID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid transaction id")
		return
	}
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)

	var sellerID, buyerID int
	var status string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT t.SellerID, t.BuyerID, o.OfferStatus
         FROM Transaction t JOIN Offer o ON o.OfferID = t.OfferID
         WHERE t.TransactionID = ?`, txID,
	).Scan(&sellerID, &buyerID, &status)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "transaction not found")
		return
	}
	if status != "Accepted" {
		respondError(w, http.StatusConflict, "can only rate accepted transactions")
		return
	}
	if memberID != sellerID && memberID != buyerID {
		mw.RespondForbidden(w)
		return
	}

	var body struct {
		Stars      int     `json:"stars"`
		ReviewText *string `json:"review_text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.Stars < 1 || body.Stars > 5 {
		respondError(w, http.StatusBadRequest, "stars must be between 1 and 5")
		return
	}

	var ratedID int
	if memberID == sellerID {
		ratedID = buyerID
	} else {
		ratedID = sellerID
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Rating (TransactionID, RaterID, RatedID, Stars, ReviewText) VALUES (?, ?, ?, ?, ?)`,
		txID, memberID, ratedID, body.Stars, body.ReviewText)
	if err != nil {
		if sqlContains(err.Error(), "Duplicate") {
			respondError(w, http.StatusConflict, "you have already rated this transaction")
		} else {
			respondError(w, http.StatusInternalServerError, "rating failed")
		}
		return
	}
	ratingID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedTransactionID)
         VALUES (?, 'RatingReceived', 'New Rating', CONCAT('You received a ', ?, '-star rating'), ?)`,
		ratedID, body.Stars, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"rating_id": ratingID, "message": "rating submitted"})
}

func sqlContains(s, sub string) bool {
	for i := 0; i <= len(s)-len(sub); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
