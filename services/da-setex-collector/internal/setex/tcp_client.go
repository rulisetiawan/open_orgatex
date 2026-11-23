package setex

import (
	"encoding/binary"
	"fmt"
	"io"
	"math"
	"net"
	"time"
)

const FrameSize = 516

// TCPClient manages communication with SETEX SECOM controller on TCP port 50000.
type TCPClient struct {
	Host    string
	Port    int
	Timeout time.Duration
}

func NewTCPClient(host string, port int, timeout time.Duration) *TCPClient {
	if timeout <= 0 {
		timeout = 3 * time.Second
	}
	return &TCPClient{
		Host:    host,
		Port:    port,
		Timeout: timeout,
	}
}

// BuildReadFrame constructs standard 516-byte SC737 read frame.
// service: 1 = SV_READ, 11 = SV_READ_BLOCK.
func BuildReadFrame(service byte, obj uint16, startAddress uint16, count uint16) []byte {
	var payload []byte
	if service == 1 {
		payload = make([]byte, 2)
		binary.LittleEndian.PutUint16(payload, startAddress)
	} else {
		payload = make([]byte, 4)
		binary.LittleEndian.PutUint16(payload[0:2], startAddress)
		binary.LittleEndian.PutUint16(payload[2:4], count)
	}

	frame := make([]byte, FrameSize)
	binary.LittleEndian.PutUint16(frame[0:2], 2)                     // Magic
	binary.LittleEndian.PutUint16(frame[2:4], uint16(16+len(payload))) // Header + payload length
	frame[4] = 10
	frame[5] = 12
	frame[6] = 0
	binary.LittleEndian.PutUint16(frame[9:11], 1)
	frame[14] = 1       // Message Type: 1 = Request
	frame[15] = service // Service: 11 = SV_READ_BLOCK
	binary.LittleEndian.PutUint16(frame[16:18], obj)
	binary.LittleEndian.PutUint16(frame[18:20], uint16(len(payload)))
	copy(frame[20:20+len(payload)], payload)

	return frame
}

// Exchange connects to the controller, sends the request frame, and reads the 516-byte response.
func (c *TCPClient) Exchange(reqFrame []byte) ([]byte, error) {
	addr := fmt.Sprintf("%s:%d", c.Host, c.Port)
	conn, err := net.DialTimeout("tcp", addr, c.Timeout)
	if err != nil {
		return nil, fmt.Errorf("dial controller %s: %w", addr, err)
	}
	defer conn.Close()

	if err := conn.SetDeadline(time.Now().Add(c.Timeout)); err != nil {
		return nil, fmt.Errorf("set deadline: %w", err)
	}

	if _, err := conn.Write(reqFrame); err != nil {
		return nil, fmt.Errorf("send frame: %w", err)
	}

	resp := make([]byte, FrameSize)
	if _, err := io.ReadFull(conn, resp); err != nil {
		return nil, fmt.Errorf("read response frame: %w", err)
	}

	return resp, nil
}

// ValidateFrame validates the header of a 516-byte response frame.
func ValidateFrame(resp []byte, service byte, obj uint16) (int, error) {
	if len(resp) != FrameSize {
		return 0, fmt.Errorf("invalid frame size: expected %d, got %d", FrameSize, len(resp))
	}

	magic := binary.LittleEndian.Uint16(resp[0:2])
	declared := binary.LittleEndian.Uint16(resp[2:4])
	replyObj := binary.LittleEndian.Uint16(resp[16:18])
	size := binary.LittleEndian.Uint16(resp[18:20])

	if magic != 2 || declared != size+16 {
		return 0, fmt.Errorf("invalid magic or declared size in header (magic=%d, declared=%d, size=%d)", magic, declared, size)
	}

	if resp[15] != service || replyObj != obj {
		return 0, fmt.Errorf("response mismatch: expected service=%d, obj=%d; got service=%d, obj=%d", service, obj, resp[15], replyObj)
	}

	if resp[14] != 2 {
		return 0, fmt.Errorf("controller rejected request (msg_type=%d)", resp[14])
	}

	return int(size), nil
}

// ReadBlock reads a block of uint16 registers (e.g. Object 1025 Info Words).
func (c *TCPClient) ReadBlock(obj uint16, startAddress uint16, count uint16) ([]uint16, []byte, error) {
	if count < 1 || count > 240 {
		return nil, nil, fmt.Errorf("count must be between 1 and 240 (requested %d)", count)
	}

	req := BuildReadFrame(11, obj, startAddress, count)
	resp, err := c.Exchange(req)
	if err != nil {
		return nil, nil, err
	}

	size, err := ValidateFrame(resp, 11, obj)
	if err != nil {
		return nil, resp, err
	}

	expectedBytes := int(count) * 2
	if size != expectedBytes {
		return nil, resp, fmt.Errorf("payload size mismatch: expected %d bytes, got %d", expectedBytes, size)
	}

	words := make([]uint16, count)
	for i := 0; i < int(count); i++ {
		offset := 20 + i*2
		words[i] = binary.LittleEndian.Uint16(resp[offset : offset+2])
	}

	return words, resp, nil
}

// ReadSETBlock reads target setpoint registers (Object 1009 SET/SOLL words).
func (c *TCPClient) ReadSETBlock(startAddress uint16, count uint16) ([]uint16, error) {
	words, _, err := c.ReadBlock(1009, startAddress, count)
	return words, err
}

// ReadActiveFunction reads active function parameters from Object 6 (e.g. Func 141 Temp Control, Func 713 Fill).
func (c *TCPClient) ReadActiveFunction(funcID uint16) ([]float32, []uint16, error) {
	frame := make([]byte, FrameSize)
	binary.LittleEndian.PutUint16(frame[0:2], 2)
	binary.LittleEndian.PutUint16(frame[2:4], 80)
	frame[4] = 10
	frame[5] = 12
	frame[6] = 0
	binary.LittleEndian.PutUint16(frame[9:11], 1)
	frame[14] = 1 // Message Type: 1 = Request
	frame[15] = 1 // Service: 1 = SV_READ
	binary.LittleEndian.PutUint16(frame[16:18], 6)  // Object 6
	binary.LittleEndian.PutUint16(frame[18:20], 64) // Payload Length 64
	frame[20] = 0                                  // Active line 0
	binary.LittleEndian.PutUint16(frame[21:23], funcID)

	resp, err := c.Exchange(frame)
	if err != nil {
		return nil, nil, err
	}

	if _, err := ValidateFrame(resp, 1, 6); err != nil {
		return nil, nil, err
	}

	values := make([]float32, 6)
	paramIDs := make([]uint16, 6)
	for i := 0; i < 6; i++ {
		offsetVal := 25 + 8*i
		offsetPID := 29 + 8*i
		if offsetPID+2 <= len(resp) {
			bits := binary.LittleEndian.Uint32(resp[offsetVal : offsetVal+4])
			values[i] = math.Float32frombits(bits)
			paramIDs[i] = binary.LittleEndian.Uint16(resp[offsetPID : offsetPID+2])
		}
	}

	return values, paramIDs, nil
}
