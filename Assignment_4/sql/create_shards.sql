-- Assignment 4: create 3 logical shards using modulo routing
-- Base application database name: CampusTradingB
-- Shard key rule: shard_id = record_id % 3

CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_0;
CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_1;
CREATE DATABASE IF NOT EXISTS CampusTradingB_shard_2;

-- Reference tables are replicated to every shard.
-- Partitioned tables are created in dependency order so foreign keys can be restored safely.
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Member LIKE CampusTradingB.Member;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Member LIKE CampusTradingB.Member;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Member LIKE CampusTradingB.Member;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Administrator LIKE CampusTradingB.Administrator;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Administrator LIKE CampusTradingB.Administrator;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Administrator LIKE CampusTradingB.Administrator;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Category LIKE CampusTradingB.Category;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Category LIKE CampusTradingB.Category;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Category LIKE CampusTradingB.Category;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.WishRequest LIKE CampusTradingB.WishRequest;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.WishRequest LIKE CampusTradingB.WishRequest;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.WishRequest LIKE CampusTradingB.WishRequest;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Listing LIKE CampusTradingB.Listing;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Listing LIKE CampusTradingB.Listing;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Listing LIKE CampusTradingB.Listing;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.ListingImage LIKE CampusTradingB.ListingImage;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.ListingImage LIKE CampusTradingB.ListingImage;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.ListingImage LIKE CampusTradingB.ListingImage;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Offer LIKE CampusTradingB.Offer;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Offer LIKE CampusTradingB.Offer;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Offer LIKE CampusTradingB.Offer;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.`Transaction` LIKE CampusTradingB.`Transaction`;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.`Transaction` LIKE CampusTradingB.`Transaction`;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.`Transaction` LIKE CampusTradingB.`Transaction`;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.MessageThread LIKE CampusTradingB.MessageThread;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.MessageThread LIKE CampusTradingB.MessageThread;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.MessageThread LIKE CampusTradingB.MessageThread;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Message LIKE CampusTradingB.Message;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Message LIKE CampusTradingB.Message;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Message LIKE CampusTradingB.Message;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Notification LIKE CampusTradingB.Notification;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Notification LIKE CampusTradingB.Notification;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Notification LIKE CampusTradingB.Notification;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Watchlist LIKE CampusTradingB.Watchlist;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Watchlist LIKE CampusTradingB.Watchlist;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Watchlist LIKE CampusTradingB.Watchlist;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Report LIKE CampusTradingB.Report;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Report LIKE CampusTradingB.Report;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Report LIKE CampusTradingB.Report;

CREATE TABLE IF NOT EXISTS CampusTradingB_shard_0.Rating LIKE CampusTradingB.Rating;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_1.Rating LIKE CampusTradingB.Rating;
CREATE TABLE IF NOT EXISTS CampusTradingB_shard_2.Rating LIKE CampusTradingB.Rating;

-- Data migration will use the modulo router in Go:
--   shard_id = ListingID % 3
--   shard_id = MemberID % 3
-- Follow-up step: copy rows from CampusTradingB into the appropriate shard.
