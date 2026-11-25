package setex

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"regexp"
	"sort"
	"sync"
	"time"

	"github.com/jlaffaye/ftp"
)

type FTPClient struct {
	Host     string
	Port     int
	User     string
	Password string
	Timeout  time.Duration
	mu       sync.Mutex

	lastPRSize int64
	lastALSize int64
}

type ControllerStatus struct {
	BatchNo     string    `json:"batch_no"`
	StepNo      int       `json:"step_no"`
	ProgramNo   string    `json:"program_no"`
	StatusText  string    `json:"status_text"`
	RawBytesLen int       `json:"raw_bytes_len"`
	Timestamp   time.Time `json:"timestamp"`
}

func NewFTPClient(host string, port int, user, password string, timeout time.Duration) *FTPClient {
	if timeout <= 0 {
		timeout = 4 * time.Second
	}
	if port <= 0 {
		port = 21
	}
	return &FTPClient{
		Host:     host,
		Port:     port,
		User:     user,
		Password: password,
		Timeout:  timeout,
	}
}

func (c *FTPClient) connect() (*ftp.ServerConn, error) {
	addr := fmt.Sprintf("%s:%d", c.Host, c.Port)
	client, err := ftp.Dial(addr, ftp.DialWithTimeout(c.Timeout), ftp.DialWithDisabledEPSV(true))
	if err != nil {
		return nil, fmt.Errorf("dial ftp %s: %w", addr, err)
	}

	user := c.User
	pass := c.Password
	if user == "" {
		if err := client.Login("anonymous", "anonymous@"); err != nil {
			if err2 := client.Login("anonymous", ""); err2 != nil {
				client.Quit()
				return nil, fmt.Errorf("ftp login failed: %w", err)
			}
		}
	} else if err := client.Login(user, pass); err != nil {
		client.Quit()
		return nil, fmt.Errorf("ftp login failed: %w", err)
	}

	return client, nil
}

// FetchStatusAct retrieves and decodes STATUS.ACT binary file from controller.
func (c *FTPClient) FetchStatusAct() (*ControllerStatus, []byte, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	client, err := c.connect()
	if err != nil {
		return nil, nil, err
	}
	defer client.Quit()

	// Candidate paths
	paths := []string{
		"/Storage/sc777ce/STATUS/STATUS.ACT",
		"/Storage/SC777CE/STATUS/STATUS.ACT",
		"/Flashdisk/SC797CE/STATUS/STATUS.ACT",
		"/Flashdisk/SC797CE/STATUS.ACT",
		"/Storage/sc777ce/STATUS.ACT",
		"/Network/F/OT/10B/STATUS.ACT",
		"STATUS.ACT",
	}

	var statusBytes []byte
	for _, p := range paths {
		r, err := client.Retr(p)
		if err == nil {
			buf, err := io.ReadAll(r)
			r.Close()
			if err == nil && len(buf) > 0 {
				statusBytes = buf
				break
			}
		}
	}

	if len(statusBytes) == 0 {
		return nil, nil, fmt.Errorf("STATUS.ACT not found in candidate paths on %s", c.Host)
	}

	status := &ControllerStatus{
		Timestamp:   time.Now(),
		RawBytesLen: len(statusBytes),
		StatusText:  "RUNNING",
	}

	// 1. Extract batch number at offset 36..48 (skipping leading null bytes in SETEX struct)
	if len(statusBytes) >= 48 {
		trimmed := bytes.TrimLeft(statusBytes[36:48], "\x00 ")
		if idx := bytes.IndexByte(trimmed, 0); idx >= 0 {
			trimmed = trimmed[:idx]
		}
		rawB := regexp.MustCompile(`[^A-Za-z0-9_-]`).ReplaceAllString(string(trimmed), "")
		if len(rawB) >= 4 {
			status.BatchNo = rawB
		}
	}
	if status.BatchNo == "" {
		reBatch := regexp.MustCompile(`\b\d{6}\b`)
		matches := reBatch.FindAllString(string(statusBytes), -1)
		if len(matches) > 0 {
			sort.Strings(matches)
			status.BatchNo = matches[len(matches)-1]
		}
	}

	// 2. Extract Step Number:
	// - SETEX 797CE (size 10188): offset 0x15E
	// - SECOM 777   (size 10104): offset 0x15C
	stepOffset := 0x15C
	if len(statusBytes) == 10188 {
		stepOffset = 0x15E
	}
	if len(statusBytes) >= stepOffset+2 {
		sVal := binary.LittleEndian.Uint16(statusBytes[stepOffset : stepOffset+2])
		if sVal >= 1 && sVal <= 255 {
			status.StepNo = int(sVal)
		}
	}

	// 3. Extract Program Number from offset 52..64 (name) or fallback
	if len(statusBytes) >= 64 {
		rawP := string(statusBytes[52:64])
		for i, ch := range rawP {
			if ch == 0 {
				rawP = rawP[:i]
				break
			}
		}
		rawP = regexp.MustCompile(`[^A-Za-z0-9_-]`).ReplaceAllString(rawP, "")
		if rawP != "" {
			status.ProgramNo = rawP
		}
	}

	return status, statusBytes, nil
}

// FetchBatchLogsDelta checks if PRxxxxxx.LOG or ALxxxxxx.LOG grew in size, and downloads delta.
func (c *FTPClient) FetchBatchLogsDelta(batchNo string) (prNewBytes []byte, alNewBytes []byte, err error) {
	if batchNo == "" {
		return nil, nil, nil
	}

	c.mu.Lock()
	defer c.mu.Unlock()

	client, err := c.connect()
	if err != nil {
		return nil, nil, err
	}
	defer client.Quit()

	prCandidates := []string{
		fmt.Sprintf("/Flashdisk/SC797CE/BATCH/%s/PR%s.LOG", batchNo, batchNo),
		fmt.Sprintf("/Storage/sc777ce/BATCH/%s/PR%s.LOG", batchNo, batchNo),
		fmt.Sprintf("/Network/F/OT/10B/BATCH/%s/PR%s.LOG", batchNo, batchNo),
	}

	for _, p := range prCandidates {
		curSize, err := client.FileSize(p)
		if err == nil && curSize > c.lastPRSize {
			r, err := client.Retr(p)
			if err == nil {
				buf, err := io.ReadAll(r)
				r.Close()
				if err == nil && len(buf) > 0 {
					if int64(len(buf)) > c.lastPRSize {
						prNewBytes = buf[c.lastPRSize:]
					} else {
						prNewBytes = buf
					}
					c.lastPRSize = curSize
					break
				}
			}
		}
	}

	return prNewBytes, alNewBytes, nil
}
