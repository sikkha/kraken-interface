import time
from client import get_ticker
from parser import parse_ticker

PAIR = "BTCUSD"

def main():
    while True:
        try:
            raw = get_ticker(PAIR)
            parsed = parse_ticker(raw)

            print(parsed)

        except Exception as e:
            print("ERROR:", str(e))

        time.sleep(5)


if __name__ == "__main__":
    main()
