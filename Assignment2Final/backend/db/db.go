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

func Init() {
	dsn := os.Getenv("DB_DSN")
	if dsn == "" {
		host := getEnv("DB_HOST", "localhost")
		port := getEnv("DB_PORT", "3306")
		user := getEnv("DB_USER", "root")
		pass := getEnv("DB_PASSWORD", "")
		name := getEnv("DB_NAME", "CampusTradingB")
		dsn = fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4&loc=Local",
			user, pass, host, port, name)
	}

	var err error
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
	log.Println("db: connected to MySQL")
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
