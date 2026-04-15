// seed creates the SuperAdmin account in CampusTradingB.
// Run after init.sql: go run ./backend/cmd/seed
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strings"

	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"
	"golang.org/x/crypto/bcrypt"
)

const (
	defaultEmail    = "superadmin@iitgn.ac.in"
	defaultPassword = "Admin@iitgn2025"
	defaultName     = "Super Administrator"
)

func main() {
	_ = godotenv.Load()

	dsn := os.Getenv("DB_DSN")
	if dsn == "" {
		host := getEnv("DB_HOST", "localhost")
		port := getEnv("DB_PORT", "3306")
		user := getEnv("DB_USER", "root")
		pass := getEnv("DB_PASSWORD", "")
		name := getEnv("DB_NAME", "CampusTradingB")
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4&loc=UTC",
			user, pass, host, port, name)
	}

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("seed: open: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatalf("seed: ping: %v", err)
	}

	email := getEnv("SUPERADMIN_EMAIL", defaultEmail)
	password := getEnv("SUPERADMIN_PASSWORD", defaultPassword)
	name := getEnv("SUPERADMIN_NAME", defaultName)

	email = strings.ToLower(strings.TrimSpace(email))

	// Check if superadmin already exists
	var existingID int
	err = db.QueryRow(`SELECT user_id FROM sys_user WHERE email = ?`, email).Scan(&existingID)
	if err == nil {
		log.Printf("seed: superadmin %s already exists (user_id=%d), skipping", email, existingID)
		return
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		log.Fatalf("seed: bcrypt: %v", err)
	}

	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("seed: begin tx: %v", err)
	}
	defer tx.Rollback()

	// Insert sys_user
	res, err := tx.Exec(
		`INSERT INTO sys_user (email, password_hash) VALUES (?, ?)`,
		email, string(hash),
	)
	if err != nil {
		log.Fatalf("seed: insert sys_user: %v", err)
	}
	userID, _ := res.LastInsertId()

	// Assign admin role
	var roleID int
	_ = tx.QueryRow(`SELECT role_id FROM sys_role WHERE role_name = 'admin'`).Scan(&roleID)
	if roleID == 0 {
		roleID = 1
	}
	_, err = tx.Exec(`INSERT INTO sys_user_role (user_id, role_id) VALUES (?, ?)`, userID, roleID)
	if err != nil {
		log.Fatalf("seed: assign role: %v", err)
	}

	// Create Administrator record
	res2, err := tx.Exec(
		`INSERT INTO Administrator (user_id, Name, Role) VALUES (?, ?, 'SuperAdmin')`,
		userID, name,
	)
	if err != nil {
		log.Fatalf("seed: insert Administrator: %v", err)
	}
	adminID, _ := res2.LastInsertId()

	if err := tx.Commit(); err != nil {
		log.Fatalf("seed: commit: %v", err)
	}

	log.Printf("seed: SuperAdmin created successfully!")
	log.Printf("  Email:    %s", email)
	log.Printf("  Password: %s", password)
	log.Printf("  AdminID:  %d", adminID)
	log.Printf("  UserID:   %d", userID)
	log.Println("seed: IMPORTANT - change the default password before deploying to production!")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
