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
	"sort"
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

func hasListingWishRequestTable(ctx context.Context) bool {
	var count int
	err := appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*)
		   FROM information_schema.TABLES
		  WHERE TABLE_SCHEMA = DATABASE()
		    AND TABLE_NAME = 'ListingWishRequest'`).Scan(&count)
	return err == nil && count > 0
}

type listingRow struct {
	ListingID        int
	SellerID         int
	CategoryID       int
	Title            string
	Description      *string
	AskingPrice      float64
	IsNegotiable     bool
	Condition        *string
	Status           string
	CreatedDate      time.Time
	LastModifiedDate *time.Time
	WishRequestID    *int
}

func fetchListingRowsAcrossShards(ctx context.Context, baseWhere string, args []interface{}) ([]listingRow, error) {
	query := `SELECT ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable,
	                 ` + "`Condition`" + `, Status, CreatedDate, LastModifiedDate, WishRequestID
	            FROM Listing l` + baseWhere

	var rows []listingRow
	for _, shardDB := range appdb.AllShardConnections() {
		shardRows, err := shardDB.QueryContext(ctx, query, args...)
		if err != nil {
			return nil, err
		}
		for shardRows.Next() {
			var row listingRow
			if err := shardRows.Scan(&row.ListingID, &row.SellerID, &row.CategoryID, &row.Title, &row.Description,
				&row.AskingPrice, &row.IsNegotiable, &row.Condition, &row.Status, &row.CreatedDate,
				&row.LastModifiedDate, &row.WishRequestID); err != nil {
				shardRows.Close()
				return nil, err
			}
			rows = append(rows, row)
		}
		shardRows.Close()
	}
	return rows, nil
}

func sortListingRows(rows []listingRow, sortKey string) {
	sort.SliceStable(rows, func(i, j int) bool {
		a := rows[i]
		b := rows[j]
		switch sortKey {
		case "oldest":
			return a.CreatedDate.Before(b.CreatedDate)
		case "price_asc":
			return a.AskingPrice < b.AskingPrice
		case "price_desc":
			return a.AskingPrice > b.AskingPrice
		default:
			return a.CreatedDate.After(b.CreatedDate)
		}
	})
}

func memberNameByID(ctx context.Context, memberID int) string {
	var name string
	_ = centralShardDB().QueryRowContext(ctx, `SELECT Name FROM Member WHERE MemberID = ?`, memberID).Scan(&name)
	return name
}

func categoryNameByID(ctx context.Context, categoryID int) string {
	var name string
	_ = replicatedShardDB().QueryRowContext(ctx, `SELECT CategoryName FROM Category WHERE CategoryID = ?`, categoryID).Scan(&name)
	return name
}

func loadWishRequestSummaryByID(ctx context.Context, wishRequestID int) (*models.WishRequestSummary, error) {
	var wr models.WishRequestSummary
	var minBudget, maxBudget *float64
	err := wishRequestShardDB(wishRequestID).QueryRowContext(ctx,
		`SELECT w.WishRequestID, w.RequesterID, m.Name, c.CategoryName,
		        w.ItemDescription, w.MinBudget, w.MaxBudget, w.Status
		   FROM WishRequest w
		   JOIN Category c ON c.CategoryID = w.CategoryID
		  WHERE w.WishRequestID = ?`, wishRequestID,
	).Scan(&wr.WishRequestID, &wr.RequesterID, &wr.RequesterName, &wr.CategoryName,
		&wr.ItemDescription, &minBudget, &maxBudget, &wr.Status)
	if err != nil {
		return nil, err
	}
	wr.MinBudget = minBudget
	wr.MaxBudget = maxBudget
	return &wr, nil
}

func loadListingWishRequestIDs(ctx context.Context, listingID int) []int {
	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT WishRequestID FROM ListingWishRequest WHERE ListingID = ? ORDER BY WishRequestID`, listingID)
	if err != nil {
		return nil
	}
	defer rows.Close()

	var ids []int
	for rows.Next() {
		var wishRequestID int
		if err := rows.Scan(&wishRequestID); err == nil {
			ids = append(ids, wishRequestID)
		}
	}
	return ids
}

func loadWatchlistCount(ctx context.Context, listingID int) int {
	shardDB := listingShardDB(listingID)
	var count int
	_ = shardDB.QueryRowContext(ctx, `SELECT COUNT(*) FROM Watchlist WHERE ListingID = ?`, listingID).Scan(&count)
	return count
}

