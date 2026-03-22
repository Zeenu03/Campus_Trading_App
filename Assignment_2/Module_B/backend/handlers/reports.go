package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/reports — admin
func ListReports(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)
	status := r.URL.Query().Get("status")

	baseWhere := " WHERE 1=1"
	var args []interface{}
	if status != "" {
		baseWhere += " AND r.Status = ?"
		args = append(args, status)
	}

	var total int
	_ = appdb.DB.QueryRowContext(r.Context(), "SELECT COUNT(*) FROM Report r"+baseWhere, args...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	query := `SELECT r.ReportID, r.ReporterID, m.Name, r.ReportedMemberID, r.ReportedListingID,
               r.ReportType, r.Description, r.Status, r.SubmittedDate, r.ResolvedDate,
               r.ResolvedByAdminID, r.Resolution
              FROM Report r JOIN Member m ON m.MemberID = r.ReporterID` +
		baseWhere + " ORDER BY r.SubmittedDate DESC LIMIT ? OFFSET ?"
	args = append(args, pageSize, offset)

	rows, err := appdb.DB.QueryContext(r.Context(), query, args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var reports []models.Report
	for rows.Next() {
		var rpt models.Report
		_ = rows.Scan(&rpt.ReportID, &rpt.ReporterID, &rpt.ReporterName,
			&rpt.ReportedMemberID, &rpt.ReportedListingID,
			&rpt.ReportType, &rpt.Description, &rpt.Status, &rpt.SubmittedDate,
			&rpt.ResolvedDate, &rpt.ResolvedByAdminID, &rpt.Resolution)
		reports = append(reports, rpt)
	}
	if reports == nil {
		reports = []models.Report{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: reports, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// POST /api/v1/reports — auth
func CreateReport(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	var body struct {
		ReportedMemberID  *int    `json:"reported_member_id"`
		ReportedListingID *int    `json:"reported_listing_id"`
		ReportType        string  `json:"report_type"`
		Description       string  `json:"description"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.ReportedMemberID == nil && body.ReportedListingID == nil {
		respondError(w, http.StatusBadRequest, "must specify reported_member_id or reported_listing_id")
		return
	}
	if body.ReportType == "" || body.Description == "" {
		respondError(w, http.StatusBadRequest, "report_type and description required")
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
		`INSERT INTO Report (ReporterID, ReportedMemberID, ReportedListingID, ReportType, Description)
         VALUES (?, ?, ?, ?, ?)`,
		memberID, body.ReportedMemberID, body.ReportedListingID, body.ReportType, body.Description)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "report creation failed")
		return
	}
	reportID, _ := res.LastInsertId()
	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"report_id": reportID, "message": "report filed"})
}

// PUT /api/v1/reports/:id/resolve — admin
func ResolveReport(w http.ResponseWriter, r *http.Request) {
	reportID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid report id")
		return
	}
	ctx := r.Context()

	// Get admin ID for the current user
	var adminID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT AdminID FROM Administrator WHERE user_id = ?`, mw.GetUserID(ctx),
	).Scan(&adminID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusForbidden, "admin account not found")
		return
	}

	var body struct {
		Resolution string `json:"resolution"`
		Status     string `json:"status"` // Resolved or Dismissed
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	if body.Resolution == "" {
		respondError(w, http.StatusBadRequest, "resolution text required")
		return
	}
	if body.Status == "" {
		body.Status = "Resolved"
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()
	_ = mw.SetSessionVars(tx, mw.GetSessionID(ctx), mw.GetUserID(ctx))

	_, err = tx.ExecContext(ctx,
		`UPDATE Report SET Status = ?, Resolution = ?, ResolvedByAdminID = ?, ResolvedDate = NOW()
         WHERE ReportID = ?`,
		body.Status, body.Resolution, adminID, reportID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "resolve failed")
		return
	}
	_ = tx.Commit()
	respondJSON(w, http.StatusOK, map[string]string{"message": "report " + body.Status})
}
