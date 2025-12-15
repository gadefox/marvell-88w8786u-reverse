import time, struct, subprocess
import usb.core, usb.util
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

usb_iface = 0
usb_ep = 1
verbose = True

def info(msg: str):
  print(Fore.CYAN + " " + msg)

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
    dev.reset()
  except usb.core.USBError as e:
    error(str(e))

  return dev

def print_id():
  result = subprocess.run("lsusb | grep 88W8786U | awk '{print $6}'", shell=True, capture_output=True, text=True)
  info("marvell 88W8786U vid:pid -> " + result.stdout.strip())

def usb_get_status(dev: usb.core.Device):
  try:
    data = dev.ctrl_transfer(0x80, 0, 0, 0, 2, timeout=100)
    status = data[0] | (data[1] << 8)

    info(f"self-powered: {bool(status & 0x01)}")
    info(f"remote wakeup: {bool(status & 0x02)}")
  except usb.core.USBError as e:
    error(str(e))

def usb_release(dev: usb.core.Device):
  try:
    usb.util.release_interface(dev, usb_iface)
    usb.util.dispose_resources(dev)
  except usb.core.USBError as e:
    error(str(e))

def cmd_to_str(cmd: int) -> str:
  if cmd == 1:
    return "DNLD"
  if cmd == 4:
    return "LAST"
  return f"CMD{cmd}"

def packet_request(data: bytes, size: int):
  if not verbose:
    return

  cmd, addr, length, crc, seqnum = struct.unpack("<5I", data[:20])
  s_cmd = cmd_to_str(cmd)
  print(Fore.BLUE + f"{seqnum} {s_cmd}")
  print(" sent header:" +
        " addr=" + Fore.YELLOW + f"0x{addr:X}({addr})" + Style.RESET_ALL +
        " length=" + Fore.YELLOW + f"{length}" + Style.RESET_ALL +
        " crc=" + Fore.YELLOW + f"0x{crc:X}" + Style.RESET_ALL)
  
  size -= 20
  if size != 0:
    print(f" sent payload: " + Fore.YELLOW + f"{size}" + Style.RESET_ALL + " bytes")

def packet_response(data):
  if not verbose:
    return

  result, seqnum = struct.unpack("<II", data[:8])
  if result != 0:
    icon = Fore.RED + "❌"
  else:
    icon = Fore.GREEN + "✅"

  if seqnum > 2000:
    errcode = "status=" + Fore.YELLOW + f"0x{seqnum:X}"
  else:
    errcode = "seqnum=" + Fore.YELLOW + f"{seqnum}"
  print(" response: " + icon + Style.RESET_ALL + errcode + Style.RESET_ALL)

def packet_send(dev: usb.core.Device, data: bytes):
  size = dev.write(usb_ep, data, timeout=100)
  packet_request(data, size)
  data = dev.read(usb_ep | 0x80, 2048, timeout=100)
  packet_response(data)

def packet_read_and_upload(dev: usb.core.Device, file, seqnum: int) -> bool:
  header = file.read(16)  # 4x DWORD = 16 bytes
  if len(header) == 0:
    return False

  data = header + struct.pack("<I", seqnum)
  cmd, addr, length, crc = struct.unpack("<4I", header)
  if cmd == 1:
    data += file.read(length)

  try:
    packet_send(dev, data)
  except usb.core.USBError as e:
    error(str(e))
    packet_send(dev, data)

  return True

def handle_block(dev: usb.core.Device, id: int, seqnum: int) -> int:
  path = Path(f"pkt/{id}")
  if not path.exists():
    error(f"File '{path}' not found")
    return -1

  with open(path, "rb") as file:
    while True:
      if not packet_read_and_upload(dev, file, seqnum):
        break
      seqnum += 1

  return seqnum

def upload_firmware(dev: usb.core.Device):
  blocs = [0, 1, 2, 4]
  seqnum = 0

  for id in blocs:
    seqnum = handle_block(dev, id, seqnum)
    if seqnum == -1:
      return False

  time.sleep(0.025)
  return True

def main():
  dev = usb_init()
  if dev != None:
    if upload_firmware(dev):
      print_id()
      usb_get_status(dev)
    usb_release(dev)

main()
