import struct, time
import usb.core, usb.util
from colorama import init, Fore, Style

init(autoreset=True)

usb_iface = 0
usb_ep = 1
magic = 0xF00DFACE

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

  try:
    while True:
      dev.read(usb_ep | 0x80, 2048, timeout=100)
  except usb.core.USBError as e:
    pass

  return dev

def usb_release(dev: usb.core.Device):
  try:
    usb.util.release_interface(dev, usb_iface)
    usb.util.dispose_resources(dev)
  except usb.core.USBError as e:
    error(str(e))

def response(data, payload):
  if (len(data) < 12):
    warn(data.tobytes().hex())
    return False

  mret, cmd, size, seqnum, result = struct.unpack("<1I4H", data[:12])
  cmd &= 0x7FFF

  if mret != magic:
    warn(f"incorrect magic word: {mret:X}")
    return False

  if result != 0:
    if result == 1:
      error(f"command {cmd:X} failed")
    elif result == 2:
      error(f"command {cmd:X} is not supported")
    else:
      error(f"command {cmd:X}: unknown error")
    return False

  print(Fore.GREEN + "✅" + Style.RESET_ALL +
        "command=" + Fore.YELLOW + f"{cmd:X}" + Style.RESET_ALL +
        " size=" + Fore.YELLOW + f"{size}" + Style.RESET_ALL +
        " seqnum=" + Fore.YELLOW + f"{seqnum}" + Style.RESET_ALL)
  if payload:
    print("  payload=" + Fore.YELLOW + f"{data[12:].tobytes().hex()}" + Style.RESET_ALL)

  return True

def gpio_set(dev: usb.core.Device, seqnum: int, gpio: int):
  try:
    data = struct.pack("<1I8H2B", magic, 0x4E, 18, seqnum, 0,
                       1,       # ACT_SET
                       0,       # Reserved / returns LED count
                       0x0108,  # Type
                       2,       # Length=2 bytes
                       1,       # LED num (byte)
                       gpio)    # GPIO (byte)
    dev.write(usb_ep, data, timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    if response(data, False):
      print(f"  GPIO={data[21]}")
  except usb.core.USBError as e:
    error(str(e))

  return seqnum + 1

def gpio_set_state(dev: usb.core.Device, seqnum: int, state: int, behavior: int, config: int):
  try:
    data = struct.pack("<1I8H4B", magic, 0x4E, 20, seqnum, 0,
                       1,        # ACT_SET
                       0,        # Reserved / returns LED count
                       0x0109,   # Type
                       4,        # Length=4 bytes
                       state,    # byte
                       1,        # LED num (byte)
                       behavior, # byte
                       config)   # byte
    dev.write(usb_ep, data, timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    if response(data, False):
      print(f"  state={data[20]} behavior={data[22]}({data[23]})")
  except usb.core.USBError as e:
    error(str(e))

  return seqnum + 1

def gpio_set_all_states(dev: usb.core.Device, seqnum: int, behavior: int, config: int):
  for state in range(9):
    seqnum = gpio_set_state(dev, seqnum, state, behavior, config)
  return seqnum

def gpio_print_state(data, lednum: int):
  type, size, index, led, behavior, config = struct.unpack("<2H4B", data)
  if type != 0x0109:
    warn(f"invalid type: {type}")
    return False
  if size != 4:
    warn(f"invalid size: {size}")
    return False
  if led != lednum:
    warn(f"wrong LED index: {led}")
    return False

  print(f"    state{index}=behavior{behavior}({config})")
  return True

def gpio_get_resp(data):
  leds, type, size = struct.unpack("<3H", data[2:8])
  if leds > 3:
    warn(f"invalid LED count: {ledcnt}")
    return
  if type != 0x0108:
    warn(f"invalid type: {type}")
    return
  if size != leds * 2:
    warn(f"invalid size: {size}")
    return

  for i in range(3):
    l = i * 2 + 8

    lednum = data[l]
    gpio = data[l + 1]

    if gpio == 18:
      print(f"  LED{lednum}=disabled")
    else:
      print(f"  LED{data[l]}=GPIO{gpio}")

    for c in range(i * 72 + 14, i * 72 + 86, 8):
      if not gpio_print_state(data[c:c + 8], lednum):
        break

def gpio_get(dev: usb.core.Device, seqnum: int):
  try:
    data = struct.pack("<1I5H", magic, 0x4E, 10, seqnum, 0, 0)
    dev.write(usb_ep, data, timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    if response(data, False):
      gpio_get_resp(data[12:])
  except usb.core.USBError as e:
    error(str(e))

  return seqnum + 1

def gpio_blink(dev: usb.core.Device, seqnum: int, gpio: int):
  print(f"==== GPIO{gpio}")
  seqnum = gpio_set(dev, seqnum, gpio)

  for i in range(2):
    print(f"---- GPIO{gpio} off")
    seqnum = gpio_set_state(dev, seqnum, 0, 1, 0)
    time.sleep(1.5)
    print(f"---- GPIO{gpio} on")
    seqnum = gpio_set_state(dev, seqnum, 0, 0, 0)
    time.sleep(1.5)

  return seqnum

def gpio_test_behavior2(dev: usb.core.Device, seqnum: int):
  seqnum = gpio_set(dev, seqnum, 2)  # GPIO2

  for cfg in range(256):
    seqnum = gpio_set_state(dev, seqnum, 0, 2, cfg)
    time.sleep(2)

  return seqnum

def gpio_test_behavior3(dev: usb.core.Device, seqnum: int):
  seqnum = gpio_set(dev, seqnum, 2)  # GPIO2

  for cfg in range(16):
    seqnum = gpio_set_state(dev, seqnum, 0, 3, cfg)
    time.sleep(2)

  return seqnum

def gpio_test_behavior4(dev: usb.core.Device, seqnum: int):
  seqnum = gpio_set(dev, seqnum, 2)  # GPIO2

  for cfg in range(16):
    seqnum = gpio_set_state(dev, seqnum, 0, 4, cfg << 4)
    time.sleep(2)

  return seqnum

def main():
  seqnum = 0
  dev = usb_init()
  if dev != None:
#    for i in range(5):
#      seqnum = gpio_blink(dev, seqnum, 2)
    time.sleep(3)
#    gpio_test_behavior2(dev, seqnum)

    for gpio in range(8):
      if gpio in (1, 2, 4, 5, 6, 7):
        print(f"==== GPIO{gpio}: ignored")
      else:
        seqnum = gpio_blink(dev, seqnum, gpio)

    usb_release(dev)

main()
