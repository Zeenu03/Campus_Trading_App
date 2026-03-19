package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/wishrequests — auth, browse active
func ListWishRequests(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)

	var total int
	_ = appdb.DB.QueryRowContext(r.Context(),
		`SELECT COUNT(*) FROM WishRequest WHERE Status = 'Active'`).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	rows, err := appdb.DB.QueryContext(r.Context(),
		`SELECT w.WishRequestID, w.RequesterID, m.Name, w.ItemDescription,
             w.MinBudget, w.MaxBudget, w.PreferredCondition, w.Status, w.CreatedDate
          FROM WishRequest w JOIN Member m ON m.MemberID = w.RequesterID
          WHERE w.Status = 'Active'
          ORDER BY w.CreatedDate DESC LIMIT ? OFFSET ?`, pageSize, offset)
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
		_ = rows.Scan(&wr.WishRequestID, &wr.RequesterID, &wr.RequesterName,
			&wr.ItemDescription, &min, &max, &cond, &wr.Status, &wr.CreatedDate)
		wr.MinBudget = min
		wr.MaxBudget = max
		wr.PreferredCondition = cond
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
		ItemDescription   string   `json:"item_description"`
		MinBudget         *float64 `json:"min_budget"`
		MaxBudget         *float64 `json:"max_budget"`
		PreferredCondition *string `json:"preferred_condition"`
		NeededByDate      *string  `json:"needed_by_date"`
		AdditionalDetails *string  `json:"additional_details"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.ItemDescription == "" {
		respondError(w, http.StatusBadRequest, "item_description required")
		return
	}
	if body.MinBudget != nil && body.MaxBudget != nil && *body.MaxBudget < *body.MinBudget {
		respondError(w, http.StatusBadRequest, "max_budget must be >= min_budget")
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
		`INSERT INTO WishRequest (RequesterID, ItemDescription, MinBudget, MaxBudget, PreferredCondition, NeededByDate, AdditionalDetails)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
		memberID, body.ItemDescription, body.MinBudget, body.MaxBudget,
		body.PreferredCondition, body.NeededByDate, body.AdditionalDetails)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "wish request creation failed")
		return
	}
	wrID, _ := res.LastInsertId()
	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"wish_request_id": wrID, "message": "wish request posted"})
}

// PUT /api/v1/wishrequests/:id — own
func UpdateWishRequest(w http.ResponseWriter, r *http.Request) {
	wrID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid wish request id")
		return
	}
	ctx := r.Context()

	var requesterID int
	var requesterUserID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT w.RequesterID, m.user_id FROM WishRequest w JOIN Member m ON m.MemberID = w.RequesterID WHERE w.WishRequestID = ?`, wrID,
	).Scan(&requesterID, &requesterUserID)
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

	// Allow updating status to Cancelled
	if v, ok := body["status"]; ok && v == "Cancelled" {
		tx, err := appdb.DB.BeginTx(ctx, nil)
		if err != nil {
			respondError(w, http.StatusInternalServerError, "tx failed")
			return
		}
		defer tx.Rollback()
		_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))
		_, _ = tx.ExecContext(ctx, `UPDATE WishRequest SET Status = 'Cancelled' WHERE WishRequestID = ?`, wrID)
		_ = tx.Commit()
	}

	var setClauses []string
	var args []interface{}
	fields := map[string]string{
		"item_description":   "ItemDescription",
		"min_budget":         "MinBudget",
		"max_budget":         "MaxBudget",
		"preferred_condition": "PreferredCondition",
		"additional_details": "AdditionalDetails",
	}
	for k, col := range fields {
		if v, ok := body[k]; ok {
			setClauses = append(setClauses, col+" = ?")
			args = append(args, v)
		}
	}
	if len(setClauses) > 0 {
		args = append(args, wrID)
		tx, _ := appdb.DB.BeginTx(ctx, nil)
		_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))
		_, _ = tx.ExecContext(ctx, "UPDATE WishRequest SET "+join(setClauses, ", ")+" WHERE WishRequestID = ?", args...)
		_ = tx.Commit()
	}

	respondJSON(w, http.StatusOK, map[string]string{"message": "updated"})
}
