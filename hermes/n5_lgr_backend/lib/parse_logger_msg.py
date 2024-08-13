import re
from datetime import datetime, timedelta
import binascii
import ctypes


class N5LoggerParse:
    def __init__(self) -> None:
        self.test_mode = False
        self.pattern = pattern = (
            r"(\w{3}\s+\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4}) : Msg: (.*)"
        )
        self.header_format = {
            "device_id": {"size": 6, "ascii": True},
            "msg_type": {
                "size": 1,
                "enum": [
                    "SIGFOX_UPLINK",
                    "FILE_ACTION",
                    "DIAG_DEPRECATED",
                    "BOOT_INFO",
                    "IBEACON_SCAN",
                    "MESSAGE_LIST",
                    "CORE_MSG_UPLINK",
                ],
            },
            "flags": {
                "size": 1,
                "bits": [
                    {
                        "size": 3,
                        "name": "Trumi Sample Rate",
                        "enum": [
                            "TRUMI_NEXT_EXEC_UNDEFINED",
                            "TRUMI_NEXT_EXEC_ASAP",
                            "TRUMI_NEXT_EXEC_IN_500MS",
                            "TRUMI_NEXT_EXEC_IN_1S",
                            "TRUMI_NEXT_EXEC_IN_10S",
                        ],
                    },
                    {
                        "size": 2,
                        "name": "Trumi Acc Mode",
                        "enum": [
                            "TRUMI_ACC_UNDEFINED",
                            "TRUMI_ACC_SINGLE_SAMPLE",
                            "TRUMI_ACC_100HZ",
                            "TRUMI_ACC_1600HZ",
                        ],
                    },
                ],
            },
            "seq_num": {"size": 4},
            "msg_gen_ts": {"size": 4, "timestamp": True},
            "cell_id": {"size": 4, "hex": True},
            "cell_id_ts": {"size": 4, "timestamp": True},
            "actual_temp": {"size": 1},
            "trumi_st": {
                "size": 1,
                "enum": [
                    "TRUMI_STATE_UNKNOWN",
                    "TRUMI_STATE_SLEEP",
                    "TRUMI_STATE_MOTION_DETECTION",
                    "TRUMI_STATE_RELOCATION ",
                ],
            },
            "trumi_st_upd_count": {"size": 2},
            "trumi_st_upd_ts": {"size": 4, "timestamp": True},
            "trumi_st_trans_count": {"size": 2},
            "reloc_st_trans_count": {"size": 2},
            "stored_st_trans_count": {"size": 2},
            "wifi_aps": {"size": 18, "hex": True},
            "reserved_1": {"size": 2},
            "pld_sz": {"size": 2},
            "pld_crc": {"size": 2, "hex": True},
            "buffer_link_type": {
                "size": 1,
                "enum": [
                    "Link Lost",
                    "Link OK",
                ],
            },
            "header_crc": {"size": 1, "hex": True},
            "payload": {"size": 2},  # DEFAULT TO AS THIS WILL CHANGE ANYWAY WHEN FOUND
        }

    def parse_msg(self, message):
        # Match the pattern in the input string
        match = re.match(self.pattern, message)

        # Extract timestamp and message data
        if match:
            timestamp = match.group(1)
            msg_data = match.group(2)
        else:
            # If not matched, set all key values to blank string, and only set 3 values to parse
            for key in self.header_format:
                parsed_msg_dict[key] = ""
            parsed_msg["device_id"] = binascii.unhexlify(message[0:12]).decode("utf-8")
            parsed_msg["msg_gen_ts"] = datetime.now()
            parsed_msg["payload"] = message

            return parsed_msg_dict

        parsed_msg_dict = {
            "data_msg": msg_data,
            "lgr_msg_ts": timestamp,
            "xyz_raw": "n/a",
        }

        payload_type = ""
        data_pos = 0
        for field, field_settings in self.header_format.items():
            bytes_to_char_len = field_settings["size"] * 2
            field_msg = msg_data[data_pos : data_pos + bytes_to_char_len]

            field_settings_keys = field_settings.keys()
            field_msg_int = int(field_msg, 16)

            if "enum" in field_settings_keys:
                try:
                    field_msg = field_settings["enum"][field_msg_int]
                except (KeyError, IndexError):
                    field_msg = f"Unknown enum value: {field_msg_int}"

                # Check for enum flag states
                if field == "trumi_st" and field_msg == "TRUMI_STATE_MOTION_DETECTION":
                    payload_type = "decompress_payload"

                elif field == "buffer_link_type" and field_msg == "Link Lost":
                    payload_type = "link_lost_mode"
                    parsed_msg_dict["trumi_st"] = "VARIOUS"

            elif "timestamp" in field_settings_keys:
                if field_msg_int != 0:
                    ts_delta = timedelta(seconds=field_msg_int)
                    epoch_offset = datetime(2000, 1, 1)
                    timestamp = epoch_offset + ts_delta
                    field_msg = timestamp.strftime("%a %B %d, %Y %I:%M:%S %p")
                else:
                    field_msg = "No timestamp"

            elif "bits" in field_settings_keys:
                # For "bits", three keys are mandatory -> size, name, enum.
                # Get binary string of value, then reverse so it can be iterated through
                field_bits_rev = format(field_msg_int, "08b")[::-1]

                bit_start = 0
                flag_msg = ""
                for bit_info in field_settings["bits"]:
                    end_bits = bit_start + bit_info["size"]
                    bit_value = int(field_bits_rev[bit_start:end_bits][::-1], 2)
                    bit_start = end_bits
                    try:
                        flag_msg += (
                            f'{bit_info["name"]}: {bit_info["enum"][bit_value]}\n'
                        )
                    except IndexError:
                        flag_msg += (
                            f"Error with bit value: {bit_value} in {bit_info['name']}\n"
                        )

                if flag_msg:
                    field_msg = flag_msg
                else:
                    field_msg = f"Error with flags value: {field_msg}"

            elif field == "actual_temp":
                if field_msg_int == 255:
                    field_msg = "n/a"
                else:
                    actual_temp = (field_msg_int / 2) - 40
                    field_msg = f"{actual_temp} C"
            elif field == "payload":
                payload = msg_data[data_pos:]
                parsed_payload = self._parse_payload(payload, payload_type)
                parsed_msg_dict.update({"xyz_raw": parsed_payload["xyz_data_raw"]})
                field_msg = parsed_payload["xyz_data"]
            else:
                if "hex" in field_settings_keys:
                    field_msg = field_msg
                elif "ascii" in field_settings_keys:
                    field_msg = binascii.unhexlify(field_msg).decode("utf-8")
                else:
                    field_msg = field_msg_int

            data_pos += bytes_to_char_len

            parsed_msg_dict.update({field: field_msg})

            if field == "msg_type" and field_msg == "BOOT_INFO":
                # Convert hex string to bytes
                hex_bytes = binascii.unhexlify(msg_data[data_pos:])
                # Convert bytes to ASCII while skipping non-ASCII characters
                boot_msg = "".join(chr(byte) for byte in hex_bytes if byte < 128)

                parsed_msg_dict.update({"payload": boot_msg})
                break

            if field == "actual_temp":
                if field_msg == 255:
                    field_msg = "Not Implemented yet."

        # Set keys that have not been populated to default value of null string
        for key in self.header_format:
            if key not in parsed_msg_dict:
                parsed_msg_dict[key] = ""

        return parsed_msg_dict

    def _parse_payload(self, payload, payload_type):

        xyz_data = ""
        incorrect_payload = ""

        if payload_type == "decompress_payload":
            decompressed_payload = self._decompress_payload(payload)
            binary_data = decompressed_payload["decomp_payload"]
            incorrect_payload = decompressed_payload["fifo_error"]
            # 196 is (32 samples * 6 bytes) + 4 bytes for timestamp
            timestamp_interval_every = 196
        elif payload_type == "link_lost_mode":
            binary_data = binascii.unhexlify(payload)
            # 12 is 4 byte timestamp, trumi state of 2 bytes plus 6 byte data
            timestamp_interval_every = 12
        else:
            binary_data = binascii.unhexlify(payload)
            # 10 is sample of 6 bytes and 4 byte timestamp
            timestamp_interval_every = 10

        # Iterate over binary data in chunks of 6 bytes
        accel_sample_idx = 0
        xyz_bytes = []
        accel_sample_timestamp = ""

        index = 0
        while index < len(binary_data):
            fifo_timestamp = binary_data[index : index + 4]
            field_msg_int = int.from_bytes(fifo_timestamp, byteorder="little")
            ts_delta = timedelta(seconds=field_msg_int)
            epoch_offset = datetime(2000, 1, 1)
            timestamp = epoch_offset + ts_delta
            accel_sample_timestamp = timestamp.strftime("%a %B %d, %Y %I:%M:%S %p")

            if payload_type == "link_lost_mode":
                # 0-4 -> timestamp
                # 4-6 -> Trumi state
                # 6-12 -> XYZ data
                trumi_st_int = int.from_bytes(
                    binary_data[index + 4 : index + 6], byteorder="little", signed=True
                )
                try:
                    trumi_st = self.header_format["trumi_st"]["enum"][trumi_st_int]
                except IndexError:
                    trumi_st = f"Unknow state -> {trumi_st_int}"
                data_p = binary_data[index + 6 : index + timestamp_interval_every]
            else:
                # 0-4 -> timestamp
                # 4-10 -> XYZ data
                trumi_st = ""
                data_p = binary_data[index + 4 : index + timestamp_interval_every]

            index += timestamp_interval_every

            # If trumi mode (sample size is 196 in trumi mode), set a newline
            # for each 32 sample lots
            if timestamp_interval_every == 196:
                xyz_data += f"{accel_sample_timestamp},\n"

            for i in range(0, len(data_p), 6):
                accel_sample_idx += 1
                # Extract XYZ value from the chunk
                xyz_bytes = data_p[i : i + 6]

                # Interpret XYZ bytes (assuming little-endian encoding)
                x = int.from_bytes(xyz_bytes[0:2], byteorder="little", signed=True)
                y = int.from_bytes(xyz_bytes[2:4], byteorder="little", signed=True)
                z = int.from_bytes(xyz_bytes[4:6], byteorder="little", signed=True)

                # Print XYZ values, if trumi mode don't add timestamp for each
                # sample
                if timestamp_interval_every == 196:
                    xyz_data += f"[{accel_sample_idx}] X: {x} Y: {y} Z: {z},\n"
                else:
                    xyz_data += (
                        f"[{accel_sample_idx}] X: {x} Y: {y} Z: {z}, "
                        f"{accel_sample_timestamp},{trumi_st}\n"
                    )

        xyz_data = (
            f"{accel_sample_idx} accelerometer samples\n"
            f"{incorrect_payload}\n{xyz_data}\n"
        )
        xyz_data_raw = binascii.hexlify(binary_data).decode("utf-8")
        parsed_payload = {"xyz_data": xyz_data, "xyz_data_raw": xyz_data_raw}

        return parsed_payload

    def _decompress_payload(self, payload: str) -> bytes:

        # Test mode
        if self.test_mode:
            dll = ctypes.CDLL("./hermes/n5_lgr_backend/lib/rice.dll")
        else:
            # Real mode
            dll = ctypes.CDLL("./n5_lgr_backend/lib/rice.so")

        # Define the argument types
        dll.Rice_Uncompress.argtypes = [
            ctypes.c_void_p,  # void* in
            ctypes.c_void_p,  # void* out
            ctypes.c_uint,  # unsigned int insize
            ctypes.c_uint,  # unsigned int outsize
            ctypes.c_int,  # int format
        ]

        # Define the return type
        dll.Rice_Uncompress.restype = None  # The function doesn't return anything

        payload_data = bytes.fromhex(payload)

        payload_len = len(payload_data)

        index = 0
        fifo_num = 0
        decompressed_payload = {"decomp_payload": b"", "fifo_error": ""}
        while index < payload_len:
            fifo_num += 1
            fifo_length = payload_data[index]
            fifo_timestamp = payload_data[index + 1 : index + 5]
            index += 5
            fifo_data_size = index + fifo_length

            if fifo_data_size > payload_len:
                decompressed_payload["fifo_error"] = (
                    f"Error at fifo payload number {fifo_num}"
                )
                break
            else:
                fifo_data = payload_data[index:fifo_data_size]

                input_buffer = ctypes.create_string_buffer(fifo_data)
                # Allocate a buffer for the output
                # Buffer will always be 192 bytes (32 samples * 6 bytes each) in trumi mode
                output_buffer = ctypes.create_string_buffer(192)

                # Call the function
                dll.Rice_Uncompress(
                    input_buffer,
                    output_buffer,
                    len(input_buffer),
                    len(output_buffer),
                    3,
                )

                decompressed_payload["decomp_payload"] += (
                    fifo_timestamp + output_buffer.raw
                )

                # field_msg_int = int.from_bytes(fifo_timestamp, byteorder="little")
                # ts_delta = timedelta(seconds=field_msg_int)
                # epoch_offset = datetime(2000, 1, 1)
                # timestamp = epoch_offset + ts_delta
                # accel_sample_timestamp = timestamp.strftime("%a, %B %d, %Y %I:%M:%S %p")
                # print(
                #     f"{accel_sample_timestamp} - {output_buffer.raw.hex()} ({len(output_buffer.raw.hex())})"
                # )

            index += fifo_length

        return decompressed_payload


