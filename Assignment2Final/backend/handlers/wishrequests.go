package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
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
	allowedWishRequestStatuses = map[string]struct{}{
		"Active": {}, "Fulfilled": {}, "Expired": {}, "Cancelled": {},
	}
	maxImagesPerWishRequest = 10
)

func hasWishRequestFulfilledDateColumn(ctx context.Context) bool {
	var count int
	err := appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*)
		   FROM information_schema.COLUMNS
		  WHERE TABLE_SCHEMA = DATABASE()
		    AND TABLE_NAME = 'WishRequest'
		    AND COLUMN_NAME = 'FulfilledDate'`).Scan(&count)
	return err == nil && count > 0
}

func expireDueWishRequests(ctx context.Context) {
	_, _ = appdb.DB.ExecContext(ctx,
		`UPDATE WishRequest
		 SET Status = 'Expired', FulfilledDate = NULL
		 WHERE Status = 'Active'
		   AND NeededByDate IS NOT NULL
		   AND NeededByDate < CURDATE()`)
}

func loadWishRequestWithImages(ctx context.Context, wishRequestID int) (*models.WishRequest, int, error) {
	var wr models.WishRequest
	var requesterUserID int
	var min, max *float64
	var cond *string
	var needed *time.Time
	var details *string
	var fulfilled *time.Time
	hasFulfilledDate := hasWishRequestFulfilledDateColumn(ctx)

	query := `SELECT w.WishRequestID, w.RequesterID, m.user_id, m.Name,
	        w.CategoryID, c.CategoryName, w.ItemDescription,
	        w.MinBudget, w.MaxBudget, w.PreferredCondition,
	        w.NeededByDate, w.AdditionalDetails,
	        w.Status, w.CreatedDate`
	if hasFulfilledDate {
		query += ", w.FulfilledDate"
	}
	query += `
		 FROM WishRequest w
		 JOIN Member m ON m.MemberID = w.RequesterID
		 JOIN Category c ON c.CategoryID = w.CategoryID
		 WHERE w.WishRequestID = ?`

	row := appdb.DB.QueryRowContext(ctx, query, wishRequestID)
	if hasFulfilledDate {
		err := row.Scan(&wr.WishRequestID, &wr.RequesterID, &requesterUserID, &wr.RequesterName,
			&wr.CategoryID, &wr.CategoryName, &wr.ItemDescription,
			&min, &max, &cond,
			&needed, &details,
			&wr.Status, &wr.CreatedDate, &fulfilled)
		if err != nil {
			return nil, 0, err
		}
	} else {
		err := row.Scan(&wr.WishRequestID, &wr.RequesterID, &requesterUserID, &wr.RequesterName,
			&wr.CategoryID, &wr.CategoryName, &wr.ItemDescription,
			&min, &max, &cond,
			&needed, &details,
			&wr.Status, &wr.CreatedDate)
		if err != nil {
			return nil, 0, err
		}
	}

	wr.MinBudget = min
	wr.MaxBudget = max
	wr.PreferredCondition = cond
	wr.NeededByDate = needed
	wr.AdditionalDetails = details
	wr.FulfilledDate = fulfilled

	imgRows, err := appdb.DB.QueryContext(ctx,
		`SELECT ImageID, ImageURL, ImageOrder, UploadedDate
		 FROM WishRequestImage WHERE WishRequestID = ? ORDER BY ImageOrder`, wishRequestID)
	if err != nil {
		return nil, 0, err
	}
	defer imgRows.Close()

	for imgRows.Next() {
		var img models.WishRequestImage
		var storedPath string
		if err := imgRows.Scan(&img.ImageID, &storedPath, &img.ImageOrder, &img.UploadedDate); err != nil {
			return nil, 0, err
		}
		img.WishRequestID = wishRequestID
		img.ImageURL = imagePathToURL(storedPath)
		wr.Images = append(wr.Images, img)
	}

	if wr.Images == nil {
		wr.Images = []models.WishRequestImage{}
	}

	var linked models.ListingSummary
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT l.ListingID, l.SellerID, m.Name, l.Title, l.AskingPrice, l.Status
		   FROM ListingWishRequest lw
		   JOIN Listing l ON l.ListingID = lw.ListingID
		   JOIN Member m ON m.MemberID = l.SellerID
		  WHERE lw.WishRequestID = ?
		  ORDER BY lw.LinkedDate DESC
		  LIMIT 1`, wishRequestID,
	).Scan(&linked.ListingID, &linked.SellerID, &linked.SellerName, &linked.Title, &linked.AskingPrice, &linked.Status)
	if err == nil {
		wr.LinkedListing = &linked
	} else {
		err = appdb.DB.QueryRowContext(ctx,
			`SELECT l.ListingID, l.SellerID, m.Name, l.Title, l.AskingPrice, l.Status
			   FROM Listing l
			   JOIN Member m ON m.MemberID = l.SellerID
			  WHERE l.WishRequestID = ?
			  ORDER BY l.CreatedDate DESC
			  LIMIT 1`, wishRequestID,
		).Scan(&linked.ListingID, &linked.SellerID, &linked.SellerName, &linked.Title, &linked.AskingPrice, &linked.Status)
		if err == nil {
			wr.LinkedListing = &linked
		}
	}

	return &wr, requesterUserID, nil
}

