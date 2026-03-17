import time
import struct
import socket
import select
import can
import evdev
from evdev import ecodes
from smbus2 import SMBus
from adafruit_servokit import ServoKit

# ==========================================
# 1. CONFIGURATION
# ==========================================

# --- WIFI UDP CONFIG ---
UDP_IP = "0.0.0.0"
UDP_PORT = 8080
PHONE_IP = None
PHONE_PORT = 8080

# --- USB CONTROLLER CONFIG ---
CONTROLLER_PATH = '/dev/input/event2' # Check this on your Pi!

# --- CAN BUS (MIT Motors) ---
CAN_INTERFACE = 'can0'
ID_M1 = 1  # Left Stick X
ID_M2 = 2  # Left Stick Y
ID_M3 = 3  # L1/R1
MIT_MAX_SPEED = 10.0
P_MIN, P_MAX = -12.5, 12.5
V_MIN, V_MAX = -65.0, 65.0
KP_MIN, KP_MAX = 0.0, 500.0
KD_MIN, KD_MAX = 0.0, 5.0
T_MIN, T_MAX = -18.0, 18.0

# --- HARDWARE ---
SERVO_CH1 = 0       # Right Stick Y (Existing)
SERVO_L2_CH = 1     # L2 Trigger (New)
SERVO_R2_CH = 2     # R2 Trigger (New)

INA226_ADDRESS = 0x45
INA_REG_BUS_VOLTAGE = 0x02
BATTERY_CELLS = 6
LOW_VOLT_LIMIT = 3.5 * BATTERY_CELLS

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================

def float_to_uint(x, x_min, x_max, bits):
    span = x_max - x_min
    if x < x_min: x = x_min
    elif x > x_max: x = x_max
    return int((x - x_min) * ((1 << bits) - 1) / span)

def pack_mit_message(p_des, v_des, kp, kd, t_ff):
    p_int = float_to_uint(p_des, P_MIN, P_MAX, 16)
    v_int = float_to_uint(v_des, V_MIN, V_MAX, 12)
    kp_int = float_to_uint(kp, KP_MIN, KP_MAX, 12)
    kd_int = float_to_uint(kd, KD_MIN, KD_MAX, 12)
    t_int = float_to_uint(t_ff, T_MIN, T_MAX, 12)
    buf = bytearray(8)
    buf[0] = (p_int >> 8) & 0xFF
    buf[1] = p_int & 0xFF
    buf[2] = (v_int >> 4) & 0xFF
    buf[3] = ((v_int & 0xF) << 4) | ((kp_int >> 8) & 0xF)
    buf[4] = kp_int & 0xFF
    buf[5] = (kd_int >> 4) & 0xFF
    buf[6] = ((kd_int & 0xF) << 4) | ((t_int >> 8) & 0xF)
    buf[7] = t_int & 0xFF
    return buf

def log(tag, message):
    full_msg = f"{tag}:{message}"
    print(full_msg)
    if PHONE_IP:
        try:
            sock.sendto(full_msg.encode(), (PHONE_IP, PHONE_PORT))
        except: pass

def send_motor_command(bus, motor_id, velocity):
    data = pack_mit_message(0.0, velocity, 0.0, 1.0, 0.0)
    msg = can.Message(arbitration_id=motor_id, data=data, is_fd=True)
    try:
        bus.send(msg)
    except can.CanError:
        log("ERROR", f"CAN Send Fail ID {motor_id}")

def read_battery_voltage(bus_i2c):
    try:
        raw = bus_i2c.read_word_data(INA226_ADDRESS, INA_REG_BUS_VOLTAGE)
        swapped = ((raw << 8) & 0xFF00) | ((raw >> 8) & 0x00FF)
        return swapped * 0.00125
    except: return 0.0

# ==========================================
# 3. INITIALIZATION
# ==========================================
print("--- Haro Universal Brain Init ---")

# 1. NETWORKING
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
sock.setblocking(False)
print(f"UDP Listening on {UDP_PORT}")

# 2. PHYSICAL CONTROLLER
gamepad = None
try:
    gamepad = evdev.InputDevice(CONTROLLER_PATH)
    print(f"USB Controller: {gamepad.name}")
except FileNotFoundError:
    print("USB Controller NOT found (WiFi Only Mode)")

# 3. MOTORS & SERVOS
try:
    can_bus = can.interface.Bus(channel=CAN_INTERFACE, bustype='socketcan', fd=True)
except OSError:
    log("ERROR", "CAN Bus Fail")

try:
    servo_kit = ServoKit(channels=16)
except:
    log("ERROR", "Servo Driver Fail")

i2c_bus = SMBus(1)

# Enable Motors
for mid in [ID_M1, ID_M2, ID_M3]:
    send_motor_command(can_bus, mid, 0.0)

# ==========================================
# 4. MAIN LOOP (MULTIPLEXER)
# ==========================================
last_batt_check = 0
active_source = "NONE" # Remembers if we are using "WIFI" or "USB"

