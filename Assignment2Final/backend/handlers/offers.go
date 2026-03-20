package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/listings/:id/my-offer — returns the requesting buyer's own offer on this listing, or 404
func GetMyOffer(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
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

	var o models.Offer
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.OfferID, o.ListingID, o.BuyerID, m.Name, o.OfferedPrice, o.AgreedPrice,
             o.OfferStatus, o.Reason, o.SubmittedDate, o.ResponseDate
          FROM Offer o JOIN Member m ON m.MemberID = o.BuyerID
          WHERE o.ListingID = ? AND o.BuyerID = ?`, listingID, memberID,
	).Scan(&o.OfferID, &o.ListingID, &o.BuyerID, &o.BuyerName,
		&o.OfferedPrice, &o.AgreedPrice, &o.OfferStatus, &o.Reason,
		&o.SubmittedDate, &o.ResponseDate)
	if err == sql.ErrNoRows {
		respondJSON(w, http.StatusOK, nil)
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	respondJSON(w, http.StatusOK, o)
}

// GET /api/v1/listings/:id/offers — own seller or admin
func ListOffersForListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}
	ctx := r.Context()

	var sellerUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id FROM Listing l JOIN Member m ON m.MemberID = l.SellerID WHERE l.ListingID = ?`,
		listingID).Scan(&sellerUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT o.OfferID, o.ListingID, o.BuyerID, m.Name, o.OfferedPrice, o.AgreedPrice,
             o.OfferStatus, o.Reason, o.SubmittedDate, o.ResponseDate
          FROM Offer o JOIN Member m ON m.MemberID = o.BuyerID
          WHERE o.ListingID = ? ORDER BY o.SubmittedDate DESC`, listingID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var offers []models.Offer
	for rows.Next() {
		var o models.Offer
		_ = rows.Scan(&o.OfferID, &o.ListingID, &o.BuyerID, &o.BuyerName,
			&o.OfferedPrice, &o.AgreedPrice, &o.OfferStatus, &o.Reason,
			&o.SubmittedDate, &o.ResponseDate)
		offers = append(offers, o)
	}
	if offers == nil {
		offers = []models.Offer{}
	}
	respondJSON(w, http.StatusOK, offers)
}

// POST /api/v1/listings/:id/offers — member
// Creates an offer, upserts a MessageThread linking the offer, and auto-adds the listing to the buyer's watchlist.
func CreateOffer(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
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

	var sellerID int
	var listingStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT SellerID, Status FROM Listing WHERE ListingID = ?`, listingID,
	).Scan(&sellerID, &listingStatus)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if sellerID == memberID {
		respondError(w, http.StatusForbidden, "cannot offer on your own listing")
		return
	}
	if listingStatus != "Listed" {
		respondError(w, http.StatusConflict, "listing is not available for offers")
		return
	}

	var body struct {
		OfferedPrice float64 `json:"offered_price"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.OfferedPrice <= 0 {
		respondError(w, http.StatusBadRequest, "offered_price must be > 0")
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
		`INSERT INTO Offer (ListingID, BuyerID, OfferedPrice)
         VALUES (?, ?, ?)
         ON DUPLICATE KEY UPDATE OfferedPrice = VALUES(OfferedPrice), OfferStatus = 'Submitted',
             Reason = NULL, ResponseDate = NULL`,
		listingID, memberID, body.OfferedPrice,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "offer creation failed")
		return
	}
	offerID, _ := res.LastInsertId()
	// ON DUPLICATE KEY returns lastInsertId=0; fetch real ID when buyer re-offers
	if offerID == 0 {
		_ = tx.QueryRowContext(ctx,
			`SELECT OfferID FROM Offer WHERE ListingID = ? AND BuyerID = ?`,
			listingID, memberID).Scan(&offerID)
	}

	// Upsert MessageThread — promote chat-only thread to offer-backed, or create fresh
	_, err = tx.ExecContext(ctx,
		`INSERT INTO MessageThread (ListingID, BuyerID, OfferID)
         VALUES (?, ?, ?)
         ON DUPLICATE KEY UPDATE OfferID = VALUES(OfferID)`,
		listingID, memberID, offerID,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "thread upsert failed")
		return
	}

	// Auto-add to watchlist (idempotent — IGNORE on duplicate)
	_, _ = tx.ExecContext(ctx,
		`INSERT IGNORE INTO Watchlist (MemberID, ListingID) VALUES (?, ?)`,
		memberID, listingID)

	// Notify seller
	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID)
         VALUES (?, 'OfferReceived', 'New Offer', 'You received a new offer on your listing', ?, ?)`,
		sellerID, listingID, offerID)

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"offer_id": offerID, "message": "offer submitted"})
}