func loadMyWatchlistID(ctx context.Context, listingID int, memberID int) *int {
	shardDB := listingShardDB(listingID)
	var watchlistID int
	err := shardDB.QueryRowContext(ctx,
		`SELECT WatchlistID FROM Watchlist WHERE ListingID = ? AND MemberID = ?`, listingID, memberID).Scan(&watchlistID)
	if err != nil {
		return nil
	}
	return &watchlistID
}

// GET /api/v1/listings — auth, browse with filters
func ListListings(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)
	status := r.URL.Query().Get("status")
	sort := r.URL.Query().Get("sort") // newest, oldest, price_asc, price_desc
	titleQ := strings.TrimSpace(r.URL.Query().Get("q"))
	minPriceStr := strings.TrimSpace(r.URL.Query().Get("min_price"))
	maxPriceStr := strings.TrimSpace(r.URL.Query().Get("max_price"))

	if status == "" {
		status = "Listed"
	}

	baseWhere := " WHERE l.Status = ?"
	args := []interface{}{status}

	if titleQ != "" {
		baseWhere += " AND l.Title LIKE ?"
		args = append(args, "%"+titleQ+"%")
	}
	if minPriceStr != "" {
		if v, err := strconv.ParseFloat(minPriceStr, 64); err == nil {
			baseWhere += " AND l.AskingPrice >= ?"
			args = append(args, v)
		}
	}
	if maxPriceStr != "" {
		if v, err := strconv.ParseFloat(maxPriceStr, 64); err == nil {
			baseWhere += " AND l.AskingPrice <= ?"
			args = append(args, v)
		}
	}

	legacyCat := strings.TrimSpace(r.URL.Query().Get("category"))
	catIDs := listingFilterCategoryIDs(r.URL.Query()["category_id"], legacyCat)
	if len(catIDs) > 0 {
		baseWhere += " AND l.CategoryID IN (" + strings.Repeat("?,", len(catIDs)-1) + "?)"
		for _, id := range catIDs {
			args = append(args, id)
		}
	}

	conds := listingFilterConditions(r.URL.Query()["condition"])
	if len(conds) > 0 {
		baseWhere += " AND l.Condition IN (" + strings.Repeat("?,", len(conds)-1) + "?)"
		for _, c := range conds {
			args = append(args, c)
		}
	}

	rows, err := fetchListingRowsAcrossShards(r.Context(), baseWhere, args)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	sortListingRows(rows, sort)
	total := len(rows)
	offset, totalPages := paginate(page, pageSize, total)
	if offset > total {
		offset = total
	}
	end := offset + pageSize
	if end > total {
		end = total
	}
	pageRows := rows[offset:end]

	listings := make([]models.Listing, 0, len(pageRows))
	for _, row := range pageRows {
		l := models.Listing{
			ListingID:        row.ListingID,
			SellerID:         row.SellerID,
			SellerName:       memberNameByID(r.Context(), row.SellerID),
			CategoryID:       row.CategoryID,
			CategoryName:     categoryNameByID(r.Context(), row.CategoryID),
			Title:            row.Title,
			Description:      row.Description,
			AskingPrice:      row.AskingPrice,
			IsNegotiable:     row.IsNegotiable,
			Condition:        row.Condition,
			Status:           row.Status,
			CreatedDate:      row.CreatedDate,
			LastModifiedDate: row.LastModifiedDate,
			WishRequestID:    row.WishRequestID,
			WatcherCount:     loadWatchlistCount(r.Context(), row.ListingID),
			MyWatchlistID:    loadMyWatchlistID(r.Context(), row.ListingID, mw.GetMemberID(r.Context())),
		}
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
	expireDueWishRequests(ctx)

	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var body struct {
		CategoryID     int     `json:"category_id"`
		Title          string  `json:"title"`
		Description    *string `json:"description"`
		AskingPrice    float64 `json:"asking_price"`
		IsNegotiable   bool    `json:"is_negotiable"`
		Condition      *string `json:"condition"`
		WishRequestID  *int    `json:"wish_request_id"`
		WishRequestIDs []int   `json:"wish_request_ids"`
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

	selectedWishRequestIDs := make([]int, 0, len(body.WishRequestIDs))
	seenWishRequest := map[int]struct{}{}
	for _, id := range body.WishRequestIDs {
		if id <= 0 {
			respondError(w, http.StatusBadRequest, "wish_request_ids must contain positive integers")
			return
		}
		if _, seen := seenWishRequest[id]; seen {
			continue
		}
		seenWishRequest[id] = struct{}{}
		selectedWishRequestIDs = append(selectedWishRequestIDs, id)
	}
	if len(selectedWishRequestIDs) == 0 && body.WishRequestID != nil && *body.WishRequestID > 0 {
		selectedWishRequestIDs = append(selectedWishRequestIDs, *body.WishRequestID)
	}
	if len(selectedWishRequestIDs) > 1 {
		respondError(w, http.StatusBadRequest, "only one wish request can be linked to a listing")
		return
	}
	// Enforce: max 2 active listings if 0 completed transactions.
	var completedTx int
	for _, shardDB := range appdb.AllShardConnections() {
		var shardCompleted int
		_ = shardDB.QueryRowContext(ctx,
			`SELECT COUNT(*) FROM Transaction WHERE (SellerID = ? OR BuyerID = ?) AND Status = 'Completed'`,
			memberID, memberID).Scan(&shardCompleted)
		completedTx += shardCompleted
	}

	if completedTx == 0 {
		var activeListings int
		rows, err := fetchListingRowsAcrossShards(ctx, " WHERE l.SellerID = ? AND l.Status = 'Listed'", []interface{}{memberID})
		if err != nil {
			respondError(w, http.StatusInternalServerError, "listing count failed")
			return
		}
		activeListings = len(rows)
		if activeListings >= 2 {
			respondError(w, http.StatusForbidden, "max 2 active listings allowed until you complete a transaction")
			return
		}
	}

	listingID, err := nextRecordID(ctx, "Listing", "ListingID")
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to allocate listing id")
		return
	}
	listingDB := listingShardDB(listingID)
	tx, err := listingDB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()

	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	legacyWishRequestID := body.WishRequestID
	if len(selectedWishRequestIDs) > 0 {
		legacyWishRequestID = &selectedWishRequestIDs[0]
	}

	res, err := tx.ExecContext(ctx,
		"INSERT INTO Listing (ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable, "+
			"`Condition`, WishRequestID) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
		listingID, memberID, body.CategoryID, body.Title, body.Description, body.AskingPrice, body.IsNegotiable,
		body.Condition, legacyWishRequestID,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "listing creation failed: "+err.Error())
		return
	}
	_ = res

	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	if len(selectedWishRequestIDs) > 0 {
		inClause := strings.Repeat("?,", len(selectedWishRequestIDs)-1) + "?"
		wishArgs := make([]interface{}, 0, len(selectedWishRequestIDs))
		for _, wrID := range selectedWishRequestIDs {
			wishArgs = append(wishArgs, wrID)
		}

		rows, err := appdb.DB.QueryContext(ctx,
			`SELECT WishRequestID, RequesterID
			   FROM WishRequest
			  WHERE WishRequestID IN (`+inClause+`)
			    AND Status = 'Active'
			    AND (NeededByDate IS NULL OR NeededByDate >= CURDATE())`,
			wishArgs...)
		if err == nil {
			requesterByWishID := map[int]int{}
			for rows.Next() {
				var wrID, requesterID int
				if err := rows.Scan(&wrID, &requesterID); err == nil {
					requesterByWishID[wrID] = requesterID
				}
			}
			rows.Close()

			if len(requesterByWishID) == len(selectedWishRequestIDs) {
				if hasWishRequestFulfilledDateColumn(ctx) {
					updateArgs := append([]interface{}{time.Now()}, wishArgs...)
					_, _ = appdb.DB.ExecContext(ctx,
						`UPDATE WishRequest
						    SET Status = 'Fulfilled', FulfilledDate = ?
						  WHERE WishRequestID IN (`+inClause+`) AND Status = 'Active'`,
						updateArgs...)
				} else {
					_, _ = appdb.DB.ExecContext(ctx,
						`UPDATE WishRequest
						    SET Status = 'Fulfilled'
						  WHERE WishRequestID IN (`+inClause+`) AND Status = 'Active'`,
						wishArgs...)
				}

				if hasListingWishRequestTable(ctx) {
					for _, wrID := range selectedWishRequestIDs {
						_, _ = appdb.DB.ExecContext(ctx,
							`INSERT INTO ListingWishRequest (ListingID, WishRequestID) VALUES (?, ?)`,
							listingID, wrID)
					}
				}

				for _, wrID := range selectedWishRequestIDs {
					requesterID := requesterByWishID[wrID]
					if requesterID != memberID {
						matchMsg := fmt.Sprintf("Your wish request was fulfilled by new listing \"%s\".", body.Title)
						if len(matchMsg) > 1000 {
							matchMsg = matchMsg[:997] + "..."
						}
						_, _ = appdb.DB.ExecContext(ctx,
							`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID)
							 VALUES (?, 'WishRequestMatched', 'Wish request fulfilled', ?, ?)`,
							requesterID, matchMsg, listingID)
					}
				}
			}
		}
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
	shardDB := listingShardDB(listingID)

	err := shardDB.QueryRowContext(ctx,
		`SELECT ListingID, SellerID, CategoryID, Title, Description, AskingPrice, IsNegotiable,
		        `+"`Condition`"+`, Status, CreatedDate, LastModifiedDate, WishRequestID
	      FROM Listing
	     WHERE ListingID = ?`, listingID,
	).Scan(&l.ListingID, &l.SellerID, &l.CategoryID, &l.Title, &desc, &l.AskingPrice, &l.IsNegotiable,
		&cond, &l.Status, &l.CreatedDate, &lastMod, &wishReqID)
	if err == sql.ErrNoRows {
		return nil, err
	}
	if err != nil {
		return nil, err
	}
	l.SellerName = memberNameByID(ctx, l.SellerID)
	l.CategoryName = categoryNameByID(ctx, l.CategoryID)
	l.Description = desc
	l.Condition = cond
	l.LastModifiedDate = lastMod
	l.WishRequestID = wishReqID

	l.WishRequestIDs = loadListingWishRequestIDs(ctx, listingID)

	linkedWishID := 0
	if l.WishRequestID != nil && *l.WishRequestID > 0 {
		linkedWishID = *l.WishRequestID
	} else if len(l.WishRequestIDs) > 0 {
		linkedWishID = l.WishRequestIDs[0]
	}
	if linkedWishID > 0 {
		if wr, err := loadWishRequestSummaryByID(ctx, linkedWishID); err == nil {
			l.LinkedWishRequest = wr
		}
	}

	l.WatcherCount = loadWatchlistCount(ctx, listingID)

	if memberID > 0 {
		l.MyWatchlistID = loadMyWatchlistID(ctx, listingID, memberID)
	}

	imgRows, err := shardDB.QueryContext(ctx,
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
	listingDB := listingShardDB(listingID)

	var sellerID int
	err = listingDB.QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, listingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	var sellerUserID int
	_ = centralShardDB().QueryRowContext(ctx, `SELECT user_id FROM Member WHERE MemberID = ?`, sellerID).Scan(&sellerUserID)
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
		Status       string
	}
	err = listingDB.QueryRowContext(ctx,
		"SELECT Title, Description, AskingPrice, IsNegotiable, `Condition`, CategoryID, Status "+
			"FROM Listing WHERE ListingID = ?", listingID,
	).Scan(&cur.Title, &cur.Description, &cur.AskingPrice, &cur.IsNegotiable,
		&cur.Condition, &cur.CategoryID, &cur.Status)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "load listing failed")
		return
	}

	nextPrice := cur.AskingPrice
	nextCat := cur.CategoryID

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
	if nextCat <= 0 {
		respondError(w, http.StatusBadRequest, "invalid category_id")
		return
	}

	newStatus := cur.Status
	if v, ok := patch["status"]; ok {
		newStatus = v.(string)
	}
	priceDropped := patch["asking_price"] != nil && newStatus == "Listed" && nextPrice < cur.AskingPrice
	statusChanged := patch["status"] != nil && newStatus != cur.Status

	var setClauses []string
	var args []interface{}

	colMap := map[string]string{
		"title": "Title", "description": "Description", "asking_price": "AskingPrice",
		"is_negotiable": "IsNegotiable", "condition": "`Condition`",
		"status": "Status", "category_id": "CategoryID",
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

	tx, err := listingDB.BeginTx(ctx, nil)
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

	if priceDropped || statusChanged {
		wRows, wErr := tx.QueryContext(ctx, `SELECT MemberID FROM Watchlist WHERE ListingID = ?`, listingID)
		if wErr == nil {
			for wRows.Next() {
				var wid int
				if wRows.Scan(&wid) != nil {
					continue
				}
				if priceDropped {
					pdMsg := fmt.Sprintf("A listing on your watchlist now has asking price %.2f (reduced).", nextPrice)
					_, _ = tx.ExecContext(ctx,
						`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID)
						 VALUES (?, 'PriceDropped', 'Price dropped', ?, ?)`,
						wid, pdMsg, listingID)
				}
				if statusChanged {
					scMsg := fmt.Sprintf("A listing on your watchlist changed status to %s.", newStatus)
					_, _ = tx.ExecContext(ctx,
						`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID)
						 VALUES (?, 'StatusChanged', 'Listing status updated', ?, ?)`,
						wid, scMsg, listingID)
				}
			}
			wRows.Close()
		}
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
	listingDB := listingShardDB(listingID)

	var sellerID int
	err = listingDB.QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, listingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	var sellerUserID int
	_ = centralShardDB().QueryRowContext(ctx, `SELECT user_id FROM Member WHERE MemberID = ?`, sellerID).Scan(&sellerUserID)
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	tx, err := listingDB.BeginTx(ctx, nil)
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
	type submittedOffer struct {
		offerID, buyerID, sellerID int
		price                      float64
	}
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

	for _, ao := range affectedOffers {
		resTx, errTx := tx.ExecContext(ctx,
			`INSERT INTO Transaction (ListingID, SellerID, BuyerID, OfferID, AgreedPrice)
             VALUES (?, ?, ?, ?, ?)`,
			listingID, ao.sellerID, ao.buyerID, ao.offerID, ao.price)
		if errTx != nil {
			continue
		}
		withdrawTxID, _ := resTx.LastInsertId()
		withdrawMsg := "The seller withdrew this listing. Your submitted offer was closed."
		_, _ = tx.ExecContext(ctx,
			`INSERT INTO Notification (RecipientID, NotificationType, Title, Message, RelatedListingID, RelatedOfferID, RelatedTransactionID)
			 VALUES (?, 'General', 'Listing withdrawn', ?, ?, ?, ?)`,
			ao.buyerID, withdrawMsg, listingID, ao.offerID, withdrawTxID)
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
	listingDB := listingShardDB(listingID)

	var sellerID int
	err = listingDB.QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, listingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	var sellerUserID int
	_ = centralShardDB().QueryRowContext(ctx, `SELECT user_id FROM Member WHERE MemberID = ?`, sellerID).Scan(&sellerUserID)
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	var imageCount int
	_ = listingDB.QueryRowContext(ctx, "SELECT COUNT(*) FROM ListingImage WHERE ListingID = ?", listingID).Scan(&imageCount)
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

	nextOrder := 1
	_ = listingDB.QueryRowContext(ctx, "SELECT COALESCE(MAX(ImageOrder), 0) + 1 FROM ListingImage WHERE ListingID = ?", listingID).Scan(&nextOrder)

	imgID, err := nextRecordID(ctx, "ListingImage", "ImageID")
	if err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "failed to allocate image id")
		return
	}
	tx, err := listingDB.BeginTx(ctx, nil)
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
		"INSERT INTO ListingImage (ImageID, ListingID, ImageURL, ImageOrder) VALUES (?, ?, ?, ?)",
		imgID, listingID, storedPath, nextOrder)
	if err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "insert failed: "+err.Error())
		return
	}
	_ = res
	if err := tx.Commit(); err != nil {
		os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}
	img := models.ListingImage{
		ImageID:    imgID,
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
	listingDB := listingShardDB(listingID)

	var sellerID int
	err = listingDB.QueryRowContext(ctx,
		`SELECT SellerID FROM Listing WHERE ListingID = ?`, listingID).Scan(&sellerID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "listing not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	var sellerUserID int
	_ = centralShardDB().QueryRowContext(ctx, `SELECT user_id FROM Member WHERE MemberID = ?`, sellerID).Scan(&sellerUserID)
	if !mw.IsOwnerOrAdmin(ctx, sellerUserID) {
		mw.RespondForbidden(w)
		return
	}

	var storedPath string
	err = listingDB.QueryRowContext(ctx,
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

	_, err = listingDB.ExecContext(ctx,
		"DELETE FROM ListingImage WHERE ImageID = ? AND ListingID = ?", imageID, listingID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "delete failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"message": "image removed"})
}

func listingFilterCategoryIDs(fromQuery []string, legacy string) []int {
	var raw []string
	raw = append(raw, fromQuery...)
	if strings.TrimSpace(legacy) != "" {
		raw = append(raw, legacy)
	}
	seen := map[int]struct{}{}
	var out []int
	for _, s := range raw {
		s = strings.TrimSpace(s)
		if s == "" {
			continue
		}
		id, err := strconv.Atoi(s)
		if err != nil || id <= 0 {
			continue
		}
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		out = append(out, id)
	}
	return out
}

func listingFilterConditions(fromQuery []string) []string {
	seen := map[string]struct{}{}
	var out []string
	for _, c := range fromQuery {
		c = strings.TrimSpace(c)
		if c == "" {
			continue
		}
		if _, ok := allowedListingConditions[c]; !ok {
			continue
		}
		if _, dup := seen[c]; dup {
			continue
		}
		seen[c] = struct{}{}
		out = append(out, c)
	}
	return out
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
