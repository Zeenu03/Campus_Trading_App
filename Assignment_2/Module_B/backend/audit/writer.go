package audit

import (
	"fmt"
	"os"
	"sync"
	"time"
)

var (
	mu      sync.Mutex
	logPath string
	ist     *time.Location
)

func Init(path string) {
	logPath = path
	// Load IST explicitly so Append never depends on the process-wide time.Local.
	var err error
	ist, err = time.LoadLocation("Asia/Kolkata")
	if err != nil {
		// Fallback: fixed offset UTC+05:30 requires no tzdata file.
		ist = time.FixedZone("IST", 5*60*60+30*60)
	}
	if err := os.MkdirAll(dirOf(path), 0755); err != nil {
		fmt.Fprintf(os.Stderr, "audit: cannot create log dir: %v\n", err)
	}
}

// Append writes one structured line to the audit log file.
// Timestamps are always in IST (UTC+05:30).
func Append(sessionID, action, targetTable, targetID, ipAddress, status string, userID int) {
	mu.Lock()
	defer mu.Unlock()

	if logPath == "" {
		logPath = "./logs/audit.log"
	}
	if ist == nil {
		ist = time.FixedZone("IST", 5*60*60+30*60)
	}

	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "audit: cannot open log file: %v\n", err)
		return
	}
	defer f.Close()

	sid := sessionID
	if sid == "" {
		sid = "NULL"
	}

	line := fmt.Sprintf("[%s] session=%s user_id=%d action=%s table=%s id=%s ip=%s status=%s\n",
		time.Now().In(ist).Format(time.RFC3339Nano),
		sid,
		userID,
		action,
		targetTable,
		targetID,
		ipAddress,
		status,
	)
	_, _ = f.WriteString(line)
}

func dirOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' || path[i] == '\\' {
			return path[:i]
		}
	}
	return "."
}
