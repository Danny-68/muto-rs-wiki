import ast

targets = [
    '/root/muto-llm-2.0/packages/muto_hexapod_lib/muto_hexapod_lib/core/MutoLibCore.py',
    '/root/muto-llm-2.0/muto-llm-2.0/packages/muto_hexapod_lib/muto_hexapod_lib/core/MutoLibCore.py',
]

new_block = """\
    def move(self, x, y, z):
        '''STM32 firmware gait — vervangt Python IK hexapod.move()'''
        def _cmd(addr, data=0):
            body = [0x01, addr, data]
            chk = (0xFF - ((0x09 + sum(body)) & 0xFF)) & 0xFF
            return bytes([0x55, 0x00, 0x09] + body + [chk, 0x00, 0xAA])

        if x == 0 and y == 0 and z == 0:
            self.ser.write(_cmd(0x11, 0x00))
            return
        level = 15
        if x > 0:
            self.ser.write(_cmd(0x12, level))
        elif x < 0:
            self.ser.write(_cmd(0x13, level))
        elif y > 0:
            self.ser.write(_cmd(0x14, level))
        elif y < 0:
            self.ser.write(_cmd(0x15, level))
        elif z > 0:
            self.ser.write(_cmd(0x16, level))
        elif z < 0:
            self.ser.write(_cmd(0x17, level))
"""

for filepath in targets:
    with open(filepath, 'r') as f:
        lines = f.readlines()

    with open(filepath + '.orig2', 'w') as f:
        f.writelines(lines)

    # Zoek start def move en einde (volgende def)
    start = None
    end = None
    for i, line in enumerate(lines):
        if '    def move(self, x, y, z):' in line and start is None and i > 600:
            start = i
        if start and i > start + 2 and line.startswith('    def '):
            end = i
            break

    print(f"{filepath.split('/')[3]}: regels {start+1}-{end}")

    if start and end:
        new_lines = lines[:start] + [new_block] + lines[end:]
        try:
            ast.parse(''.join(new_lines))
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            print(f'  ✅ Gepatcht')
        except SyntaxError as e:
            print(f'  ❌ Syntax fout: {e}')
    else:
        print(f'  ❌ Blok niet gevonden: start={start}, end={end}')
