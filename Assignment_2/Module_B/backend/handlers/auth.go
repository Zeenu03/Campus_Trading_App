package handlers

import (
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"os"
	"slices"
	"strconv"
	"strings"
	"time"

	appdb "campus-trading/db"
	mw "campus-trading/middleware"
	"campus-trading/models"

	"golang.org/x/crypto/bcrypt"
)

func normalizeOptionalPtr(ptr *string) *string {
	if ptr == nil {
		return nil
	}
	s := strings.TrimSpace(*ptr)
	if s == "" {
		return nil
	}
	return &s
}

func validateRegisterHostelRoom(hostel *string, room *string) string {
	h := ""
	if hostel != nil {
		h = strings.TrimSpace(*hostel)
	}
	r := ""
	if room != nil {
		r = strings.TrimSpace(*room)
	}
	if h == "" && r == "" {
		return ""
	}
	if h == "" {
		return "hostel is required when room_number is provided"
	}
	if r == "" {
		return "room_number is required when hostel is provided"
	}
	if !slices.Contains(HOSTELS, h) {
		return "invalid hostel name"
	}
	n, err := strconv.Atoi(r)
	if err != nil || n < 100 || n > 499 {
		return "room_number must be an integer from 100 to 499"
	}
	return ""
}

// POST /api/v1/auth/login
func Login(w http.ResponseWriter, r *http.Request) {
	var req models.LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Email = strings.ToLower(strings.TrimSpace(req.Email))
	if req.Email == "" || req.Password == "" {
		respondError(w, http.StatusBadRequest, "email and password required")
		return
	}

	var userID int
	var passwordHash string
	var isActive bool

	err := appdb.DB.QueryRowContext(r.Context(),
		`SELECT user_id, password_hash, is_active FROM sys_user WHERE email = ?`,
		req.Email,
	).Scan(&userID, &passwordHash, &isActive)

	if err == sql.ErrNoRows {
		respondError(w, http.StatusUnauthorized, "invalid credentials")
		return
	}
	if err != nil {
		respondError(w, http.StatusInternalServerError, "database error")
		return
	}
	if !isActive {
		respondError(w, http.StatusForbidden, "account inactive")
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(passwordHash), []byte(req.Password)); err != nil {
		respondError(w, http.StatusUnauthorized, "invalid credentials")
		return
	}

	// Create session
	sessionID, err := generateSessionID()
	if err != nil {
		respondError(w, http.StatusInternalServerError, "could not generate session")
		return
	}

	expiresAt := time.Now().Add(24 * time.Hour) // Set session to expire 24 hours from now
	_, err = appdb.DB.ExecContext(r.Context(),
		`INSERT INTO sys_session (session_id, user_id, expires_at) VALUES (?, ?, ?)`,
		sessionID, userID, expiresAt,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "could not create session")
		return
	}

	// Update last login for users with the admin role
	roles, err := mw.LoadRoleNames(r.Context(), userID)
	if err == nil {
		for _, role := range roles {
			if role == "admin" {
				_, _ = appdb.DB.ExecContext(r.Context(),
					`UPDATE Administrator SET LastLoginDate = NOW() WHERE user_id = ?`, userID)
				break
			}
		}
	}

	http.SetCookie(w, &http.Cookie{
		Name:     "session_id",
		Value:    sessionID,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteLaxMode,
		Expires:  expiresAt,
	})

	respondJSON(w, http.StatusOK, map[string]string{"message": "logged in"})
}

// POST /api/v1/auth/logout
func Logout(w http.ResponseWriter, r *http.Request) {
	sessionID := mw.GetSessionID(r.Context())
	if sessionID == "" {
		respondError(w, http.StatusUnauthorized, "not logged in")
		return
	}

	_, err := appdb.DB.ExecContext(r.Context(),
		`UPDATE sys_session SET is_revoked = TRUE WHERE session_id = ?`, sessionID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "logout failed")
		return
	}

	http.SetCookie(w, &http.Cookie{
		Name:     "session_id",
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		MaxAge:   -1,
	})
	respondJSON(w, http.StatusOK, map[string]string{"message": "logged out"})
}

