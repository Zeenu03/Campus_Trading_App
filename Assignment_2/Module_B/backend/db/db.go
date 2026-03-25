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
		host := os.Getenv("DB_HOST")
		if host == "" {
			log.Fatalf("DB_HOST is not set in the environment variables")
		}
		port := os.Getenv("DB_PORT")
		if port == "" {
			log.Fatalf("DB_PORT is not set in the environment variables")
		}
		user := os.Getenv("DB_USER")
		if user == "" {
			log.Fatalf("DB_USER is not set in the environment variables")
		}
		pass := os.Getenv("DB_PASSWORD")
		if pass == "" {
			log.Fatalf("DB_PASSWORD is not set in the environment variables")
		}
		name := os.Getenv("DB_NAME")
		if name == "" {
			log.Fatalf("DB_NAME is not set in the environment variables")
		}
		// loc=Asia%2FKolkata  — driver parses DATETIME values back into IST time.Time.
		// time_zone=%2B05%3A30 — driver issues SET time_zone='+05:30' on EVERY new
		//   connection it opens, so CURRENT_TIMESTAMP(3) in triggers and table defaults
		//   always produces IST regardless of MySQL's global timezone setting.
		fmt.Println(user, pass, host, port, name)
		dsn = fmt.Sprintf(
			"%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4",
			user, pass, host, port, name,
		)
		fmt.Println(dsn)
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

	log.Println("db: connected to MySQL (timezone: IST UTC+05:30)")
}
