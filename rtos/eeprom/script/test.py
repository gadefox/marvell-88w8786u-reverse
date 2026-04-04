import sys, struct
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

def error(msg: str):
  print(Fore.RED + "❌" + msg)

def read32(data: bytes, addr: int) -> int:
  if addr < 0 or addr + 4 > len(data):
    error(f"out of bounds @ {addr:04X}")
    return None
  return struct.unpack_from(">I", data, addr)[0]

def calc_sum(data: bytes, addr: int, size: int) -> int:
  sum = 0

  for i in range(size >> 2):
    val = read32(data, addr + i * 4)
    if val is None:
      return None

    sum += val >> 24
    sum += val >> 16
    sum += val >> 8
    sum += val
    sum &= 0xFF

  return sum

def check_blocks(data: bytes):
  addr = read32(data, 0x4C)

  while True:
    if addr is None:
      return False
    if addr == 0xFFFFFFFF:
      return True

    size = read32(data, addr)
    if size is None:
      return False

    size >>= 16
    if size == 0xFFFF:
      return True

    print(Fore.CYAN + "block:" + Style.RESET_ALL +
          " addr=" + Fore.YELLOW + f"{addr:04X}" + Style.RESET_ALL +
          " size=" + Fore.YELLOW + f"{size}" + Style.RESET_ALL + " bytes")

    sum = calc_sum(data, addr, size)
    if sum != 1:
      error(f"checksum mismatch @ {addr:04X}, sum={sum}")
      return False

    addr = read32(data, addr + 4)

def main():
  if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} dump file")
    return

  path = Path(sys.argv[1])
  if not path.exists():
    error(f"File '{path}' not found")
    return

  with open(path, "rb") as file:
    data = file.read()

  check_blocks(data)

main()
