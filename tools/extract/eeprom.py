import struct
import usb.core, usb.util
from colorama import init, Fore, Style

init(autoreset=True)

usb_iface = 0
usb_ep = 1
fw_magic = 0xF00DFACE

def warn(msg: str):
  print(Fore.YELLOW + " " + msg)

def error(msg: str):
  print(Fore.RED + "❌" + msg)

def usb_init() -> usb.core.Device:
  dev = usb.core.find(idVendor=0x1286, idProduct=0x203c)
  if dev is None:
    error("USB device not found")
    return None

  try:
    if dev.is_kernel_driver_active(usb_iface):
      dev.detach_kernel_driver(usb_iface)

    usb.util.claim_interface(dev, usb_iface)
  except usb.core.USBError as e:
    error(str(e))

  return dev

def usb_release(dev: usb.core.Device):
  try:
    usb.util.release_interface(dev, usb_iface)
    usb.util.dispose_resources(dev)
  except usb.core.USBError as e:
    error(str(e))

def command_response(data):
  if (len(data) < 12):
    warn(data.tobytes().hex())
    return

  magic, cmd, size, seqnum, result = struct.unpack("<1I4H", data[:12])
  cmd &= 0x7FFF

  if magic != fw_magic:
    warn(f"incorrect magic word: 0x{magic:X}")
    return
  if result != 0:
    if result == 1:
      error(f"command 0x{cmd:X} failed")
    elif result == 2:
      error(f"command 0x{cmd:X} is not supported")
    else:
      error(f"command 0x{cmd:X}: unknown error")
    return

  print(Fore.GREEN + "✅" + Style.RESET_ALL +
        "command=" + Fore.YELLOW + f"0x{cmd:X}" + Style.RESET_ALL +
        " size=" + Fore.YELLOW + f"{size}" + Style.RESET_ALL +
        " seqnum=" + Fore.YELLOW + f"{seqnum}" + Style.RESET_ALL +
        " payload=" + Fore.YELLOW + f"{data[12:].tobytes().hex()}" + Style.RESET_ALL)

def get_hw_spec(dev: usb.core.Device, seqnum: int):
  try:
    data = struct.pack("<1I4H", fw_magic, 3, 72, seqnum, 0)
    dev.write(usb_ep, data + bytes(64), timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    command_response(data)
  except usb.core.USBError as e:
    error(str(e))
  return seqnum + 1

def eeprom_read(dev: usb.core.Device, seqnum: int, offset: int, size: int):
  try:
    data = struct.pack("<1I7H", fw_magic, 0x59, size + 14, seqnum, 0, 0, offset, size)
    dev.write(usb_ep, data + bytes(size), timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    data = data[18:]
    data = data[:20]
    print(data.tobytes().hex())
  except usb.core.USBError as e:
    error(str(e))
  return seqnum + 1

def main():
  seqnum = 0
  dev = usb_init()
  if dev != None:
    seqnum = get_hw_spec(dev, seqnum)
    for offset in range(0, 1020, 20):
      seqnum = eeprom_read(dev, seqnum, offset, 20)
    seqnum = eeprom_read(dev, seqnum, offset + 20, 4)
    usb_release(dev)

main()
