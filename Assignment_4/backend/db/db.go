package db

import (
	"database/sql"
	"fmt"
	"log"
	"net"
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
	shardUser := getEnv("SHARD_USER", getEnv("DB_USER", "root"))
	shardPassword := getEnv("SHARD_PASSWORD", getEnv("DB_PASSWORD", ""))
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

	defaultHost, defaultPort := shardDefaultsFromDSN(dsn)
	shardTargets := loadShardTargets(baseDatabase, sharding.DefaultShardCount, defaultHost, defaultPort)
	sharding.Configure(baseDatabase, sharding.DefaultShardCount, shardTargets)
	Shards = openShardConnections(dsn, baseDatabase, shardTargets, shardUser, shardPassword)

	log.Printf("db: connected to MySQL (database=%s, shards=%d, timezone: UTC)", baseDatabase, len(Shards))
}

func shardDefaultsFromDSN(dsn string) (string, string) {
	defaultHost := getEnv("DB_HOST", "localhost")
	defaultPort := getEnv("DB_PORT", "3306")
	if parsed, err := mysql.ParseDSN(dsn); err == nil && parsed.Addr != "" {
		if host, port, splitErr := net.SplitHostPort(parsed.Addr); splitErr == nil {
			defaultHost = host
			defaultPort = port
		}
	}
	return defaultHost, defaultPort
}

func loadShardTargets(baseDatabase string, shardCount int, defaultHost string, defaultPort string) []sharding.ShardTarget {
	targets := make([]sharding.ShardTarget, 0, shardCount)
	for shardID := 0; shardID < shardCount; shardID++ {
		host := getEnv(fmt.Sprintf("SHARD_%d_HOST", shardID), defaultHost)
		portValue := getEnv(fmt.Sprintf("SHARD_%d_PORT", shardID), defaultPort)
		port, err := strconv.Atoi(portValue)
		if err != nil {
			port = 3306
		}
		databaseName := getEnv(fmt.Sprintf("SHARD_%d_DB_NAME", shardID), baseDatabase)
		targets = append(targets, sharding.ShardTarget{ShardID: shardID, Host: host, Port: port, DatabaseName: databaseName})
	}
	return targets
}

func openShardConnections(dsn string, baseDatabase string, targets []sharding.ShardTarget, shardUser string, shardPassword string) []*sql.DB {
	connections := make([]*sql.DB, 0, len(targets))
	for _, target := range targets {
		shardDSN := buildShardDSN(dsn, baseDatabase, target, shardUser, shardPassword)
		conn, err := sql.Open("mysql", shardDSN)
		if err != nil {
			log.Fatalf("db: failed to open shard %d: %v", target.ShardID, err)
		}
		conn.SetMaxOpenConns(25)
		conn.SetMaxIdleConns(10)
		conn.SetConnMaxLifetime(5 * time.Minute)
		if err := conn.Ping(); err != nil {
			log.Fatalf("db: failed to ping shard %d: %v", target.ShardID, err)
		}
		connections = append(connections, conn)
	}
	return connections
}

func buildShardDSN(dsn, fallbackDatabase string, target sharding.ShardTarget, shardUser string, shardPassword string) string {
	parsed, err := mysql.ParseDSN(dsn)
	if err != nil {
		return dsn
	}
	if shardUser != "" {
		parsed.User = shardUser
	}
	parsed.Passwd = shardPassword
	if target.DatabaseName != "" {
		parsed.DBName = target.DatabaseName
	} else {
		parsed.DBName = fallbackDatabase
	}
	if target.Host != "" && target.Port > 0 {
		parsed.Addr = net.JoinHostPort(target.Host, strconv.Itoa(target.Port))
	}
	return parsed.FormatDSN()
}

func ShardDatabaseName(shardID int) string {
	config := sharding.CurrentConfiguration()
	if shardID >= 0 && shardID < len(config.Shards) {
		return config.Shards[shardID].DatabaseName
	}
	return config.BaseDatabase
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
