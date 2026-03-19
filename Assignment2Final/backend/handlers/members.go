package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strings"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/members — admin only, paginated
func ListMembers(w http.ResponseWriter, r *http.Request) {
	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)
	search := r.URL.Query().Get("search")

	var total int
	countQuery := `SELECT COUNT(*) FROM Member m JOIN sys_user u ON u.user_id = m.user_id WHERE 1=1`
	var args []interface{}
	if search != "" {
		countQuery += " AND (m.Name LIKE ? OR u.email LIKE ?)"
		like := "%" + search + "%"
		args = append(args, like, like)
	}
	_ = appdb.DB.QueryRowContext(r.Context(), countQuery, args...).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	query := `SELECT m.MemberID, m.user_id, m.Name, u.email, m.ContactNumber,
               m.Department, m.YearOfStudy, m.Hostel, m.RoomNumber, m.AccountStatus
              FROM Member m JOIN sys_user u ON u.user_id = m.user_id WHERE 1=1`
	if search != "" {
		query += " AND (m.Name LIKE ? OR u.email LIKE ?)"
	}
	query += " ORDER BY m.AccountCreationDate DESC LIMIT ? OFFSET ?"
	args = append(args, pageSize, offset)

	rows, err := appdb.DB.QueryContext(r.Context(), query, args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var members []map[string]interface{}
	for rows.Next() {
		var m models.Member
		var dept, hostel *string
		var yr *int
		if err := rows.Scan(&m.MemberID, &m.UserID, &m.Name, &m.Email, &m.ContactNumber,
			&dept, &yr, &hostel, &m.RoomNumber, &m.AccountStatus); err != nil {
			continue
		}
		members = append(members, map[string]interface{}{
			"member_id":      m.MemberID,
			"user_id":        m.UserID,
			"name":           m.Name,
			"email":          m.Email,
			"contact_number": m.ContactNumber,
			"department":     dept,
			"year_of_study":  yr,
			"hostel":         hostel,
			"account_status": m.AccountStatus,
		})
	}
	if members == nil {
		members = []map[string]interface{}{}
	}

	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data:       members,
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	})
}

