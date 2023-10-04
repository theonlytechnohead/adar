from simplenc import BinaryCoder


class ReadCoded:
	data: bytes | bytearray
	decoder: BinaryCoder = None