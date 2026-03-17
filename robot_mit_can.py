# import evdev
# import can
# import struct
# import time
# from evdev import InputDevice, ecodes

# # --- CONFIGURATION ---
# CAN_INTERFACE = 'can0'
# MOTOR_ID = 1  # Default ID for most new motors
# # MIT Motor Limits (Check your motor manual!)
# P_MIN, P_MAX = -12.5, 12.5
# V_MIN, V_MAX = -65.0, 65.0
# KP_MIN, KP_MAX = 0.0, 500.0
# KD_MIN, KD_MAX = 0.0, 5.0
# T_MIN, T_MAX = -18.0, 18.0

# # --- HELPER FUNCTIONS (The "Math" Part) ---
# def float_to_uint(x, x_min, x_max, bits):
#     """Converts a float to an unsigned integer within range."""
#     span = x_max - x_min
#     offset = x_min
#     # Clamp value
#     if x < x_min: x = x_min
#     elif x > x_max: x = x_max
    
#     return int((x - offset) * ((1 << bits) - 1) / span)

# def pack_mit_message(p_des, v_des, kp, kd, t_ff):
#     """Packs control values into the 8-byte MIT format."""
#     p_int = float_to_uint(p_des, P_MIN, P_MAX, 16)
#     v_int = float_to_uint(v_des, V_MIN, V_MAX, 12)
#     kp_int = float_to_uint(kp, KP_MIN, KP_MAX, 12)
#     kd_int = float_to_uint(kd, KD_MIN, KD_MAX, 12)
#     t_int = float_to_uint(t_ff, T_MIN, T_MAX, 12)

#     # Bit manipulation to stuff 5 numbers into 8 bytes
#     # Byte 0-1: Position (16 bit)
#     # Byte 2-3: Velocity (12 bit) + KP (4 bit)
#     # Byte 4-5: KP (8 bit) + KD (8 bit)
#     # ... (This standard packing is complex, see below for simplified buffer construction)
    
#     # Standard MIT Packet Construction
#     buf = bytearray(8)
#     buf[0] = (p_int >> 8) & 0xFF
#     buf[1] = p_int & 0xFF
#     buf[2] = (v_int >> 4) & 0xFF
#     buf[3] = ((v_int & 0xF) << 4) | ((kp_int >> 8) & 0xF)
#     buf[4] = kp_int & 0xFF
#     buf[5] = (kd_int >> 4) & 0xFF
#     buf[6] = ((kd_int & 0xF) << 4) | ((t_int >> 8) & 0xF)
#     buf[7] = t_int & 0xFF
#     return buf

# # --- MAIN SETUP ---
# try:
#     bus = can.interface.Bus(channel=CAN_INTERFACE, bustype='socketcan', fd=True)
#     print("CAN Bus Connected!")
# except OSError:
#     print("CAN Bus Error. Did you run the 'ip link' command?")
#     exit()

# try:
#     # Adjust '/dev/input/event2' to your Xbox path
#     gamepad = InputDevice('/dev/input/event2') 
#     print(f"Xbox Connected: {gamepad.name}")
# except:
#     print("Xbox not found.")
#     exit()

# # --- CONTROL LOOP ---
# print("Enabling Motor (Send Zero Command)...")
# # Send a zero command to "Enable" the motor (often required)
# msg = can.Message(arbitration_id=MOTOR_ID, data=pack_mit_message(0,0,0,0,0), is_fd=True)
# bus.send(msg)

# current_velocity = 0.0

# for event in gamepad.read_loop():
#     if event.type == ecodes.EV_ABS:
#         # Code 1 is Left Stick Y (Up/Down)
#         if event.code == 1:
#             raw = event.value
#             if abs(raw) > 5000:
#                 # Map Xbox (-32000 to 32000) to Velocity (-10 to 10 rad/s)
#                 current_velocity = - (raw / 32768.0) * 10.0
#             else:
#                 current_velocity = 0.0
            
#             # SEND CAN COMMAND
#             # We use Velocity Control Mode:
#             # Position = 0 (Ignored if Kp=0)
#             # Velocity = Target
#             # Kp = 0 (No position stiffness)
#             # Kd = 1.0 (Damping to smooth motion)
#             # Torque = 0 (Feedforward)
            
#             data_payload = pack_mit_message(0.0, current_velocity, 0.0, 1.0, 0.0)
            
#             msg = can.Message(arbitration_id=MOTOR_ID, data=data_payload, is_fd=True)
#             bus.send(msg)
#             # print(f"Sent Vel: {current_velocity:.2f}")