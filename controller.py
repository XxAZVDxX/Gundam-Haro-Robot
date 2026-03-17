import socket

UDP_IP = "0.0.0.0"
UDP_PORT = 8080

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"Haro Full Controller Listening on {UDP_PORT}...")

try:
    while True:
        data, addr = sock.recvfrom(1024)
        message = data.decode("utf-8")
        
        try:
            parts = message.split(',')
            
            # --- PARSE JOYSTICKS (Float -1.0 to 1.0) ---
            lx = float(parts[0])
            ly = float(parts[1])
            rx = float(parts[2])
            ry = float(parts[3])
            
            # --- PARSE BUTTONS (Integer 0 or 1) ---
            btn_a = int(parts[4])
            btn_b = int(parts[5])
            btn_x = int(parts[6])
            btn_y = int(parts[7])
            btn_l1 = int(parts[8])
            btn_r1 = int(parts[9])
            
            # --- PARSE D-PAD (Integer 0 or 1) ---
            d_up = int(parts[10])
            d_down = int(parts[11])
            d_left = int(parts[12])
            d_right = int(parts[13])
            
            # --- PARSE EYE COLOR (Integer 0-3) ---
            eye_idx = int(parts[14])

            # === YOUR ROBOT LOGIC HERE ===
            
            # Example: Shoot if 'A' is pressed
            if btn_a == 1:
                print("FIRE WEAPON!")

            # Example: Open Ear Flaps if L1/R1 pressed
            if btn_l1 == 1:
                print("Left Flap Open")

            # Debug Print (Only printing X button to keep screen clean)
            # print(f"L:({lx:.1f},{ly:.1f}) BtnA:{btn_a} Eye:{eye_idx}")

        except (ValueError, IndexError):
            pass
            
except KeyboardInterrupt:
    print("Stopping...")