package middleware

import (
	"net/http"
)

// RoleGuard returns middleware that requires the session user to have one of the given roles.
// Admins always pass through when "admin" is in the required list.
func RoleGuard(required ...string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx := r.Context()
			roles := GetRoles(ctx)

			for _, req := range required {
				for _, has := range roles {
					if has == req {
						next.ServeHTTP(w, r)
						return
					}
				}
			}

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusForbidden)
			_, _ = w.Write([]byte(`{"error":"insufficient permissions"}`))
		})
	}
}

// AdminOnly is a convenience guard that requires the "admin" role.
func AdminOnly(next http.Handler) http.Handler {
	return RoleGuard("admin")(next)
}

// MemberOnly requires the "member" role.
func MemberOnly(next http.Handler) http.Handler {
	return RoleGuard("member")(next)
}

// AnyAuth requires at least one role (session must exist — any authenticated user).
func AnyAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		roles := GetRoles(r.Context())
		if len(roles) == 0 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"error":"authentication required"}`))
			return
		}
		next.ServeHTTP(w, r)
	})
}
