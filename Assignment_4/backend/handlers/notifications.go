package handlers

import (
	"database/sql"
	"net/http"
	"sort"

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
	for _, shardDB := range appdb.AllShardConnections() {
		var shardTotal int
		_ = shardDB.QueryRowContext(ctx,
			`SELECT COUNT(*) FROM Notification WHERE RecipientID = ?`, memberID).Scan(&shardTotal)
		total += shardTotal
	}

	_, totalPages := paginate(page, pageSize, total)

	var notifs []models.Notification
	for _, shardDB := range appdb.AllShardConnections() {
		rows, err := shardDB.QueryContext(ctx,
			`SELECT NotificationID, RecipientID, NotificationType, Title, Message,
             RelatedListingID, RelatedOfferID, RelatedTransactionID, IsRead, CreatedDate, ReadDate
          FROM Notification WHERE RecipientID = ?`, memberID)
		if err != nil {
			respondError(w, http.StatusInternalServerError, "query failed")
			return
		}
		for rows.Next() {
			var n models.Notification
			_ = rows.Scan(&n.NotificationID, &n.RecipientID, &n.NotificationType,
				&n.Title, &n.Message, &n.RelatedListingID, &n.RelatedOfferID,
				&n.RelatedTransactionID, &n.IsRead, &n.CreatedDate, &n.ReadDate)
			notifs = append(notifs, n)
		}
		rows.Close()
	}

	sort.SliceStable(notifs, func(i, j int) bool {
		return notifs[i].CreatedDate.After(notifs[j].CreatedDate)
	})
	offset, end := paginate(page, pageSize, len(notifs))
	if offset > len(notifs) {
		offset = len(notifs)
	}
	if end > len(notifs) {
		end = len(notifs)
	}
	notifs = notifs[offset:end]
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
	err = notificationShardDB(notifID).QueryRowContext(ctx,
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

	tx, err := notificationShardDB(notifID).BeginTx(ctx, nil)
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
