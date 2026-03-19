package middleware

import (
	"database/sql"
	"fmt"
	"net/http"
	"strings"
	"time"

	appaudit "campus-trading/audit"
	appdb "campus-trading/db"
)

// responseWriter wraps http.ResponseWriter to capture status code.
type responseWriter struct {
	http.ResponseWriter
	status int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.status = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) statusCode() int {
	if rw.status == 0 {
		return http.StatusOK
	}
	return rw.status
}

// AuditMiddleware captures every API request and writes to audit_log + audit.log file.
// It must be the outermost middleware (Use'd first) so it wraps all inner middleware.
func AuditMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		ww := &responseWriter{ResponseWriter: w}

		next.ServeHTTP(ww, r)

		// Gather context values set by SessionGuard
		ctx := r.Context()
		sessionID := GetSessionID(ctx)
		userID := GetUserID(ctx)
		statusCode := ww.statusCode()

		action := r.Method
		targetTable := routeToTable(r.URL.Path)
		targetID := extractID(r.URL.Path)
		ipAddress := realIP(r)
		auditStatus := "success"
		if statusCode >= 400 {
			auditStatus = "fail"
		}

		_ = start // available for duration if needed

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
			`INSERT INTO audit_log (session_id, user_id, action, target_table, target_id, ip_address, status)
             VALUES (?, ?, ?, ?, ?, ?, ?)`,
			sidVal, uidVal, action, targetTable, tidVal, ipAddress, auditStatus,
		)

		// Write to audit.log file
		appaudit.Append(sessionID, action, targetTable, targetID, ipAddress, auditStatus, userID)
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
		return "sys_session"
	case "members":
		return "Member"
	case "listings":
		return "Listing"
	case "offers":
		return "Offer"
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
	case "admin":
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