// PUT /api/v1/offers/:id/accept — own seller accepts buyer's offered price
func AcceptOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID, sellerID int
	var offeredPrice float64
	var sellerUserID int
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, o.OfferedPrice, m.user_id, o.OfferStatus
          FROM Offer o
          JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member m ON m.MemberID = l.SellerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerID, &offeredPrice, &sellerUserID, &offerStatus)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "offer is no longer active")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, err = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Accepted', AgreedPrice = ?, ResponseDate = NOW() WHERE OfferID = ?`,
		offeredPrice, offerID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "accept failed")
		return
	}

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', ResponseDate = NOW()
         WHERE ListingID = ? AND OfferStatus = 'Submitted' AND OfferID != ?`,
		listingID, offerID)

	_, _ = tx.ExecContext(ctx,
		`UPDATE Listing SET Status = 'Sold', LastModifiedDate = NOW() WHERE ListingID = ?`, listingID)

	_, _ = tx.ExecContext(ctx,
		`DELETE FROM Watchlist WHERE ListingID = ?`, listingID)

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice)
         VALUES (?, ?, ?, ?, ?)`,
		listingID, sellerID, buyerID, offerID, offeredPrice)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferAccepted', 'Offer Accepted', 'Your offer has been accepted!', ?, ?, ?)`,
		buyerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]interface{}{"transaction_id": txID, "message": "offer accepted"})
}

// PUT /api/v1/offers/:id/decline — seller declines buyer's offer (reason required)
func DeclineOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID, sellerID int
	var sellerUserID int
	var offeredPrice float64
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, m.user_id, o.OfferedPrice, o.OfferStatus
          FROM Offer o JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member m ON m.MemberID = l.SellerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerID, &sellerUserID, &offeredPrice, &offerStatus)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "offer is no longer active")
		return
	}

	var body struct {
		Reason string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Reason == "" {
		respondError(w, http.StatusBadRequest, "reason is required")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', Reason = ?, ResponseDate = NOW() WHERE OfferID = ?`,
		body.Reason, offerID)

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice, Status, Reason)
         VALUES (?, ?, ?, ?, ?, 'Cancelled', ?)`,
		listingID, sellerID, buyerID, offerID, offeredPrice, body.Reason)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferDeclined', 'Offer Declined', 'Your offer was declined.', ?, ?, ?)`,
		buyerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer declined"})
}

// PUT /api/v1/offers/:id/withdraw — seller withdraws the offer (reason required)
func WithdrawOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID, sellerID int
	var buyerUserID int
	var offeredPrice float64
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, mb.user_id, o.OfferedPrice, o.OfferStatus
          FROM Offer o
          JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member mb ON mb.MemberID = o.BuyerID
          WHERE o.OfferID = ?`,
		offerID).Scan(&listingID, &buyerID, &sellerID, &buyerUserID, &offeredPrice, &offerStatus)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, buyerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "offer is no longer active")
		return
	}

	var body struct {
		Reason string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Reason == "" {
		respondError(w, http.StatusBadRequest, "reason is required")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Withdrawn', Reason = ?, ResponseDate = NOW()
         WHERE OfferID = ? AND OfferStatus = 'Submitted'`,
		body.Reason, offerID)

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice, Status, Reason)
         VALUES (?, ?, ?, ?, ?, 'Cancelled', ?)`,
		listingID, sellerID, buyerID, offerID, offeredPrice, body.Reason)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferWithdrawn', 'Offer Withdrawn', 'The buyer withdrew their offer.', ?, ?, ?)`,
		sellerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer withdrawn"})
}

