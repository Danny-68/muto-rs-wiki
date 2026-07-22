filepath = '/root/muto-llm-2.0/muto-llm-2.0/packages/muto_hexapod_lib/muto_hexapod_lib/Largemodel/robot_controller.py'

with open(filepath, 'r') as f:
    lines = f.readlines()

# Backup
with open(filepath + '.orig', 'w') as f:
    f.writelines(lines)

# Regels 417-450 (1-indexed) = indices 416-449 (0-indexed)
# Vervang door STM32 directe aanpak
new_block = """\
        # Yahboom STM32 firmware gait — identiek aan muto_driver_fixed.py
        def _stm32(addr, data=0):
            body = [0x01, addr, data]
            chk = (0xFF - ((0x09 + sum(body)) & 0xFF)) & 0xFF
            return bytes([0x55, 0x00, 0x09] + body + [chk, 0x00, 0xAA])

        STM32_CMD = {
            'forward':   _stm32(0x12, 15),
            'backward':  _stm32(0x13, 15),
            'left':      _stm32(0x14, 15),
            'right':     _stm32(0x15, 15),
            'turn_left': _stm32(0x16, 15),
            'turn_right':_stm32(0x17, 15),
        }
        STM32_STOP = _stm32(0x11, 0x00)

        cmd = STM32_CMD.get(direction)
        if cmd is None:
            return False, f"Onbekende richting: {direction}", None

        start_time = time.time()
        self.robot.ser.write(cmd)

        end_time = start_time + total_time
        canceled = False
        while time.time() < end_time:
            if self.cancel_event.is_set():
                canceled = True
                break
            time.sleep(0.05)

        self.robot.ser.write(STM32_STOP)
        time.sleep(0.1)

        if canceled:
            time.sleep(self.default_config.get('pause_between_actions_s', 0.5))
            return False, f"{action_name}已被取消 {action_name} canceled", {
                'action_name': action_name,
                'direction': direction,
                'speed_level': speed_level,
                'move_params': {'x': x, 'y': y, 'z': z},
                'total_time_s': total_time,
                'actual_time_s': time.time() - start_time,
                'estimated_distance_cm': estimated_distance_cm,
                'target_speed_ms': target_speed_ms,
                'actual_speed_ms': actual_speed,
                'canceled': True
            }
"""

# Toon wat we gaan vervangen
print("Te vervangen (regels 417-450):")
for i in range(416, 450):
    print(f"  {i+1}: {lines[i]}", end='')

# Vervang regels 416 t/m 449 (0-indexed)
new_lines = lines[:416] + [new_block] + lines[450:]

import ast
try:
    ast.parse(''.join(new_lines))
    with open(filepath, 'w') as f:
        f.writelines(new_lines)
    print(f"\n✅ Patch 1 OK — {len(lines)} → {len(new_lines)} regels")
except SyntaxError as e:
    print(f"\n❌ Syntax fout: {e}")