// POST /api/v1/auth/register — atomic member creation
func Register(w http.ResponseWriter, r *http.Request) {
	var req models.RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body")
		return
	}

	req.Email = strings.ToLower(strings.TrimSpace(req.Email))

	// Domain validation
	if !strings.HasSuffix(req.Email, "@iitgn.ac.in") {
		respondError(w, http.StatusBadRequest, "email must be @iitgn.ac.in domain")
		return
	}
	if req.Name == "" || req.Password == "" || req.ContactNumber == "" {
		respondError(w, http.StatusBadRequest, "name, password, and contact_number are required")
		return
	}
	if len(req.Password) < 8 {
		respondError(w, http.StatusBadRequest, "password must be at least 8 characters")
		return
	}

	if msg := validateRegisterHostelRoom(req.Hostel, req.RoomNumber); msg != "" {
		respondError(w, http.StatusBadRequest, msg)
		return
	}
	req.Hostel = normalizeOptionalPtr(req.Hostel)
	req.RoomNumber = normalizeOptionalPtr(req.RoomNumber)

	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "password hashing failed")
		return
	}

	// Atomic transaction: sys_user → sys_user_role → Member
	tx, err := appdb.DB.BeginTx(r.Context(), nil)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "transaction start failed")
		return
	}
	defer tx.Rollback()

	res, err := tx.ExecContext(r.Context(),
		`INSERT INTO sys_user (email, password_hash) VALUES (?, ?)`,
		req.Email, string(hash),
	)
	if err != nil {
		if strings.Contains(err.Error(), "Duplicate entry") {
			respondError(w, http.StatusConflict, "email already registered")
		} else {
			respondError(w, http.StatusInternalServerError, "user creation failed")
		}
		return
	}
	userID, _ := res.LastInsertId()

	// Assign member role (role_id = 2)
	var roleID int
	err = tx.QueryRowContext(r.Context(),
		`SELECT role_id FROM sys_role WHERE role_name = 'member'`,
	).Scan(&roleID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get role ID")
		return
	}

	_, err = tx.ExecContext(r.Context(),
		`INSERT INTO sys_user_role (user_id, role_id) VALUES (?, ?)`,
		userID, roleID,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "role assignment failed")
		return
	}

	_, err = tx.ExecContext(r.Context(),
		`INSERT INTO Member (user_id, Name, ContactNumber, Department, YearOfStudy, Hostel, RoomNumber, Bio)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
		userID, req.Name, req.ContactNumber,
		req.Department, req.YearOfStudy, req.Hostel, req.RoomNumber, req.Bio,
	)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "member creation failed")
		return
	}

	if err := tx.Commit(); err != nil {
		respondError(w, http.StatusInternalServerError, "commit failed")
		return
	}

	respondJSON(w, http.StatusCreated, map[string]string{"message": "registered successfully"})
}

// GET /api/v1/auth/me
func Me(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	userID := mw.GetUserID(ctx)
	roles := mw.GetRoles(ctx)
	if userID == 0 {
		respondError(w, http.StatusUnauthorized, "not authenticated")
		return
	}

	var email string
	_ = appdb.DB.QueryRowContext(ctx,
		`SELECT email FROM sys_user WHERE user_id = ?`, userID,
	).Scan(&email)

	resp := map[string]interface{}{
		"user_id": userID,
		"email":   email,
		"roles":   roles,
	}

	if mw.HasRole(ctx, "member") {
		memberID := mw.GetMemberID(ctx)
		if memberID > 0 {
			resp["member_id"] = memberID
			var name, contact string
			var dept, hostel, room, bio, img *string
			var yrStudy *int
			var isActive bool
			_ = appdb.DB.QueryRowContext(ctx,
				`SELECT m.Name, m.ContactNumber, m.Department, m.YearOfStudy, m.Hostel, m.RoomNumber, m.Bio, m.Image, u.is_active
             FROM Member m JOIN sys_user u ON u.user_id = m.user_id WHERE m.MemberID = ?`, memberID,
			).Scan(&name, &contact, &dept, &yrStudy, &hostel, &room, &bio, &img, &isActive)
			resp["name"] = name
			resp["contact_number"] = contact
			resp["department"] = dept
			resp["year_of_study"] = yrStudy
			resp["hostel"] = hostel
			resp["is_active"] = isActive
		}
	}

	if mw.HasRole(ctx, "admin") {
		var adminID int
		var adminName, adminRole string
		err := appdb.DB.QueryRowContext(ctx,
			`SELECT AdminID, Name, Role FROM Administrator WHERE user_id = ?`, userID,
		).Scan(&adminID, &adminName, &adminRole)
		if err == nil {
			resp["admin_id"] = adminID
			resp["admin_role"] = adminRole
			if _, hasName := resp["name"]; !hasName {
				resp["name"] = adminName
			}
		}
	}

	respondJSON(w, http.StatusOK, resp)
}

func generateSessionID() (string, error) {
	b := make([]byte, 32)
	_, err := rand.Read(b)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

func frontendURL() string {
	if v := os.Getenv("FRONTEND_URL"); v != "" {
		return v
	}
	return "http://localhost:5173"
}
