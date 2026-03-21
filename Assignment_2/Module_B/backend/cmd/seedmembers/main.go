// seedmembers inserts 5 sample member accounts (no listings).
// Run after init.sql (and optionally cmd/seed for SuperAdmin):
//
//	cd Assignment2Final/backend && go run ./cmd/seedmembers
package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"
	"golang.org/x/crypto/bcrypt"
)

// Shared login password for all sample users (change in production).
const samplePassword = "Sample@iitgn25"

type sampleMember struct {
	Email         string
	Name          string
	ContactNumber string
	Department    string
	YearOfStudy   int
	Hostel        string
	RoomNumber    string
	Bio           string
}

func main() {
	_ = godotenv.Load()

	dsn := os.Getenv("DB_DSN")
	if dsn == "" {
		port := getEnv("DB_PORT", "3306")
		user := getEnv("DB_USER", "root")
		pass := getEnv("DB_PASSWORD", "")
		name := getEnv("DB_NAME", "CampusTradingB")
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4&loc=Asia%%2FKolkata",
			user, pass, "127.0.0.1", port, name)
	}

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("seedmembers: open: %v", err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		log.Fatalf("seedmembers: ping: %v", err)
	}

	var memberRoleID int
	err = db.QueryRow(`SELECT role_id FROM sys_role WHERE role_name = 'member'`).Scan(&memberRoleID)
	if err != nil {
		log.Fatalf("seedmembers: need sys_role 'member' (run init.sql): %v", err)
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(samplePassword), bcrypt.DefaultCost)
	if err != nil {
		log.Fatalf("seedmembers: bcrypt: %v", err)
	}
	hashStr := string(hash)

	samples := []sampleMember{
		{"sample.user1@iitgn.ac.in", "Priya Sharma", "9876543210", "Computer Science", 2, "Apex", "101", "CS undergrad, interested in systems."},
		{"sample.user2@iitgn.ac.in", "Arjun Mehta", "9876543211", "Electrical Engineering", 3, "Nilgiri", "205", ""},
		{"sample.user3@iitgn.ac.in", "Sneha Iyer", "9876543212", "Mechanical Engineering", 1, "Himadri", "312", "First year — looking for textbooks."},
		{"sample.user4@iitgn.ac.in", "Rahul Verma", "9876543213", "Chemical Engineering", 4, "Vindhya", "408", ""},
		{"sample.user5@iitgn.ac.in", "Ananya Patel", "9876543214", "Materials Science", 2, "Apex", "118", "Lab gear and notes sometimes."},
	}

	created := 0
	for _, s := range samples {
		var existing int
		err := db.QueryRow(`SELECT user_id FROM sys_user WHERE email = ?`, s.Email).Scan(&existing)
		if err == nil {
			log.Printf("seedmembers: skip (exists) %s user_id=%d", s.Email, existing)
			continue
		}
		if err != sql.ErrNoRows {
			log.Fatalf("seedmembers: lookup %s: %v", s.Email, err)
		}

		tx, err := db.Begin()
		if err != nil {
			log.Fatalf("seedmembers: begin: %v", err)
		}

		res, err := tx.Exec(
			`INSERT INTO sys_user (email, password_hash) VALUES (?, ?)`,
			s.Email, hashStr,
		)
		if err != nil {
			_ = tx.Rollback()
			log.Fatalf("seedmembers: insert sys_user %s: %v", s.Email, err)
		}
		userID, _ := res.LastInsertId()

		_, err = tx.Exec(`INSERT INTO sys_user_role (user_id, role_id) VALUES (?, ?)`, userID, memberRoleID)
		if err != nil {
			_ = tx.Rollback()
			log.Fatalf("seedmembers: role %s: %v", s.Email, err)
		}

		var bio interface{}
		if s.Bio != "" {
			bio = s.Bio
		}

		_, err = tx.Exec(
			`INSERT INTO Member (user_id, Name, ContactNumber, Department, YearOfStudy, Hostel, RoomNumber, Bio)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
			userID, s.Name, s.ContactNumber, s.Department, s.YearOfStudy, s.Hostel, s.RoomNumber, bio,
		)
		if err != nil {
			_ = tx.Rollback()
			log.Fatalf("seedmembers: insert Member %s: %v", s.Email, err)
		}

		if err := tx.Commit(); err != nil {
			log.Fatalf("seedmembers: commit %s: %v", s.Email, err)
		}
		log.Printf("seedmembers: created %s (%s) user_id=%d", s.Name, s.Email, userID)
		created++
	}

	log.Printf("seedmembers: done (%d new users, %d skipped). Password for all: %s", created, len(samples)-created, samplePassword)
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
