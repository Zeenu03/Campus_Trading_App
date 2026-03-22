package handlers

import (
	"database/sql"
	"net/http"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"
)

// GET /api/v1/notifications — member, own notifications
func ListNotifications(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)
	if memberID == 0 {
		respondError(w, http.StatusForbidden, "member only")
		return
	}

	page := queryInt(r, "page", 1)
	pageSize := queryInt(r, "page_size", 20)

	var total int
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM Notification WHERE RecipientID = ?`, memberID).Scan(&total)

	offset, totalPages := paginate(page, pageSize, total)

	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT NotificationID, RecipientID, NotificationType, Title, Message,
             RelatedListingID, RelatedOfferID, RelatedTransactionID, IsRead, CreatedDate, ReadDate
          FROM Notification WHERE RecipientID = ?
          ORDER BY CreatedDate DESC LIMIT ? OFFSET ?`, memberID, pageSize, offset)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "query failed")
		return
	}
	defer rows.Close()

	var notifs []models.Notification
	for rows.Next() {
		var n models.Notification
		_ = rows.Scan(&n.NotificationID, &n.RecipientID, &n.NotificationType,
			&n.Title, &n.Message, &n.RelatedListingID, &n.RelatedOfferID,
			&n.RelatedTransactionID, &n.IsRead, &n.CreatedDate, &n.ReadDate)
		notifs = append(notifs, n)
	}
	if notifs == nil {
		notifs = []models.Notification{}
	}
	respondJSON(w, http.StatusOK, models.PaginatedResponse{
		Data: notifs, Total: total, Page: page, PageSize: pageSize, TotalPages: totalPages,
	})
}

// PUT /api/v1/notifications/:id/read — own
func MarkNotificationRead(w http.ResponseWriter, r *http.Request) {
	notifID, err := urlParamInt(r, "id")
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid notification id")
		return
	}
	ctx := r.Context()
	memberID := mw.GetMemberID(ctx)

	var recipientID int
	err = appdb.DB.QueryRowContext(ctx,
		`SELECT RecipientID FROM Notification WHERE NotificationID = ?`, notifID,
	).Scan(&recipientID)
	if err == sql.ErrNoRows {
		respondError(w, http.StatusNotFound, "notification not found")
		return
	}
	if recipientID != memberID && !mw.HasRole(ctx, "admin") {
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
		`UPDATE Notification SET IsRead = TRUE, ReadDate = NOW() WHERE NotificationID = ?`, notifID)
	_ = tx.Commit()

	respondJSON(w, http.StatusOK, map[string]string{"message": "marked as read"})
}
