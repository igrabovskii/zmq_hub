#!/usr/bin/env python3
import sys
import zmq

XPUB_ADDR = "tcp://127.0.0.1:5552"

def main():
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.connect(XPUB_ADDR)
    topic = sys.argv[1] if len(sys.argv) > 1 else ""
    sock.setsockopt(zmq.SUBSCRIBE, topic.encode())
    print(f"SUB connected to {XPUB_ADDR}, topic='{topic or '*'}'")
    while True:
        frames = sock.recv_multipart()
        print("RECV", [f.decode(errors="ignore") for f in frames])

if __name__ == "__main__":
    main()
