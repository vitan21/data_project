
import sys
import time

total = 50
for i in range(total + 1):
  percent = int(i * 100 / total)
  bar = "=" * (i // 2) + " " * (25 - i // 2)
  sys.stdout.write(f"\r[{bar}] {percent}%")
  sys.stdout.flush()
  time.sleep(0.01)

print()  # Переход на новую строку по завершении