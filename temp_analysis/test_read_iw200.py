import socket
import struct

HOST = "172.16.110.160"
PORT = 50000

def test_read(count=200):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((HOST, PORT))
        
        # Build frame:
        # frame header: 20 bytes
        # magic=2, declared_len=payload_len+16, station=1, msg_type=1, service=11, obj=1025, size=4
        # payload for read: startAddress (uint16), count (uint16)
        payload = struct.pack('<HH', 1, count)
        header = bytearray(20)
        struct.pack_into('<H', header, 0, 2)
        struct.pack_into('<H', header, 2, len(payload) + 16)
        struct.pack_into('<H', header, 9, 1)
        header[14] = 1 # Request
        header[15] = 11 # SV_READ_BLOCK
        struct.pack_into('<H', header, 16, 1025)
        struct.pack_into('<H', header, 18, len(payload))
        
        req = header + payload
        req = req.ljust(516, b'\x00')
        s.sendall(req)
        
        resp = s.recv(516)
        s.close()
        
        if len(resp) < 20:
            print("Response too short:", len(resp))
            return
            
        magic = struct.unpack_from('<H', resp, 0)[0]
        declared = struct.unpack_from('<H', resp, 2)[0]
        msg_type = resp[14]
        service = resp[15]
        obj = struct.unpack_from('<H', resp, 16)[0]
        size = struct.unpack_from('<H', resp, 18)[0]
        
        print(f"Read count={count}:")
        print(f"  magic={magic}, declared={declared}, msg_type={msg_type}, service={service}, obj={obj}, size={size}")
        if msg_type == 2:
            words = [struct.unpack_from('<H', resp, 20 + i*2)[0] for i in range(size // 2)]
            print(f"  Successfully read {len(words)} words!")
            print(f"  Word 1 (IW1): {words[0]}, Word 10 (IW10): {words[9]}, Word 94: {words[93]}")
            if len(words) >= 183:
                print(f"  Word 183 (IW183): {words[182]}")
        else:
            print(f"  Controller rejected request with msg_type={msg_type}")
    except Exception as e:
        print("Error:", e)

test_read(200)