# State Variables
lx, ly, rx, ry = 0.0, 0.0, 0.0, 0.0
btn_l1, btn_r1 = 0, 0
l2_val, r2_val = 0.0, 0.0  # <--- NEW: Trigger values (0.0 to 1.0)

try:
    while True:
        # Prepare list of inputs to check (Socket + USB Controller if it exists)
        potential_readers = [sock]
        if gamepad:
            potential_readers.append(gamepad)
        
        # 'select' waits until one of them has data (timeout 0.01s)
        ready_to_read, _, _ = select.select(potential_readers, [], [], 0.01)

        for source in ready_to_read:
            
            # CASE A: WIFI DATA RECEIVED
            if source == sock:
                try:
                    data, addr = sock.recvfrom(1024)
                    PHONE_IP = addr[0]
                    msg = data.decode("utf-8")
                    parts = msg.split(',')
                    
                    # Update State from WiFi
                    # CSV Format: lx, ly, rx, ry, A, B, X, Y, L1, R1, L2, R2 ...
                    if len(parts) >= 10:
                        lx, ly = float(parts[0]), float(parts[1])
                        rx, ry = float(parts[2]), float(parts[3])
                        btn_l1, btn_r1 = int(parts[8]), int(parts[9])
                    
                    # <--- NEW: Parse L2 (index 10) and R2 (index 11)
                    if len(parts) >= 12:
                        l2_val = float(parts[10])
                        r2_val = float(parts[11])
                    
                    active_source = "WIFI"
                except: pass

            # CASE B: USB CONTROLLER EVENT
            elif source == gamepad:
                for event in gamepad.read():
                    if event.type == ecodes.EV_ABS:
                        # Normalize 32768 to 1.0
                        val = event.value / 32768.0
                        if event.code == ecodes.ABS_X: lx = val
                        elif event.code == ecodes.ABS_Y: ly = -val # Invert Y
                        elif event.code == ecodes.ABS_RX: rx = val
                        elif event.code == ecodes.ABS_RY: ry = -val
                        # USB Triggers often use ABS_Z and ABS_RZ (Check your specific controller!)
                        elif event.code == ecodes.ABS_Z: l2_val = max(0.0, val) # Usually 0..255 or 0..1024
                        elif event.code == ecodes.ABS_RZ: r2_val = max(0.0, val)
                        
                    elif event.type == ecodes.EV_KEY:
                        if event.code == ecodes.BTN_TL: btn_l1 = event.value
                        elif event.code == ecodes.BTN_TR: btn_r1 = event.value
                    
                    active_source = "USB"

        # --- EXECUTE LOGIC (Regardless of Source) ---
        
        # Deadzone
        if abs(lx) < 0.1: lx = 0
        if abs(ly) < 0.1: ly = 0

        # Drive Motors
        v1 = lx * MIT_MAX_SPEED
        v2 = -ly * MIT_MAX_SPEED # Inverted Y for M2
        
        v3 = 0.0
        if btn_l1: v3 -= MIT_MAX_SPEED
        if btn_r1: v3 += MIT_MAX_SPEED

        send_motor_command(can_bus, ID_M1, v1)
        send_motor_command(can_bus, ID_M2, v2)
        send_motor_command(can_bus, ID_M3, v3)

        # --- SERVO CONTROL ---
        
        # 1. Head/Camera (Right Stick Y) -> Channel 0
        servo_angle_1 = (ry + 1.0) * 90
        servo_angle_1 = max(0, min(180, servo_angle_1))
        try:
            servo_kit.servo[SERVO_CH1].angle = servo_angle_1
        except: pass

        # 2. L2 Trigger -> Channel 1 (NEW)
        # Maps 0.0-1.0 to 0-180 degrees
        l2_angle = l2_val * 180
        l2_angle = max(0, min(180, l2_angle))
        try:
            servo_kit.servo[SERVO_L2_CH].angle = l2_angle
        except: pass

        # 3. R2 Trigger -> Channel 2 (NEW)
        # Maps 0.0-1.0 to 0-180 degrees
        r2_angle = r2_val * 180
        r2_angle = max(0, min(180, r2_angle))
        try:
            servo_kit.servo[SERVO_R2_CH].angle = r2_angle
        except: pass

        # --- BATTERY & LOGS ---
        if time.time() - last_batt_check > 2.0:
            volts = read_battery_voltage(i2c_bus)
            
            status = "OK"
            if volts < LOW_VOLT_LIMIT: status = "LOW"
            
            # Send log to phone (Even if using USB controller!)
            log("BATTERY", f"{volts:.2f}V [{status}] Src:{active_source}")
            last_batt_check = time.time()

except KeyboardInterrupt:
    print("\nStopping...")
    for mid in [ID_M1, ID_M2, ID_M3]:
        send_motor_command(can_bus, mid, 0.0)