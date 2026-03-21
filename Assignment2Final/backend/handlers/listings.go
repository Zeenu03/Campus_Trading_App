package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"

	"github.com/google/uuid"
)

var (
	allowedListingStatuses = map[string]struct{}{
		"Listed": {}, "Sold": {}, "Withdrawn": {},
	}
	allowedListingConditions = map[string]struct{}{
		"New": {}, "Like New": {}, "Good": {}, "Fair": {}, "Poor": {},
	}
	allowedImageTypes = map[string]struct{}{
		"image/jpeg": {}, "image/png": {}, "image/webp": {}, "image/gif": {},
	}
	maxImageSize        = int64(5 << 20) // 5MB
	maxImagesPerListing = 10
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
               l.CreatedDate, l.IsDonation
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
		if err := rows.Scan(&l.ListingID, &l.SellerID, &l.SellerName, &l.CategoryID, &l.CategoryName,
			&l.Title, &l.AskingPrice, &l.IsNegotiable, &cond, &l.Status,
			&l.CreatedDate, &l.IsDonation); err != nil {
			continue
		}
		l.Condition = cond
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
		CategoryID    int     `json:"category_id"`
		Title         string  `json:"title"`
		Description   *string `json:"description"`
		AskingPrice   float64 `json:"asking_price"`
		IsNegotiable  bool    `json:"is_negotiable"`
		Condition     *string `json:"condition"`
		IsDonation    bool    `json:"is_donation"`
		WishRequestID *int    `json:"wish_request_id"`
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

	res, err := tx.ExecContext(ctx,
		"INSERT INTO Listing (SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable, "+
			"`Condition`, IsDonation, WishRequestID) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		memberID, body.CategoryID, body.Title, body.Description, body.AskingPrice, body.IsNegotiable,
		body.Condition, body.IsDonation, body.WishRequestID,
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

// loadListingWithImages returns listing row with seller/category names, images, watcher count,
// and (when memberID > 0) the requesting member's own watchlist entry ID for this listing.
func loadListingWithImages(ctx context.Context, listingID int, memberID int) (*models.Listing, error) {
	var l models.Listing
	var desc, cond *string
	var lastMod *time.Time
	var wishReqID *int

	err := appdb.DB.QueryRowContext(ctx,
		`SELECT l.ListingID, l.SellerID, m.Name, l.CategoryID, c.CategoryName,
             l.Title, l.Description, l.AskingPrice, l.IsNegotiable, l.Condition,
             l.Status, l.CreatedDate, l.LastModifiedDate,
             l.IsDonation, l.WishRequestID
          FROM Listing l
          JOIN Member m ON m.MemberID = l.SellerID
          JOIN Category c ON c.CategoryID = l.CategoryID
          WHERE l.ListingID = ?`, listingID,
	).Scan(&l.ListingID, &l.SellerID, &l.SellerName, &l.CategoryID, &l.CategoryName,
		&l.Title, &desc, &l.AskingPrice, &l.IsNegotiable, &cond,
		&l.Status, &l.CreatedDate, &lastMod,
		&l.IsDonation, &wishReqID)
	if err != nil {
		return nil, err
	}
	l.Description = desc
	l.Condition = cond
	l.LastModifiedDate = lastMod
	l.WishRequestID = wishReqID

	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Watchlist WHERE ListingID = ?`, listingID).Scan(&l.WatcherCount)

	if memberID > 0 {
		var wid int
		err2 := appdb.DB.QueryRowContext(ctx,
			`SELECT WatchlistID FROM Watchlist WHERE ListingID = ? AND MemberID = ?`,
			listingID, memberID).Scan(&wid)
		if err2 == nil {
			l.MyWatchlistID = &wid
		}
	}

	imgRows, err := appdb.DB.QueryContext(ctx,
		`SELECT ImageID, ImageURL, ImageOrder FROM ListingImage WHERE ListingID = ? ORDER BY ImageOrder`, listingID)
	if err != nil {
		return nil, err
	}
	defer imgRows.Close()
	for imgRows.Next() {
		var img models.ListingImage
		var storedPath string
		if err := imgRows.Scan(&img.ImageID, &storedPath, &img.ImageOrder); err != nil {
			return nil, err
		}
		img.ImageURL = imagePathToURL(storedPath)
		img.ListingID = listingID
		l.Images = append(l.Images, img)
	}
	return &l, nil
}

// imagePathToURL converts stored filesystem path to URL path for frontend.
func imagePathToURL(stored string) string {
	if stored == "" {
		return ""
	}
	if strings.HasPrefix(stored, "/uploads/") {
		return stored
	}
	return "/uploads/" + strings.TrimPrefix(stored, "/")
}

// GET /api/v1/listings/:id — auth, detail
func GetListing(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}

	l, err := loadListingWithImages(r.Context(), listingID, mw.GetMemberID(r.Context()))
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, l)
}

// PUT /api/v1/listings/:id — own or admin (partial update; merged with current row and validated)
func UpdateListing(w http.ResponseWriter, r *http.Request) {
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
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
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
	if body == nil {
		body = map[string]interface{}{}
	}

	var cur struct {
		Title        string
		Description  sql.NullString
		AskingPrice  float64
		IsNegotiable bool
		Condition    sql.NullString
		CategoryID   int
		IsDonation   bool
		Status       string
	}
	err = appdb.DB.QueryRowContext(ctx,
		"SELECT Title, Description, AskingPrice, IsNegotiable, `Condition`, CategoryID, IsDonation, Status "+
			"FROM Listing WHERE ListingID = ?", listingID,
	).Scan(&cur.Title, &cur.Description, &cur.AskingPrice, &cur.IsNegotiable,
		&cur.Condition, &cur.CategoryID, &cur.IsDonation, &cur.Status)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "load listing failed")
		return
	}

	// Donation requires price 0: if turning on donation without asking_price, force 0 in the patch.
	if v, ok := body["is_donation"]; ok {
		if b, err := jsonToBool(v); err == nil && b {
			if _, has := body["asking_price"]; !has {
				body["asking_price"] = float64(0)
			}
		}
	}

	nextPrice := cur.AskingPrice
	nextCat := cur.CategoryID
	nextDon := cur.IsDonation

	patch := make(map[string]interface{})

	if v, ok := body["title"]; ok {
		s, ok := v.(string)
		if !ok {
			respondError(w, http.StatusBadRequest, "title must be a string")
			return
		}
		s = strings.TrimSpace(s)
		if s == "" {
			respondError(w, http.StatusBadRequest, "title cannot be empty")
			return
		}
		if utf8.RuneCountInString(s) > 200 {
			respondError(w, http.StatusBadRequest, "title too long (max 200 characters)")
			return
		}
		patch["title"] = s
	}

	if v, has := body["description"]; has {
		if v == nil {
			patch["description"] = nil
		} else if s, ok := v.(string); ok {
			s = strings.TrimSpace(s)
			if s == "" {
				patch["description"] = nil
			} else {
				if utf8.RuneCountInString(s) > 2000 {
					respondError(w, http.StatusBadRequest, "description too long (max 2000 characters)")
					return
				}
				patch["description"] = s
			}
		} else {
			respondError(w, http.StatusBadRequest, "description must be a string or null")
			return
		}
	}

	if v, ok := body["asking_price"]; ok {
		p, err := jsonNumToFloat(v)
		if err != nil {
			respondError(w, http.StatusBadRequest, "invalid asking_price")
			return
		}
		nextPrice = p
		patch["asking_price"] = p
	}

	if v, ok := body["is_negotiable"]; ok {
		b, err := jsonToBool(v)
		if err != nil {
			respondError(w, http.StatusBadRequest, "invalid is_negotiable")
			return
		}
		patch["is_negotiable"] = b
	}

	if v, has := body["condition"]; has {
		if v == nil {
			patch["condition"] = nil
		} else if s, ok := v.(string); ok {
			s = strings.TrimSpace(s)
			if s == "" {
				patch["condition"] = nil
			} else {
				if _, ok := allowedListingConditions[s]; !ok {
					respondError(w, http.StatusBadRequest, "invalid condition")
					return
				}
				patch["condition"] = s
			}
		} else {
			respondError(w, http.StatusBadRequest, "condition must be a string or null")
			return
		}
	}

	if v, ok := body["category_id"]; ok {
		cid, err := jsonNumToInt(v)
		if err != nil || cid <= 0 {
			respondError(w, http.StatusBadRequest, "invalid category_id")
			return
		}
		nextCat = cid
		patch["category_id"] = cid
	}

	if v, ok := body["is_donation"]; ok {
		b, err := jsonToBool(v)
		if err != nil {
			respondError(w, http.StatusBadRequest, "invalid is_donation")
			return
		}
		nextDon = b
		patch["is_donation"] = b
	}

	if v, ok := body["status"]; ok {
		s, ok := v.(string)
		if !ok {
			respondError(w, http.StatusBadRequest, "status must be a string")
			return
		}
		if _, ok := allowedListingStatuses[s]; !ok {
			respondError(w, http.StatusBadRequest, "invalid status")
			return
		}
		patch["status"] = s
	}

	// Merged row must satisfy DB CHECK constraints
	if nextPrice < 0 {
		respondError(w, http.StatusBadRequest, "asking_price must be >= 0")
		return
	}
	if nextDon && nextPrice != 0 {
		respondError(w, http.StatusBadRequest, "donation listing must have asking_price 0")
		return
	}
	if nextCat <= 0 {
		respondError(w, http.StatusBadRequest, "invalid category_id")
		return
	}

	var setClauses []string
	var args []interface{}

	colMap := map[string]string{
		"title": "Title", "description": "Description", "asking_price": "AskingPrice",
		"is_negotiable": "IsNegotiable", "condition": "`Condition`",
		"status": "Status", "category_id": "CategoryID", "is_donation": "IsDonation",
	}
	for jsonKey, col := range colMap {
		if v, ok := patch[jsonKey]; ok {
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

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()

	if err := mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx)); err != nil {
		respondError(w, http.StatusInternalServerError, "session vars failed")
		return
	}

	_, err = tx.ExecContext(ctx, "UPDATE Listing SET "+join(setClauses, ", ")+" WHERE ListingID = ?", args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "update failed: "+err.Error())
		return
	}
	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	l, err := loadListingWithImages(ctx, listingID, mw.GetMemberID(ctx))
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to load listing after update")
		return
	}
	respondJSON(w, http.StatusOK, l)
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
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
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
	if err := mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx)); err != nil {
		respondError(w, http.StatusInternalServerError, "session vars failed")
		return
	}

	// Read optional reason from body
	var body struct {
		Reason string `json:"reason"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body)
	reason := body.Reason
	if reason == "" {
		reason = "Listing withdrawn by seller"
	}

	// Collect all submitted offers so we can create Declined transactions
	type submittedOffer struct{ offerID, buyerID, sellerID int; price float64 }
	var affectedOffers []submittedOffer
	offerRows, err := tx.QueryContext(ctx,
		`SELECT o.OfferID, o.BuyerID, l.SellerID, o.OfferedPrice
         FROM Offer o JOIN Listing l ON l.ListingID = o.ListingID
         WHERE o.ListingID = ? AND o.OfferStatus = 'Submitted'`, listingID)
	if err == nil {
		for offerRows.Next() {
			var ao submittedOffer
			_ = offerRows.Scan(&ao.offerID, &ao.buyerID, &ao.sellerID, &ao.price)
			affectedOffers = append(affectedOffers, ao)
		}
		offerRows.Close()
	}

	_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Withdrawn', LastModifiedDate = NOW() WHERE ListingID = ?`, listingID)
	_, _ = tx.ExecContext(ctx,
		`UPDATE Offer SET OfferStatus = 'Withdrawn', Reason = ?, ResponseDate = NOW()
         WHERE ListingID = ? AND OfferStatus = 'Submitted'`, reason, listingID)

	// Create a Declined transaction for each affected offer
	for _, ao := range affectedOffers {
		_, _ = tx.ExecContext(ctx,
			`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice, Status, Reason)
             VALUES (?, ?, ?, ?, ?, 'Declined', ?)`,
			listingID, ao.sellerID, ao.buyerID, ao.offerID, ao.price, reason)
	}

	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"message": "listing withdrawn"})
}

