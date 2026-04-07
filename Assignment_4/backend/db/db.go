package db

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"strconv"
	"time"

	mysql "github.com/go-sql-driver/mysql"

	"campus-trading/sharding"
)

var DB *sql.DB

var Shards []*sql.DB

func Init() {
	var err error
	var baseDatabase string

	dsn := os.Getenv("DB_DSN")
	name := getEnv("DB_NAME", "CampusTradingB")
	if dsn == "" {
		host := getEnv("DB_HOST", "localhost")
		port := getEnv("DB_PORT", "3306")
		user := getEnv("DB_USER", "root")
		pass := getEnv("DB_PASSWORD", "")

		dsn = fmt.Sprintf(
			"%s:%s@tcp(%s:%s)/%s?parseTime=true&charset=utf8mb4&loc=UTC",
			user, pass, host, port, name,
		)
	}

	baseDatabase = name
	if parsed, parseErr := mysql.ParseDSN(dsn); parseErr == nil && parsed.DBName != "" {
		baseDatabase = parsed.DBName
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

	sharding.Configure(baseDatabase, sharding.DefaultShardCount)
	Shards = openShardConnections(baseDatabase, sharding.DefaultShardCount, dsn)

	log.Printf("db: connected to MySQL (database=%s, shards=%d, timezone: UTC)", baseDatabase, sharding.DefaultShardCount)
}

func openShardConnections(baseDatabase string, shardCount int, dsn string) []*sql.DB {
	connections := make([]*sql.DB, 0, shardCount)
	for shardID := 0; shardID < shardCount; shardID++ {
		shardDSN := replaceDBName(dsn, fmt.Sprintf("%s_shard_%d", baseDatabase, shardID))
		conn, err := sql.Open("mysql", shardDSN)
		if err != nil {
			log.Fatalf("db: failed to open shard %d: %v", shardID, err)
		}
		conn.SetMaxOpenConns(25)
		conn.SetMaxIdleConns(10)
		conn.SetConnMaxLifetime(5 * time.Minute)
		if err := conn.Ping(); err != nil {
			log.Fatalf("db: failed to ping shard %d: %v", shardID, err)
		}
		connections = append(connections, conn)
	}
	return connections
}

func replaceDBName(dsn, database string) string {
	parsed, err := mysql.ParseDSN(dsn)
	if err != nil {
		return dsn
	}
	parsed.DBName = database
	return parsed.FormatDSN()
}

func ShardDatabaseName(shardID int) string {
	return fmt.Sprintf("%s_shard_%d", sharding.CurrentConfiguration().BaseDatabase, shardID)
}

func ShardConnectionForRecordID(recordID int) (*sql.DB, int) {
	config := sharding.CurrentConfiguration()
	router := sharding.NewRouter(config.BaseDatabase, config.ShardCount)
	target := router.TargetFor(recordID)
	return ShardConnectionForID(target.ShardID), target.ShardID
}

func ShardConnectionForID(shardID int) *sql.DB {
	if shardID < 0 || shardID >= len(Shards) {
		return DB
	}
	return Shards[shardID]
}

func AllShardConnections() []*sql.DB {
	return append([]*sql.DB(nil), Shards...)
}

func ShardCount() int {
	return len(Shards)
}

func ParseShardID(value string) int {
	shardID, err := strconv.Atoi(value)
	if err != nil {
		return 0
	}
	return shardID
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
