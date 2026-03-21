package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/listings/:id/my-thread — returns the requesting buyer's thread for this listing, or null
func GetMyThread(w http.ResponseWriter, r *http.Request) {
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

	var threadID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT ThreadID FROM MessageThread WHERE ListingID = ? AND BuyerID = ?`,
		listingID, memberID).Scan(&threadID)
	if err == sql.ErrNoRows {
		respondJSON(w, http.StatusOK, nil)
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]int{"thread_id": threadID})
}

// POST /api/v1/listings/:id/threads — buyer initiates a chat-only thread (no offer required)
func CreateThread(w http.ResponseWriter, r *http.Request) {
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
		respondError(w, http.StatusForbidden, "cannot open a chat on your own listing")
		return
	}
	if listingStatus != "Listed" {
		respondError(w, http.StatusConflict, "listing is not available")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	// Insert chat-only thread (OfferID = NULL); ignore if a thread already exists for this buyer
	res, err := tx.ExecContext(ctx,
		`INSERT IGNORE INTO MessageThread (ListingID, BuyerID, OfferID) VALUES (?, ?, NULL)`,
		listingID, memberID,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "thread creation failed")
		return
	}

	threadID, _ := res.LastInsertId()
	// IGNORE returns 0 when row already existed — fetch real ID
	if threadID == 0 {
		_ = tx.QueryRowContext(ctx,
			`SELECT ThreadID FROM MessageThread WHERE ListingID = ? AND BuyerID = ?`,
			listingID, memberID).Scan(&threadID)
	}

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"thread_id": threadID, "message": "thread created"})
}

// GET /api/v1/listings/:id/interactions — seller sees all buyer interactions (offers + chat-only)
// Ordered chronologically by thread creation date (first-come first-served).
func ListInteractions(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}
	ctx := r.Context()

	var sellerUserID int
	var askingPrice float64
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id, l.AskingPrice
          FROM Listing l JOIN Member m ON m.MemberID = l.SellerID
          WHERE l.ListingID = ?`, listingID,
	).Scan(&sellerUserID, &askingPrice)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT
            mt.ThreadID,
            mt.ListingID,
            mt.BuyerID,
            mb.Name                                          AS BuyerName,
            mt.OfferID,
            o.OfferedPrice,
            o.SellerAskingPrice,
            o.AgreedPrice,
            o.OfferStatus,
            o.Reason                                         AS OfferReason,
            mt.CreatedDate,
            mt.IsActive,
            (SELECT msg.MessageText
               FROM Message msg
              WHERE msg.ThreadID = mt.ThreadID
              ORDER BY msg.SentDate DESC
              LIMIT 1)                                       AS LastMessagePreview
         FROM MessageThread mt
         JOIN Member mb ON mb.MemberID = mt.BuyerID
         LEFT JOIN Offer o ON o.OfferID = mt.OfferID
         WHERE mt.ListingID = ?
         ORDER BY mt.CreatedDate ASC`, listingID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var interactions []models.MessageThread
	for rows.Next() {
		var it models.MessageThread
		_ = rows.Scan(
			&it.ThreadID, &it.ListingID, &it.BuyerID, &it.BuyerName,
			&it.OfferID, &it.OfferedPrice, &it.SellerAskingPrice, &it.AgreedPrice,
			&it.OfferStatus, &it.OfferReason,
			&it.CreatedDate, &it.IsActive,
			&it.LastMessagePreview,
		)
		it.AskingPrice = askingPrice
		interactions = append(interactions, it)
	}
	if interactions == nil {
		interactions = []models.MessageThread{}
	}
	respondJSON(w, http.StatusOK, interactions)
}

// GET /api/v1/threads/:id/messages — paginated messages for a thread
// Accessible by the buyer of the thread or the seller of the listing.
func ListMessages(w http.ResponseWriter, r *http.Request) {
	threadID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid thread id")
		return
	}
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var buyerID, sellerID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT mt.BuyerID, l.SellerID
          FROM MessageThread mt JOIN Listing l ON l.ListingID = mt.ListingID
          WHERE mt.ThreadID = ?`, threadID,
	).Scan(&buyerID, &sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "thread not found")
		return
	}
	if memberID != buyerID && memberID != sellerID {
		mw.RespondForbidden(w)
		return
	}

	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 50)

	var total int
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Message WHERE ThreadID = ?`, threadID).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT msg.MessageID, msg.ThreadID, msg.SenderID, m.Name, msg.MessageText, msg.SentDate
          FROM Message msg JOIN Member m ON m.MemberID = msg.SenderID
          WHERE msg.ThreadID = ?
          ORDER BY msg.SentDate ASC
          LIMIT ? OFFSET ?`, threadID, pageSize, offset)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var messages []models.Message
	for rows.Next() {
		var msg models.Message
		_ = rows.Scan(&msg.MessageID, &msg.ThreadID, &msg.SenderID, &msg.SenderName, &msg.MessageText, &msg.SentDate)
		messages = append(messages, msg)
	}
	if messages == nil {
		messages = []models.Message{}
	}

	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data:       messages,
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	})
}

// POST /api/v1/threads/:id/messages — send a message in a thread
// Accessible by the buyer of the thread or the seller of the listing.
func SendMessage(w http.ResponseWriter, r *http.Request) {
	threadID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid thread id")
		return
	}
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var buyerID, sellerID int
	var isActive bool
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT mt.BuyerID, l.SellerID, mt.IsActive
          FROM MessageThread mt JOIN Listing l ON l.ListingID = mt.ListingID
          WHERE mt.ThreadID = ?`, threadID,
	).Scan(&buyerID, &sellerID, &isActive)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "thread not found")
		return
	}
	if memberID != buyerID && memberID != sellerID {
		mw.RespondForbidden(w)
		return
	}
	if !isActive {
		respondError(w, http.StatusConflict, "thread is closed")
		return
	}

	var body struct {
		MessageText string `json:"message_text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.MessageText == "" {
		respondError(w, http.StatusBadRequest, "message_text is required")
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
		`INSERT INTO Message (ThreadID, SenderID, MessageText) VALUES (?, ?, ?)`,
		threadID, memberID, body.MessageText)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "send failed")
		return
	}
	msgID, _ := res.LastInsertId()

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"message_id": msgID, "message": "sent"})
}
