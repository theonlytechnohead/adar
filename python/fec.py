import base64
import zfex


k = 2  # number of blocks required to decode, 1 <= k <= m
m = 3  # number of blocks produced in total, k <= m <= 256


def encode(byte1: bytes, byte2: bytes) -> list[bytes]:
    encoder = zfex.Encoder(k, m)
    return encoder.encode([byte1, byte2], (0, 1))


def decode(byte1: bytes, byte2: bytes) -> bytes:
    decoder = zfex.Decoder(k, m)
    return decoder.decode((byte1, byte2), (0, 1))


if __name__ == "__main__":
    b0 = b'\x11'*8
    print(f"start byte:\t{base64.b16encode(b0)}")

    b1, b2 = encode(b0)
    print(f"check bytes:\t{base64.b16encode(b1)}, {base64.b16encode(b2)}")

    r0, = decode(b1)
    print(f"end byte:\t{base64.b16encode(r0)}")
    r0, = decode(b2)
    print(f"end byte:\t{base64.b16encode(r0)}")