// GET /api/v1/wishrequests — auth, browse active
func ListWishRequests(w http.ResponseWriter, r *http.Request) {
	expireDueWishRequests(r.Context())

	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)
	sort := strings.TrimSpace(r.URL.Query().Get("sort"))
	titleQ := strings.TrimSpace(r.URL.Query().Get("q"))
	minBudgetStr := strings.TrimSpace(r.URL.Query().Get("min_budget"))
	maxBudgetStr := strings.TrimSpace(r.URL.Query().Get("max_budget"))

	baseWhere := " WHERE w.Status = 'Active'"
	args := []interface{}{}

	if titleQ != "" {
		baseWhere += " AND w.ItemDescription LIKE ?"
		args = append(args, "%"+titleQ+"%")
	}

	if minBudgetStr != "" {
		if v, err := strconv.ParseFloat(minBudgetStr, 64); err == nil {
			baseWhere += " AND (w.MaxBudget IS NULL OR w.MaxBudget >= ?)"
			args = append(args, v)
		}
	}
	if maxBudgetStr != "" {
		if v, err := strconv.ParseFloat(maxBudgetStr, 64); err == nil {
			baseWhere += " AND (w.MinBudget IS NULL OR w.MinBudget <= ?)"
			args = append(args, v)
		}
	}

	legacyCat := strings.TrimSpace(r.URL.Query().Get("category"))
	catIDs := listingFilterCategoryIDs(r.URL.Query()["category_id"], legacyCat)
	if len(catIDs) > 0 {
		baseWhere += " AND w.CategoryID IN (" + strings.Repeat("?,", len(catIDs)-1) + "?)"
		for _, id := range catIDs {
			args = append(args, id)
		}
	}

	conds := listingFilterConditions(r.URL.Query()["condition"])
	if len(conds) > 0 {
		baseWhere += " AND w.PreferredCondition IN (" + strings.Repeat("?,", len(conds)-1) + "?)"
		for _, c := range conds {
			args = append(args, c)
		}
	}

	var total int
	_ = appdb.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM WishRequest w"+baseWhere, args...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)
	orderBy := " ORDER BY w.CreatedDate DESC"
	switch sort {
	case "oldest":
		orderBy = " ORDER BY w.CreatedDate ASC"
	case "budget_asc":
		orderBy = " ORDER BY COALESCE((w.MinBudget + w.MaxBudget)/2, w.MinBudget, w.MaxBudget, 0) ASC"
	case "budget_desc":
		orderBy = " ORDER BY COALESCE((w.MinBudget + w.MaxBudget)/2, w.MinBudget, w.MaxBudget, 0) DESC"
	}

	queryArgs := append([]interface{}{}, args...)
	queryArgs = append(queryArgs, pageSize, offset)

	rows, err := appdb.DB.QueryContext(r.Context(),
		`SELECT w.WishRequestID, w.RequesterID, m.Name, w.CategoryID, c.CategoryName,
	             w.ItemDescription, w.MinBudget, w.MaxBudget, w.PreferredCondition,
	             w.Status, w.CreatedDate,
	             i.ImageID, i.ImageURL, i.ImageOrder
	          FROM WishRequest w
	          JOIN Member m ON m.MemberID = w.RequesterID
	          JOIN Category c ON c.CategoryID = w.CategoryID
	          LEFT JOIN WishRequestImage i
	            ON i.WishRequestID = w.WishRequestID
	           AND i.ImageOrder = (
	             SELECT MIN(i2.ImageOrder)
	             FROM WishRequestImage i2
	             WHERE i2.WishRequestID = w.WishRequestID
	           )`+baseWhere+orderBy+` LIMIT ? OFFSET ?`, queryArgs...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var wrs []models.WishRequest
	for rows.Next() {
		var wr models.WishRequest
		var min, max *float64
		var cond *string
		var imgID *int
		var imgURL *string
		var imgOrder *int
		_ = rows.Scan(&wr.WishRequestID, &wr.RequesterID, &wr.RequesterName, &wr.CategoryID, &wr.CategoryName,
			&wr.ItemDescription, &min, &max, &cond, &wr.Status, &wr.CreatedDate,
			&imgID, &imgURL, &imgOrder)
		wr.MinBudget = min
		wr.MaxBudget = max
		wr.PreferredCondition = cond
		if imgID != nil && imgURL != nil && imgOrder != nil {
			wr.Images = []models.WishRequestImage{{
				ImageID:       *imgID,
				WishRequestID: wr.WishRequestID,
				ImageURL:      imagePathToURL(*imgURL),
				ImageOrder:    *imgOrder,
			}}
		}
		wrs = append(wrs, wr)
	}
	if wrs == nil {
		wrs = []models.WishRequest{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: wrs, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// POST /api/v1/wishrequests — member
func CreateWishRequest(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	expireDueWishRequests(ctx)

	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	// Enforce max 5 active wish requests
	var activeCount int
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM WishRequest WHERE RequesterID = ? AND Status = 'Active'`,
		memberID).Scan(&activeCount)
	if activeCount >= 5 {
		respondError(w, http.StatusConflict, "maximum 5 active wish requests allowed")
		return
	}

	var body struct {
		CategoryID         int      `json:"category_id"`
		ItemDescription    string   `json:"item_description"`
		MinBudget          *float64 `json:"min_budget"`
		MaxBudget          *float64 `json:"max_budget"`
		PreferredCondition *string  `json:"preferred_condition"`
		NeededByDate       *string  `json:"needed_by_date"`
		AdditionalDetails  *string  `json:"additional_details"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.CategoryID <= 0 {
		respondError(w, http.StatusBadRequest, "category_id required")
		return
	}
	body.ItemDescription = strings.TrimSpace(body.ItemDescription)
	if body.ItemDescription == "" {
		respondError(w, http.StatusBadRequest, "item_description is required")
		return
	}
	if utf8.RuneCountInString(body.ItemDescription) > 500 {
		respondError(w, http.StatusBadRequest, "item_description too long (max 500 characters)")
		return
	}
	if body.MinBudget != nil && body.MaxBudget != nil && *body.MaxBudget < *body.MinBudget {
		respondError(w, http.StatusBadRequest, "max_budget must be >= min_budget")
		return
	}
	if body.PreferredCondition != nil {
		v := strings.TrimSpace(*body.PreferredCondition)
		if v == "" {
			body.PreferredCondition = nil
		} else {
			if _, ok := allowedListingConditions[v]; !ok {
				respondError(w, http.StatusBadRequest, "invalid preferred_condition")
				return
			}
			body.PreferredCondition = &v
		}
	}
	if body.AdditionalDetails != nil {
		v := strings.TrimSpace(*body.AdditionalDetails)
		if v == "" {
			body.AdditionalDetails = nil
		} else if utf8.RuneCountInString(v) > 1000 {
			respondError(w, http.StatusBadRequest, "additional_details too long (max 1000 characters)")
			return
		} else {
			body.AdditionalDetails = &v
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
		`INSERT INTO WishRequest (RequesterID, CategoryID, ItemDescription, MinBudget, MaxBudget, PreferredCondition, NeededByDate, AdditionalDetails)
	         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		memberID, body.CategoryID, body.ItemDescription, body.MinBudget, body.MaxBudget,
		body.PreferredCondition, body.NeededByDate, body.AdditionalDetails)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "wish request creation failed")
		return
	}
	wrID, _ := res.LastInsertId()
	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"wish_request_id": wrID, "message": "wish request posted"})
}

// GET /api/v1/wishrequests/:id — auth, detail
func GetWishRequest(w http.ResponseWriter, r *http.Request) {
	expireDueWishRequests(r.Context())

	wishRequestID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}

	wr, requesterUserID, err := loadWishRequestWithImages(r.Context(), wishRequestID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}

	if wr.Status != "Active" && !mw.IsOwnerOrAdmin(r.Context(), requesterUserID) {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}

	respondJSON(w, http.StatusOK, wr)
}

// PUT /api/v1/wishrequests/:id — own
func UpdateWishRequest(w http.ResponseWriter, r *http.Request) {
	wishRequestID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}
	ctx := r.Context()
	expireDueWishRequests(ctx)

	var requesterUserID int
	var cur struct {
		CategoryID         int
		ItemDescription    string
		MinBudget          sql.NullFloat64
		MaxBudget          sql.NullFloat64
		PreferredCondition sql.NullString
		NeededByDate       sql.NullTime
		AdditionalDetails  sql.NullString
		Status             string
	}

	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id,
		        w.CategoryID, w.ItemDescription, w.MinBudget, w.MaxBudget,
		        w.PreferredCondition, w.NeededByDate, w.AdditionalDetails, w.Status
		 FROM WishRequest w
		 JOIN Member m ON m.MemberID = w.RequesterID
		 WHERE w.WishRequestID = ?`, wishRequestID,
	).Scan(&requesterUserID,
		&cur.CategoryID, &cur.ItemDescription, &cur.MinBudget, &cur.MaxBudget,
		&cur.PreferredCondition, &cur.NeededByDate, &cur.AdditionalDetails, &cur.Status)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, requesterUserID) {
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

	attemptsNonStatusUpdate := false
	for key := range body {
		if key != "status" {
			attemptsNonStatusUpdate = true
			break
		}
	}
	if attemptsNonStatusUpdate && (cur.Status == "Cancelled" || cur.Status == "Fulfilled" || cur.Status == "Expired") {
		respondError(w, http.StatusBadRequest, "only active wish requests can be edited")
		return
	}

	nextCategoryID := cur.CategoryID
	nextDescription := cur.ItemDescription
	nextMinBudget := (*float64)(nil)
	if cur.MinBudget.Valid {
		v := cur.MinBudget.Float64
		nextMinBudget = &v
	}
	nextMaxBudget := (*float64)(nil)
	if cur.MaxBudget.Valid {
		v := cur.MaxBudget.Float64
		nextMaxBudget = &v
	}
	nextStatus := cur.Status

	patch := map[string]interface{}{}

	if v, ok := body["item_description"]; ok {
		s, ok := v.(string)
		if !ok {
			respondError(w, http.StatusBadRequest, "item_description must be a string")
			return
		}
		s = strings.TrimSpace(s)
		if s == "" {
			respondError(w, http.StatusBadRequest, "item_description cannot be empty")
			return
		}
		if utf8.RuneCountInString(s) > 500 {
			respondError(w, http.StatusBadRequest, "item_description too long (max 500 characters)")
			return
		}
		nextDescription = s
		patch["item_description"] = s
	}

	if v, ok := body["category_id"]; ok {
		cid, err := jsonNumToInt(v)
		if err != nil || cid <= 0 {
			respondError(w, http.StatusBadRequest, "invalid category_id")
			return
		}
		nextCategoryID = cid
		patch["category_id"] = cid
	}

	if v, has := body["min_budget"]; has {
		if v == nil {
			nextMinBudget = nil
			patch["min_budget"] = nil
		} else {
			n, err := jsonNumToFloat(v)
			if err != nil {
				respondError(w, http.StatusBadRequest, "invalid min_budget")
				return
			}
			nextMinBudget = &n
			patch["min_budget"] = n
		}
	}

	if v, has := body["max_budget"]; has {
		if v == nil {
			nextMaxBudget = nil
			patch["max_budget"] = nil
		} else {
			n, err := jsonNumToFloat(v)
			if err != nil {
				respondError(w, http.StatusBadRequest, "invalid max_budget")
				return
			}
			nextMaxBudget = &n
			patch["max_budget"] = n
		}
	}

	if v, has := body["preferred_condition"]; has {
		if v == nil {
			patch["preferred_condition"] = nil
		} else if s, ok := v.(string); ok {
			s = strings.TrimSpace(s)
			if s == "" {
				patch["preferred_condition"] = nil
			} else {
				if _, ok := allowedListingConditions[s]; !ok {
					respondError(w, http.StatusBadRequest, "invalid preferred_condition")
					return
				}
				patch["preferred_condition"] = s
			}
		} else {
			respondError(w, http.StatusBadRequest, "preferred_condition must be a string or null")
			return
		}
	}

	if v, has := body["needed_by_date"]; has {
		if v == nil {
			patch["needed_by_date"] = nil
		} else if s, ok := v.(string); ok {
			s = strings.TrimSpace(s)
			if s == "" {
				patch["needed_by_date"] = nil
			} else {
				if _, err := time.Parse("2006-01-02", s); err != nil {
					respondError(w, http.StatusBadRequest, "needed_by_date must be YYYY-MM-DD")
					return
				}
				patch["needed_by_date"] = s
			}
		} else {
			respondError(w, http.StatusBadRequest, "needed_by_date must be a string or null")
			return
		}
	}

	if v, has := body["additional_details"]; has {
		if v == nil {
			patch["additional_details"] = nil
		} else if s, ok := v.(string); ok {
			s = strings.TrimSpace(s)
			if s == "" {
				patch["additional_details"] = nil
			} else {
				if utf8.RuneCountInString(s) > 1000 {
					respondError(w, http.StatusBadRequest, "additional_details too long (max 1000 characters)")
					return
				}
				patch["additional_details"] = s
			}
		} else {
			respondError(w, http.StatusBadRequest, "additional_details must be a string or null")
			return
		}
	}

	if v, ok := body["status"]; ok {
		s, ok := v.(string)
		if !ok {
			respondError(w, http.StatusBadRequest, "status must be a string")
			return
		}
		s = strings.TrimSpace(s)
		if _, ok := allowedWishRequestStatuses[s]; !ok {
			respondError(w, http.StatusBadRequest, "invalid status")
			return
		}

		switch cur.Status {
		case "Active":
			if s != "Active" && s != "Cancelled" {
				respondError(w, http.StatusBadRequest, "from Active, only Cancelled is allowed")
				return
			}
		case "Expired":
			if s != "Expired" && s != "Active" && s != "Cancelled" {
				respondError(w, http.StatusBadRequest, "from Expired, only Active (reopen) or Cancelled is allowed")
				return
			}
		case "Cancelled", "Fulfilled":
			if s != cur.Status {
				respondError(w, http.StatusBadRequest, "status cannot be changed for cancelled or fulfilled wish request")
				return
			}
		}

		if s == "Fulfilled" || s == "Expired" {
			respondError(w, http.StatusBadRequest, "this status is managed by the system")
			return
		}

		nextStatus = s
		patch["status"] = s
		if (s == "Active" || s == "Cancelled") && hasWishRequestFulfilledDateColumn(ctx) {
			patch["fulfilled_date"] = nil
		}
	}

	if nextCategoryID <= 0 {
		respondError(w, http.StatusBadRequest, "invalid category_id")
		return
	}
	if strings.TrimSpace(nextDescription) == "" {
		respondError(w, http.StatusBadRequest, "item_description cannot be empty")
		return
	}
	if nextMinBudget != nil && nextMaxBudget != nil && *nextMaxBudget < *nextMinBudget {
		respondError(w, http.StatusBadRequest, "max_budget must be >= min_budget")
		return
	}
	if _, ok := allowedWishRequestStatuses[nextStatus]; !ok {
		respondError(w, http.StatusBadRequest, "invalid status")
		return
	}

	var setClauses []string
	var args []interface{}
	colMap := map[string]string{
		"category_id":         "CategoryID",
		"item_description":    "ItemDescription",
		"min_budget":          "MinBudget",
		"max_budget":          "MaxBudget",
		"preferred_condition": "PreferredCondition",
		"needed_by_date":      "NeededByDate",
		"additional_details":  "AdditionalDetails",
		"status":              "Status",
		"fulfilled_date":      "FulfilledDate",
	}
	for key, col := range colMap {
		if v, ok := patch[key]; ok {
			setClauses = append(setClauses, col+" = ?")
			args = append(args, v)
		}
	}

	if len(setClauses) == 0 {
		respondJSON(w, http.StatusOK, map[string]string{"message": "updated"})
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
	args = append(args, wishRequestID)
	if _, err := tx.ExecContext(ctx,
		"UPDATE WishRequest SET "+join(setClauses, ", ")+" WHERE WishRequestID = ?", args...); err != nil {
		respondError(w, http.StatusInternalServerError, "update failed")
		return
	}
	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{"message": "updated"})
}

// DELETE /api/v1/wishrequests/:id — own or admin
func DeleteWishRequest(w http.ResponseWriter, r *http.Request) {
	wishRequestID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}
	ctx := r.Context()

	var requesterUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id
		 FROM WishRequest w
		 JOIN Member m ON m.MemberID = w.RequesterID
		 WHERE w.WishRequestID = ?`, wishRequestID,
	).Scan(&requesterUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, requesterUserID) {
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
	if _, err := tx.ExecContext(ctx,
		`DELETE FROM WishRequest WHERE WishRequestID = ?`, wishRequestID); err != nil {
		respondError(w, http.StatusInternalServerError, "delete failed")
		return
	}
	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{"message": "wish request deleted"})
}

// POST /api/v1/wishrequests/:id/images — own or admin, upload image
func AddWishRequestImage(w http.ResponseWriter, r *http.Request) {
	wishRequestID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}
	ctx := r.Context()

	var requesterUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id
		 FROM WishRequest w
		 JOIN Member m ON m.MemberID = w.RequesterID
		 WHERE w.WishRequestID = ?`, wishRequestID,
	).Scan(&requesterUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, requesterUserID) {
		mw.RespondForbidden(w)
		return
	}

	var imageCount int
	_ = appdb.DB.QueryRowContext(ctx, "SELECT COUNT(*) FROM WishRequestImage WHERE WishRequestID = ?", wishRequestID).Scan(&imageCount)
	if imageCount >= maxImagesPerWishRequest {
		respondError(w, http.StatusBadRequest, "maximum 10 images per wish request")
		return
	}

	if err := r.ParseMultipartForm(maxImageSize + 1024); err != nil {
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
	relDir := filepath.Join("wishrequests", strconv.Itoa(wishRequestID))
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
		_ = os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "failed to write file")
		return
	}

	storedPath := filepath.ToSlash(filepath.Join(relDir, filename))
	var nextOrder int
	_ = appdb.DB.QueryRowContext(ctx,
		"SELECT COALESCE(MAX(ImageOrder), 0) + 1 FROM WishRequestImage WHERE WishRequestID = ?", wishRequestID).Scan(&nextOrder)

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		_ = os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	if err := mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx)); err != nil {
		_ = os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "session vars failed")
		return
	}
	res, err := tx.ExecContext(ctx,
		"INSERT INTO WishRequestImage (WishRequestID, ImageURL, ImageOrder) VALUES (?, ?, ?)",
		wishRequestID, storedPath, nextOrder)
	if err != nil {
		_ = os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "insert failed: "+err.Error())
		return
	}
	imageID, _ := res.LastInsertId()
	if err := tx.Commit(); err != nil {
		_ = os.Remove(absPath)
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	respondJSON(w, http.StatusCreated, models.WishRequestImage{
		ImageID:       int(imageID),
		WishRequestID: wishRequestID,
		ImageURL:      imagePathToURL(storedPath),
		ImageOrder:    nextOrder,
	})
}

// DELETE /api/v1/wishrequests/:id/images/:imageId — own or admin
func DeleteWishRequestImage(w http.ResponseWriter, r *http.Request) {
	wishRequestID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}
	imageID, err := urlParamInt(r, "imageId")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid image id")
		return
	}
	ctx := r.Context()

	var requesterUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.user_id
		 FROM WishRequest w
		 JOIN Member m ON m.MemberID = w.RequesterID
		 WHERE w.WishRequestID = ?`, wishRequestID,
	).Scan(&requesterUserID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "wish request not found")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "lookup failed")
		return
	}
	if !mw.IsOwnerOrAdmin(ctx, requesterUserID) {
		mw.RespondForbidden(w)
		return
	}

	var storedPath string
	err = appdb.DB.QueryRowContext(ctx,
		"SELECT ImageURL FROM WishRequestImage WHERE ImageID = ? AND WishRequestID = ?",
		imageID, wishRequestID).Scan(&storedPath)
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

	if _, err := appdb.DB.ExecContext(ctx,
		"DELETE FROM WishRequestImage WHERE ImageID = ? AND WishRequestID = ?", imageID, wishRequestID); err != nil {
		respondError(w, http.StatusInternalServerError, "delete failed")
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{"message": "image removed"})
}