if __name__ == "__main__":
    n5lgr = N5LoggerParse()
    msg_list = [
        # "Mon Jul 15 10:21:42 2024 : Msg: 54415450414a000c0000001f2e27b4ae0015055b2e27b3a47c0112b72e27afe0000100000002489bd5f8df60489bd5f8df61489bd5f8df62000001185a3c0050a0b3272ec6ff1800bd03aab3272ec4ff1800be03b4b3272ec3ff1800bc03beb3272ec4ff1700bc03c8b3272ec4ff1900be03d2b3272ec3ff1a00be03dcb3272ec4ff1900bf03e6b3272ec6ff1a00c103f0b3272ec3ff1900bf03fab3272ec6ff1700bd0304b4272ec5ff1700bd030eb4272ec4ff1800bf0318b4272ec4ff1c00bb0322b4272ec4ff1800bd032cb4272ec4ff1900c10336b4272ec7ff1b00bd0340b4272ec6ff1a00c0034ab4272ec4ff1800be0354b4272ec5ff1a00bf035eb4272ec5ff1900be0368b4272ec7ff1900be0372b4272ec6ff1c00bf037cb4272ec6ff1800bf0386b4272ec3ff1800be0390b4272ec5ff1900bf039ab4272ec4ff1800bf03a4b4272ec4ff1800bf03aeb4272e8bffb8ffd403"
        # "Mon Jul  8 15:48:48 2024 : Msg: 484557474850000c000000022e1ec6df022f2bcf2e1ec6678a01000f2e1ec6840000000000010000000000000000000000000000000000000000000a7c3d007edfc61e2e5cffe90081fc",
        "Mon Jul 8 15:57:05 2024 : Msg: 484557474850001a000000962e1ec8cd022f2bcf2e1ec667ff026f0f2e1ec6df000100000001ffffffffffffffffffffffffffffffffffff000003a5e012004697cac81e2e070f23ffedb8791fff6fc348fffb7e1a47ffdbd0d23ffedd8690fff6e43487ffb721a43ffdb70b23ffedb8591fff6dc348fffb721a47ffdbd0f23ffee08991fff70c4c8fffb862a4bffdc11527ffee08549fffb861327ffee284c9fffb8e1325ffee384497ffb8e1125ffee38448fffb8a1121ffee284c8fffb8a1325ffee184c9fffb7e1327ffedd84c9fffb761125ffedc83c8fffb6e96cbc81e2e07152bffee28892fff70c4497ffb82264bffdc11327ffee18993fff714224fffdc70894fff71c264fffdc90892fff72c1e47ffdc90791fff7143c97ffb861a4fffdc10d27ffedf8793fff6ec3c9fffb721e53ffdb70f27ffedb8793fff6d44497ffb6a1e47ffdb50f23ffeda8791fff6d43c9fffb6a1e4fffdb71125ffedc8992fff6fc549fffb862a57ffdc50a96fff70c2a57ffdc595cbc81e2e070f27ffee18593fff7042ca7ffb86124fffdc50927ffee28593fff70c2c9fffb82164fffdc10b25ffee18592fff7042c8fffb7a1647ffdbb0925ffedd8493fff6e4249fffb66164fffdb30d27ffed98692fff6cc2c97ffb661643ffdb50b21ffedb8590fff6e4348fffb721a4bffdbb0d25ffede8591fff704348fffb861a47ffdc30d25ffee38693fff71c349fffb8a1e4fffdc397ccc81e2e071127ffedc8893fff6ec449fffb76224fffdbb1123ffedc8891fff6e42647ffdb90a92fff6e4264fffdbd0894fff6fc2257ffdc10994fff70c264fffdc50993fff71c2a4fffdc70a92fff71c2a47ffdc50991fff714224bffdc30792fff70c1e4bffdc30d25ffee08793fff6fc449fffb7a264bffdbb1125ffedc8792fff6e43c8fffb722247ffdb71125ffedb8892fff6dc449fffb7298ccc81e2e071129ffee28891fff70c4c8fffb8a264fffdc71329ffee48894fff724224fffdc70892fff7141e47ffdc30790fff704348fffb7a1a47ffdbb0d23ffede8791fff6fc4497ffb7a2247ffdbb1323ffedd8992fff6ec224fffdbb0992fff6f4264bffdbf0993fff6f4264fffdbf0993fff70c264fffdc50993fff714264bffdc70992fff71c2a4bffdc70991fff714264fffdc50894fff714096cdc81e2e07111fffedd8892fff6e4449fffb72224bffdb91123ffedc8892fff6e4224bffdb90892fff6ec224bffdbd0792fff6fc1e47ffdbf0f23ffee08692fff70c3c97ffb8a1e4fffdc70f25ffee38791fff71c3c97ffb8a1e4bffdc51125ffee18791fff704348fffb7e1a4bffdbd0f25ffedd8791fff6ec348fffb721e43ffdb70f21ffeda8790fff6d43c7fffb6e223fffdb9111fffedd8"
    ]
    n5lgr.test_mode = True
    for message in msg_list:
        parsed_msg = n5lgr.parse_msg(message)

        for key, value in parsed_msg.items():
            if key != "data_msg":
                print(f"{key}: {value}")