// GET /api/v1/members/:id/portfolio — own or admin
func GetPortfolio(w http.ResponseWriter, r *http.Request) {
	memberID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid member id")
		return
	}

	ctx := r.Context()
	if !mw.IsMemberOwnerOrAdmin(ctx, memberID) {
		mw.RespondForbidden(w)
		return
	}

	// Fetch member info
	var m models.Member
	var email string
	var dept, hostel, room, bio, img *string
	var yr *int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT m.MemberID, m.user_id, m.Name, u.email, m.ContactNumber,
             m.Department, m.YearOfStudy, m.Hostel, m.RoomNumber, m.Bio, m.Image,
             m.IsVerified, m.AccountStatus, m.AccountCreationDate
          FROM Member m JOIN sys_user u ON u.user_id = m.user_id
          WHERE m.MemberID = ?`, memberID,
	).Scan(&m.MemberID, &m.UserID, &m.Name, &email, &m.ContactNumber,
		&dept, &yr, &hostel, &room, &bio, &img,
		&m.IsVerified, &m.AccountStatus, &m.AccountCreationDate)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "member not found")
		return
	}

	// Listings
	listRows, _ := appdb.DB.QueryContext(ctx,
		`SELECT ListingID, Title, AskingPrice, Status, CreatedDate
         FROM Listing WHERE SellerID = ? ORDER BY CreatedDate DESC`, memberID)
	var listings []map[string]interface{}
	if listRows != nil {
		defer listRows.Close()
		for listRows.Next() {
			var id int
			var title, status string
			var price float64
			var created interface{}
			_ = listRows.Scan(&id, &title, &price, &status, &created)
			listings = append(listings, map[string]interface{}{
				"listing_id":   id,
				"title":        title,
				"asking_price": price,
				"status":       status,
				"created_date": created,
			})
		}
	}
	if listings == nil {
		listings = []map[string]interface{}{}
	}

	// Transactions (as buyer or seller)
	txRows, _ := appdb.DB.QueryContext(ctx,
		`SELECT t.TransactionID, l.Title, t.AgreedPrice, t.Status, t.CreatedDate
         FROM Transaction t JOIN Listing l ON l.ListingID = t.ListingID
         WHERE t.SellerID = ? OR t.BuyerID = ?
         ORDER BY t.CreatedDate DESC`, memberID, memberID)
	var transactions []map[string]interface{}
	if txRows != nil {
		defer txRows.Close()
		for txRows.Next() {
			var id int
			var title, status string
			var price float64
			var created interface{}
			_ = txRows.Scan(&id, &title, &price, &status, &created)
			transactions = append(transactions, map[string]interface{}{
				"transaction_id": id,
				"listing_title":  title,
				"agreed_price":   price,
				"status":         status,
				"created_date":   created,
			})
		}
	}
	if transactions == nil {
		transactions = []map[string]interface{}{}
	}

	// Ratings received
	ratingRows, _ := appdb.DB.QueryContext(ctx,
		`SELECT r.RatingID, r.Stars, r.ReviewText, r.RatingDate
         FROM Rating r WHERE r.RatedID = ? ORDER BY r.RatingDate DESC`, memberID)
	var ratings []map[string]interface{}
	if ratingRows != nil {
		defer ratingRows.Close()
		for ratingRows.Next() {
			var id, stars int
			var review *string
			var ratingDate interface{}
			_ = ratingRows.Scan(&id, &stars, &review, &ratingDate)
			ratings = append(ratings, map[string]interface{}{
				"rating_id":   id,
				"stars":       stars,
				"review_text": review,
				"rating_date": ratingDate,
			})
		}
	}
	if ratings == nil {
		ratings = []map[string]interface{}{}
	}

	// WishRequests
	wrRows, _ := appdb.DB.QueryContext(ctx,
		`SELECT WishRequestID, ItemDescription, Status, CreatedDate
         FROM WishRequest WHERE RequesterID = ? ORDER BY CreatedDate DESC`, memberID)
	var wishRequests []map[string]interface{}
	if wrRows != nil {
		defer wrRows.Close()
		for wrRows.Next() {
			var id int
			var desc, status string
			var created interface{}
			_ = wrRows.Scan(&id, &desc, &status, &created)
			wishRequests = append(wishRequests, map[string]interface{}{
				"wish_request_id":  id,
				"item_description": desc,
				"status":           status,
				"created_date":     created,
			})
		}
	}
	if wishRequests == nil {
		wishRequests = []map[string]interface{}{}
	}

	// Watchlist (only for own profile)
	var watchlist []map[string]interface{}
	if mw.GetMemberID(ctx) == memberID {
		wlRows, _ := appdb.DB.QueryContext(ctx,
			`SELECT w.WatchlistID, l.ListingID, l.Title, l.AskingPrice, l.Status
             FROM Watchlist w JOIN Listing l ON l.ListingID = w.ListingID
             WHERE w.MemberID = ?`, memberID)
		if wlRows != nil {
			defer wlRows.Close()
			for wlRows.Next() {
				var wid, lid int
				var title, status string
				var price float64
				_ = wlRows.Scan(&wid, &lid, &title, &price, &status)
				watchlist = append(watchlist, map[string]interface{}{
					"watchlist_id": wid,
					"listing_id":   lid,
					"title":        title,
					"asking_price": price,
					"status":       status,
				})
			}
		}
	}
	if watchlist == nil {
		watchlist = []map[string]interface{}{}
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"member": map[string]interface{}{
			"member_id":      m.MemberID,
			"name":           m.Name,
			"email":          email,
			"contact_number": m.ContactNumber,
			"department":     dept,
			"year_of_study":  yr,
			"hostel":         hostel,
			"room_number":    room,
			"bio":            bio,
			"image":          img,
			"is_verified":    m.IsVerified,
			"account_status": m.AccountStatus,
			"created_date":   m.AccountCreationDate,
		},
		"listings":      listings,
		"transactions":  transactions,
		"ratings":       ratings,
		"wish_requests": wishRequests,
		"watchlist":     watchlist,
	})
}

// PUT /api/v1/members/:id — own or admin
func UpdateMember(w http.ResponseWriter, r *http.Request) {
	memberID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid member id")
		return
	}

	ctx := r.Context()
	if !mw.IsMemberOwnerOrAdmin(ctx, memberID) {
		mw.RespondForbidden(w)
		return
	}

	var body map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		respondError(w, http.StatusBadRequest, "invalid body")
		return
	}

	// Build SET clause dynamically
	var setClauses []string
	var args []interface{}
	allowed := []string{"Name", "ContactNumber", "Department", "YearOfStudy", "Hostel", "RoomNumber", "Bio", "Image"}
	for _, col := range allowed {
		if v, ok := body[strings.ToLower(col)]; ok {
			setClauses = append(setClauses, col+" = ?")
			args = append(args, v)
		}
		// Also check snake_case
		snake := toSnake(col)
		if v, ok := body[snake]; ok {
			found := false
			for _, c := range setClauses {
				if c == col+" = ?" {
					found = true
					break
				}
			}
			if !found {
				setClauses = append(setClauses, col+" = ?")
				args = append(args, v)
			}
		}
	}
	if len(setClauses) == 0 {
		respondError(w, http.StatusBadRequest, "no valid fields to update")
		return
	}
	setClauses = append(setClauses, "LastModifiedDate = NOW()")
	args = append(args, memberID)

	_, err = appdb.DB.ExecContext(ctx,
		"UPDATE Member SET "+strings.Join(setClauses, ", ")+" WHERE MemberID = ?", args...)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "update failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"message": "updated"})
}

// DELETE /api/v1/members/:id — admin only, soft delete
func DeleteMember(w http.ResponseWriter, r *http.Request) {
	memberID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid member id")
		return
	}

	ctx := r.Context()

	// Get user_id for the member
	var userID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT user_id FROM Member WHERE MemberID = ?`, memberID).Scan(&userID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "member not found")
		return
	}

	tx, err := appdb.DB.BeginTx(ctx, nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "tx failed")
		return
	}
	defer tx.Rollback()

	sessionID := mw.GetSessionID(ctx)
	_ = mw.SetSessionVars(tx, sessionID, mw.GetUserID(ctx))

	// Soft delete: set AccountStatus, deactivate sys_user, revoke sessions, withdraw listings, expire offers
	_, _ = tx.ExecContext(ctx, `UPDATE Member SET AccountStatus = 'Deleted' WHERE MemberID = ?`, memberID)
	_, _ = tx.ExecContext(ctx, `UPDATE sys_user SET is_active = FALSE WHERE user_id = ?`, userID)
	_, _ = tx.ExecContext(ctx, `UPDATE sys_session SET is_revoked = TRUE WHERE user_id = ?`, userID)
	_, _ = tx.ExecContext(ctx, `UPDATE Listing SET Status = 'Withdrawn' WHERE SellerID = ? AND Status = 'Listed'`, memberID)
	_, _ = tx.ExecContext(ctx, `UPDATE Offer SET OfferStatus = 'Expired' WHERE BuyerID = ? AND OfferStatus = 'Submitted'`, memberID)

	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}
	respondJSON(w, http.StatusOK, map[string]string{"message": "member soft-deleted"})
}

func toSnake(s string) string {
	var out []rune
	for i, c := range s {
		if c >= 'A' && c <= 'Z' && i > 0 {
			out = append(out, '_')
		}
		out = append(out, c+32)
	}
	return string(out)
}
