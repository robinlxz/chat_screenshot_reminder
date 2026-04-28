import argparse
import os
import sys

import uvicorn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import HOST, PORT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run("src.main:app", host=HOST, port=PORT, reload=args.reload)


if __name__ == "__main__":
    main()