// PUT /api/v1/offers/:id/price — buyer updates their offered price (offer must be Submitted)
func UpdateOfferPrice(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var buyerUserID int
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id, o.OfferStatus FROM Offer o JOIN Member m ON m.MemberID = o.BuyerID WHERE o.OfferID = ?`,
		offerID).Scan(&buyerUserID, &offerStatus)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, buyerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "can only update a submitted offer")
		return
	}

	var body struct {
		OfferedPrice float64 `json:"offered_price"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.OfferedPrice <= 0 {
		respondError(w, http.StatusBadRequest, "offered_price must be > 0")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferedPrice = ? WHERE OfferID = ? AND OfferStatus = 'Submitted'`,
		body.OfferedPrice, offerID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer price updated"})
}

// PUT /api/v1/offers/:id/buyer-accept — buyer accepts the seller's current asking price
func BuyerAcceptOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID, sellerID int
	var buyerUserID int
	var askingPrice float64
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, mb.user_id, l.AskingPrice, o.OfferStatus
          FROM Offer o
          JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member mb ON mb.MemberID = o.BuyerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerID, &buyerUserID, &askingPrice, &offerStatus)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, buyerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "offer is no longer active")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, err = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Accepted', AgreedPrice = ?, ResponseDate = NOW() WHERE OfferID = ?`,
		askingPrice, offerID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "accept failed")
		return
	}

	// Auto-decline all other submitted offers on this listing
	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', ResponseDate = NOW()
         WHERE ListingID = ? AND OfferStatus = 'Submitted' AND OfferID != ?`,
		listingID, offerID)

	_, _ = tx.ExecContext(ctx,
		`UPDATE Listing SET Status = 'Sold', LastModifiedDate = NOW() WHERE ListingID = ?`, listingID)

	_, _ = tx.ExecContext(ctx,
		`DELETE FROM Watchlist WHERE ListingID = ?`, listingID)

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice)
         VALUES (?, ?, ?, ?, ?)`,
		listingID, sellerID, buyerID, offerID, askingPrice)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferAccepted', 'Offer Accepted', 'The buyer accepted your asking price!', ?, ?, ?)`,
		sellerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]interface{}{"transaction_id": txID, "message": "offer accepted at asking price"})
}

// PUT /api/v1/offers/:id/buyer-decline — buyer declines (reason required)
func BuyerDeclineOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID, sellerID int
	var buyerUserID int
	var offeredPrice float64
	var offerStatus string
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, mb.user_id, o.OfferedPrice, o.OfferStatus
          FROM Offer o
          JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member mb ON mb.MemberID = o.BuyerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerID, &buyerUserID, &offeredPrice, &offerStatus)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, buyerUserID) {
		mw.RespondForbidden(w)
		return
	}
	if offerStatus != "Submitted" {
		respondError(w, http.StatusConflict, "offer is no longer active")
		return
	}

	var body struct {
		Reason string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Reason == "" {
		respondError(w, http.StatusBadRequest, "reason is required")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', Reason = ?, ResponseDate = NOW() WHERE OfferID = ?`,
		body.Reason, offerID)

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice, Status, Reason)
         VALUES (?, ?, ?, ?, ?, 'Cancelled', ?)`,
		listingID, sellerID, buyerID, offerID, offeredPrice, body.Reason)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferDeclined', 'Offer Declined', 'The buyer declined your listing price.', ?, ?, ?)`,
		sellerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer declined"})
}