// POST /api/v1/listings/:id/images — own or admin, upload image (multipart)
func AddListingImage(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	fmt.Println(listingID)
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
	fmt.Println(sellerUserID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	var imageCount int
	_ = appdb.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM ListingImage WHERE ListingID = ?", listingID).Scan(&imageCount)
	if imageCount >= maxImagesPerListing {
		respondError(w, http.StatusBadRequest, "maximum 10 images per listing")
		return
	}

	if err := r.ParseMultipartForm(maxImageSize + 1024); err != nil { // maxMemory for form fields
		respondError(w, http.StatusBadRequest, "invalid multipart form or file too large")
		return
	}
	file, header, err := r.FormFile("image")
	if err != nil {
		respondError(w, http.StatusBadRequest, "image file required (field name: image)")
		return
	}
	defer file.Close()

	ct := header.Header.Get("Content-Type")
	if _, ok := allowedImageTypes[ct]; !ok {
		respondError(w, http.StatusBadRequest, "invalid image type; use JPEG, PNG, WebP, or GIF")
		return
	}
	if header.Size > maxImageSize {
		respondError(w, http.StatusBadRequest, "image too large (max 5MB)")
		return
	}

	ext := ".jpg"
	switch ct {
	case "image/png":
		ext = ".png"
	case "image/webp":
		ext = ".webp"
	case "image/gif":
		ext = ".gif"
	}
	baseDir := os.Getenv("UPLOADS_DIR")
	if baseDir == "" {
		baseDir = "./uploads"
	}
	relDir := filepath.Join("listings", strconv.Itoa(listingID))
	absDir := filepath.Join(baseDir, relDir)
	if err := os.MkdirAll(absDir, 0755); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create upload directory")
		return
	}
	filename := uuid.New().String() + ext
	absPath := filepath.Join(absDir, filename)
	dst, err := os.Create(absPath)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to save file")
		return
	}
	defer dst.Close()
	if _, err := io.Copy(dst, file); err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "failed to write file")
		return
	}
	storedPath := filepath.Join(relDir, filename)
	storedPath = filepath.ToSlash(storedPath)

	var nextOrder int
	_ = appdb.DB.QueryRowContext(ctx, "SELECT COALESCE(MAX(ImageOrder), 0) + 1 FROM ListingImage WHERE ListingID = ?", listingID).Scan(&nextOrder)

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	if err := mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx)); err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "session vars failed")
		return
	}
	res, err := tx.ExecContext(ctx,
		"INSERT INTO ListingImage (ListingID, ImageURL, ImageOrder) VALUES (?, ?, ?)",
		listingID, storedPath, nextOrder)
	if err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "insert failed: "+err.Error())
		return
	}
	imgID, _ := res.LastInsertId()
	if err := tx.Commit(); err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}
	img := models.ListingImage{
		ImageID:    int(imgID),
		ListingID:  listingID,
		ImageURL:   imagePathToURL(storedPath),
		ImageOrder: nextOrder,
	}
	respondJSON(w, http.StatusCreated, img)
}

// DELETE /api/v1/listings/:id/images/:imageId — own or admin, remove image
func DeleteListingImage(w http.ResponseWriter, r *http.Request) {
	listingID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid listing id")
		return
	}
	imageID, err := urlParamInt(r, "imageId")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid image id")
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
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	var storedPath string
	err = appdb.DB.QueryRowContext(ctx,
		"SELECT ImageURL FROM ListingImage WHERE ImageID = ? AND ListingID = ?",
		imageID, listingID).Scan(&storedPath)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "image not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}

	baseDir := os.Getenv("UPLOADS_DIR")
	if baseDir == "" {
		baseDir = "./uploads"
	}
	absPath := filepath.Join(baseDir, filepath.FromSlash(storedPath))
	_ = os.Remove(absPath)

	_, err = appdb.DB.ExecContext(ctx,
		"DELETE FROM ListingImage WHERE ImageID = ? AND ListingID = ?", imageID, listingID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "delete failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"message": "image removed"})
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
