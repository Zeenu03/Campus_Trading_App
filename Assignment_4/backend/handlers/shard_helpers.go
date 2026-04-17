package handlers

import (
	"context"
	"database/sql"
	"fmt"

	appdb "campus-trading/db"
	"campus-trading/sharding"
)

func listingShardDB(listingID int) *sql.DB {
	db, _ := appdb.ShardConnectionForRecordID(listingID)
	return db
}

func shardDBForTableRow(tableName string, rowID int) *sql.DB {
	target, route, err := sharding.RouteTableRow(tableName, rowID)
	if err != nil {
		return appdb.DB
	}
	if route.Placement == sharding.PlacementCentral {
		return centralShardDB()
	}
	if route.Placement == sharding.PlacementReplicate {
		return appdb.ShardConnectionForID(0)
	}
	return appdb.ShardConnectionForID(target.ShardID)
}

func centralShardDB() *sql.DB {
	return appdb.ShardConnectionForID(0)
}

func replicatedShardDB() *sql.DB {
	return appdb.ShardConnectionForID(0)
}

func memberShardDB(memberID int) *sql.DB {
	return shardDBForTableRow("Member", memberID)
}

func wishRequestShardDB(wishRequestID int) *sql.DB {
	return shardDBForTableRow("WishRequest", wishRequestID)
}

func notificationShardDB(notificationID int) *sql.DB {
	return shardDBForTableRow("Notification", notificationID)
}

func watchlistShardDB(watchlistID int) *sql.DB {
	return shardDBForTableRow("Watchlist", watchlistID)
}

func reportShardDB(reportID int) *sql.DB {
	return shardDBForTableRow("Report", reportID)
}

func ratingShardDB(ratingID int) *sql.DB {
	return shardDBForTableRow("Rating", ratingID)
}

func threadShardDB(threadID int) *sql.DB {
	return shardDBForTableRow("MessageThread", threadID)
}

func offerShardDB(offerID int) *sql.DB {
	return shardDBForTableRow("Offer", offerID)
}

func transactionShardDB(transactionID int) *sql.DB {
	return shardDBForTableRow("Transaction", transactionID)
}

func messageShardDB(messageID int) *sql.DB {
	return shardDBForTableRow("Message", messageID)
}

func loadListingTitleFromShard(ctx context.Context, listingID int) string {
	var title string
	_ = listingShardDB(listingID).QueryRowContext(ctx, `SELECT Title FROM Listing WHERE ListingID = ?`, listingID).Scan(&title)
	return title
}

func listingTx(ctx context.Context, listingID int) (*sql.Tx, error) {
	return listingShardDB(listingID).BeginTx(ctx, nil)
}

func rowFromAllShards(ctx context.Context, scanDest []any, query string, args ...any) (*sql.DB, error) {
	for _, shardDB := range appdb.AllShardConnections() {
		err := shardDB.QueryRowContext(ctx, query, args...).Scan(scanDest...)
		if err == nil {
			return shardDB, nil
		}
		if err != sql.ErrNoRows {
			return nil, err
		}
	}
	return nil, sql.ErrNoRows
}

func rowsFromAllShards(ctx context.Context, query string, args ...any) ([]*sql.Rows, error) {
	rows := make([]*sql.Rows, 0, len(appdb.AllShardConnections()))
	for _, shardDB := range appdb.AllShardConnections() {
		shardRows, err := shardDB.QueryContext(ctx, query, args...)
		if err != nil {
			for _, existing := range rows {
				existing.Close()
			}
			return nil, err
		}
		rows = append(rows, shardRows)
	}
	return rows, nil
}

func nextRecordID(ctx context.Context, tableName string, pkColumn string) (int, error) {
	_, route, err := sharding.RouteTableRow(tableName, 0)
	if err == nil && (route.Placement == sharding.PlacementCentral || route.Placement == sharding.PlacementReplicate) {
		query := fmt.Sprintf("SELECT COALESCE(MAX(%s), 0) FROM %s", pkColumn, tableName)
		var maxID int
		if err := centralShardDB().QueryRowContext(ctx, query).Scan(&maxID); err != nil {
			return 0, err
		}
		return maxID + 1, nil
	}
	maxID := 0
	for _, shardDB := range appdb.AllShardConnections() {
		query := fmt.Sprintf("SELECT COALESCE(MAX(%s), 0) FROM %s", pkColumn, tableName)
		var shardMax int
		if err := shardDB.QueryRowContext(ctx, query).Scan(&shardMax); err != nil {
			return 0, err
		}
		if shardMax > maxID {
			maxID = shardMax
		}
	}
	return maxID + 1, nil
}
