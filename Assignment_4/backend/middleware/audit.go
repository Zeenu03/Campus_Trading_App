package middleware

import (
	"context"
	"database/sql"
	"fmt"
	"net/http"
	"strings"

	appaudit "campus-trading/audit"
	appdb "campus-trading/db"
)

// auditCtx is a mutable struct injected into the request context by AuditMiddleware.
// SessionGuard populates it when a valid session is found, so the outer middleware
// can read the authenticated identity after the full handler chain returns.
type auditCtx struct {
	SessionID string
	UserID    int
}

type auditCtxKey struct{}

// AuditMiddleware captures every API request and writes to audit_log + audit.log file.
// It must be the outermost middleware (Use'd first) so it wraps all inner middleware.
func AuditMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ac := &auditCtx{}
		r = r.WithContext(context.WithValue(r.Context(), auditCtxKey{}, ac))

		next.ServeHTTP(w, r)

		sessionID := ac.SessionID
		userID := ac.UserID

		action := r.Method
		if action == "GET" {
			return
		}
		targetTable := routeToTable(r.URL.Path)
		targetID := extractID(r.URL.Path)
		ipAddress := realIP(r)

		// Write to audit_log DB table
		var sidVal interface{} = sessionID
		if sessionID == "" {
			sidVal = sql.NullString{}
		}
		var uidVal interface{} = userID
		if userID == 0 {
			uidVal = sql.NullInt64{}
		}
		var tidVal interface{} = targetID
		if targetID == "" {
			tidVal = sql.NullString{}
		}

		_, _ = appdb.DB.Exec(
			`INSERT INTO audit_log (session_id, user_id, action, target_table, target_id, ip_address)
             VALUES (?, ?, ?, ?, ?, ?)`,
			sidVal, uidVal, action, targetTable, tidVal, ipAddress,
		)

		appaudit.Append(sessionID, action, targetTable, targetID, ipAddress, userID)
	})
}

// SetSessionVars sets MySQL user-defined variables on the given *sql.Tx so that
// audit triggers can read @session_id and @current_user_id.
// Call this at the start of every write transaction in handlers.
func SetSessionVars(tx *sql.Tx, sessionID string, userID int) error {
	_, err := tx.Exec("SET @session_id = ?, @current_user_id = ?", sessionID, userID)
	return err
}

// routeToTable maps URL paths to approximate table names for auditing.
func routeToTable(path string) string {
	path = strings.TrimPrefix(path, "/api/v1/")
	parts := strings.Split(path, "/")
	if len(parts) == 0 {
		return "unknown"
	}
	switch parts[0] {
	case "auth":
		// /auth/login|register → sys_user; /auth/logout|me → sys_session
		if len(parts) > 1 {
			switch parts[1] {
			case "login", "register":
				return "sys_user"
			case "logout", "me":
				return "sys_session"
			}
		}
		return "sys_session"
	case "members":
		return "Member"
	case "listings":
		if len(parts) > 2 {
			switch parts[2] {
			case "images":
				return "ListingImage"
			case "offers":
				return "Offer"
			case "threads":
				return "MessageThread"
			case "my-offer":
				return "Offer"
			case "my-thread":
				return "MessageThread"
			case "interactions":
				return "MessageThread"
			}
		}
		return "Listing"
	case "offers":
		return "Offer"
	case "threads":
		return "Message"
	case "transactions":
		return "Transaction"
	case "wishrequests":
		return "WishRequest"
	case "watchlist":
		return "Watchlist"
	case "notifications":
		return "Notification"
	case "reports":
		return "Report"
	case "categories":
		return "Category"
	case "admin":
		if len(parts) > 1 {
			switch parts[1] {
			case "users":
				return "sys_user"
			case "members":
				return "Member"
			case "audit-log":
				return "audit_log"
			}
		}
		return "audit_log"
	default:
		return parts[0]
	}
}

func extractID(path string) string {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	// Look for numeric segment after the resource name
	for i, p := range parts {
		if i > 0 && isNumeric(p) {
			return p
		}
	}
	return ""
}

func isNumeric(s string) bool {
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return len(s) > 0
}

func realIP(r *http.Request) string {
	if ip := r.Header.Get("X-Real-IP"); ip != "" {
		return ip
	}
	if ip := r.Header.Get("X-Forwarded-For"); ip != "" {
		return strings.Split(ip, ",")[0]
	}
	// Strip port
	addr := r.RemoteAddr
	if idx := strings.LastIndex(addr, ":"); idx >= 0 {
		return addr[:idx]
	}
	return fmt.Sprintf("%s", addr)
}
