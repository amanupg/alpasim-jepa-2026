"""Slim AlpaSim rollout logs: drop the JPEG bytes of camera images, keep everything else.

Each rollout.asl is a length-delimited stream of LogEntry protobufs (alpasim_utils.logs). About 95% of the
bytes are driver_camera_image entries (full-HD JPEGs). This writes rollout.slim.asl with every entry kept,
in order, and only `driver_camera_image.camera_image.image_bytes` emptied (timestamps and camera ids
stay). It then verifies the slim file before deleting the original:
  * same number of entries and the same entry kind at every position;
  * every non-image entry byte-identical; every image entry identical once its bytes are emptied.
Usage (alpasim-base python): slim_asl.py [--delete] RUN_DIR [RUN_DIR ...]
"""
import glob, os, struct, sys
from alpasim_grpc.v0.logging_pb2 import LogEntry


def entries(path):
    with open(path, "rb") as f:
        while (head := f.read(4)):
            (n,) = struct.unpack(">L", head)
            body = f.read(n)
            if len(body) != n:
                raise IOError(f"{path}: truncated entry")
            yield body


def slim_one(src, dst):
    with open(dst, "wb") as out:
        for raw in entries(src):
            e = LogEntry.FromString(raw)
            if e.WhichOneof("log_entry") == "driver_camera_image":
                e.driver_camera_image.camera_image.image_bytes = b""
                raw = e.SerializeToString()
            out.write(struct.pack(">L", len(raw)) + raw)


def verify(src, dst):
    a, b = list(entries(src)), list(entries(dst))
    if len(a) != len(b):
        return f"entry count {len(a)} != {len(b)}"
    for i, (ra, rb) in enumerate(zip(a, b)):
        ea, eb = LogEntry.FromString(ra), LogEntry.FromString(rb)
        ka, kb = ea.WhichOneof("log_entry"), eb.WhichOneof("log_entry")
        if ka != kb:
            return f"entry {i}: kind {ka} != {kb}"
        if ka == "driver_camera_image":
            ea.driver_camera_image.camera_image.image_bytes = b""
            if ea.SerializeToString() != rb:
                return f"entry {i}: image entry differs beyond its bytes"
        elif ra != rb:
            return f"entry {i}: {ka} not byte-identical"
    return None


def main():
    delete = "--delete" in sys.argv
    runs = [a for a in sys.argv[1:] if a != "--delete"]
    tot_src = tot_dst = n = bad = 0
    for run in runs:
        for src in sorted(glob.glob(f"{run}/rollouts/*/*/rollout.asl")):
            dst = src[:-4] + ".slim.asl"
            slim_one(src, dst)
            err = verify(src, dst)
            s, d = os.path.getsize(src), os.path.getsize(dst)
            if err:
                bad += 1
                os.remove(dst)
                print("FAILED", src, err)
                continue
            tot_src += s; tot_dst += d; n += 1
            if delete:
                os.remove(src)
        print(f"{run}: ok so far {n} files, {tot_src/1e9:.2f} GB -> {tot_dst/1e9:.3f} GB, failed {bad}", flush=True)
    print(f"TOTAL {n} files verified, {tot_src/1e9:.2f} GB -> {tot_dst/1e9:.3f} GB, failed {bad}, originals deleted: {delete}")


if __name__ == "__main__":
    main()
