CREATE TABLE IF NOT EXISTS `Directories` (
    `path` TEXT PRIMARY KEY,
    `vencoder` TEXT NOT NULL,
    `aencoder` TEXT NOT NULL,
    `sencoder` TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS `Files` (
    `uuid` TEXT PRIMARY KEY,
    `parentDir` TEXT NOT NULL REFERENCES `Directories`(`path`),
    `filePath` TEXT NOT NULL UNIQUE,
    `preservePath` TEXT DEFAULT NULL UNIQUE,
    `streams` TEXT NOT NULL DEFAULT '[]',
    `format` TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS `Events` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `timestamp` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `fileId` TEXT NOT NULL REFERENCES `Files`(`uuid`),
    `level` INTEGER NOT NULL,
    `message` TEXT NOT NULL
);