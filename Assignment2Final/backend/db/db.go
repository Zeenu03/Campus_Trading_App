package db

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

var DB *sql.DB

// IST is the Indian Standard Time location (UTC+05:30).
var IST *time.Location

func Init() {
	var err error
	IST, err = time.LoadLocation("Asia/Kolkata")
	if err != nil {
		log.Fatalf("db: could not load Asia/Kolkata timezone: %v", err)
	}
	// Set the process-wide local timezone to IST so time.Now() is always IST.
	time.Local = IST

	dsn := os.Getenv("DB_DSN")
	if dsn == "" {
		host := getEnv("DB_HOST", "localhost")
		port := getEnv("DB_PORT", "3306")
		user := getEnv("DB_USER", "root")
		pass := getEnv("DB_PASSWORD", "")
		name := getEnv("DB_NAME", "CampusTradingB")
		// loc=Asia%2FKolkata tells the MySQL driver to interpret DATETIME values as IST.
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4&loc=Asia%%2FKolkata",
			user, pass, host, port, name)
	}

	DB, err = sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("db: failed to open: %v", err)
	}

	DB.SetMaxOpenConns(25)
	DB.SetMaxIdleConns(10)
	DB.SetConnMaxLifetime(5 * time.Minute)

	if err = DB.Ping(); err != nil {
		log.Fatalf("db: failed to ping MySQL: %v", err)
	}

	// Ensure every MySQL connection uses IST for NOW() / CURRENT_TIMESTAMP.
	if _, err = DB.Exec("SET time_zone = '+05:30'"); err != nil {
		log.Fatalf("db: failed to set timezone: %v", err)
	}

	log.Println("db: connected to MySQL (timezone: IST UTC+05:30)")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
