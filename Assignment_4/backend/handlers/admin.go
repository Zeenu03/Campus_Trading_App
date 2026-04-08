package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
	"campus-trading/sharding"

	"golang.org/x/crypto/bcrypt"
)

// GET /api/v1/admin/audit-log — admin, paginated (newest log_id first)
// Query params:
//
//	page, page_size — pagination
//	source          — "api" (ip_address IS NOT NULL) | "trigger" (ip_address IS NULL)
//	unauthorized    — "1" → session_id IS NULL with write action (INSERT/UPDATE/DELETE)
//	ip              — substring match on ip_address (API rows only have IP)
//	user_id         — exact match on user_id
//	action          — exact match on action (e.g. POST, INSERT)
func GetAuditLog(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 50)

	q := r.URL.Query()
	source := q.Get("source")
	unauthorized := q.Get("unauthorized")
	ipSub := strings.TrimSpace(q.Get("ip"))
	action := strings.TrimSpace(q.Get("action"))
	userIDStr := strings.TrimSpace(q.Get("user_id"))

	where := " WHERE 1=1"
	var args []interface{}

	switch source {
	case "api":
		where += " AND ip_address IS NOT NULL"
	case "trigger":
		where += " AND ip_address IS NULL"
	}

	if unauthorized == "1" {
		where += " AND session_id IS NULL AND action IN ('INSERT','UPDATE','DELETE')"
	}

	if ipSub != "" {
		where += " AND ip_address LIKE ?"
		args = append(args, "%"+ipSub+"%")
	}

	if uid, err := strconv.Atoi(userIDStr); err == nil && userIDStr != "" {
		where += " AND user_id = ?"
		args = append(args, uid)
	}

	if action != "" {
		where += " AND LOWER(action) = LOWER(?)"
		args = append(args, action)
	}

	var total int
	_ = appdb.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM audit_log"+where, args...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	// ORDER BY log_id DESC — newest inserts first; breaks timestamp ties vs triggers.
	queryArgs := append(args, pageSize, offset)
	rows, err := appdb.DB.QueryContext(r.Context(),
		`SELECT log_id, timestamp, session_id, user_id, action, target_table, target_id, ip_address
         FROM audit_log`+where+` ORDER BY log_id DESC LIMIT ? OFFSET ?`, queryArgs...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var logs []models.AuditLog
	for rows.Next() {
		var l models.AuditLog
		_ = rows.Scan(&l.LogID, &l.Timestamp, &l.SessionID, &l.UserID,
			&l.Action, &l.TargetTable, &l.TargetID, &l.IPAddress)
		logs = append(logs, l)
	}
	if logs == nil {
		logs = []models.AuditLog{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: logs, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// GET /api/v1/admin/benchmark — admin, runs EXPLAIN on 5 queries, times them
func Benchmark(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	queries := []struct {
		Name  string
		Query string
		Args  []interface{}
	}{
		{
			Name:  "Q1: Listed listings by date",
			Query: "SELECT * FROM Listing WHERE Status='Listed' ORDER BY CreatedDate DESC LIMIT 20",
		},
		{
			Name:  "Q2: Listings by SellerID",
			Query: "SELECT * FROM Listing WHERE SellerID = ?",
			Args:  []interface{}{1},
		},
		{
			Name:  "Q3: Submitted offers for a listing",
			Query: "SELECT * FROM Offer WHERE ListingID = ? AND OfferStatus = 'Submitted'",
			Args:  []interface{}{1},
		},
		{
			Name:  "Q4: Unread notifications",
			Query: "SELECT * FROM Notification WHERE RecipientID = ? AND IsRead = FALSE",
			Args:  []interface{}{1},
		},
		{
			Name:  "Q5: Average rating for a member",
			Query: "SELECT AVG(Stars) FROM Rating WHERE RatedID = ?",
			Args:  []interface{}{1},
		},
	}

	type ExplainRow struct {
		ID           *int    `json:"id"`
		SelectType   *string `json:"select_type"`
		Table        *string `json:"table"`
		Partitions   *string `json:"partitions"`
		Type         *string `json:"type"`
		PossibleKeys *string `json:"possible_keys"`
		Key          *string `json:"key"`
		KeyLen       *string `json:"key_len"`
		Ref          *string `json:"ref"`
		Rows         *int64  `json:"rows"`
		Filtered     *string `json:"filtered"`
		Extra        *string `json:"extra"`
	}

	var results []models.BenchmarkResult
	for _, q := range queries {
		// EXPLAIN
		explainQuery := "EXPLAIN " + q.Query
		explainRows, err := appdb.DB.QueryContext(ctx, explainQuery, q.Args...)
		var accessType, extra string
		var rowsExamined int64
		var possibleKeys, keyUsed, keyLen *string
		if err == nil {
			defer explainRows.Close()
			if explainRows.Next() {
				var er ExplainRow
				_ = explainRows.Scan(&er.ID, &er.SelectType, &er.Table, &er.Partitions,
					&er.Type, &er.PossibleKeys, &er.Key, &er.KeyLen, &er.Ref,
					&er.Rows, &er.Filtered, &er.Extra)
				if er.Type != nil {
					accessType = *er.Type
				}
				if er.Rows != nil {
					rowsExamined = *er.Rows
				}
				if er.Extra != nil {
					extra = *er.Extra
				}
				possibleKeys = er.PossibleKeys
				keyUsed = er.Key
				keyLen = er.KeyLen
			}
		}

		// Time actual execution (3 runs, take average)
		var totalMs float64
		runs := 3
		for i := 0; i < runs; i++ {
			start := time.Now()
			rows, err := appdb.DB.QueryContext(ctx, q.Query, q.Args...)
			if err == nil {
				for rows.Next() {
				}
				rows.Close()
			}
			totalMs += float64(time.Since(start).Microseconds()) / 1000.0
		}
		avgMs := totalMs / float64(runs)

		extraPtr := &extra
		rowsPtr := &rowsExamined
		results = append(results, models.BenchmarkResult{
			QueryName:    q.Name,
			Query:        q.Query,
			AccessType:   accessType,
			PossibleKeys: possibleKeys,
			KeyUsed:      keyUsed,
			KeyLen:       keyLen,
			RowsExamined: rowsPtr,
			Extra:        extraPtr,
			DurationMs:   avgMs,
		})
	}

	// Check whether indexes exist
	var indexCount int
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM information_schema.STATISTICS
         WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME LIKE 'idx_%'`,
	).Scan(&indexCount)

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"indexes_applied": indexCount > 0,
		"index_count":     indexCount,
		"results":         results,
		"note":            "Run sql/indexes.sql then re-hit this endpoint to compare before/after",
		"sharding":        sharding.CurrentConfiguration(),
	})
}

// GET /api/v1/admin/stats — admin dashboard stats
func AdminStats(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var totalMembers, activeListings, openReports, totalTransactions int
	_ = appdb.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM Member m JOIN sys_user u ON u.user_id = m.user_id WHERE u.is_active = TRUE`).Scan(&totalMembers)
	_ = appdb.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM Listing WHERE Status = 'Listed'`).Scan(&activeListings)
	_ = appdb.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM Report WHERE Status IN ('Submitted','UnderReview')`).Scan(&openReports)
	_ = appdb.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM Transaction WHERE Status = 'Completed'`).Scan(&totalTransactions)

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"total_active_members":   totalMembers,
		"active_listings":        activeListings,
		"open_reports":           openReports,
		"completed_transactions": totalTransactions,
	})
}

// POST /api/v1/admin/users — SuperAdmin only, create admin accounts
func CreateAdminUser(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Verify requester is SuperAdmin
	var adminRole string
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT a.Role FROM Administrator a WHERE a.user_id = ?`, mw.GetUserID(ctx),
	).Scan(&adminRole)
	if adminRole != "SuperAdmin" {
		mw.RespondForbidden(w)
		return
	}

	var body struct {
		Name     string `json:"name"`
		Email    string `json:"email"`
		Password string `json:"password"`
		Role     string `json:"role"` // Moderator, Support, SuperAdmin
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}
	body.Email = strings.ToLower(strings.TrimSpace(body.Email))
	if body.Name == "" || body.Email == "" || body.Password == "" {
		respondError(w, http.StatusBadRequest, "name, email, password required")
		return
	}
	if body.Role == "" {
		body.Role = "Moderator"
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(body.Password), bcrypt.DefaultCost)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "hashing failed")
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
		`INSERT INTO sys_user (email, password_hash) VALUES (?, ?)`,
		body.Email, string(hash))
	if err != nil {
		if sqlContains(err.Error(), "Duplicate") {
			respondError(w, http.StatusConflict, "email already exists")
		} else {
			respondError(w, http.StatusInternalServerError, "user creation failed")
		}
		return
	}
	userID, _ := res.LastInsertId()

	var roleID int
	_ = tx.QueryRowContext(ctx, `SELECT role_id FROM sys_role WHERE role_name = 'admin'`).Scan(&roleID)
	_, _ = tx.ExecContext(ctx, `INSERT INTO sys_user_role (user_id, role_id) VALUES (?, ?)`, userID, roleID)

	res2, err := tx.ExecContext(ctx,
		`INSERT INTO Administrator (user_id, Name, Role) VALUES (?, ?, ?)`,
		userID, body.Name, body.Role)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "admin record creation failed")
		return
	}
	adminID, _ := res2.LastInsertId()

	_ = tx.Commit()
	respondJSON(w, http.StatusCreated, map[string]interface{}{"admin_id": adminID, "message": "admin created"})
}

// GET /api/v1/admin/members/:id — get member with user info (admin)
func AdminGetMember(w http.ResponseWriter, r *http.Request) {
	memberID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid member id")
		return
	}

	var result struct {
		MemberID int     `json:"member_id"`
		UserID   int     `json:"user_id"`
		Name     string  `json:"name"`
		Email    string  `json:"email"`
		Contact  string  `json:"contact_number"`
		Dept     *string `json:"department"`
		IsActive bool    `json:"is_active"`
	}
	err = appdb.DB.QueryRowContext(r.Context(),
		`SELECT m.MemberID, m.user_id, m.Name, u.email, m.ContactNumber, m.Department, u.is_active
         FROM Member m JOIN sys_user u ON u.user_id = m.user_id
         WHERE m.MemberID = ?`, memberID,
	).Scan(&result.MemberID, &result.UserID, &result.Name, &result.Email,
		&result.Contact, &result.Dept, &result.IsActive)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "member not found")
		return
	}
	respondJSON(w, http.StatusOK, result)
}
