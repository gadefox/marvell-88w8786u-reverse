import struct
import usb.core, usb.util
from colorama import init, Fore, Style

init(autoreset=True)

usb_iface = 0
usb_ep = 1
fw_magic = 0xF00DFACE

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

def call_stub(dev: usb.core.Device, seqnum: int, offset: int):
  try:
    data = struct.pack("<1I5H", fw_magic, 0x97, 10, seqnum, 0, offset)
    dev.write(usb_ep, data, timeout=100)

    data = dev.read(usb_ep | 0x80, 2048, timeout=100)
    data = data[13:]
    data = data[:-1]
    print(data.tobytes().decode("ascii"))
  except usb.core.USBError as e:
    error(str(e))
  return seqnum + 1

def main():
  seqnum = 0
  dev = usb_init()
  if dev != None:
    seqnum = call_stub(dev, seqnum, 0)
    for block in range(256):
      seqnum = call_stub(dev, seqnum, block)
    usb_release(dev)

main()
