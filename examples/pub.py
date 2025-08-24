#!/usr/bin/env python3
import sys
import time
import zmq

XSUB_ADDR = "tcp://127.0.0.1:5551"

def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.connect(XSUB_ADDR)
    time.sleep(0.2)
    topic = sys.argv[1] if len(sys.argv) > 1 else "demo"
    msg = sys.argv[2] if len(sys.argv) > 2 else "hello"
    while True:
        sock.send_multipart([topic.encode(), msg.encode()])
        print(f"PUB {topic} {msg}")
        time.sleep(1.0)

if __name__ == "__main__":
    main()
