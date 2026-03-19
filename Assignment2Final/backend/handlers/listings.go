package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"time"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/listings — auth, browse with filters
func ListListings(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)
	category := r.URL.Query().Get("category")
	status := r.URL.Query().Get("status")
	condition := r.URL.Query().Get("condition")
	sort := r.URL.Query().Get("sort") // price_asc, price_desc, newest

	if status == "" {
		status = "Listed"
	}

	baseWhere := " WHERE l.Status = ?"
	args := []interface{}{status}

	if category != "" {
		baseWhere += " AND l.CategoryID = ?"
		args = append(args, category)
	}
	if condition != "" {
		baseWhere += " AND l.Condition = ?"
		args = append(args, condition)
	}

	var total int
	_ = appdb.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM Listing l"+baseWhere, args...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	orderBy := " ORDER BY l.CreatedDate DESC"
	switch sort {
	case "price_asc":
		orderBy = " ORDER BY l.AskingPrice ASC"
	case "price_desc":
		orderBy = " ORDER BY l.AskingPrice DESC"
	}

	query := `SELECT l.ListingID, l.SellerID, m.Name, l.CategoryID, c.CategoryName,
               l.Title, l.AskingPrice, l.IsNegotiable, l.Condition, l.Status,
               l.CreatedDate, l.ExpiryDate, l.IsDonation
              FROM Listing l
              JOIN Member m ON m.MemberID = l.SellerID
              JOIN Category c ON c.CategoryID = l.CategoryID` +
		baseWhere + orderBy + " LIMIT ? OFFSET ?"
	args = append(args, pageSize, offset)

	rows, err := appdb.DB.QueryContext(r.Context(), query, args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var listings []models.Listing
	for rows.Next() {
		var l models.Listing
		var cond *string
		var expiry *time.Time
		if err := rows.Scan(&l.ListingID, &l.SellerID, &l.SellerName, &l.CategoryID, &l.CategoryName,
			&l.Title, &l.AskingPrice, &l.IsNegotiable, &cond, &l.Status,
			&l.CreatedDate, &expiry, &l.IsDonation); err != nil {
			continue
		}
		l.Condition = cond
		l.ExpiryDate = expiry
		listings = append(listings, l)
	}
	if listings == nil {
		listings = []models.Listing{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: listings, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// POST /api/v1/listings — member, create
func CreateListing(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var body struct {
		CategoryID               int      `json:"category_id"`
		Title                    string   `json:"title"`
		Description              *string  `json:"description"`
		AskingPrice              float64  `json:"asking_price"`
		IsNegotiable             bool     `json:"is_negotiable"`
		Condition                *string  `json:"condition"`
		CourseCode               *string  `json:"course_code"`
		ExpiryDate               *string  `json:"expiry_date"`
		IsDonation               bool     `json:"is_donation"`
		PreferredMeetingLocation *string  `json:"preferred_meeting_location"`
		WishRequestID            *int     `json:"wish_request_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.Title == "" || body.CategoryID == 0 {
		respondError(w, http.StatusBadRequest, "title and category_id required")
		return
	}
	if body.AskingPrice < 0 {
		respondError(w, http.StatusBadRequest, "asking_price must be >= 0")
		return
	}
	if body.IsDonation && body.AskingPrice != 0 {
		respondError(w, http.StatusBadRequest, "donation listing must have price 0")
		return
	}

	// Enforce: max 2 active listings if 0 completed transactions
	var completedTx int
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Transaction WHERE (SellerID = ? OR BuyerID = ?) AND Status = 'Completed'`,
		memberID, memberID).Scan(&completedTx)

	if completedTx == 0 {
		var activeListings int
		_ = appdb.DB.QueryRowContext(ctx,
			`SELECT COUNT(*) FROM Listing WHERE SellerID = ? AND Status = 'Listed'`,
			memberID).Scan(&activeListings)
		if activeListings >= 2 {
			respondError(w, http.StatusForbidden, "max 2 active listings allowed until you complete a transaction")
			return
		}
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()

	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	var expiryVal interface{} = nil
	if body.ExpiryDate != nil {
		t, err := time.Parse("2006-01-02", *body.ExpiryDate)
		if err == nil {
			expiryVal = t
		}
	}

	res, err := tx.ExecContext(ctx,
		`INSERT INTO Listing (SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable,
          Condition, CourseCode, ExpiryDate, IsDonation, PreferredMeetingLocation, WishRequestID)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		memberID, body.CategoryID, body.Title, body.Description, body.AskingPrice, body.IsNegotiable,
		body.Condition, body.CourseCode, expiryVal, body.IsDonation,
		body.PreferredMeetingLocation, body.WishRequestID,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "listing creation failed: "+err.Error())
		return
	}
	listingID, _ := res.LastInsertId()

	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}
	respondJSON(w, http.StatusCreated, map[string]interface{}{"listing_id": listingID, "message": "listing created"})
}

// GET /api/v1/listings/:id — auth, detail
func GetListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}

	var l models.Listing
	var desc, cond, courseCode, meetLoc *string
	var lastMod, expiry *time.Time
	var wishReqID *int

	err = appdb.DB.QueryRowContext(r.Context(),
		`SELECT l.ListingID, l.SellerID, m.Name, l.CategoryID, c.CategoryName,
             l.Title, l.Description, l.AskingPrice, l.IsNegotiable, l.Condition,
             l.CourseCode, l.Status, l.CreatedDate, l.LastModifiedDate, l.ExpiryDate,
             l.IsDonation, l.PreferredMeetingLocation, l.WishRequestID
          FROM Listing l
          JOIN Member m ON m.MemberID = l.SellerID
          JOIN Category c ON c.CategoryID = l.CategoryID
          WHERE l.ListingID = ?`, listingID,
	).Scan(&l.ListingID, &l.SellerID, &l.SellerName, &l.CategoryID, &l.CategoryName,
		&l.Title, &desc, &l.AskingPrice, &l.IsNegotiable, &cond,
		&courseCode, &l.Status, &l.CreatedDate, &lastMod, &expiry,
		&l.IsDonation, &meetLoc, &wishReqID)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}
	l.Description = desc
	l.Condition = cond
	l.CourseCode = courseCode
	l.LastModifiedDate = lastMod
	l.ExpiryDate = expiry
	l.PreferredMeetingLocation = meetLoc
	l.WishRequestID = wishReqID

	// Load images
	imgRows, _ := appdb.DB.QueryContext(r.Context(),
		`SELECT ImageID, ImageURL, ImageOrder FROM ListingImage WHERE ListingID = ? ORDER BY ImageOrder`, listingID)
	if imgRows != nil {
		defer imgRows.Close()
		for imgRows.Next() {
			var img models.ListingImage
			_ = imgRows.Scan(&img.ImageID, &img.ImageURL, &img.ImageOrder)
			img.ListingID = listingID
			l.Images = append(l.Images, img)
		}
	}

	respondJSON(w, http.StatusOK, l)
}

// PUT /api/v1/listings/:id — own or admin
func UpdateListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}

	ctx := r.Context()

	// Check ownership
	var sellerID int
	var sellerUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT l.SellerID, m.user_id FROM Listing l JOIN Member m ON m.MemberID = l.SellerID WHERE l.ListingID = ?`,
		listingID).Scan(&sellerID, &sellerUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()

	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	setMap := map[string]string{
		"title": "Title", "description": "Description", "asking_price": "AskingPrice",
		"is_negotiable": "IsNegotiable", "condition": "Condition",
		"status": "Status", "preferred_meeting_location": "PreferredMeetingLocation",
	}
	var setClauses []string
	var args []interface{}
	for jsonKey, col := range setMap {
		if v, ok := body[jsonKey]; ok {
			setClauses = append(setClauses, col+" = ?")
			args = append(args, v)
		}
	}
	if len(setClauses) == 0 {
		respondError(w, http.StatusBadRequest, "no valid fields")
		return
	}
	setClauses = append(setClauses, "LastModifiedDate = NOW()")
	args = append(args, listingID)

	_, err = tx.ExecContext(ctx, "UPDATE Listing SET "+join(setClauses, ", ")+" WHERE ListingID = ?", args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "update failed")
		return
	}
	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "listing updated"})
}

// DELETE /api/v1/listings/:id — own or admin (withdraw)
func DeleteListing(w http.ResponseWriter, r *http.Request) {
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

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Withdrawn', LastModifiedDate = NOW() WHERE ListingID = ?`, listingID)
	_, _ = tx.ExecContext(ctx, `UPDATE Offer SET OfferStatus = 'Expired' WHERE ListingID = ? AND OfferStatus = 'Submitted'`, listingID)

	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "listing withdrawn"})
}

func join(s []string, sep string) string {
	result := ""
	for i, v := range s {
		if i > 0 {
			result += sep
		}
		result += v
	}
	return result
}
