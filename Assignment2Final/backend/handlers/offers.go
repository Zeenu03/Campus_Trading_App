package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/listings/:id/offers — own seller or admin
func ListOffersForListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}
	ctx := r.Context()

	// Verify requester is the seller or admin
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
             o.OfferMessage, o.OfferStatus, o.SubmittedDate, o.ResponseDate, o.ExpiryDate
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
			&o.OfferedPrice, &o.AgreedPrice, &o.OfferMessage, &o.OfferStatus,
			&o.SubmittedDate, &o.ResponseDate, &o.ExpiryDate)
		offers = append(offers, o)
	}
	if offers == nil {
		offers = []models.Offer{}
	}
	respondJSON(w, http.StatusOK, offers)
}

// POST /api/v1/listings/:id/offers — member
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

	// Cannot offer on own listing
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
		OfferedPrice float64  `json:"offered_price"`
		OfferMessage *string  `json:"offer_message"`
		ExpiryDate   *string  `json:"expiry_date"`
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
		`INSERT INTO Offer (ListingID, BuyerID, OfferedPrice, OfferMessage, ExpiryDate)
         VALUES (?, ?, ?, ?, ?)`,
		listingID, memberID, body.OfferedPrice, body.OfferMessage, body.ExpiryDate,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "offer creation failed")
		return
	}
	offerID, _ := res.LastInsertId()

	// Update listing status to Pending
	_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Pending' WHERE ListingID = ? AND Status = 'Listed'`, listingID)

	// Notify seller
	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID)
         VALUES (?, 'OfferReceived', 'New Offer', CONCAT('You received a new offer on your listing'), ?, ?)`,
		sellerID, listingID, offerID)

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"offer_id": offerID, "message": "offer submitted"})
}

// PUT /api/v1/offers/:id/accept — own seller
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
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, l.SellerID, o.OfferedPrice, m.user_id
          FROM Offer o
          JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member m ON m.MemberID = l.SellerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerID, &offeredPrice, &sellerUserID)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
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

	// Accept this offer
	_, err = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Accepted', AgreedPrice = ?, ResponseDate = NOW() WHERE OfferID = ?`,
		offeredPrice, offerID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "accept failed")
		return
	}

	// Auto-decline all other submitted offers on this listing
	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', ResponseDate = NOW()
         WHERE ListingID = ? AND OfferStatus = 'Submitted' AND OfferID != ?`,
		listingID, offerID)

	// Update listing status to Reserved
	_, _ = tx.ExecContext(ctx,
		`UPDATE Listing SET Status = 'Reserved', LastModifiedDate = NOW() WHERE ListingID = ?`, listingID)

	// Create transaction record
	res, err := tx.ExecContext(ctx,
		`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice)
         VALUES (?, ?, ?, ?, ?)`,
		listingID, sellerID, buyerID, offerID, offeredPrice)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction creation failed")
		return
	}
	txID, _ := res.LastInsertId()

	// Notify buyer
	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
         VALUES (?, 'OfferAccepted', 'Offer Accepted', 'Your offer has been accepted!', ?, ?, ?)`,
		buyerID, listingID, offerID, txID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]interface{}{"transaction_id": txID, "message": "offer accepted"})
}

// PUT /api/v1/offers/:id/decline — own seller
func DeclineOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var listingID, buyerID int
	var sellerUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT o.ListingID, o.BuyerID, m.user_id
          FROM Offer o JOIN Listing l ON l.ListingID = o.ListingID
          JOIN Member m ON m.MemberID = l.SellerID
          WHERE o.OfferID = ?`, offerID,
	).Scan(&listingID, &buyerID, &sellerUserID)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
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

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Declined', ResponseDate = NOW() WHERE OfferID = ?`, offerID)

	// Check if any other submitted offers; if not, set listing back to Listed
	var otherOffers int
	_ = tx.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Offer WHERE ListingID = ? AND OfferStatus = 'Submitted'`, listingID,
	).Scan(&otherOffers)
	if otherOffers == 0 {
		_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Listed' WHERE ListingID = ?`, listingID)
	}

	// Notify buyer
	_, _ = tx.ExecContext(ctx,
		`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID)
         VALUES (?, 'OfferDeclined', 'Offer Declined', 'Your offer was declined.', ?, ?)`,
		buyerID, listingID, offerID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer declined"})
}

// PUT /api/v1/offers/:id/withdraw — own buyer
func WithdrawOffer(w http.ResponseWriter, r *http.Request) {
	offerID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid offer id")
		return
	}
	ctx := r.Context()

	var buyerUserID, listingID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id, o.ListingID FROM Offer o JOIN Member m ON m.MemberID = o.BuyerID WHERE o.OfferID = ?`,
		offerID).Scan(&buyerUserID, &listingID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "offer not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, buyerUserID) {
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

	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Withdrawn', ResponseDate = NOW() WHERE OfferID = ? AND OfferStatus = 'Submitted'`,
		offerID)

	var otherOffers int
	_ = tx.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Offer WHERE ListingID = ? AND OfferStatus = 'Submitted'`, listingID,
	).Scan(&otherOffers)
	if otherOffers == 0 {
		_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Listed' WHERE ListingID = ?`, listingID)
	}

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "offer withdrawn"})
}
