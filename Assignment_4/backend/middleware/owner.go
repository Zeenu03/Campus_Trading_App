package middleware

// OwnerGuard is implemented as helper functions called within handlers,
// rather than as generic middleware, because ownership checks are resource-specific.
//
// Usage in handlers:
//
//	if !IsOwnerOrAdmin(r.Context(), resourceOwnerUserID) {
//	    respondForbidden(w)
//	    return
//	}

import (
	"context"
	"net/http"
)

// IsOwnerOrAdmin returns true if the session user owns the resource (by user_id)
// OR has the admin role.
func IsOwnerOrAdmin(ctx context.Context, ownerUserID int) bool {
	if HasRole(ctx, "admin") {
		return true
	}
	return GetUserID(ctx) == ownerUserID
}

// IsMemberOwnerOrAdmin returns true if the session's memberID matches or is admin.
func IsMemberOwnerOrAdmin(ctx context.Context, ownerMemberID int) bool {
	if HasRole(ctx, "admin") {
		return true
	}
	return GetMemberID(ctx) == ownerMemberID
}

// RespondForbidden writes a 403 response.
func RespondForbidden(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	_, _ = w.Write([]byte(`{"error":"forbidden"}`))
}
