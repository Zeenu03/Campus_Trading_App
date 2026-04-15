package middleware

import (
	"context"
	"database/sql"
	"net/http"
	"time"

	appdb "campus-trading/db"
)

type contextKey string

const (
	CtxUserID    contextKey = "userID"
	CtxRoles     contextKey = "roles"
	CtxSessionID contextKey = "sessionID"
	CtxMemberID  contextKey = "memberID"
)

// SessionGuard validates the session cookie and injects user_id + roles into context.
func SessionGuard(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie("session_id")
		if err != nil {
			respondUnauthorized(w, "missing session cookie")
			return
		}

		sessionID := cookie.Value
		if sessionID == "" {
			respondUnauthorized(w, "empty session")
			return
		}

		var userID int
		var expiresAt time.Time
		var isRevoked bool

		err = appdb.DB.QueryRowContext(r.Context(),
			`SELECT user_id, expires_at, is_revoked FROM sys_session WHERE session_id = ?`,
			sessionID,
		).Scan(&userID, &expiresAt, &isRevoked)

		if err == sql.ErrNoRows {
			respondUnauthorized(w, "session not found")
			return
		}
		if err != nil {
			respondUnauthorized(w, "session lookup error")
			return
		}
		if isRevoked {
			respondUnauthorized(w, "session revoked")
			return
		}
		if time.Now().After(expiresAt) {
			respondUnauthorized(w, "session expired")
			return
		}

		// Check user is still active
		var isActive bool
		err = appdb.DB.QueryRowContext(r.Context(),
			`SELECT is_active FROM sys_user WHERE user_id = ?`, userID,
		).Scan(&isActive)
		if err != nil || !isActive {
			respondUnauthorized(w, "user inactive or not found")
			return
		}

		roles, err := LoadRoleNames(r.Context(), userID)
		if err != nil {
			respondUnauthorized(w, "role lookup error")
			return
		}

		// Resolve MemberID for member users (NULL for admin-only users)
		var memberID int
		for _, shardDB := range appdb.AllShardConnections() {
			err = shardDB.QueryRowContext(r.Context(), `SELECT MemberID FROM Member WHERE user_id = ?`, userID).Scan(&memberID)
			if err == nil {
				break
			}
			if err != sql.ErrNoRows {
				respondUnauthorized(w, "member lookup error")
				return
			}
		}

		ctx := context.WithValue(r.Context(), CtxUserID, userID)
		ctx = context.WithValue(ctx, CtxRoles, roles)
		ctx = context.WithValue(ctx, CtxSessionID, sessionID)
		ctx = context.WithValue(ctx, CtxMemberID, memberID)

		// Write identity back into the mutable auditCtx injected by AuditMiddleware
		// so it can log the correct session and user after the handler chain returns.
		if ac, ok := r.Context().Value(auditCtxKey{}).(*auditCtx); ok {
			ac.SessionID = sessionID
			ac.UserID = userID
		}

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// GetUserID extracts user_id from context (0 if not set).
func GetUserID(ctx context.Context) int {
	v, _ := ctx.Value(CtxUserID).(int)
	return v
}

// GetMemberID extracts memberID from context (0 if not a member).
func GetMemberID(ctx context.Context) int {
	v, _ := ctx.Value(CtxMemberID).(int)
	return v
}

// GetSessionID extracts session_id string from context.
func GetSessionID(ctx context.Context) string {
	v, _ := ctx.Value(CtxSessionID).(string)
	return v
}

// GetRoles returns the slice of role strings from context.
func GetRoles(ctx context.Context) []string {
	v, _ := ctx.Value(CtxRoles).([]string)
	return v
}

// LoadRoleNames returns role_name values for a user from sys_user_role + sys_role.
func LoadRoleNames(ctx context.Context, userID int) ([]string, error) {
	rows, err := appdb.DB.QueryContext(ctx,
		`SELECT r.role_name FROM sys_role r
		 JOIN sys_user_role ur ON ur.role_id = r.role_id
		 WHERE ur.user_id = ?`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var roles []string
	for rows.Next() {
		var role string
		if err := rows.Scan(&role); err != nil {
			continue
		}
		roles = append(roles, role)
	}
	return roles, rows.Err()
}

// HasRole returns true if the context roles contain the given role.
func HasRole(ctx context.Context, role string) bool {
	for _, r := range GetRoles(ctx) {
		if r == role {
			return true
		}
	}
	return false
}

func respondUnauthorized(w http.ResponseWriter, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"error":"` + msg + `"}`))
}
